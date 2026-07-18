# api: dashboard read contract — design

Implements issue #15's read contract in the api service: the three
endpoints the dashboard (merged, currently rendering fixture data through
its nginx `/api/` proxy) polls for real data. The contract shapes are
fixed by #15 and pinned by the dashboard's committed
[fixture.json](../../../services/dashboard/fixture.json); this spec covers
how the api serves them from the worker-owned `agg.db`.

## Endpoints

All reads follow the `get_stats` precedent: `ctx.db.agg_ro()` returns a
read-only connection or `None`; a missing/schema-less `agg.db` degrades to
the empty answer, never a 500. Per #15 the dashboard renders absent
endpoints and empty arrays identically, so `[]` is the uniform "no data
yet" response — no 404s to special-case.

- **`GET /sites` → `["acme", "demo"]`** — sorted union of configured
  sites (`ctx.cfg.sites`) and `SELECT DISTINCT site_id FROM page_current`.
  A configured site appears before its first event; a decommissioned
  site with residual data still appears (data or config, per #15).
- **`GET /sites/{site_id}/pages` → `[{page_url, count, p75_ms,
  last_seen_ms}]`** — `page_current` rows for the site, `ORDER BY count
  DESC LIMIT 20`. `last_seen` is epoch seconds in agg.db; converted to
  `last_seen_ms` (the add-don't-repurpose rule, same as `/stats`).
  Unknown site → `[]`, same as a known site with no data.
- **`GET /sites/{site_id}/trend` → `[{bucket_start_ms, p75_ms}]`** —
  per-minute site-wide p75, time-ascending. For each minute in the
  trailing 60 (per `ctx.clock`, matching the worker's `page_current`
  window), merge that minute's `page_minute.hist` blobs across the
  site's pages and report the merged histogram's p75. Minutes with no
  rows are omitted — the dashboard renders whatever points arrive (#15
  locks shape, not bucket width or density).

## The histogram port

Per-page `p75_ms` values cannot be combined into a site p75 — only the
histograms can. The api therefore ports the read side of the worker's
encoding (`services/worker/internal/aggregate/histogram.go`): 128
little-endian uint32 bins, log-spaced over 50–30000 ms; p75 = upper edge
of the bin where the cumulative count crosses 0.75 × total. ~20 lines of
pure Python in `api/hist.py` (functional core — no ctx), with a test
vector cross-checked against the Go implementation's semantics.

**Contract note:** this widens the agg.db schema-as-contract (#11) from
"columns the api reads" to include the `hist` blob encoding. Recorded on
#15 so the worker owner knows the encoding is now load-bearing.

Alternatives rejected:

- *Worker precomputes a site-minute table* — new table, worker changes,
  cross-service PR; not cheap, and the encoding stays private at the cost
  of a second derived table to keep honest.
- *Count-weighted average of per-page p75s* — statistically wrong;
  percentiles don't average.

## Structure

The fixed api layout, one command per endpoint: `commands/get_sites.py`,
`commands/get_site_pages.py`, `commands/get_site_trend.py`; matching
endpoint factories; three `app.py` routes. Pydantic response models pin
the wire shapes. Contract tests on real SQLite seed agg.db with the
worker's DDL (the `test_stats.py` precedent) and cover: empty/no-agg.db
answers, union semantics, top-20 ordering, seconds→ms conversion, hist
merge correctness, and the trailing-window cutoff via `FakeClock`.
