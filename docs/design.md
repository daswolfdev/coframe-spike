# Design

Judged against [OBJECTIVE.md](../OBJECTIVE.md). Reviewed under
[SPEC-REVIEW.md](SPEC-REVIEW.md). This document grows a section per service
as each lands; today it covers the platform.

## Platform

**Shape:** a root Makefile fronting Docker Compose. Five team verbs
(`up/down/ps/logs/deploy`) plus maintainer `smoke`. The Makefile discovers
`services/*/compose.yaml` fragments (underscore-prefixed excluded) and merges
them with `platform/compose.base.yaml` into one compose project (`perfmon`).
Shared state is one named volume (`data`) holding the SQLite files — see
*The queue* below.

**Why compose + make:** the whole platform is a file the team already knows
how to read, runs identically on any laptop, and needs no controller to
operate. Rejected alternative: k3s/kind — real orchestrator semantics at the
cost of far more surface to operate and explain; over-engineering at
5 engineers and laptop scale.

**Why discovery over registration:** a service exists by having a directory;
the "forgot to register it" failure cannot happen, and OBJECTIVE.md's
"fourth service without platform changes" is literally true. Rejected
alternative: one central compose.yaml listing every service — more obvious
(whole topology in one file) but every addition edits a platform file.

**Least confident decision:** compose multi-file merge semantics as the
backbone. If fragment merging surprises us, the fallback is the central
registry — same directory layout, so switching is cheap.

**Deliberately not built (and triggers to build):** reverse proxy / service
mesh (trigger: real port-collision pain or TLS needs); CI (trigger: second
contributor breaking main); observability stack (trigger: first service PR —
logs/metrics land with something to observe); queue/db containers — resolved
by the api PR: none, ever, at this scale (see *The queue* below).

## The queue (platform shared state)

**Shape:** a SQLite table in `/data/queue.db` on the platform's one named
volume — the entire shared-infra footprint. No queue or database containers.
Evidence: [the benchmark report](reports/2026-07-18-sqlite-wal-throughput.md)
measured ~126,000 inserts/s under cross-process producer/consumer contention
(~126× the objective's 1,000 events/s ceiling) and ~9,300 QPS concurrent
reads, on laptop hardware, real disk.

**The queue contract** (all of it):

- Schema — owned and created by the api; consumers read/delete, never define:
  `events(id INTEGER PRIMARY KEY, site_id, page_url, lcp_ms, timestamp,
  session_id, received_at)`. Fields are added, never repurposed.
- Connection pragmas — applied by *every* process opening the file:
  `synchronous=NORMAL`, `busy_timeout=5000` (`journal_mode=WAL` persists in
  the file; the api sets it once at init).
- Claim protocol — consumers batch-claim under `BEGIN IMMEDIATE`, delete on
  commit: at-least-once on crash (details land with the worker).

**Transport, not a log — deliberate.** Events are destroyed at claim-commit;
authority over historical aggregates transfers to `agg.db` at that moment, so
aggregates are *not* rebuildable by replay. Accepted loss: no backfill; a
worker aggregation bug is unrecoverable for consumed events. Buys
maintainability — no retention/compaction machinery (~86M rows/day at
ceiling) that no deliverable needs. Revisit trigger: the first real need to
reprocess history (backfill, bug recovery, a second consumer) → retained
event log with consumer offsets.

**Rejected alternative:** Redis (or NATS) — a real broker with blocking pop
and acks, but a second stateful system to operate, back up, and explain, when
the measured need is 1,000/s against a store with two orders of magnitude of
headroom. Revisit trigger: a second host (WAL's shared-memory index is
single-machine — the same trigger that swaps stores to Postgres).

## api

**Shape:** FastAPI, host port 8080. In: `POST /events` (validated, one queue
insert, `202`; `busy_timeout` exhaustion → `503` backpressure to the SDK
rather than silent loss) and `GET /config/{site_id}`. Out: rows in the queue;
config JSON. Also `/healthz` (compose healthcheck) and `/stats`
(`events_received_total`, `queue_depth`, `uptime_s` — queue depth is *the*
load-parameter metric: steady-state ≈ 0, growth = worker down or drowning).

**Where state lives:** the queue (above), which the api owns DDL for; and
site config, whose system of record is the **committed seed file**
(`services/api/config.seed.json`) loaded into memory at boot — config has no
runtime write path in any deliverable, so a config database would be state
without an owner of change. Rejected alternatives: `config.db` in SQLite
(trigger to build: the first feature that edits config at runtime, e.g. the
dashboard toggling an experiment); a JSON-blob queue payload (moves the
schema into every consumer's parser — information leakage across the
api/worker boundary).

**Faults:** worker down → api unaffected, depth grows and says so; duplicate
SDK retries after a lost `202` → accepted, aggregates are monitoring-grade
statistics; api restart → accepted events are durable (WAL,
`synchronous=NORMAL`; the last-checkpoint power-loss window is an accepted
monitoring-data trade-off). Scaling knob: `API_WORKERS` (multi-process
writers are exactly what the benchmark measured); named trigger before
touching it: sustained ingest p95 growth or `503`s at the SDK.

---

*Part of the repo canon — see [CLAUDE.md](../CLAUDE.md).*
