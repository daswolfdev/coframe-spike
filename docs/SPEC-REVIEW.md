# SPEC-REVIEW — Staff-Eng Review Guide for Specs

The go-to checklist for reviewing any spec or design doc in this repo. It turns
our three foundational documents into gates a spec must pass, in order:

- [OBJECTIVE.md](../OBJECTIVE.md) — what this repo is for; every decision is
  judged against it
- [SOFTWARE-DESIGN.md](SOFTWARE-DESIGN.md) — Ousterhout: the code-structure lens
- [DATA-INTENSIVE.md](DATA-INTENSIVE.md) — Kleppmann: the data-and-state lens

A spec that fails a gate stops there: fix and re-review before applying later
gates. Every finding must cite the principle it violates — "I'd do it
differently" is not a finding.

---

## Gate 0 — Objective fit (OBJECTIVE.md)

The scoping gate. Over-engineered and under-built are **both** wrong answers.

- [ ] **Does this serve a deliverable?** Point at the OBJECTIVE.md checklist
      line this work advances. If you can't, it's scope creep.
- [ ] **Laptop constraint.** Does everything still come up with the single
      `make up`? Does the spec add anything that breaks one-command bring-up?
- [ ] **4th-service pathway.** Does the change keep "add a service in <15 min,
      no platform changes" true — or does it quietly add a new registration
      point?
- [ ] **Scaling ceiling.** Is the design viable at 1,000 events/s and 1,000
      concurrent users — and does it stop there? Sharding, replication, or
      caching layers without a named load parameter are over-engineering.
- [ ] **Under-building check.** Is anything labeled "later" that a deliverable
      actually requires now?

## Gate 1 — Design lens (SOFTWARE-DESIGN.md)

The complexity gate. Judge every element by one question: does it reduce
complexity?

- [ ] **Deep modules.** For each component: is the interface much smaller than
      the functionality it hides? A wrapper that exposes what it wraps is
      negative value.
- [ ] **Information leakage.** Is any single design decision (a format, a
      naming rule, a port number) smeared across multiple components? One
      decision, one owner.
- [ ] **Complexity pulled downward.** Where there's unavoidable ugliness, does
      the implementer absorb it, or is it pushed up to every caller/operator?
- [ ] **Knowledge boundaries, not execution order.** Are modules structured
      around what they *know*, or around the order things happen (temporal
      decomposition)?
- [ ] **Errors defined out of existence.** Could an error case be made
      impossible instead of handled? (e.g., idempotent operations, discovery
      instead of registration.)
- [ ] **Design it twice.** Does the spec show a genuinely different rejected
      alternative per major decision? A strawman doesn't count.
- [ ] **Red-flag sweep.** Run the red-flag table in SOFTWARE-DESIGN.md against
      the proposed interfaces; name any hits.

## Gate 2 — Data lens (DATA-INTENSIVE.md)

The state gate. Skip only if the spec touches no data or state — say so
explicitly in the review.

- [ ] **Goal named.** For each trade-off: does the spec say whether it buys
      reliability, scalability, or maintainability?
- [ ] **One system of record.** Is exactly one store authoritative for each
      piece of state, with everything else derived and rebuildable? Two systems
      claiming truth is an automatic fail.
- [ ] **Load in parameters, latency in percentiles.** Are load claims concrete
      (req/s, fan-out) and performance targets percentile-based (p75/p95/p99),
      never averages?
- [ ] **Schema is a contract.** Can old and new code coexist during a deploy?
      Are fields added, never repurposed?
- [ ] **Faults tolerated, not assumed away.** What happens when the queue is
      down, the worker restarts mid-batch, a message is delivered twice? The
      spec should answer, not the reviewer.

## Verdict

End every review with one of:

- **Approve** — all gates pass; list any non-blocking nits separately.
- **Revise** — list findings as `Gate N — principle — what fails — suggested
  direction`, most severe first. The author fixes and re-requests review from
  the first failed gate.

Keep reviews short. Three cited findings beat ten vibes.

---

*Part of the repo canon — see [CLAUDE.md](../CLAUDE.md).*
