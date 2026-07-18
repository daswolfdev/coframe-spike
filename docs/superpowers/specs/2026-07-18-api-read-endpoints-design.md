# API read endpoints — design (#15)

The last unbuilt piece of the read contract the dashboard already calls:
`GET /sites`, `GET /sites/{id}/pages`, `GET /sites/{id}/trend`, served from
the worker-owned `agg.db`. Contract home: issue #15; executable example:
`services/dashboard/fixture.json`.

## The contract (already negotiated on #15)

| Endpoint | Source | Shape |
|---|---|---|
| `GET /sites` | config map ∪ `page_current` sites | `["acme", "demo"]`, sorted |
| `GET /sites/{id}/pages` | `page_current`, count desc, top 20 | `[{page_url, count, p75_ms, last_seen_ms}]` |
| `GET /sites/{id}/trend` | site-level minute buckets, oldest first | `[{bucket_start_ms, p75_ms}]` |

Unknown site or not-yet-existing agg.db/schema → `[]`, never 500: the
dashboard renders empty and 404 identically ("no data yet"), and mid-rollout
states (file absent, schema absent, `site_minute` absent on an old agg.db)
are real, not exceptional. `last_seen` is epoch seconds in agg.db; the api
converts ×1000 at the read layer (add-don't-repurpose, per #15).

## The one design decision: site-level trend

`page_minute` is per *page*; the trend is per *site*. A site's honest
per-minute p75 requires merging LCP histograms across its pages — counts
add, percentiles don't. Two sketches:

1. **API decodes `hist` blobs and merges in Python.** No worker change; but
   it duplicates the histogram's bin math in a second language against an
   unversioned blob format, and both the worker spec ("denormalized … so
   readers never parse blobs") and #15's plan ("never parsing `hist`")
   forbid exactly this. Change-amplification red flag: resize the bins in
   Go and the api silently mis-reads every trend.
2. **Worker folds an additive `site_minute` table** (`site_id, minute,
   count, hist, p75_ms, last_seen`) in the same `Apply` transaction, from
   histograms it already builds per batch. The api reads `p75_ms` as a
   plain column. Additive schema change, sanctioned by the #11/#15
   negotiation ("if the API PR needs a field … it's additive").

**Chosen: 2.** Histogram semantics stay with their one owner; the api stays
a reader of plain columns. Cost: ~1 extra row write per active site per
minute (bounded by site count, not traffic) and trend history starts at the
worker's deploy — acceptable, demos run on fresh volumes. Rejected
alongside: a count-weighted average of per-page p75s — an average wearing a
percentile's name ([DATA-INTENSIVE.md](../../DATA-INTENSIVE.md)).

## Bounds

- Pages: top 20 by count (the dashboard renders a short table).
- Trend: newest 1,440 buckets (24 h) — bounds the payload while bucket
  pruning stays deferred (worker spec's stated trigger).
- Load at ceiling: ~200 req/s pages+trend, measured read headroom ~9,300
  QPS ([report](../../reports/2026-07-18-sqlite-wal-throughput.md)).

## API internals

Per the [service canon](../../../services/api/CLAUDE.md): one command per
endpoint (`list_sites`, `get_top_pages`, `get_trend`), endpoints as thin
factories, routes in `app.py`. The read-with-degrade dance on agg.db
(open read-only → query → `OperationalError` means "not yet" → `None`) is
now shared by four commands, so it moves into `Db` as one helper
(`agg_rows`), replacing `get_stats`'s inline copy.
