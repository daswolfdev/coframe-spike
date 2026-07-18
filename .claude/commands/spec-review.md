---
description: Review a spec as a staff engineer using docs/SPEC-REVIEW.md
argument-hint: [spec-path]
---

Review a spec as a staff engineer.

1. **Target:** `$ARGUMENTS` if given. Otherwise the newest spec in
   `docs/superpowers/specs/` by the `YYYY-MM-DD` filename prefix. If that
   directory is empty or the choice is ambiguous, ask which spec to review.
2. Read `docs/SPEC-REVIEW.md` and follow it exactly: apply the gates in order,
   stop at the first failing gate, cite the violated principle for every
   finding, and end with its verdict format.
3. Review only — do not edit the spec or any other file. State the target
   spec's path at the top of the review.
