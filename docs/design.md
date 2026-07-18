# Design

Judged against [OBJECTIVE.md](../OBJECTIVE.md). Reviewed under
[SPEC-REVIEW.md](SPEC-REVIEW.md). This document grows a section per service
as each lands; today it covers the platform. The three product services —
[api](../services/api/README.md), [worker](../services/worker/README.md),
[dashboard](../services/dashboard/README.md) — land in follow-up PRs.

## Platform

**Shape:** a root Makefile fronting Docker Compose. Six team verbs
(`up/down/ps/logs/deploy/new`) plus maintainer `smoke`; `new` scaffolds a
service from the template, and `smoke` deploys through that same scaffold,
so the pathway is re-proven on every smoke run. The Makefile discovers
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
