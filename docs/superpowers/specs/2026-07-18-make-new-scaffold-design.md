# `make new` Service Scaffold — Design

**Date:** 2026-07-18
**Status:** Approved in brainstorming
**Branch:** `make-new-scaffold` → PR into `main`

## Goal

Strengthen the add-a-service demonstration ([OBJECTIVE.md](../../../OBJECTIVE.md)
hard constraint 2) with a `make new S=<name>` target that scaffolds an empty
service from [services/_template/](../../../services/_template/README.md).
The mechanical steps of the pathway (copy, rename) become one command; the
judgment steps (Dockerfile, healthcheck, port) stay human, exactly as
[adding-a-service.md](../../adding-a-service.md) documents them.

## Scope

Makefile + doc edits only — no new scripts or platform files. No behavior
change to any existing verb except `smoke`, which is refactored to reuse the
new target.

## Design

### Target: `make new S=<name>`

**Guards (in order, each a clean error):**

1. `S` undefined → `$(error usage: make new S=<service-name>)` — same idiom
   as `deploy`.
2. Name fails `^[a-z][a-z0-9-]*$` → error. Lowercase DNS/compose-safe;
   structurally cannot start with `_`, so the result is always discovered by
   the platform.
3. `services/$(S)` already exists → error; never overwrite.

**Action (the same lines `smoke` uses today):**

```sh
mkdir -p services/$(S)
cp services/_template/Dockerfile services/$(S)/Dockerfile
sed 's/_template/$(S)/g' services/_template/compose.yaml > services/$(S)/compose.yaml
```

The single `sed` rewrites both the compose service name and the build
context. POSIX-only (no `sed -i`), per house rules.

**No README is generated.** A scaffolded `.md` would trip the doc-reachable
gate, and the template's README belongs to the template.

**Output:** print the remaining human steps — replace the Dockerfile, make
the healthcheck real, pick a port, `make deploy S=<name>` — and point at
[adding-a-service.md](../../adding-a-service.md).

### Smoke refactor

`smoke`'s inline `mkdir`/`cp`/`sed` lines become `$(MAKE) new S=smoke-test`
(after its existing `rm -rf`). Every smoke run now re-proves the scaffold
pathway mechanically, keeping the claim continuously true.

### Docs

- Makefile header comment gains the verb.
- [adding-a-service.md](../../adding-a-service.md): steps 1–2's copy/rename
  collapse into `make new S=alerts` *(1 min)*; the walkthrough keeps its
  explanations for the manual edits that remain (port, Dockerfile,
  healthcheck).
- One sentence in [design.md](../../design.md)'s platform section.

## Rejected alternatives

- **Helper script called by make** — right if the scaffold grew prompts or
  port scanning; for ~6 lines of shell it is a second place to look for
  platform behavior. The inline recipe matches the `smoke` precedent.
- **Scaffold + auto-deploy** — flashier demo but conflates two verbs and
  deploys a placeholder the user has not edited.
- **Port handling (`P=<port>` / auto-pick)** — port choice is a judgment
  call the docs assign to the service owner; the template's comments already
  explain it.

## Done when

- `make new S=demo-x` then `make deploy S=demo-x` comes up healthy.
- Re-running `make new S=demo-x` fails cleanly without touching the
  existing directory.
- `make new` (no `S`) and `make new S=Bad_Name` fail with usage errors.
- `make smoke` still passes, now via the scaffold path.
- `make check` passes (docs linked, links resolve).
