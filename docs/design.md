# Design

Judged against [OBJECTIVE.md](../OBJECTIVE.md). Reviewed under
[SPEC-REVIEW.md](SPEC-REVIEW.md). This document grows a section per service
as each lands; today it covers the platform.

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

## worker

**Shape:** Go binary; consumes `queue.db` (batch claim via
`BEGIN IMMEDIATE`, 250ms poll, ≤2,000 rows), folds per-`(site_id,
page_url)` minute buckets of log-binned LCP histograms plus a running
row into `agg.db` (worker is its only writer). Effectively-once: batch
marker inside the agg transaction, startup recovery, crash-only error
policy. State: `queue.db` rows are transient; `page_minute` is the
system of record for aggregates; `page_current` is derived. Full spec:
[superpowers/specs/2026-07-18-worker-design.md](superpowers/specs/2026-07-18-worker-design.md).

**Why SQLite + single loop:** measured (see
[reports/2026-07-18-sqlite-wal-throughput.md](reports/2026-07-18-sqlite-wal-throughput.md))
at ~33× drain headroom over the 1,000 events/s ceiling. Rejected
alternative: staged goroutine pipeline — concurrency without a load
parameter demanding it. Driver `modernc.org/sqlite` (pure Go,
CGO-free cross-compile); rejected: `mattn/go-sqlite3` (CGO speed the
headroom makes irrelevant).

**Least confident decision:** the queue schema is a two-service
contract defined by the consumer before the producer exists; the API
PR may want additive changes.

**Deliberately not built (and triggers):** bucket pruning (trigger:
agg.db size or dashboard p95 degrading); multi-worker claims (trigger:
drain headroom exhausted — post-ceiling); exact percentiles (trigger:
a product need finer than the histogram's ≈5% resolution).

---

*Part of the repo canon — see [CLAUDE.md](../CLAUDE.md).*
