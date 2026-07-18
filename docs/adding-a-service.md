# Adding a Service (< 15 minutes, zero platform changes)

A service is a directory under `services/` with a `compose.yaml` and a
`Dockerfile`. The platform discovers it by existence — there is nothing to
register anywhere. The starting point is
[services/_template/](../services/_template/README.md).

Worked example: adding a service called `alerts`.

1. **Scaffold it** *(1 min)*
   `make new S=alerts` — copies the template and renames it (compose
   service name and build context both match the directory automatically).
   The name must be a DNS label — lowercase letters/digits/hyphens, starting
   with a letter, not ending in a hyphen — because it doubles as the
   service's network alias; `make new` rejects anything else.
2. **Pick a port, if it listens** *(2 min)* — in
   `services/alerts/compose.yaml`, uncomment `ports` and pick a host port
   nothing else publishes (`make ps` shows what's taken; the service owns
   its port, there is no central registry; keep the `127.0.0.1:` prefix —
   everything binds loopback-only). The template's other fields (`init`,
   `logging`, healthcheck timing) are platform posture — keep them as-is.
3. **Replace the Dockerfile** *(5 min)* — whatever builds and runs your
   service. Log to stdout; no log files.
4. **Make the healthcheck real** *(2 min)* — replace `["CMD", "true"]` with a
   probe of your service, e.g. `["CMD", "wget", "-qO-", "http://localhost:8080/healthz"]`.
   Not optional: `make check` rejects a service that still carries the
   placeholder probe, in any spelling.
5. **Deploy it** *(2 min)*
   `make deploy S=alerts` — builds and starts just your service.
6. **Verify** *(1 min)*
   `make ps` shows it healthy; `make logs S=alerts` follows its logs.

Total: ~13 minutes. Platform files touched: **none**.

Maintainers: `make smoke` mechanically re-proves this pathway (scaffolds
via `make new`, deploys it, waits for healthy, tears down).
