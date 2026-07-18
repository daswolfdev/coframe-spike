# worker

Go queue consumer: drains `queue.db` into per-`(site_id, page_url)`
aggregates in `agg.db` — minute buckets with mergeable LCP histograms,
a running row per page, and site-level minute buckets (`site_minute`,
the dashboard trend's source — #15). Effectively-once (batch marker + startup
recovery), crash-only error policy. Design:
[docs/superpowers/specs/2026-07-18-worker-design.md](../../docs/superpowers/specs/2026-07-18-worker-design.md).

Ops surface: `GET /healthz` (200 = loop ticking), `GET /stats` (JSON:
events consumed, queue depth, flush p50/p95). Port 8082 (dashboard owns
8081).

Verify end-to-end (through the real producer):

    make up
    python3 tools/loadgen.py --rate 50   # Ctrl-C when done; prints sent-count
    curl -s localhost:8082/stats         # events_consumed_total = sent-count, queue_depth 0

Local canon: [CLAUDE.md](CLAUDE.md); Go practices: [docs/GO.md](docs/GO.md).
House rules: [CLAUDE.md](../../CLAUDE.md).
