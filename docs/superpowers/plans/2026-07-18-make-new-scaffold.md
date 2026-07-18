# `make new` Service Scaffold — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a guarded `make new S=<name>` verb that scaffolds an empty service from `services/_template`, refactor `make smoke` to reuse it, and update the docs.

**Architecture:** One inline POSIX-sh recipe in the root Makefile (the platform's entire interface — no new script files). `smoke` becomes a consumer of `new`, so the scaffold path is re-proven on every smoke run. Spec: [2026-07-18-make-new-scaffold-design.md](../specs/2026-07-18-make-new-scaffold-design.md).

**Tech Stack:** GNU/Apple make 3.81-compatible Makefile, POSIX sh only (`expr` BRE for name validation — a `case` glob cannot express the character set). Verification is by running commands, not a test framework — there is none for Makefiles here; each task lists exact commands with expected output.

**Review nits carried in:** `make new`'s next-steps output printing during `make smoke` is accepted noise — do NOT add machinery to suppress it.

---

### Task 1: The `new` target

**Files:**
- Modify: `Makefile` (header comment, `.PHONY`, new target after `deploy`)

- [ ] **Step 1: Establish the failing check**

Run: `make new S=demo-x`
Expected: `make: *** No rule to make target 'new'.  Stop.`

- [ ] **Step 2: Add the verb to the header comment**

In the Makefile header block, insert a line between the `deploy` and `smoke` lines:

```make
#   make deploy S=api  rebuild + restart ONE service
#   make new S=alerts  scaffold an empty service from the template
#   make smoke         (maintainer) prove the add-a-service pathway end-to-end
```

- [ ] **Step 3: Add `new` to `.PHONY`**

```make
.PHONY: up down ps logs deploy new smoke check hooks
```

- [ ] **Step 4: Add the target**

Insert after the `deploy` target, before `check`. Note `$$` (make-escaped `$`) in the `expr` pattern, and that guard order matches the spec: S unset → invalid name → already exists.

```make
# Scaffold an empty service from services/_template: copy the Dockerfile,
# rewrite the service name + build context in compose.yaml. The name guard
# (lowercase DNS-safe, no leading _) also keeps sed's replacement literal
# and the result discoverable. `make smoke` deploys through this same path.
new:
ifndef S
	$(error usage: make new S=<service-name>)
endif
	@expr "x$(S)" : 'x[a-z][a-z0-9-]*$$' >/dev/null || \
	  { echo "new: invalid name '$(S)' — lowercase letters, digits, hyphens; must start with a letter"; exit 1; }
	@test ! -e services/$(S) || \
	  { echo "new: services/$(S) already exists"; exit 1; }
	mkdir -p services/$(S)
	cp services/_template/Dockerfile services/$(S)/Dockerfile
	sed 's/_template/$(S)/g' services/_template/compose.yaml > services/$(S)/compose.yaml
	@echo "new: services/$(S) scaffolded. Next steps (docs/adding-a-service.md):"
	@echo "  1. replace services/$(S)/Dockerfile with your build"
	@echo "  2. make the healthcheck in services/$(S)/compose.yaml real"
	@echo "  3. if it listens: uncomment ports, pick a free host port (make ps)"
	@echo "  4. make deploy S=$(S)"
```

- [ ] **Step 5: Verify the guards**

Run each; every failure must leave no `services/` residue:

| Command | Expected |
|---|---|
| `make new` | `*** usage: make new S=<service-name>.  Stop.` |
| `make new S=Bad_Name` | `new: invalid name 'Bad_Name' — …` (exit ≠ 0) |
| `make new S=` | same invalid-name error (empty S is defined, so `ifndef` passes; the regex catches it) |
| `make new S=_hidden` | same invalid-name error |

- [ ] **Step 6: Verify the happy path**

```sh
make new S=demo-x
ls services/demo-x            # Dockerfile  compose.yaml
grep -c demo-x services/demo-x/compose.yaml   # ≥ 2 (service name + build context)
grep _template services/demo-x/compose.yaml   # no output
make new S=demo-x             # "new: services/demo-x already exists", exit ≠ 0
```

- [ ] **Step 7: Verify against a live deploy, then clean up**

Requires Docker. The template healthcheck is a placeholder, so the scaffold comes up healthy as-is:

```sh
make deploy S=demo-x          # builds and starts it; ps shows it
docker inspect -f '{{.State.Health.Status}}' perfmon-demo-x-1   # healthy (retry a few seconds)
make down
rm -rf services/demo-x
```

- [ ] **Step 8: Commit**

```sh
git add Makefile
git commit -m "Add make new S=<name>: scaffold a service from the template"
```

### Task 2: Smoke reuses the scaffold

**Files:**
- Modify: `Makefile` (`smoke` target)

- [ ] **Step 1: Replace smoke's inline copy/rename with the verb**

Change the first lines of the `smoke` recipe from:

```make
smoke:
	rm -rf services/smoke-test
	mkdir -p services/smoke-test
	cp services/_template/Dockerfile services/smoke-test/Dockerfile
	sed 's/_template/smoke-test/g' services/_template/compose.yaml > services/smoke-test/compose.yaml
	$(MAKE) up
```

to:

```make
smoke:
	rm -rf services/smoke-test
	$(MAKE) new S=smoke-test
	$(MAKE) up
```

The rest of the recipe (health-wait loop, teardown) is untouched. `new`'s next-steps output will print mid-smoke — accepted noise, leave it.

- [ ] **Step 2: Run the smoke test end-to-end**

Requires Docker.

Run: `make smoke`
Expected: `smoke: PASS — template deployed healthy, tore down clean`, and `services/smoke-test` no longer exists.

- [ ] **Step 3: Commit**

```sh
git add Makefile
git commit -m "make smoke: scaffold via make new, re-proving the pathway"
```

### Task 3: Docs

**Files:**
- Modify: `docs/adding-a-service.md` (steps 1–2)
- Modify: `docs/design.md` (Platform section)

- [ ] **Step 1: Collapse the manual copy/rename steps in adding-a-service.md**

Replace steps 1 and 2 of the worked example:

```markdown
1. **Copy the template** *(1 min)*
   `cp -r services/_template services/alerts`
2. **Edit `services/alerts/compose.yaml`** *(3 min)* — three changes:
   the service name `_template` → `alerts` (must match the directory name),
   the build context `./services/_template` → `./services/alerts`, and — if
   the service listens — uncomment `ports` and pick a host port nothing else
   publishes (`make ps` shows what's taken; the service owns its port, there
   is no central registry).
```

with:

```markdown
1. **Scaffold it** *(1 min)*
   `make new S=alerts` — copies the template and renames it (compose
   service name and build context both match the directory automatically).
2. **Pick a port, if it listens** *(2 min)* — in
   `services/alerts/compose.yaml`, uncomment `ports` and pick a host port
   nothing else publishes (`make ps` shows what's taken; the service owns
   its port, there is no central registry).
```

Update the total line to match: `Total: ~13 minutes. Platform files touched: **none**.`

Also update the closing maintainer line to name the reuse:

```markdown
Maintainers: `make smoke` mechanically re-proves this pathway (scaffolds
via `make new`, deploys it, waits for healthy, tears down).
```

- [ ] **Step 2: One sentence in design.md's Platform section**

In `docs/design.md`, update the Platform **Shape** paragraph's first sentences from:

```markdown
**Shape:** a root Makefile fronting Docker Compose. Five team verbs
(`up/down/ps/logs/deploy`) plus maintainer `smoke`.
```

to:

```markdown
**Shape:** a root Makefile fronting Docker Compose. Six team verbs
(`up/down/ps/logs/deploy/new`) plus maintainer `smoke`; `new` scaffolds a
service from the template, and `smoke` deploys through that same scaffold,
so the pathway is re-proven on every smoke run.
```

- [ ] **Step 3: Run the convention gate**

Run: `make check`
Expected: `conventions: all checks passed`

- [ ] **Step 4: Commit**

```sh
git add docs/adding-a-service.md docs/design.md
git commit -m "Docs: adding-a-service starts at make new; design.md notes the verb"
```

### Task 4: Final verification (spec "Done when")

- [ ] **Step 1: Re-run the spec's done-list**

```sh
make new S=demo-x && make deploy S=demo-x    # comes up; healthy per docker inspect
make new S=demo-x                            # fails cleanly, directory untouched
make down && rm -rf services/demo-x
make new                                     # usage error
make new S=Bad_Name                          # invalid-name error
make smoke                                   # PASS via the scaffold path
make check                                   # all checks passed
```

- [ ] **Step 2: Push and open the PR**

```sh
git push -u origin make-new-scaffold
gh pr create --title "make new S=<name>: scaffold a service from the template" \
  --body "Implements docs/superpowers/specs/2026-07-18-make-new-scaffold-design.md (spec-reviewed: Approve). make smoke now deploys through the scaffold, keeping the <15-min pathway continuously proven. Relates to #8.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```
