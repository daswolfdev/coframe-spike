# Runbook — worker down (stale aggregates, growing queue)

The failure this platform is designed to survive, and the one demonstrated in
the [recording](demo.md). One page; follow top to bottom.

## Symptoms

- Dashboard aggregates stop updating — last-updated timestamp ages visibly;
  ops strip shows **queue depth climbing** instead of hovering near zero.
- Event ingestion is **unaffected**: `POST /events` keeps returning 202/200.
  If ingestion is *also* failing, this is not your incident — check the api.

## Confirm (60 seconds)

```sh
make ps                # worker: Exited / unhealthy; api + dashboard healthy
make logs S=worker     # last lines before death: panic? OOM? clean exit?
```

Two signals confirm it: worker not running/healthy in `make ps`, and queue
depth rising on the ops strip. Depth alone can also mean the worker is alive
but drowning — `make ps` disambiguates.

## Recover

```sh
make deploy S=worker   # rebuild + restart just the worker
```

Then watch the drain:

- `make ps` — worker healthy again.
- Ops strip — queue depth falls (drain rate is ~33× ingest at target load,
  so minutes of backlog clear in seconds).
- Dashboard last-updated goes fresh.

## Verify nothing was lost

Events queued while the worker was down were buffered in `queue.db`, not
dropped. After depth returns to ~0, confirm the aggregates moved forward
(top-pages counts increased over pre-incident values). During the demo this
is exact: load-generator sent-count equals aggregated event count.

## If recovery fails

- Worker restarts then dies again: `make logs S=worker` — a poison event or
  bad deploy; roll back to the previous image (`git revert` the service
  change, `make deploy S=worker`).
- Depth still growing with a healthy worker: it's drowning, not dead — bump
  the dequeue batch size (see [design.md](design.md), Worker knob) and
  redeploy.

## Why this is survivable by design

The queue is a durable SQLite table on disk ([design.md](design.md), "Queue")
— a dead consumer means growth, not loss. Sustained queue-depth growth is the
single metric this runbook exists for.
