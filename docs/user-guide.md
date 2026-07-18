# User Guide

How the team uses the platform day to day. One page; the Makefile is the
whole interface — nobody types `docker compose`.

## The loop

```sh
make up              # everything: built, started, healthy — one command
make ps              # what's running, health, ports
make logs            # last 100 + live tail (or one: make logs S=api)
make errors          # like logs, error/exception lines only
make deploy S=api    # ship a change to ONE service: rebuild + restart it
make down            # tear it all down
```

Work on a service, then `make deploy S=<name>` — nothing else restarts, no
SSH, no screen sessions. If something looks wrong, start with `make ps`, then
`make logs S=<name>`; for the worker-down signature (stale dashboard, queue
depth climbing) go straight to the [runbook](runbook.md).

## Where things are

- **Dashboard:** <http://localhost:8081> — top pages, p75 LCP trend, active
  experiments (platform health deliberately stays in the terminal:
  `curl localhost:8000/stats`). `?fixture=1` renders
  canned data; `python3 tools/loadgen.py` generates real traffic.
- **API:** <http://localhost:8000> — `POST /events` (SDK ingest),
  `GET /config/{site_id}` (SDK config), `/healthz`, `/stats` (queue depth
  + data freshness — today's ops signal), and the dashboard's read
  contract (#15): `/sites`, `/sites/{site_id}/pages`,
  `/sites/{site_id}/trend`.
- **Worker:** <http://localhost:8082> — ops only: `/healthz` (loop ticking),
  `/stats` (events consumed, queue depth, flush timings).
- Each service owns its host port in its own `services/<name>/compose.yaml`.

## Changing SDK config (experiments, sampling)

Config is code ([design.md](design.md), "Config as code"): the site map
lives in `services/api/api/cfg.py`, git is the system of record.

```sh
$EDITOR services/api/api/cfg.py     # change a sampling rate, add an experiment
make deploy S=api                    # health-gated, seconds
curl localhost:8000/config/demo      # see it live
```

Every config change is a commit — reviewable, revertable, auditable.

## Adding a service

Copy the template, deploy, done — under 15 minutes, no platform changes:
[adding-a-service.md](adding-a-service.md). Maintainers can prove the
pathway any time with `make smoke`.

## House rule

If you find yourself reaching for `docker` or `docker compose` directly for
routine work, the Makefile is missing a verb — add it rather than working
around it ([CLAUDE.md](../CLAUDE.md) discipline).
