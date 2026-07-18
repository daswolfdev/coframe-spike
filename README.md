# perfmon — platform take-home

A web-performance-monitoring stack (event ingest API, aggregating worker,
dashboard) and the **minimum platform** that runs it: one command up, one
command to deploy a single service, observable, laptop-only. Built against
[OBJECTIVE.md](OBJECTIVE.md) — the source of truth for scope and grading.

## Quickstart

```sh
make up      # everything: built, started, healthy
make ps      # see it
make down    # gone
```

Dashboard at <http://localhost:8081>, API at <http://localhost:8000> (both
loopback-only). Needs Docker Engine 25+ / Compose 2.20+ — 2023-era or newer.
Observability lives in the terminal: `make logs` / `make errors` for the
stream, `curl localhost:8000/stats` for the ops signal (queue depth, data
freshness). Full day-to-day usage: [docs/user-guide.md](docs/user-guide.md).

## The 5-minute demo

**Recording: <https://www.loom.com/share/bed99531c55749bca3eb12f3a3507a2e>**
Script and locked decisions: [docs/demo.md](docs/demo.md). The failure it
demonstrates is documented in [docs/runbook.md](docs/runbook.md).

## The deliverables, mapped

Every item [OBJECTIVE.md](OBJECTIVE.md) asks for, and where to grade it:

| OBJECTIVE asks for | Where it is |
| --- | --- |
| Platform + three services, one command, observable | Quickstart above; the daily loop in the [user guide](docs/user-guide.md) |
| 5-min recording: deploy, observe, fail, recover | Linked above; script in [demo.md](docs/demo.md) |
| Per-service shape; one rejected alternative per component; least-confident decision; deliberately-didn't-build + triggers | [design.md](docs/design.md) — each section carries all four |
| The queue choice, justified | [design.md](docs/design.md) § "Queue: a SQLite table", backed by a [measured report](docs/reports/2026-07-18-sqlite-wal-throughput.md) |
| Fourth service in <15 min, documented, no platform changes | [adding-a-service.md](docs/adding-a-service.md) — and `make smoke` proves the pathway mechanically |
| Scaling argued to 1,000 events/s + 1,000 users, and no further | [design.md](docs/design.md) § "Scaling pathway" — ends at the explicit stop-line |
| One-page user guide | [user-guide.md](docs/user-guide.md) |
| One-page runbook for the demoed failure | [runbook.md](docs/runbook.md) |
| Honest hours | [hours.md](docs/hours.md) |

Beyond the deliverables: [CLAUDE.md](CLAUDE.md) is the canon and carries the
full repo map. Markdown deliberately also lives next to the code it describes
(service READMEs, sub-canons) — the `make check` gate guarantees all of it is
reachable from the canon.

## Submission checklist

- [x] Recording linked above (#21)
- [x] design.md per-service sections complete (#26)
- [x] Hours log finalized ([docs/hours.md](docs/hours.md))
- [x] **Repo flipped public** (#30): `gh repo edit --visibility public`
