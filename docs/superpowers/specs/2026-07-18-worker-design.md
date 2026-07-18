# Go Worker — Design

**Date:** 2026-07-18
**Status:** Approved (brainstormed with user; all five scoping decisions user-picked)
**Branch:** `worker` → PR into `main` (spec committed on `worker-canon`)

## Goal

Build the queue consumer from [OBJECTIVE.md](../../../OBJECTIVE.md): drain
`queue.db`, maintain rolling aggregates per `(site_id, page_url)` — event
count, p75 LCP, last-seen — in `agg.db`, observable per the platform
convention. Storage decisions ride on the measured results in
[2026-07-18-sqlite-wal-throughput.md](../../reports/2026-07-18-sqlite-wal-throughput.md);
Go practice follows [services/worker/docs/GO.md](../../../services/worker/docs/GO.md).

## Scope of this PR

The worker lands **before** the API and owns the `queue.db` schema; the API
PR conforms to it later. To make the worker verifiable and demoable without a
producer, the PR includes `cmd/eventgen`, a small synthetic-event generator.
The shared data volume lands in `platform/compose.base.yaml` now — the worker
is the first service to need it (the trigger [design.md](../../design.md)
named for the api PR).

## Decisions (user-picked during brainstorm)

1. **Worker first, owns queue schema** — plus `eventgen` for end-to-end
   verification.
2. **Both aggregate tables** — per-minute buckets (system of record for
   aggregates) plus a `page_current` running row. The running row is
   OBJECTIVE.md's literal "rolling aggregates per (site_id, page_url)"
   shape, derived from the buckets — not a read-speed cache; reads were
   already measured at ~30× headroom without it.
3. **Log-binned histograms** — mergeable, no raw-sample retention, no deps.
4. **Effectively-once via batch marker** — no loss, no double-count, at the
   price of explicit recovery logic and a crash-point test per row of the
   table below.
5. **1-minute buckets** — the trend visibly moves during the 5-minute demo
   recording.

## Architecture

Single sequential loop — claim → fold → flush → ack — chosen over a staged
goroutine pipeline (concurrency without a demanding load parameter: one
process drains ~33,000 events/s against a 1,000/s target) and over a
SQL-heavy `ATTACH` design (see Alternatives). Everything interesting lives in
two deep packages; `main` is wiring.

```
services/worker/
  cmd/worker/main.go      wiring: env, open DBs, Recover(), loop + HTTP server
  cmd/eventgen/main.go    synthetic producer: N sites × M pages, log-normal
                          LCP, configurable events/s
  internal/queue/         claim/ack/recover — all effectively-once machinery
  internal/aggregate/     histogram math + fold + agg.db upserts, behind Apply()
  compose.yaml, Dockerfile (from _template)
```

Driver: `modernc.org/sqlite` — pure Go, `CGO_ENABLED=0`, cross-compiles clean
for the macOS/Linux house rule. Rejected: `mattn/go-sqlite3` (faster via CGO,
but speed buys nothing at ~33× measured headroom).

## Data model

**queue.db** — worker defines it; API conforms. Both processes run idempotent
DDL on open (either may start first — the ordering error is defined out of
existence). PRAGMAs exactly as benchmarked: WAL, `synchronous=NORMAL`,
`busy_timeout=5000`.

```sql
CREATE TABLE IF NOT EXISTS events (
  id         INTEGER PRIMARY KEY,        -- insertion order
  site_id    TEXT NOT NULL,
  page_url   TEXT NOT NULL,
  lcp_ms     INTEGER NOT NULL,
  session_id TEXT NOT NULL,
  ts         INTEGER NOT NULL,           -- client-reported epoch ms; stored, not trusted
  claim_id   INTEGER                     -- NULL = unclaimed
);
CREATE INDEX IF NOT EXISTS events_unclaimed ON events(id) WHERE claim_id IS NULL;
```

**agg.db** — worker is the only writer (repo invariant).

```sql
CREATE TABLE page_minute (          -- the trend; system of record for aggregates
  site_id TEXT, page_url TEXT, minute INTEGER,   -- unix epoch minutes
  count INTEGER, hist BLOB, p75_ms INTEGER, last_seen INTEGER,
  PRIMARY KEY (site_id, page_url, minute));
CREATE TABLE page_current (         -- derived; rebuildable from page_minute
  site_id TEXT, page_url TEXT,
  count INTEGER, p75_ms INTEGER, last_seen INTEGER,
  PRIMARY KEY (site_id, page_url));
CREATE TABLE applied_batches (batch_id INTEGER PRIMARY KEY, applied_at INTEGER);
```

- `hist`: 128 log-spaced bins, 50ms–30s (≈5% resolution — plenty for a p75),
  fixed 512-byte little-endian uint32 blob. Per-bucket `p75_ms` is
  denormalized alongside so readers never parse blobs.
- `page_current.p75_ms`: merge of that page's trailing-60-minute bins,
  recomputed at flush for pages the batch touched. `count` is all-time.
- **Bucketing uses worker arrival time, not client `ts`** — client clocks
  lie (never trust wall-clock ordering across nodes); queue latency is
  sub-second so the two agree in practice, and no clamping logic exists to
  get wrong.

## The loop and the effectively-once protocol

Startup: open both DBs (idempotent DDL) → `Recover()` → poll every 250ms,
batch cap 2,000 (the benchmarked shape). Each non-empty tick is exactly three
transactions:

1. **Claim** (queue.db, `BEGIN IMMEDIATE`):
   `UPDATE events SET claim_id = ? WHERE id IN (SELECT id FROM events WHERE
   claim_id IS NULL ORDER BY id LIMIT 2000) RETURNING …`. Batch ids are
   monotonic — last applied + 1, held in memory; safe with one worker.
2. **Apply** (agg.db, one transaction): fold batch into in-memory histograms;
   upsert `page_minute` (read blob, add bins, write back); recompute
   `page_current` for touched pages; `INSERT applied_batches(batch_id)`;
   prune `applied_batches` beyond the newest 1,000.
3. **Ack** (queue.db): `DELETE FROM events WHERE claim_id = ?`.

Crash-point analysis (each row gets a regression test):

| Crash after | Recovery on next start | Outcome |
|---|---|---|
| Claim | claim_id set, no marker in `applied_batches` → reset claim_id to NULL | Re-delivered, folded once |
| Apply | marker present → delete the claimed rows | Counted once, no double-fold |
| Ack | nothing dangling | Clean |

`Recover()` is those two lookups — a startup function, not a concurrent
reaper. Empty ticks skip all three transactions.

**Error policy is crash-only:** any failed transaction or unexpected state
(e.g. `busy_timeout` exhaustion mid-Apply) logs and exits nonzero; compose
restarts the worker, and recovery is the single, tested startup path — the
batch marker makes a replayed batch idempotent. No in-process retry logic
exists to get wrong.

## Observability

- `log/slog` JSON to stdout: startup config line, per-flush line at debug,
  errors at error with batch id.
- `/healthz`: 200 only if a tick completed within 5s — liveness of the work,
  not the process.
- `/stats` (JSON): `events_consumed_total`, `queue_depth` (the benchmark's
  named failure signal — sustained growth means the worker is down or
  drowning), `batches_applied`, `last_flush_unix`, flush-duration p50/p95
  from an in-process ring buffer. Percentiles, never averages.

## Testing & verification

- **Unit** (table-driven): histogram bin edges, p75 read-off, blob merge;
  fold logic.
- **Integration** (real SQLite in `t.TempDir()`, no mocks): claim/ack
  round-trip; one test per crash-table row, driving `internal/queue`
  functions directly to stop between transactions.
- **End-to-end, as a command:** `eventgen` at ~200 events/s + worker for a
  few seconds → `page_minute` rows exist, `/healthz` returns 200, `/stats`
  counts match what eventgen wrote. Wired into the service smoke path.
- `go test -race ./...` always.
- The failure demo for the recording falls out for free: kill the worker
  under load, watch `queue_depth` climb, restart, watch it drain.

## Alternatives considered

- **Staged goroutine pipeline** (claimer → folder → flusher channels):
  scaling machinery without a load parameter demanding it, and every crash
  point multiplies across stages. Rejected per the GO.md screen.
- **SQL-heavy `ATTACH`** (both files on one connection, claim+apply+ack in
  one transaction): effectively-once for free — but SQLite documents that
  cross-database transactions are **not atomic in WAL mode**, the exact mode
  this design rests on; it also holds the queue write lock through the
  aggregate write, worsening API contention. Recorded because it looks so
  clean.
- **Delete-on-claim (at-most-once):** radically simpler, loses ≤1 batch of
  statistical telemetry per crash. User chose correctness; the cost is the
  crash-table machinery above.
- **Exact p75 from raw samples / t-digest:** raw samples grow with volume
  (≈86M rows/day at target); t-digest is a dependency whose tail accuracy
  p75 doesn't need.

## Risks / open questions

- **Stale `page_current.p75_ms` for silent pages:** the trailing-window p75
  only recomputes when a page receives events. `last_seen` tells the reader
  how stale it is; acceptable, and the dashboard can fall back to
  `page_minute` if it ever isn't.
- **`page_minute` growth:** ~pages × active minutes; trivial at laptop scale.
  Pruning deferred — trigger: agg.db size or dashboard query p95 degrading.
  Note pruning would break rebuilding `page_current`'s all-time count from
  buckets; that trade-off gets decided when pruning does.
- **Exactly one worker instance is assumed:** monotonic batch ids and claim
  ownership collide if two workers run (cross-deleted claims). Enforced by
  compose's default of one container per service — no `replicas` anywhere;
  scaling the worker means sharding claims, a post-ceiling problem.
- **Queue schema is now a two-service contract** defined by the consumer.
  If the API PR needs a field the worker didn't anticipate, it's additive
  (add, don't repurpose). When the API lands, consider pointing both
  services at one shared `.sql` file so the DDL has a single home.

---

*Part of the repo canon — see [CLAUDE.md](../../../CLAUDE.md); worker-local
canon in [services/worker/CLAUDE.md](../../../services/worker/CLAUDE.md).*
