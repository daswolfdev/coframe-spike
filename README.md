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

Dashboard at <http://localhost:8081>, API at <http://localhost:8000>. Full
day-to-day usage: [docs/user-guide.md](docs/user-guide.md).

## The 5-minute demo

**Recording: _not yet recorded — link lands here (tracked in #21)._**
Script and locked decisions: [docs/demo.md](docs/demo.md). The failure it
demonstrates is documented in [docs/runbook.md](docs/runbook.md).

## Where everything lives

[CLAUDE.md](CLAUDE.md) is the canon and carries the full repo map; the
deliverable docs are under [docs/](docs/design.md) — design (with per-service
sections, rejected alternatives, and the argued scaling pathway),
[adding-a-service.md](docs/adding-a-service.md) (the <15-minute pathway,
mechanically proven by `make smoke`), user guide, runbook, and the honest
[hours log](docs/hours.md). Markdown deliberately also lives next to the code
it describes (service READMEs, sub-canons) — the `make check` gate guarantees
all of it is reachable from the canon.

## Submission checklist

- [ ] Recording linked above (#21)
- [ ] design.md per-service sections complete (#26)
- [ ] Hours log finalized ([docs/hours.md](docs/hours.md))
- [ ] **Repo flipped public** (#30): `gh repo edit --visibility public`
