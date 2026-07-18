# coframe-spike-1

## THE OBJECTIVE — read this first

**[OBJECTIVE.md](OBJECTIVE.md) is the most important document in this repo.**
It defines the take-home assignment this project exists to satisfy: the
deliverables, the hard constraints (one-command laptop bring-up, a documented
<15-minute path to a fourth service *without adding it*, a scaling story to
1,000 events/s and 1,000 concurrent users and no further), and — critically —
the grading lens: **judgment, taste, and operability; over-engineered and
under-built are both wrong.** Before starting or scoping any work, check it
against OBJECTIVE.md. When any other guidance in this repo conflicts with it,
OBJECTIVE.md wins.

## Coding philosophy

Two foundational texts guide design decisions in this repo. Read them before
making architectural or data-model choices:

- [docs/SOFTWARE-DESIGN.md](docs/SOFTWARE-DESIGN.md) — distillation of
  Ousterhout's *A Philosophy of Software Design*. The lens for **code
  structure**: fight complexity, prefer deep modules with narrow interfaces,
  pull complexity downward, design it twice. When reviewing or writing code,
  check against its red-flag table.
- [docs/DATA-INTENSIVE.md](docs/DATA-INTENSIVE.md) — distillation of
  Kleppmann's *Designing Data-Intensive Applications*. The lens for **data and
  state**: name the goal (reliability / scalability / maintainability) when
  trading off, keep one system of record and treat everything else as
  rebuildable derived data, measure with percentiles not averages.
- [docs/CLEAN-CODE.md](docs/CLEAN-CODE.md) — distillation of *Clean Code* /
  *Refactoring* / *The Pragmatic Programmer*. The lens for **the line-by-line
  craft**: intent-revealing names, small pure functions, errors as values,
  YAGNI and the rule of three, the code-smell table.

House rules that follow from them:

- Working code is necessary, not sufficient — leave the design better than you
  found it.
- Extract functions for a name and a boundary, not a line count. Depth wins ties.
- Sketch two approaches before committing to non-trivial designs.
- Scale (sharding, replication, caching layers) only when a measured load
  parameter demands it, not on a hunch.

## Working discipline

- **State assumptions before coding.** Inputs, outputs, invariants, edge cases,
  failure modes — name them first (in the commit body for small work). Silent
  assumptions become silent bugs. Never pick silently between plausible
  interpretations — surface them and ask; push back when a simpler approach is
  warranted.
- **Simplify before coding.** Write the minimum code that solves the asked
  problem, nothing speculative — no unrequested flexibility or config, no
  abstractions for single-use code, no error handling for impossible cases.
  Prefer deleting, reusing, or folding into an existing seam over adding layers.
- **Define "done" as a command.** Turn the task into a verifiable check before
  making the change — a failing test that passes, a `curl` that returns 200, a
  screenshot that matches. This applies to config, infra, and ops work too.
- **Stay surgical, but leave it cleaner.** Don't refactor unrelated code or
  restyle files the task doesn't touch; within code you do touch, apply the
  Boy Scout Rule. Large cleanups get their own commit.
- **Bugs leave regression tests** — a test that would have caught it, with a
  comment naming the failure mode.
- **Re-run simplification before finishing.** After it works, review the diff
  for reuse, simplification, efficiency, and altitude cleanups; apply the
  worthwhile ones, then re-verify.

## Project tracking — GitHub Issues

GitHub Issues on this repo are the planning surface. Use them freely and
proactively (`gh issue create`, `gh issue list`, …):

- **Create issues liberally.** Planned work, scope decisions, deferred items
  ("didn't build X, would build when Y"), known gaps, and follow-ups all get an
  issue — small is fine; an issue title and two sentences beat an untracked
  TODO. Deferred-work issues double as material for the design doc's
  "deliberately didn't build" section.
- **Reference issues as you go.** Branches, commits, and PRs cite the issues
  they touch (`#12`); PRs that complete an issue close it via `Closes #12`.
- **Keep them honest.** Close what's done or obsolete; comment when scope
  changes rather than letting the issue drift from reality.

## Things to avoid

- **Committing secrets or build artifacts.** Config is committed; secrets are
  env-loaded and git-ignored (`.env` and friends). Generated output stays out
  of the tree.
- **Backwards-compat shims.** All services here deploy together with one
  command — rename the field and update both sides rather than keeping compat
  layers alive.

## Running & driving the app

*Placeholder — once `make up` (or equivalent) exists, document here: how to
bring the stack up, what state to expect on a fresh boot, and how to verify a
change end-to-end (the curl / dashboard check an agent should run to see its
work, not just its tests).*
