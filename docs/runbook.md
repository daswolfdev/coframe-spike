# Runbook

*Placeholder for the headline entry — written alongside the failure demo
recording (OBJECTIVE.md deliverable). Will cover: the demonstrated failure,
its symptoms in `make ps`/`make logs`, and step-by-step recovery.*

## api won't start: "attempt to write a readonly database"

**Symptoms:** right after `make up`, `make ps` shows `perfmon-api-1`
exited/unhealthy; `make logs S=api` ends with
`sqlite3.OperationalError: attempt to write a readonly database`.

**Cause:** the shared `data` volume exists but is owned by root, so the
non-root api (user `app`) cannot write `/data`. Docker copies ownership
from the image only when the volume is *first created* — a volume left
behind by an older image or a manual `docker run` keeps its old owner
forever. (Hit for real during the events PR — a pre-existing root-owned
`perfmon_data` crash-looped the api; a fresh volume came up correctly.)

**Recovery:**

```
make down
docker volume rm perfmon_data
make up
```

Safe on a laptop: everything in the volume is rebuildable state — the queue
drains and aggregates re-derive from new traffic (see
[DATA-INTENSIVE.md](DATA-INTENSIVE.md) on derived data).
