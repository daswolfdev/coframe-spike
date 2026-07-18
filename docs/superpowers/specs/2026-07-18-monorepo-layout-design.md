# Monorepo Layout — Design

**Date:** 2026-07-18
**Status:** Approved
**Branch:** `monorepo-layout` → PR into `main`

## Goal

Lay out the monorepo for the platform take-home (see [OBJECTIVE.md](../../../OBJECTIVE.md))
and optimize the structure around its central constraint: **a single `make up`
brings the whole platform up.** Three optimization targets, in order:

1. **The Makefile is the whole interface.** The team's mental model is
   `make up / down / logs / deploy / ps`. Compose, images, and networks are
   hidden implementation.
2. **The 4th-service pathway.** Adding a service is copy-a-template, provably
   under 15 minutes, with **zero platform edits** — the structure itself
   documents the contract.
3. **Dev-loop speed.** Rebuilding/redeploying one service never touches the
   rest.

## Scope of this PR

**Structure + docs only.** No running services. The Makefile and platform
plumbing are real; the three service directories are README stubs that later
PRs fill in. `make up` on this PR brings up an empty-but-working platform.

## Layout

```
Makefile                    # the one interface
platform/
  compose.base.yaml         # project name, shared network; later: queue, db, observability
services/
  _template/                # the 4th-service pathway in executable form
    compose.yaml
    Dockerfile
    README.md
  api/README.md             # FastAPI service — lands in a later PR
  worker/README.md          # Go aggregator — lands in a later PR
  dashboard/README.md       # static frontend — lands in a later PR
docs/
  design.md                 # per-service shape, stack choices, rejected alternatives
  adding-a-service.md       # the <15-min pathway a stranger could follow
  user-guide.md             # placeholder (filled when services exist)
  runbook.md                # placeholder (filled when failure demo exists)
```

## The Makefile (the deep module)

Five targets hiding all of Docker Compose:

| Target | Does |
|---|---|
| `make up` | Discover fragments, `docker compose -f base -f frag… up -d --build`, print status + URLs |
| `make down` | Tear everything down |
| `make logs [S=api]` | Follow logs, all services or one |
| `make deploy S=api` | Rebuild + restart **one** service (`up -d --build api`) |
| `make ps` | One-glance system status |

Mechanism:

- Discovery: `$(wildcard services/*/compose.yaml)`, then explicitly
  `$(filter-out services/_%, …)` so `_template` (and any future `_`-prefixed
  dir) never deploys.
- All fragments merge into **one compose project** (named in
  `compose.base.yaml`), so everything shares one network and `make ps` shows
  the whole system.
- With zero fragments present (this PR), `make up` still runs cleanly — the
  layout is proven before any service exists.

## The service contract

A service **is** a directory under `services/` containing:

- `compose.yaml` — a fragment defining one service whose name equals the
  directory name, with a healthcheck, logging to stdout.
- `Dockerfile` — how it builds.

That is the entire contract. No central registration: the Makefile's discovery
makes OBJECTIVE.md's "no platform changes" claim literal. `_template/` embodies
the contract; `docs/adding-a-service.md` narrates it step-by-step with a
15-minute walkthrough.

## Alternatives considered

- **Central compose registry** (one `platform/compose.yaml` listing every
  service): maximally obvious — the whole topology in one file — but adding a
  service means editing a platform file, weakening the "no platform changes"
  constraint to "small platform change." Rejected in favor of an airtight claim;
  the cost is one clever mechanism (fragment merging) the team must trust.
- **Workspace-tooled monorepo** (apps/ + packages/ + Turbo/Nx): rejected —
  three tiny polyglot services share no code, and the tooling becomes platform
  surface to operate. Over-engineered per OBJECTIVE.md's grading lens.

## Risks / open questions

- **Fragment merging is the one clever thing.** If compose merge semantics
  surprise us (e.g., cross-fragment references), fallback is the central
  registry — the directory layout is identical either way, so switching is
  cheap.
- The queue/db choice (what lives in `compose.base.yaml` as shared infra) is
  deliberately deferred to the first service PR.

## Verification

- `make up`, `make ps`, `make down` run clean on the empty platform.
- Smoke-test discovery: `cp -r services/_template services/test-svc && make up`
  brings the template service up; removed before commit.
