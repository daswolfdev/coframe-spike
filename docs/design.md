# Design

Judged against [OBJECTIVE.md](../OBJECTIVE.md). Reviewed under
[SPEC-REVIEW.md](SPEC-REVIEW.md). This document grows a section per service
as each lands; today it covers the platform, the api's write/config surface,
and the dashboard. The [worker](../services/worker/README.md) lands in a
follow-up PR.

## Platform

**Shape:** a root Makefile fronting Docker Compose. Five team verbs
(`up/down/ps/logs/deploy`) plus maintainer `smoke`. The Makefile discovers
`services/*/compose.yaml` fragments (underscore-prefixed excluded) and merges
them with `platform/compose.base.yaml` into one compose project (`perfmon`).
State lives nowhere yet — no services run; shared infra (queue, db) arrives
with the first service that needs it.

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
logs/metrics land with something to observe); queue/db in compose.base.yaml
(trigger: the api service PR chooses one and justifies it here).

## api

**Shape:** FastAPI/uvicorn (Python 3.14, uv), host port 8000. In:
`POST /events` (SDK wire format per OBJECTIVE.md; Pydantic-validated, one
autocommit INSERT — the benchmarked path, ~129k/s against a 1k/s target)
and `GET /config/{site_id}` (hardcoded site map from `cfg.py`; unknown site
404). Out: rows in the queue table; JSON config. State: `queue.db` (WAL) on
the shared `data` volume — added to `compose.base.yaml` in this PR, its
stated trigger. Internals follow the Ctx-first canon
([service README](../services/api/README.md),
[architecture](../services/api/docs/architecture.md)); read endpoints for
the dashboard (#15) land with the worker's aggregates.

**Queue contract (api↔worker):** typed columns (`id` = claim order,
`site_id`, `page_url`, `lcp_ms`, `ts_ms`, `session_id`, `received_at_ms`),
**delete-on-claim, at-most-once**: the worker claims with
`BEGIN IMMEDIATE; SELECT … ORDER BY id LIMIT n; DELETE …; COMMIT` and then
aggregates. A worker crash drops at most one claimed batch of monitoring
samples — invisible in a p75 dashboard; revisit trigger: events that carry
per-row value (billing). Rejected alternative: status-column at-least-once
queue — reclaim timers, dedup, an extra index, all buying a guarantee RUM
sampling doesn't need. (Redis as the queue was rejected earlier on the
[WAL evidence](reports/2026-07-18-sqlite-wal-throughput.md).)

**Config as code:** site SDK config (sampling rate, experiments) is
hardcoded in `cfg.py` — OBJECTIVE.md sanctions an in-memory map, git is the
system of record, and a change deploys in seconds via `make deploy S=api`,
health-gated and auditable. Rejected alternative: a seeded SQLite table —
runtime mutability that no one can exercise (there is no auth, UI, or write
endpoint either way). Trigger to build it: the first time a non-engineer
needs to change a value. Consequence: `config.db` was dropped; the api owns
only `queue.db`.

**Least confident decision:** config-as-code. If the product fiction
becomes real (customers self-serve experiments), this flips to the SQLite
table sooner than any other choice here changes — the seam (`ctx.cfg.sites`
read by one command) is one function wide on purpose.

**Deliberately not built (and triggers):** dashboard read endpoints
(trigger: worker PR defines `agg.db` — #15); `/stats` + queue-depth metric
(trigger: #19, the ops read surface); auth/rate-limiting on `POST /events`
(trigger: leaving the laptop/LAN posture, #32); event batching in the SDK
wire format (trigger: measured ingest pressure, not before).

## dashboard

**Shape:** nginx:alpine serving one static page (plain HTML + one ES module +
inline SVG, no build step) on host port 8081, proxying `/api/` to the api
same-origin. In: the read contract proposed in #15 (`/sites`,
`/sites/{id}/pages`, `/sites/{id}/trend`, `/config/{id}`). Out: pixels.
**State: none** — pure derived view; refresh rebuilds everything; nothing to
back up and nothing for the runbook. (The nginx `/api/` location is a
same-origin proxy for the dashboard's own calls, not the platform-wide
reverse proxy deliberately not built above — services still own their ports.)

**Contract posture:** built ahead of its data sources; #15 is the contract's
authoritative home while the api's read endpoints are under negotiation.
404/502 and empty data collapse into one "no data yet" render, so the
dashboard ships before the api's read endpoints and the worker's aggregates
exist, and degrades identically when they fail later. `?fixture=1` renders
the committed executable example of the contract (sync discipline lives in
[the service README](../services/dashboard/README.md)). When the api is
unreachable, last-loaded data stays on screen under a banner that says it
may be stale.

**Rejected alternatives:** a framework + bundler (React/Vite) — toolchain
and build artifacts to operate for one page of tables and a sparkline; CORS
instead of the proxy — smears the api's origin into browser JS and CORS
middleware into the api (two services own one decision), plus preflight
traffic. Load at ceiling: 1,000 users polling every 5s ≈ 600 req/s of
static/proxy traffic — nginx territory; api-side reads have measured
headroom (~9,300 QPS, [benchmark report](reports/2026-07-18-sqlite-wal-throughput.md)).
