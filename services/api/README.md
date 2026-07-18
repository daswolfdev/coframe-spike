# api

Python/FastAPI service. Today: the Ctx-first skeleton with `/healthz`.
Next: `POST /events` (site_id, page_url, lcp_ms, timestamp, session_id)
onto the SQLite queue; `GET /config/{site_id}` for SDK config. See
OBJECTIVE.md.

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
