# Reports

Committed evidence behind design decisions: benchmarks, spikes, probes, and
measurements. When a design doc or scaling argument says "we measured X," the
measurement lives here. Working discipline comes from [CLAUDE.md](../../CLAUDE.md).

## Rules

1. **One file per report**, named `YYYY-MM-DD-short-slug.md`, structured per
   [TEMPLATE.md](TEMPLATE.md). Date is the day the measurement ran.
2. **Reproducible or it didn't happen.** Commit the exact script or commands
   under [assets/](assets/) (named after the report slug) and link them from
   the report. A stranger with this repo should get comparable numbers.
3. **Record the environment.** Hardware, OS, filesystem, and tool versions —
   whatever could plausibly change the numbers. Watch for tmpfs: benchmarks
   that touch disk must run on a real filesystem.
4. **Caveats are part of the result.** State what the measurement does *not*
   show and any observed failure modes, not just the headline number.
5. **Add every report to the index below**, newest first, with a one-line
   takeaway. The takeaway states the decision the numbers support.

## Index

- [2026-07-18 — SQLite WAL throughput](2026-07-18-sqlite-wal-throughput.md) —
  SQLite in WAL mode clears both objective load targets with ~100× headroom;
  no queue/store infra beyond SQLite is needed.
