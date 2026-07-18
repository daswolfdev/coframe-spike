# Go practice, screened — July 2026

House Go conventions for the worker, current as of **Go 1.26**. Every practice
here passed the repo's two lenses:
[SOFTWARE-DESIGN.md](../../../docs/SOFTWARE-DESIGN.md) (fight complexity, deep
modules, narrow interfaces) and
[DATA-INTENSIVE.md](../../../docs/DATA-INTENSIVE.md) (one system of record,
derived data is rebuildable, percentiles not averages). What *failed* the
screen is listed at the bottom with reasons, so the screen itself is
reviewable.

## Toolchain

- `go 1.26` in `go.mod`. The Green Tea GC is now the default and cgo overhead
  dropped ~30% — take both for free; touch `GOGC`/`GOMEMLIMIT` only on a
  measured memory problem, never preemptively.
- Non-negotiable, no config: `gofmt` (via `goimports`), `go vet ./...`,
  `go test -race ./...`.
- `golangci-lint` v2 with a **minimal** `.golangci.yml` (staticcheck, errcheck
  and little else). Add a linter when it would have caught a real bug here,
  not because a list said so — linter noise is cognitive load.
- `govulncheck ./...` before release; `go fix ./...` on toolchain bumps (it is
  now a full modernization framework).
- Tool dependencies via the `go.mod` `tool` directive — no `tools.go`.

## Layout

- `cmd/worker/main.go` is wiring only: parse env, open stores, start the loop,
  handle shutdown. Everything with behavior lives in `internal/`.
- A package is a deep module: name it for what it **provides** (`aggregate`,
  `queue`), never for what it contains (`models`, `utils`, `helpers`) —
  kind-packages smear one design decision across the tree.
- Start with few, larger packages; split only when a boundary earns a name.
  A deep 40-line function beats five shallow helpers read in sequence.

## Interfaces and errors

- Accept interfaces, return structs. Define an interface where it is
  *consumed*, and only once a second implementation actually exists — an
  interface with one implementation is a shallow module wearing a costume.
- Errors are values: wrap once with `%w` adding only context the caller lacks;
  match with `errors.Is/As`. Don't log *and* return the same error.
- Prefer defining errors out of existence: idempotent claims, upserts, and
  no-op deletes beat error branches for states that don't matter.
- `panic` means programmer error and never crosses a package boundary.

## Concurrency

- Every goroutine has an owner and a known stop condition before it is
  written. `context.Context` is the first argument and the only cancellation
  mechanism.
- Boring first: one claim–fold–flush loop with batching. Add workers only
  when a measured load parameter (queue depth, claim-latency p95) demands it —
  1,000 events/s is well within one goroutine and one SQLite writer.
- Time-dependent tests use `testing/synctest` (stable since 1.25) instead of
  sleeps. Suspected leaks: the 1.26 `goroutineleak` pprof profile.

## Data and state

- Know which file is the system of record and which is derived, and say so in
  code comments. Here: `queue.db` rows are transient facts consumed
  at-least-once; `agg.db` is the fold and this worker is its **only writer**.
- At-least-once delivery means the fold must be idempotent or the batch
  commit must be atomic with the claim — decide explicitly, write it down,
  test the crash-mid-batch case.
- Plain `database/sql` + one SQLite driver, chosen and justified at build
  time. SQL is the schema contract: explicit `CREATE TABLE`, additive
  migrations only (add fields, never repurpose them).
- Batch writes inside transactions; measure the pipeline with percentiles
  (p75 LCP *is* the product — never ship an average).

## Observability

- `log/slog`, JSON handler, stdout, injected at construction — one structured
  line per event worth grepping. No logging framework.
- Expose the platform's `/healthz` + `/stats` convention; `/stats` reports the
  load parameters we'd scale on (events/s consumed, queue depth, flush p95).

## Testing

- Table-driven tests, stdlib `testing`, `go-cmp` when diffs get big.
- Test at the package boundary — the interface, not the internals; tests that
  survive refactors are tests of a deep module.
- Use real SQLite files in `t.TempDir()` instead of store mocks: the real
  thing is milliseconds and mocks are shallow modules that leak the
  implementation into every test.
- Bugs leave regression tests naming the failure mode (repo rule).

## Screened out

| Common practice | Why it failed the screen |
|---|---|
| `golang-standards/project-layout` (`/pkg`, `/build`, …) | Empty layers for a three-file service; structure without knowledge boundaries |
| Interface-per-struct + mock frameworks | Interface as complex as the implementation = shallow module; real SQLite is cheap |
| handler/service/repository layering by default | Pass-through layers, same abstraction at every level |
| DI frameworks (wire, fx) | Framework depth we'd have to operate; explicit wiring in `main` is obvious |
| Global logger / config singletons | Hidden dependencies are obscurity; pass them in |
| `context.Value` for dependencies | An invisible interface — the worst kind of unknown unknown |
| Worker pools / channel fan-out up front | Scaling without a measured load parameter |
| ORMs / query builders | A second schema language to keep faithful to the first; SQL is already the explicit contract |

---

*Part of the worker canon — see [CLAUDE.md](../CLAUDE.md); repo-wide rules in
the root [CLAUDE.md](../../../CLAUDE.md).*
