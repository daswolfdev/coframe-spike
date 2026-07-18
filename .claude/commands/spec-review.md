---
description: Review a spec as a staff engineer using docs/SPEC-REVIEW.md
argument-hint: [spec-path]
---

Review a spec as a staff engineer.

1. **Target:** `$ARGUMENTS` if given. Otherwise only specs committed on the
   current branch:
   `git diff --name-only main...HEAD -- docs/superpowers/specs/`.
   If exactly one, review it. If several, review the one from the most recent
   commit on the branch. If none (or resolution is still unclear), ask which
   spec to review — never fall back to specs already on main.
2. Read `docs/SPEC-REVIEW.md` and follow it exactly: apply the gates in order,
   stop at the first failing gate, cite the violated principle for every
   finding, and end with its verdict format.
3. Review only — do not edit the spec or any other file. State the target
   spec's path at the top of the review.

Apply the house rules and canon in [CLAUDE.md](../../CLAUDE.md) while reviewing.
