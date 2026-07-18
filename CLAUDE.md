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

House rules that follow from them:

- Working code is necessary, not sufficient — leave the design better than you
  found it.
- Extract functions for a name and a boundary, not a line count. Depth wins ties.
- Sketch two approaches before committing to non-trivial designs.
- Scale (sharding, replication, caching layers) only when a measured load
  parameter demands it, not on a hunch.
