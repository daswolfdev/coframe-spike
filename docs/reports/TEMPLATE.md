# YYYY-MM-DD — Title: the question, phrased as a claim to test

<!-- Copy this file to docs/reports/YYYY-MM-DD-short-slug.md, replace each
     section, add the report to the index in README.md. Rules live in
     [README.md](README.md); discipline in [CLAUDE.md](../../CLAUDE.md). -->

## Question

The decision this report informs, and the threshold that decides it
(e.g. "can X sustain N/s? If yes, we skip Y").

## Method

What was run, phase by phase, and what each phase models in the real system.
Link the committed script/commands: `assets/<slug>.py` (or a fenced command
block for one-liners).

## Environment

Hardware, OS/kernel, filesystem the data touched, tool versions, and any
settings that change the numbers (pragmas, flags, durations).

## Results

| Load path | Target | Measured |
|---|---|---|
|  |  |  |

One paragraph reading the table: which number decides the question, and why.

## Conclusion

The decision the numbers support, stated plainly. Include the trigger that
would revisit it ("rebuild this when Z").

## Caveats

What this measurement does not show; observed failure modes; artifacts of the
benchmark setup a reader should not extrapolate from.
