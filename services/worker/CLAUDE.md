# worker — service canon

Local guidance for the Go worker. The root [CLAUDE.md](../../CLAUDE.md) and
[OBJECTIVE.md](../../OBJECTIVE.md) still govern; this file refines them for
this directory and wins on Go-specific questions.

## Read before writing Go here

- [docs/GO.md](docs/GO.md) — Go practices circa July 2026, screened through
  the repo's design lenses. The screened-out table is as binding as the
  positive guidance.

## What this service is

Consumes the producer-owned `queue` table in `queue.db` (schema authority:
`services/api/api/db.py`, negotiated on #11; batch claims via
`BEGIN IMMEDIATE` on the consumer-owned `claim_id` column), folds rolling
aggregates per `(site_id, page_url)` — event count, p75 LCP, last-seen — into
`agg.db`, of which this worker is the **only writer**. Effectively-once via
the agg-side batch marker; crash-only error policy. The dashboard reads
aggregates through the api service, never from here. Rationale lives in
issue #11,
[docs/reports/2026-07-18-sqlite-wal-throughput.md](../../docs/reports/2026-07-18-sqlite-wal-throughput.md),
and [docs/design.md](../../docs/design.md) § worker.
