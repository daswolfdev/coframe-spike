# worker — service canon

Local guidance for the Go worker. The root [CLAUDE.md](../../CLAUDE.md) and
[OBJECTIVE.md](../../OBJECTIVE.md) still govern; this file refines them for
this directory and wins on Go-specific questions.

## Read before writing Go here

- [docs/GO.md](docs/GO.md) — Go practices circa July 2026, screened through
  the repo's design lenses. The screened-out table is as binding as the
  positive guidance.

## What this service is

Consumes `queue.db` (batch claims via `BEGIN IMMEDIATE`), folds rolling
aggregates per `(site_id, page_url)` — event count, p75 LCP, last-seen — into
`agg.db`, of which this worker is the **only writer**. The dashboard reads
aggregates through the api service, never from here. Decisions already made
(SQLite-as-queue, one-writer-per-file) live in issue #11 and
[docs/reports/2026-07-18-sqlite-wal-throughput.md](../../docs/reports/2026-07-18-sqlite-wal-throughput.md);
decisions still open (claim/ack semantics, exact vs approximate p75) get made
and recorded in [docs/design.md](../../docs/design.md) when the code lands.
