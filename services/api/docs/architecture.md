# API architecture — Ctx-first, functional core, imperative shell

The rules this document details are canon: [../CLAUDE.md](../CLAUDE.md).
What the service must do is fixed by
[../../../OBJECTIVE.md](../../../OBJECTIVE.md): `POST /events` enqueues onto
the SQLite queue, `GET /config/{site_id}` serves SDK config.

## The one idea

Every capability the app has — storage, config, secrets, logging, time — is a
field on a single frozen dataclass, the **`Ctx`**. It is built once, in one
place, and passed explicitly everywhere. There are no globals, no import-time
side effects, no module that secretly knows about the environment. Swapping
the ctx swaps the world: production wiring and test wiring differ only in
which `Ctx` gets built.

## The layers, inside out

### Pure core

Plain functions, no `Ctx`, no I/O — validation logic, transformations,
decisions. They take values and return values. Most code should want to live
here.

### Repos — `repos/` (earned, not default)

A repo exists only when one of two things is true:

1. it wraps a **true third-party external** — something with a real process
   boundary or protocol of its own (the queue qualifies), or
2. it names a **DB operation shared across multiple commands** — the rule of
   three applied to SQL.

Everything else — a query only one command runs — is inline SQL in that
command, executed on the connection the ctx carries. Contract tests run
against real SQLite (below), so wrapping every DB access in an interface for
fakeability buys nothing and costs a layer.

A repo module defines an **interface as a `Protocol`** plus its real
implementation. The `Ctx` holds the Protocol type, so commands cannot see
past the interface.

```python
# repos/queue.py
class QueueRepo(Protocol):
    def enqueue(self, event: Event) -> None: ...

@dataclass(frozen=True)
class SqliteQueueRepo:
    db_path: Path

    def enqueue(self, event: Event) -> None:
        ...
```

### Ctx — `ctx.py`

The dataclass and its composition root live together.

```python
# ctx.py
@dataclass(frozen=True)
class Repos:
    queue: QueueRepo

@dataclass(frozen=True)
class Ctx:
    db: Db          # from db.py — inline SQL in commands runs here
    repos: Repos    # true externals / shared ops only
    cfg: Cfg
    secrets: Secrets
    logger: Logger
    clock: Clock

def ctx_create(cfg: Cfg | None = None) -> Ctx:
    """The composition root — the only caller of env.py.

    No-arg call builds the production ctx: cfg_create() for config, env for
    secrets. Tests pass their own Cfg pointing at an isolated data dir.
    """
```

### Commands — `commands/`

One function per use-case. First argument is always `ctx: Ctx`. This is the
imperative shell: read through repos, call pure core, write through repos.
**All mutation goes through `ctx.repos.*`** — a command never opens a
connection, reads a file, or checks the wall clock itself.

```python
# commands/record_event.py
def record_event(ctx: Ctx, event: Event) -> None:
    ctx.repos.queue.enqueue(stamp_received(event, ctx.clock.now()))
```

### Endpoints — `endpoints/`

An endpoint is a **function that takes the ctx and returns the FastAPI
handler** — a closure over the ctx, wrapping exactly one command. Handlers
stay thin: parse/validate via Pydantic in the signature, call the command,
shape the response. No logic.

```python
# endpoints/events.py
def post_events(ctx: Ctx) -> Callable[[EventIn], Awaitable[Accepted]]:
    async def handler(event: EventIn) -> Accepted:
        record_event(ctx, event.to_domain())
        return Accepted()
    return handler
```

### App factory — `app.py`

`create_app(ctx)` is the **only** place routes are registered — the whole
HTTP surface is readable in one function.

```python
# app.py
def create_app(ctx: Ctx) -> FastAPI:
    app = FastAPI()
    app.post("/events")(post_events(ctx))
    app.get("/config/{site_id}")(get_config(ctx))
    app.get("/healthz")(healthz(ctx))
    return app
```

## Composition root — `ctx_create()` in `ctx.py`

Exactly one function assembles the world: take a `Cfg` (defaulting to the
hardcoded `cfg_create()`), read secrets from the environment (`env.py`), open
the SQLite connections, construct repos, logger, and clock, freeze them into
a `Ctx`. It lives in `ctx.py` — **not** `app.py` — because contract tests
call it too, pointed at their own isolated SQLite files; production and tests
share one wiring path.

The uvicorn entry is a one-line adapter:

```python
# app.py
def build() -> FastAPI:          # uvicorn app:build --factory
    return create_app(ctx_create())
```

## Support modules

- **`db.py`** — owns SQLite: opens and configures the connections (WAL,
  pragmas, busy timeout) and defines the `Db` dataclass that `ctx.db`
  carries — the surface commands run their data ops on. Schema/DDL lives
  here too, so "what tables exist" has one home.
- **`env.py`** — the only module that reads `os.environ`, and only secrets
  come through it. Parses raw strings into typed values; everything
  downstream takes typed arguments.
- **`cfg.py`** — non-secret config **hardcoded in Python**:
  `cfg_create() -> Cfg` returns a frozen dataclass (paths, ports, limits)
  whose values live right there in the source. No env parsing, no config
  files — changing config is a code change that ships through review and
  `make deploy`, so `git log` answers "what changed". Carried as `ctx.cfg`.
  Tests build their own variant with fields overridden as needed.
- **`secrets.py`** — secret values in a frozen dataclass whose `repr`
  redacts. Never logged, never in cfg.
- **`logger.py`** — builds the logger the ctx carries. Stdout only (the
  platform owns log collection — see the service contract in
  [../../_template/compose.yaml](../../_template/compose.yaml)).
- **`clock.py`** — `Clock` Protocol + real implementation. Tests substitute a
  fixed clock; `datetime.now()` appears nowhere else.

## Testing consequence — `test_ctx_create() -> TestCtx`

Tests get their ctx from one place: `test_ctx_create()`, which returns a
**`TestCtx`** — a subclass of `Ctx` that draws a hard line by dependency
kind:

- **SQLite runs real.** Each call builds a test `Cfg` — the hardcoded
  `cfg_create()` values with the data dir swapped to a random isolated
  directory under `/tmp` (pytest's `tmp_path`), and any field overridable
  per-test — then runs `ctx_create`'s wiring over it, so `ctx.db` points at
  fresh SQLite files. The SQL is part of what's under test, never faked.
- **Everything non-SQLite is a `Fake*`.** `TestCtx` *narrows* those fields'
  types to fake implementations that satisfy the Protocol **and** add test
  helper methods — so tests get arrange/assert affordances (`.set(...)`,
  `.advance(...)`, `.sent`) without casts, and strict typing enforces that a
  real external can never leak into a test ctx.

```python
# tests/conftest.py (not a test_*.py file — pytest must not collect it)
@dataclass(frozen=True)
class TestCtx(Ctx):
    clock: FakeClock              # narrowed: adds .advance(), .set()
    # any future non-SQLite repo field is narrowed to its Fake here

def test_ctx_create(tmp_path: Path) -> TestCtx: ...
```

Tests then call commands (or `create_app(ctx)` via `TestClient` for endpoint
tests) exactly as production does, and assert against the real database or
the fakes' helpers. No monkeypatching, no patch targets. If a test needs to
patch, the design has leaked a dependency around the ctx.
