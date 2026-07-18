# The platform's entire interface. The team never types `docker compose`.
#
#   make up            bring the whole platform up, built and running
#   make down          tear it all down
#   make ps            what's running, health, published ports
#   make logs [S=api]  follow logs, last 100 + live (all services, or one)
#   make errors [S=api] follow only error/exception lines
#   make deploy S=api  rebuild + restart ONE service
#   make smoke         (maintainer) prove the add-a-service pathway end-to-end
#   make check         run the convention gate (same entrypoint CI will use)
#   make hooks         route git hooks through .githooks (pre-commit runs the gate)
#
# Services are discovered, never registered: every services/*/compose.yaml
# is part of the platform (underscore-prefixed dirs like _template excluded).

COMPOSE_FRAGMENTS := $(filter-out services/_%,$(wildcard services/*/compose.yaml))
COMPOSE := docker compose --project-directory . \
  -f platform/compose.base.yaml \
  $(foreach f,$(COMPOSE_FRAGMENTS),-f $(f))

.PHONY: up down ps logs errors deploy smoke check hooks

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

deploy:
ifndef S
	$(error usage: make deploy S=<service>)
endif
	$(COMPOSE) up -d --build $(S)
	@$(COMPOSE) ps $(S)

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
	mkdir -p services/smoke-test
	cp services/_template/Dockerfile services/smoke-test/Dockerfile
	sed 's/_template/smoke-test/g' services/_template/compose.yaml > services/smoke-test/compose.yaml
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
