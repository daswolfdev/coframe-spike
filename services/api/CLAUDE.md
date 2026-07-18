# services/api — Python API canon

Rules for all work inside `services/api`. The repo-wide discipline in
[../../CLAUDE.md](../../CLAUDE.md) still applies, and
[../../OBJECTIVE.md](../../OBJECTIVE.md) still wins every conflict; this file
adds the toolchain and architecture rules specific to this service. Where it
is more specific than the root canon, it is authoritative inside this
directory.

## Toolchain

- **Python 3.14**, managed by **uv** (latest). All commands go through uv
  (`uv sync`, `uv run …`) — never bare `pip` or a system `python`.
- **FastAPI** + **Pydantic**, latest.
- **ruff** — linting *and* formatting.
- **ty** — type checking. **Strict, no exceptions**: no `Any` escapes, no
  untyped defs, no ignore/suppression comments. Code that won't type-check
  strictly gets redesigned, not silenced.

## Architecture — everything flows through the Ctx

Full detail and a worked example: [docs/architecture.md](docs/architecture.md).

The shape in one paragraph: a frozen dataclass `Ctx` carries every capability
the app has — SQLite connections, repo interfaces, config, secrets, logger,
clock — and `ctx_create()` in the same module is the one composition root,
shared by production and tests. Commands are
functions that take `ctx: Ctx` as their first argument and are where all work
happens. Endpoints are factories that take the ctx and return a FastAPI
handler wrapping exactly one command. `app.py` is a single factory function
that takes the ctx and returns the wired FastAPI app. Nothing reaches around
the ctx to a global, an env var, a clock, or a database.

### Layout (fixed)

| Path | Role |
|---|---|
| `app.py` | `create_app(ctx) -> FastAPI` — the only place routes are registered |
| `ctx.py` | the `Ctx` dataclass **and `ctx_create()`, the composition root** (used by production and tests alike) |
| `commands/` | one function per use-case, `ctx` first; the imperative shell's verbs |
| `endpoints/` | handler factories: take `ctx`, return the FastAPI handler for one command |
| `repos/` | **earned, not default**: only true third-party externals (e.g. the queue) or DB ops shared across multiple commands |
| `db.py` | opens/configures the SQLite connections; defines the `Db` on `ctx.db` that commands run their data ops on |
| `env.py` | the **only** module that reads `os.environ` |
| `cfg.py` | non-secret config **hardcoded in Python**: `cfg_create() -> Cfg`, carried as `ctx.cfg` |
| `secrets.py` | secret values, redacting `repr`, never logged |
| `logger.py` | logger construction (stdout only, per the service contract) |
| `clock.py` | `Clock` interface + real implementation |

### Hard rules

- **All state access flows through the ctx** — a command reaches its SQLite
  connections and repos only via `ctx`; nothing opens its own connection or
  touches a global.
- **Repos are earned, not default.** A repo exists only for a true
  third-party external (e.g. the queue) or a DB op shared across multiple
  commands. A single-command SQL op lives inline in that command, run on the
  connection the ctx carries.
- **Functional core, imperative shell.** Pure logic lives in plain functions
  with no ctx; commands orchestrate: read state, call pure logic, write
  state.
- **Cfg is code, not environment.** Non-secret values live hardcoded in
  `cfg.py` (`cfg_create() -> Cfg`) — changing config is a reviewed,
  deployable code change. Tests build a test variant and override fields as
  needed.
- **`os.environ` is read in `env.py` only** — and only secrets come from it,
  inside `ctx_create()`.
- **Time comes from `ctx.clock`** — never `datetime.now()` in commands or
  repos.
- **Logging via `ctx.logger`** — no module-level loggers, no `print`.
- **Contract tests on real SQLite, fakes for everything else.** Every test
  calls `test_ctx_create() -> TestCtx` (`TestCtx` inherits `Ctx`): SQLite
  runs real, on fresh files in a random isolated `/tmp/...` dir; any
  **non-SQLite** dependency (a true external, the clock) is narrowed to a
  `Fake*` stand-in with test helper methods. No monkeypatching, ever.
