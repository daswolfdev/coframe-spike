# API Service — Design

**Date:** 2026-07-18
**Status:** Approved (staff-eng review passed after one revise cycle — Gate 2: queue-is-transport decision made explicit)
**Branch:** `api-service` → PR into `main`
**Issues:** #11 (service), #8 (remaining platform state), informed by #7–#12

## Goal

Land the first real service — the FastAPI ingest/config API — and, with it,
the platform's shared state layer, per the trigger in
[design.md](../../design.md): "queue/db in compose.base.yaml arrives with the
api service PR." Advances OBJECTIVE.md deliverable "platform + three services."

The storage decision this PR commits is already evidenced:
[SQLite in WAL mode clears both objective load targets with ~100× headroom](../../reports/2026-07-18-sqlite-wal-throughput.md)
— the queue is a SQLite table, and no queue/db infrastructure containers are
added, ever, at this scale.

## Scope of this PR

- `services/api/` — FastAPI service satisfying the service contract.
- `platform/compose.base.yaml` — one named volume `data` (the platform's
  entire shared-infra footprint).
- `docs/design.md` — API section + queue justification.
- Not in scope: the worker (reads the queue next PR), the status page (#10),
  deploy upgrade (#9).

## API surface

| Route | Behavior |
|---|---|
| `POST /events` | Validate body (`site_id, page_url, lcp_ms, timestamp, session_id`), insert one row into the queue table, return `202`. Malformed → `422` (FastAPI default). Queue write lock exhausted (>5s) → `503`. |
| `GET /config/{site_id}` | Return that site's SDK config (experiments, sampling rate) from an in-memory map; unknown site → `404`. |
| `GET /healthz` | `200` iff the process is up **and** `queue.db` is writable (cheap `PRAGMA user_version` probe). Compose healthcheck target. |
| `GET /stats` | Small JSON for the future status page (#10): `{service, events_received_total, queue_depth, uptime_s}`. `queue_depth` is `COUNT(*)` on the queue table — cheap because steady-state depth is near zero; growth is the signal. |

## Data & state

**Queue — `/data/queue.db`, the one piece of shared state this PR creates.**

```sql
CREATE TABLE IF NOT EXISTS events (
  id          INTEGER PRIMARY KEY,   -- insertion order; worker claims by id
  site_id     TEXT    NOT NULL,
  page_url    TEXT    NOT NULL,
  lcp_ms      REAL    NOT NULL,
  timestamp   INTEGER NOT NULL,      -- event time, unix ms (SDK clock)
  session_id  TEXT    NOT NULL,
  received_at INTEGER NOT NULL       -- server time, unix ms
);
```

- Typed columns, not a JSON blob: the schema **is** the API↔worker contract
  (Kleppmann: schema as contract). Fields are added, never repurposed.
- The API owns the DDL and creates the DB on boot. The worker treats the
  table as a read/delete interface and never defines it — one decision, one
  owner. Worker semantics (batch claim via `BEGIN IMMEDIATE`, delete on
  commit, at-least-once on crash) are specified in the worker PR; this
  schema already supports them (`id` gives claim ordering).
- Pragmas per the benchmark: `journal_mode=WAL` (persists in the file),
  plus per-connection `synchronous=NORMAL` and `busy_timeout=5000`. The
  connection pragmas are part of the queue contract, stated once in
  design.md's queue section — every process opening `queue.db` applies them.
- **The queue is a transport, not a log — stated deliberately.** Events are
  destroyed at claim-commit; from that moment authority over historical
  aggregates transfers to `agg.db`, which is therefore a system of record in
  its own right, *not* rebuildable derived data. Accepted loss: no replay or
  backfill — a worker aggregation bug is unrecoverable for already-consumed
  events. Buying maintainability: retaining a log at 1,000 events/s is
  ~86M rows/day of retention/compaction machinery no deliverable needs.
  Revisit trigger: the first real need to reprocess history (backfill, bug
  recovery, a second consumer) → retained event log with consumer offsets.
- The `data` volume is the platform's shared-state seam: services that need
  state mount it; the queue file is multi-process by design (measured: ~2%
  throughput cost under cross-process contention).

**Site config — a committed seed file, no database.**

`services/api/config.seed.json` (site_id → experiments, sampling_rate),
loaded into memory at boot. OBJECTIVE.md explicitly allows "in-memory map or
SQLite"; there is no write path to config in any deliverable, so a config DB
would be state without an owner of change. Trigger to build `config.db`:
the first feature that edits config at runtime (e.g. dashboard toggling an
experiment).

## Faults (Gate 2)

- **Worker down / drowning:** queue depth grows; visible in `/stats` now, on
  the status page later (#10). API is unaffected — enqueue keeps working.
- **Write-lock contention:** `busy_timeout=5000` absorbs transient locks
  (measured worst case 68 ms); sustained exhaustion returns `503`, which is
  correct backpressure to the SDK rather than silent loss.
- **API crash / restart:** accepted events are durable at `202` (WAL,
  `synchronous=NORMAL`; power-loss window of the last checkpoint is an
  accepted monitoring-data trade-off, stated in design.md). Compose restarts
  the container; healthcheck gates readiness.
- **Duplicate delivery:** SDK retries after a lost `202` can duplicate an
  event. Accepted: aggregates are statistical (count, p75) and monitoring-
  grade; exactly-once would require an idempotency key with no deliverable
  that needs it.
- **Concurrency scaling:** one uvicorn process is the default; the knob is
  `API_WORKERS` (env → uvicorn `--workers`), safe because multi-process
  writers are exactly what the benchmark measured. Named load parameter
  before touching it: sustained ingest p95 latency or `503`s at the SDK.

## Alternatives considered

- **Redis (or NATS) as the queue:** a real queue with blocking pop and
  acks — but a second stateful system to operate, back up, and explain, when
  the measured need is 1,000/s against a store with ~126× headroom. Rejected
  per the benchmark report; revisit trigger: a second host (WAL's shm index
  is single-machine).
- **`config.db` (SQLite) for site config:** persistence for a write path
  that doesn't exist in any deliverable. Rejected as YAGNI; seed file wins.
- **JSON-blob queue payload:** flexible, but moves the schema into every
  consumer's parser — information leakage across the API/worker boundary.

## Risks / open questions

- **First-boot ordering:** worker may start before the API has created
  `queue.db`. Contract: worker waits and reports unhealthy until the table
  exists (worker PR); nothing for the platform to sequence.
- **`COUNT(*)` for depth** is O(rows); fine while depth ≈ 0, and depth growth
  is precisely the anomaly we want expensive-to-miss, not cheap-to-hide. If
  it ever matters, `MAX(id) - MIN(id)` approximates in O(1).

## Verification ("done" as commands)

```sh
make up
curl -fsS -X POST localhost:8080/events -H 'content-type: application/json' \
  -d '{"site_id":"demo","page_url":"/checkout","lcp_ms":2100,"timestamp":1752800000000,"session_id":"s1"}'   # → 202
curl -fsS localhost:8080/config/demo      # → experiments + sampling_rate JSON
curl -fsS localhost:8080/healthz          # → 200
curl -fsS localhost:8080/stats            # → queue_depth ≥ 1
make smoke                                # pathway still true, zero platform edits beyond the volume
```

---

*Part of the repo canon — see [CLAUDE.md](../../../CLAUDE.md).*
