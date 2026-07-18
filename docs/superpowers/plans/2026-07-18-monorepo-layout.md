# Monorepo Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the monorepo skeleton from the approved spec (`docs/superpowers/specs/2026-07-18-monorepo-layout-design.md`): a real Makefile-as-interface, discovery-based compose platform, service template, and the required docs — no running services yet.

**Architecture:** The root Makefile is the only interface (`up/down/logs/deploy/ps` + maintainer `smoke`). It discovers `services/*/compose.yaml` fragments (underscore-prefixed dirs excluded) and merges them with `platform/compose.base.yaml` into one compose project named `perfmon`. Services self-register by existing; the platform holds zero per-service knowledge.

**Tech Stack:** GNU Make, Docker Compose v2. No other tooling.

**Verified facts (tested on this machine):** `docker compose up -d` against a file with zero services exits 1 with "no service selected" — the `up` target must branch on the empty-fragment case. `docker compose down` on an empty project exits 0.

**Compose gotcha the code below already handles:** relative paths in fragments resolve against the *first* `-f` file's directory. The Makefile therefore passes `--project-directory .` so all fragment paths are repo-root-relative, and build contexts are written as `./services/<name>`.

---

### Task 1: Platform core — compose base + Makefile team verbs

**Files:**
- Create: `platform/compose.base.yaml`
- Create: `Makefile`

- [ ] **Step 1: Verify the failing state**

Run: `make up`
Expected: FAIL — `make: *** No rule to make target 'up'` (no Makefile exists).

- [ ] **Step 2: Create `platform/compose.base.yaml`**

```yaml
# Platform-owned compose config. Services NEVER need edits here — they
# self-register by existing as services/<name>/compose.yaml.
# Later platform PRs add shared infra (queue, db, observability) to this file.
name: perfmon
```

All services share the compose project's default network automatically; no
explicit network config until something needs one.

- [ ] **Step 3: Create `Makefile`**

```make
# The platform's entire interface. The team never types `docker compose`.
#
#   make up            bring the whole platform up, built and running
#   make down          tear it all down
#   make ps            what's running, health, published ports
#   make logs [S=api]  follow logs (all services, or one)
#   make deploy S=api  rebuild + restart ONE service
#   make smoke         (maintainer) prove the add-a-service pathway end-to-end
#
# Services are discovered, never registered: every services/*/compose.yaml
# is part of the platform (underscore-prefixed dirs like _template excluded).

COMPOSE_FRAGMENTS := $(filter-out services/_%,$(wildcard services/*/compose.yaml))
COMPOSE := docker compose --project-directory . \
  -f platform/compose.base.yaml \
  $(foreach f,$(COMPOSE_FRAGMENTS),-f $(f))

.PHONY: up down ps logs deploy smoke

up:
ifeq ($(COMPOSE_FRAGMENTS),)
	@echo "perfmon: no services discovered — platform is up (empty)."
	@echo "Add one: see docs/adding-a-service.md"
else
	$(COMPOSE) up -d --build
	@$(COMPOSE) ps
endif

down:
	$(COMPOSE) down --remove-orphans

ps:
	@$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f $(S)

deploy:
ifndef S
	$(error usage: make deploy S=<service>)
endif
	$(COMPOSE) up -d --build $(S)
	@$(COMPOSE) ps $(S)
```

- [ ] **Step 4: Verify the empty platform runs clean**

Run: `make up && make ps && make down && echo OK`
Expected: the "no services discovered" message, an empty `ps` table, a `down`
warning about no resources (exit 0), then `OK`.

Run: `make deploy`
Expected: FAIL with `usage: make deploy S=<service>` (the guard works).

- [ ] **Step 5: Commit**

```bash
git add Makefile platform/compose.base.yaml
git commit -m "Add platform core: Makefile interface + compose base"
```

### Task 2: Service template + smoke target

**Files:**
- Create: `services/_template/compose.yaml`
- Create: `services/_template/Dockerfile`
- Create: `services/_template/README.md`
- Modify: `Makefile` (add `smoke` target at the end)

- [ ] **Step 1: Create `services/_template/compose.yaml`**

```yaml
# THE SERVICE CONTRACT — a service is a directory under services/ with this
# file and a Dockerfile. Rules:
#   1. The service name below MUST equal the directory name.
#   2. Define a healthcheck (make smoke and make ps rely on it).
#   3. Log to stdout only — the platform owns log collection.
#   4. Need a host port? Pick one no other service publishes (`make ps`
#      shows what's taken), then uncomment `ports`. The service owns its
#      host port; there is no central port registry.
services:
  _template:                          # ← rename to your directory name
    build:
      context: ./services/_template   # ← update path after copying
    # ports:
    #   - "8080:8080"                 # host:container — see rule 4
    healthcheck:
      test: ["CMD", "true"]           # ← replace with a real probe
      interval: 5s
      timeout: 3s
      retries: 5
```

- [ ] **Step 2: Create `services/_template/Dockerfile`**

```dockerfile
# Placeholder build so the template deploys as-is (make smoke depends on
# this). Replace everything below with your service's real build.
FROM alpine:3.20
CMD ["sh", "-c", "while true; do echo alive; sleep 30; done"]
```

- [ ] **Step 3: Create `services/_template/README.md`**

```markdown
# _template

Copy this directory to create a service — full walkthrough in
[docs/adding-a-service.md](../../docs/adding-a-service.md). The underscore
prefix keeps this directory out of platform discovery; your copy (no
underscore) deploys automatically.

The most likely mistake: forgetting to make the service name in
`compose.yaml` match the new directory name. `make smoke` exists to prove
the pathway stays healthy.
```

- [ ] **Step 4: Append the `smoke` target to `Makefile`**

Add `smoke` to the existing `.PHONY` line, then append:

```make
# Maintainer check: proves a copied template deploys healthy with zero
# platform edits, then cleans up. Keeps the <15-minute add-a-service claim
# and the service contract (name match, healthcheck) continuously true.
smoke:
	rm -rf services/smoke-test
	cp -r services/_template services/smoke-test
	sed -i 's/_template/smoke-test/g' services/smoke-test/compose.yaml
	$(MAKE) up
	timeout 60 sh -c 'until [ "$$(docker inspect -f "{{.State.Health.Status}}" perfmon-smoke-test-1 2>/dev/null)" = "healthy" ]; do sleep 2; done'
	$(MAKE) down
	rm -rf services/smoke-test
	@echo "smoke: PASS — template deployed healthy, tore down clean"
```

(`$(MAKE) up` sub-invocations are required: `COMPOSE_FRAGMENTS` is computed at
parse time, so the same make process would not see the just-copied fragment.)

- [ ] **Step 5: Run the smoke test**

Run: `make smoke`
Expected: image builds, `perfmon-smoke-test-1` reaches healthy, platform tears
down, `smoke: PASS…` prints, and `git status` shows no leftover
`services/smoke-test/`.

Run: `make up && make ps && make down`
Expected: back to the empty-platform message — `_template` itself is never
discovered.

- [ ] **Step 6: Commit**

```bash
git add services/_template Makefile
git commit -m "Add service template and smoke target proving the pathway"
```

### Task 3: Service directory stubs

**Files:**
- Create: `services/api/README.md`
- Create: `services/worker/README.md`
- Create: `services/dashboard/README.md`

- [ ] **Step 1: Create the three READMEs**

`services/api/README.md`:

```markdown
# api

Lands in a later PR: Python/FastAPI. `POST /events` (site_id, page_url,
lcp_ms, timestamp, session_id) onto the queue; `GET /config/{site_id}`
returns SDK config. See OBJECTIVE.md.
```

`services/worker/README.md`:

```markdown
# worker

Lands in a later PR: Go. Consumes the queue; rolling aggregates per
(site_id, page_url): event count, p75 LCP, last-seen. See OBJECTIVE.md.
```

`services/dashboard/README.md`:

```markdown
# dashboard

Lands in a later PR: static HTML+JS. Top pages by volume, p75 LCP trend,
active experiments, via the api service. See OBJECTIVE.md.
```

- [ ] **Step 2: Verify discovery still ignores them**

Run: `make up`
Expected: still the empty-platform message (no `compose.yaml` in the stubs, so
nothing is discovered).

- [ ] **Step 3: Commit**

```bash
git add services/api services/worker services/dashboard
git commit -m "Stub the three service directories"
```

### Task 4: Docs — pathway walkthrough, design doc, placeholders

**Files:**
- Create: `docs/adding-a-service.md`
- Create: `docs/design.md`
- Create: `docs/user-guide.md`
- Create: `docs/runbook.md`

- [ ] **Step 1: Create `docs/adding-a-service.md`**

```markdown
# Adding a Service (< 15 minutes, zero platform changes)

A service is a directory under `services/` with a `compose.yaml` and a
`Dockerfile`. The platform discovers it by existence — there is nothing to
register anywhere.

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
```

- [ ] **Step 2: Create `docs/design.md`**

```markdown
# Design

Judged against [OBJECTIVE.md](../OBJECTIVE.md). Reviewed under
[SPEC-REVIEW.md](SPEC-REVIEW.md). This document grows a section per service
as each lands; today it covers the platform.

## Platform

**Shape:** a root Makefile fronting Docker Compose. Five team verbs
(`up/down/ps/logs/deploy`) plus maintainer `smoke`. The Makefile discovers
`services/*/compose.yaml` fragments (underscore-prefixed excluded) and merges
them with `platform/compose.base.yaml` into one compose project (`perfmon`).
State lives nowhere yet — no services run; shared infra (queue, db) arrives
with the first service that needs it.

**Why compose + make:** the whole platform is a file the team already knows
how to read, runs identically on any laptop, and needs no controller to
operate. Rejected alternative: k3s/kind — real orchestrator semantics at the
cost of far more surface to operate and explain; over-engineering at
5 engineers and laptop scale.

**Why discovery over registration:** a service exists by having a directory;
the "forgot to register it" failure cannot happen, and OBJECTIVE.md's
"fourth service without platform changes" is literally true. Rejected
alternative: one central compose.yaml listing every service — more obvious
(whole topology in one file) but every addition edits a platform file.

**Least confident decision:** compose multi-file merge semantics as the
backbone. If fragment merging surprises us, the fallback is the central
registry — same directory layout, so switching is cheap.

**Deliberately not built (and triggers to build):** reverse proxy / service
mesh (trigger: real port-collision pain or TLS needs); CI (trigger: second
contributor breaking main); observability stack (trigger: first service PR —
logs/metrics land with something to observe); queue/db in compose.base.yaml
(trigger: the api service PR chooses one and justifies it here).
```

- [ ] **Step 3: Create `docs/user-guide.md`**

```markdown
# User Guide

*Placeholder — written when the first service lands and there is something
to use. Will cover: the day-to-day loop (`make up`, `make logs`,
`make deploy S=<svc>`), where to see aggregates, and how to change SDK
config.*
```

- [ ] **Step 4: Create `docs/runbook.md`**

```markdown
# Runbook

*Placeholder — written alongside the failure demo recording (OBJECTIVE.md
deliverable). Will cover: the demonstrated failure, its symptoms in
`make ps`/`make logs`, and step-by-step recovery.*
```

- [ ] **Step 5: Verify docs tell the truth**

Run: `make smoke`
Expected: PASS — the walkthrough's mechanism (copy → rename → deploy) is
exactly what smoke exercises. If smoke passes, `adding-a-service.md` steps
1–2 and 5–6 are mechanically verified.

- [ ] **Step 6: Commit**

```bash
git add docs/adding-a-service.md docs/design.md docs/user-guide.md docs/runbook.md
git commit -m "Add pathway walkthrough, design doc, and doc placeholders"
```

### Task 5: Final verification, push, PR

- [ ] **Step 1: Full clean-tree verification**

Run: `make up && make ps && make down && make smoke && git status --short`
Expected: every command exits 0; `git status` shows an empty working tree
(no smoke residue).

- [ ] **Step 2: Push and open the PR**

```bash
git push -u origin monorepo-layout
gh pr create --base main --title "Monorepo layout: Makefile-as-interface platform skeleton" --body "$(cat <<'EOF'
Implements the approved spec (docs/superpowers/specs/2026-07-18-monorepo-layout-design.md):

- Root Makefile as the platform's whole interface: up / down / ps / logs / deploy, plus maintainer smoke
- Discovery-based compose: services self-register by existing as services/<name>/compose.yaml — zero platform edits to add one
- services/_template + docs/adding-a-service.md: the <15-minute fourth-service pathway, mechanically proven by make smoke
- docs/design.md (platform section), user-guide/runbook placeholders
- Spec + staff-eng review artifacts (SPEC-REVIEW.md, /spec-review command) from this branch's earlier commits

No services run yet — the empty platform is proven; services land in follow-up PRs.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed.
