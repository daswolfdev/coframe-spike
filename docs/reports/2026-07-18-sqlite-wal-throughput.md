# 2026-07-18 — SQLite (WAL) can carry both objective load targets alone

Report per the rules in [README.md](README.md); discipline in
[CLAUDE.md](../../CLAUDE.md).

## Question

Can SQLite in WAL mode serve as the queue *and* both app stores at the
objective's ceilings — 1,000 events/s ingest and 1,000 concurrent dashboard
users — so the stack needs no other infrastructure (no Redis, no Postgres)?
If yes, the queue becomes a SQLite table and Redis is the documented rejected
alternative.

## Method

Three phases, ~5s each, via [assets/sqlite_bench.py](assets/sqlite_bench.py)
(pass a directory on a real filesystem as `argv[1]`):

1. **Enqueue-only** — single-row autocommit INSERTs from one process; models
   per-HTTP-request enqueue by the API.
2. **Enqueue + concurrent dequeue** — same, while a second *process* batch-claims
   and deletes rows (`BEGIN IMMEDIATE`, batches of 2,000, 20 polls/s); models
   API and worker contending for the write lock on one `queue.db` file — the
   known SQLite weak spot this design must survive.
3. **Concurrent reads during writes** — 32 reader threads running a top-pages
   query against a 10,000-row aggregates table while a writer lands 500-row
   upsert batches 4×/s; models 1,000 dashboard users (polling every ~10s ≈
   a few hundred QPS) during worker flushes.

Run as: `python3 assets/sqlite_bench.py ~/.cache/sqlite-bench`

## Environment

- AMD Ryzen AI 9 HX 370, Linux 7.1.3-arch1-1
- btrfs on dm-crypt NVMe (`~/.cache`) — **not** tmpfs; a tmpfs run inflated
  phase 1 to ~370k inserts/s, so RAM-backed numbers are not comparable
- Python 3.14.6 (stdlib `sqlite3`), SQLite 3.53.3
- `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`

## Results

| Load path | Target | Measured |
|---|---|---|
| Per-request enqueue (1 txn/insert) | 1,000/s | ~129,000/s, p95 0.01ms, max 21ms |
| Enqueue while 2nd process batch-dequeues same file | 1,000/s | ~126,000/s, p95 0.01ms, max 68ms; drained ~33,000/s |
| 32 concurrent readers during upsert batches | ~few hundred QPS | ~9,300 QPS, p95 4.9ms |

Phase 2 decides the question: two processes contending on one file cost ~2%
throughput, leaving ~126× headroom over the ingest target. Worst-case single
insert stalled 68ms (one lock/checkpoint wait) — well inside any HTTP timeout.
Reads at ~30× the plausible dashboard load with p95 under 5ms, before any
caching.

## Conclusion

Yes — SQLite in WAL mode carries the queue and both stores with roughly two
orders of magnitude of headroom on every path. The stack needs no other
infrastructure; Redis is the rejected alternative for the queue. Storage will
not be the bottleneck at target load — the app-server tier (HTTP handling)
will be, so the scaling knob is uvicorn workers, not the store. **Revisit
trigger:** the day the system needs a second host (WAL's shared-memory index
requires all processes on one machine), swap the stores to Postgres.

## Caveats

- **Microbenchmark, no HTTP in front.** End-to-end events/s will be bounded by
  FastAPI request handling, not by these numbers.
- **Queue-growth failure mode observed:** in a tmpfs run at ~370k/s ingest the
  dequeuer fell far behind and the queue table ballooned, which slowed
  dequeue further. Not reachable at 1,000/s, but it is the failure the
  queue-depth metric exists to catch — sustained depth growth means the worker
  is down or drowning.
- Single writer per file is a design assumption (API owns `config.db`, worker
  owns `agg.db`, queue is multi-writer by design and measured as such).
- Occasional multi-ms max latencies (21–68ms) are checkpoint/lock waits;
  fine for this workload, but don't build anything latency-critical on the
  p100 here.
