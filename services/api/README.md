# api

Python/FastAPI service. Endpoints:

- `POST /events` — SDK wire format (`site_id, page_url, lcp_ms, timestamp,
  session_id`; `timestamp` epoch ms) → 202, one row on the SQLite queue
  (`/data/queue.db`, the api↔worker contract — schema in `api/db.py`)
- `GET /config/{site_id}` — SDK config (sampling rate, experiments) from
  the hardcoded map in `api/cfg.py`; unknown site → 404. Changing config =
  edit cfg.py + `make deploy S=api`
- `GET /healthz` — verifies the queue schema exists

Next: the dashboard read contract (#15) once the worker's aggregates exist.
See OBJECTIVE.md.

Develop (from this directory; uv manages everything):

```
uv sync                # env + deps + editable install
uv run pytest          # contract tests (real SQLite per test)
uv run ruff check .    # lint  (ruff format . to format)
uv run ty check        # strict types
```

Deploy: `make deploy S=api` from the repo root; verify with
`curl localhost:8000/healthz`.

Canon: [CLAUDE.md](CLAUDE.md); architecture: [docs/architecture.md](docs/architecture.md).
