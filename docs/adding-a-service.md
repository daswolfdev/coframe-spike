# Adding a Service (< 15 minutes, zero platform changes)

A service is a directory under `services/` with a `compose.yaml` and a
`Dockerfile`. The platform discovers it by existence — there is nothing to
register anywhere. The starting point is
[services/_template/](../services/_template/README.md).

Worked example: adding a service called `alerts`.

1. **Copy the template** *(1 min)*
   `cp -r services/_template services/alerts`
2. **Edit `services/alerts/compose.yaml`** *(3 min)* — three changes:
   the service name `_template` → `alerts` (must match the directory name),
   the build context `./services/_template` → `./services/alerts`, and — if
   the service listens — uncomment `ports` and pick a host port nothing else
   publishes (`make ps` shows what's taken; the service owns its port, there
   is no central registry).
3. **Replace the Dockerfile** *(5 min)* — whatever builds and runs your
   service. Log to stdout; no log files.
4. **Make the healthcheck real** *(2 min)* — replace `["CMD", "true"]` with a
   probe of your service, e.g. `["CMD", "wget", "-qO-", "http://localhost:8080/healthz"]`.
5. **Deploy it** *(2 min)*
   `make deploy S=alerts` — builds and starts just your service.
6. **Verify** *(1 min)*
   `make ps` shows it healthy; `make logs S=alerts` follows its logs.

Total: ~14 minutes. Platform files touched: **none**.

Maintainers: `make smoke` mechanically re-proves this pathway (copies the
template, deploys it, waits for healthy, tears down).
