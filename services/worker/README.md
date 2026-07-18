# worker

Go queue consumer: drains `queue.db` into per-`(site_id, page_url)`
aggregates in `agg.db` — minute buckets with mergeable LCP histograms,
plus a running row per page. Effectively-once (batch marker + startup
recovery), crash-only error policy. Design:
[docs/superpowers/specs/2026-07-18-worker-design.md](../../docs/superpowers/specs/2026-07-18-worker-design.md).

Ops surface: `GET /healthz` (200 = loop ticking), `GET /stats` (JSON:
events consumed, queue depth, flush p50/p95). Port 8081.

Verify end-to-end:

    make up
    docker exec perfmon-worker-1 /eventgen -queue /data/queue.db -rate 200 -duration 5s
    curl -s localhost:8081/stats   # events_consumed_total ≈ 1000, queue_depth 0

Local canon: [CLAUDE.md](CLAUDE.md); Go practices: [docs/GO.md](docs/GO.md).
House rules: [CLAUDE.md](../../CLAUDE.md).
