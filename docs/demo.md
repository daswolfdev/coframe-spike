# The 5-Minute Demo — Script

The recording is the deliverable the graders watch first
([OBJECTIVE.md](../OBJECTIVE.md): "deploy a service, show observability,
induce a failure, recover from it"). Every beat below must be *visibly true*
on screen — no narration standing in for evidence. The failure demoed here is
the one the [runbook](runbook.md) documents; they are written as a pair.

## Locked decisions

- **The failure:** worker killed mid-traffic (`docker kill` — SIGKILL, no
  goodbye). Docker treats an operator kill as a manual stop, so the restart
  policy (which exists for the worker's *own* crash-only exits) does not
  resurrect it — the outage is durable on camera (measured live, #56):
  safe, repeatable, visually obvious, recovery is a platform verb, and the
  queue proves its reason for existing: ingest keeps working, nothing lost.
- **The key number:** queue depth, read live from the api's `GET /stats`
  (#19) via `make stats` — a dedicated pane polling once a second — with
  `last_aggregate_ms` carrying the staleness story. Observability is
  demonstrated through the same surface the team and the runbook actually
  use; the dashboard ops strip (#20) is deliberately deferred — the
  terminal *is* the platform's interface.

## The beats

| Time | Beat | On screen | Proves |
|---|---|---|---|
| 0:00–0:45 | Cold start | Fresh terminal: `make up`; `make ps` → three services healthy | Hard constraint #1: one command, laptop only |
| 0:45–1:30 | Life | Load generator starts (#18); dashboard shows top pages + p75 moving; one `curl` of `GET /config/{site_id}` | The product works; both API paths exercised |
| 1:30–2:30 | Deploy | Small visible change; `make deploy S=api`; `make ps` uptimes show only api restarted; change is live | Deploys without SSH; single-service deploy |
| 2:30–3:45 | Failure | `docker kill` the worker; `make ps`: worker Exited; stats pane: `queue_depth` climbing, `last_aggregate_ms` frozen; load gen pane: errors still 0 | Observability catches it; queue decouples ingest; no data loss while down |
| 3:45–4:30 | Recover | Follow [runbook.md](runbook.md) on screen: `make ps` → `make logs S=worker` → `make deploy S=worker`; stats pane drains to 0; dashboard catches up; sent-count = aggregated-count | Recovery is a documented platform verb; zero events lost |
| 4:30–5:00 | Wrap | Point at [adding-a-service.md](adding-a-service.md) + the runbook just used; `make down` | 4th-service pathway exists; clean teardown |

## Prerequisites (tracked as issues)

- [x] [#11](https://github.com/daswolfdev/coframe-spike/issues/11) — the
  worker itself: the failure's subject, and the source of the aggregates
  every dashboard beat reads (landed: `services/worker/`)
- [x] [#15](https://github.com/daswolfdev/coframe-spike/issues/15) — api
  read endpoints the dashboard calls (`/sites`, pages, trend): landed
- [x] [#18](https://github.com/daswolfdev/coframe-spike/issues/18) — load
  generator with a sent-count, so the no-loss claim is checkable:
  `python3 tools/loadgen.py` (stdlib only; Ctrl-C prints the final count)
- [x] [#19](https://github.com/daswolfdev/coframe-spike/issues/19) — API ops
  read surface (queue depth + last-aggregate time): `GET /stats`
- [x] ~~#20 — dashboard ops strip~~ — deliberately deferred, not a
  prerequisite: the stats poll loop replaces it on screen (trigger to build:
  the first platform-health consumer who doesn't live in a terminal)
- [ ] [#21](https://github.com/daswolfdev/coframe-spike/issues/21) — README
  linking the recording; runbook filled for exactly this failure (runbook
  half: done)

## Recording rules

- One take, real time — no cuts inside a beat (cuts between beats fine).
- Terminal + browser side by side; font large enough for a laptop viewer.
- If a beat drags past its slot, cut scope (skip the config curl before
  trimming the failure beat — failure/recover is the heart).
- Rehearse the timing dry at least once: 5:00 is a hard ceiling.
