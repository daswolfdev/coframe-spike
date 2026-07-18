# Layered uv sync: the dependency layer is cached until the lock changes,
# so code edits rebuild in seconds.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-install-project --no-dev

COPY api ./api
RUN uv sync --frozen --no-dev

# Non-root runtime; /data is where cfg points the SQLite files.
RUN useradd --system --create-home app && mkdir /data && chown app:app /data
USER app

EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "api.app:build", "--factory", \
     "--host", "0.0.0.0", "--port", "8000"]
