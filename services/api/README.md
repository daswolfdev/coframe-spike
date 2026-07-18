# api

FastAPI ingest + SDK config, on host port 8080.

- `POST /events` — validate, enqueue onto `/data/queue.db`, `202` (`503` = queue
  write lock exhausted; correct backpressure, retry).
- `GET /config/{site_id}` — SDK config from the committed
  [config.seed.json](config.seed.json) (`404` unknown site).
- `GET /healthz` — compose healthcheck target.
- `GET /stats` — `{events_received_total, queue_depth, uptime_s}`; queue depth
  growth means the worker is down or drowning.

Owns the queue DDL and the config seed. Design, contract, and rejected
alternatives: [docs/design.md](../../docs/design.md). Spec:
[2026-07-18-api-service-design.md](../../docs/superpowers/specs/2026-07-18-api-service-design.md).

House rules: [CLAUDE.md](../../CLAUDE.md).
