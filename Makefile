# The platform's entire interface. The team never types `docker compose`.
#
#   make up            bring the whole platform up, built and running
#   make down          tear it all down
#   make ps            what's running, health, published ports
#   make logs [S=api]  follow logs, last 100 + live (all services, or one)
#   make errors [S=api] follow only error/exception lines
#   make stats [S=api]  poll a service's /stats once a second (Ctrl-C stops)
#   make deploy S=api  rebuild + restart ONE service
#   make new S=alerts  scaffold an empty service from the template
#   make smoke         (maintainer) prove the add-a-service pathway end-to-end
#   make check         run the convention gate (same entrypoint CI will use)
#   make hooks         route git hooks through .githooks (pre-commit runs the gate)
#   make help          print this list
#
# Services are discovered, never registered: every services/*/compose.yaml
# is part of the platform (underscore-prefixed dirs like _template excluded).

COMPOSE_FRAGMENTS := $(filter-out services/_%,$(wildcard services/*/compose.yaml))
COMPOSE := docker compose --project-directory . \
  -f platform/compose.base.yaml \
  $(foreach f,$(COMPOSE_FRAGMENTS),-f $(f))

.PHONY: up down ps logs errors stats deploy new smoke check hooks help

# The header comment above is the single source of truth for the verb list.
help:
	@sed -n 's/^#   //p' $(firstword $(MAKEFILE_LIST))

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
	$(COMPOSE) logs -f --tail=100 $(S)

# Just the bad news. BSD and GNU grep both support --line-buffered, so the
# follow stays live on macOS and Linux.
errors:
	$(COMPOSE) logs -f --tail=200 $(S) | grep --line-buffered -iE 'error|exception|traceback|panic|critical|fatal'

# Live platform health: the queue-depth/freshness surface the demo and
# runbook use. The address is discovered from the running container — the
# Makefile knows no ports (design.md: discovered, never declared).
stats:
	@svc=$${S:-api}; \
	addr=$$($(COMPOSE) ps --format json $$svc | python3 -c 'import json,sys; d=json.loads(sys.stdin.readline()); p=d["Publishers"][0]; print((p["URL"] or "127.0.0.1")+":"+str(p["PublishedPort"]))') || { echo "stats: $$svc not running (make up first)"; exit 1; }; \
	while :; do curl -s "http://$$addr/stats"; echo; sleep 1; done

deploy:
ifndef S
	$(error usage: make deploy S=<service>)
endif
	$(COMPOSE) up -d --build $(S)
	@$(COMPOSE) ps $(S)

# Scaffold an empty service from services/_template: copy the Dockerfile,
# rewrite the service name + build context in compose.yaml. The name guard
# (a lowercase DNS label — the name doubles as the service's DNS alias on
# the compose network) also keeps sed's replacement literal and bars the
# leading _ that would hide it from discovery. `make smoke` deploys through
# this same path.
new:
ifndef S
	$(error usage: make new S=<service-name>)
endif
	@case "$(S)" in ""|[!a-z]*|*[!a-z0-9-]*|*-) \
	  echo "new: invalid name '$(S)' — lowercase letters, digits, hyphens; start with a letter, end with a letter or digit"; exit 1;; \
	esac
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

check: ## Run the convention gate (same entrypoint CI will use)
	./checks/gate.sh

hooks: ## Route git hooks through .githooks (pre-commit runs the gate)
	git config core.hooksPath .githooks

# Maintainer check: proves a copied template deploys healthy with zero
# platform edits, then cleans up. Keeps the <15-minute add-a-service claim
# and the service contract (name match, healthcheck) continuously true.
# POSIX-only recipe (no `sed -i`, no `timeout`) — must run on stock macOS
# and Linux alike.
smoke:
	rm -rf services/smoke-test
	$(MAKE) new S=smoke-test
	$(MAKE) up
	i=0; until [ "$$(docker inspect -f '{{.State.Health.Status}}' perfmon-smoke-test-1 2>/dev/null)" = "healthy" ]; do \
	  i=$$((i+1)); \
	  if [ "$$i" -ge 30 ]; then \
	    echo "smoke: FAIL — service never became healthy"; \
	    $(MAKE) down; rm -rf services/smoke-test; exit 1; \
	  fi; \
	  sleep 2; \
	done
	$(MAKE) down
	rm -rf services/smoke-test
	@echo "smoke: PASS — template deployed healthy, tore down clean"
