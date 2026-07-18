# The platform's entire interface. The team never types `docker compose`.
#
#   make up            bring the whole platform up, built and running
#   make down          tear it all down
#   make ps            what's running, health, published ports
#   make logs [S=api]  follow logs (all services, or one)
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

.PHONY: up down ps logs deploy smoke check hooks

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

check: ## Run the convention gate (same entrypoint CI will use)
	./checks/gate.sh

hooks: ## Route git hooks through .githooks (pre-commit runs the gate)
	git config core.hooksPath .githooks
