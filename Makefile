.PHONY: check hooks

check: ## Run the convention gate (same entrypoint CI will use)
	./checks/gate.sh

hooks: ## Route git hooks through .githooks (pre-commit runs the gate)
	git config core.hooksPath .githooks
