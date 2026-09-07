PYTHON_VIRTUAL_ENVIRONMENT := venv
PYTHON_REQUIREMENTS_FILE   := requirements.txt
ANSIBLE_PLAYBOOK_FILE      := site.yml
ANSIBLE_INVENTORY_FILE     := inventory
ANSIBLE_LIMIT              := local

.DEFAULT_GOAL := $(PYTHON_VIRTUAL_ENVIRONMENT)

define activate
	(. $(PYTHON_VIRTUAL_ENVIRONMENT)/bin/activate && unset ANSIBLE_VAULT_PASSWORD_FILE && $1;)
endef

$(PYTHON_VIRTUAL_ENVIRONMENT): $(PYTHON_REQUIREMENTS_FILE)
	@python3 -m venv $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, pip install --upgrade pip)
	@$(call activate, pip install wheel)
	@$(call activate, pip install -r $(PYTHON_REQUIREMENTS_FILE))

.PHONY: apply
apply: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ansible-playbook -i $(ANSIBLE_INVENTORY_FILE) -l $(ANSIBLE_LIMIT) $(ANSIBLE_PLAYBOOK_FILE) --skip-tags cleanup)

.PHONY: delete
delete: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ansible-playbook -i $(ANSIBLE_INVENTORY_FILE) -l $(ANSIBLE_LIMIT) $(ANSIBLE_PLAYBOOK_FILE) --tags cleanup -e "cleanup=true")

.PHONY: check
check: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ansible-playbook -i $(ANSIBLE_INVENTORY_FILE) -l $(ANSIBLE_LIMIT) --check $(ANSIBLE_PLAYBOOK_FILE) $(RUN_ARGS))

# Role-specific targets
.PHONY: ssh
ssh: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ansible-playbook -i $(ANSIBLE_INVENTORY_FILE) -l $(ANSIBLE_LIMIT) $(ANSIBLE_PLAYBOOK_FILE) --tags ssh)

.PHONY: dotfiles
dotfiles: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ansible-playbook -i $(ANSIBLE_INVENTORY_FILE) -l $(ANSIBLE_LIMIT) $(ANSIBLE_PLAYBOOK_FILE) --tags dotfiles)

.PHONY: neovim
neovim: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ansible-playbook -i $(ANSIBLE_INVENTORY_FILE) -l $(ANSIBLE_LIMIT) $(ANSIBLE_PLAYBOOK_FILE) --tags neovim)

.PHONY: tmux
tmux: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ansible-playbook -i $(ANSIBLE_INVENTORY_FILE) -l $(ANSIBLE_LIMIT) $(ANSIBLE_PLAYBOOK_FILE) --tags tmux)

.PHONY: ai
ai: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ansible-playbook -i $(ANSIBLE_INVENTORY_FILE) -l $(ANSIBLE_LIMIT) $(ANSIBLE_PLAYBOOK_FILE) --tags ai)

# Docker MCP Toolkit: profile, secrets, features and the Grafana tool
# allowlist for the shared `sunrise` gateway. mcp-test (gateway smoke test)
# arrives in M2 alongside the launchd service it exercises.
.PHONY: mcp
mcp: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ansible-playbook -i $(ANSIBLE_INVENTORY_FILE) -l $(ANSIBLE_LIMIT) $(ANSIBLE_PLAYBOOK_FILE) --tags mcp $(RUN_ARGS))

# Gateway smoke test: initialize, tools/list, and one read-only call per
# server against the running launchd-managed gateway (make mcp starts it).
.PHONY: mcp-test
mcp-test:
	@./scripts/mcp-gateway-smoke.sh

.PHONY: packages
packages: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ansible-playbook -i $(ANSIBLE_INVENTORY_FILE) -l $(ANSIBLE_LIMIT) $(ANSIBLE_PLAYBOOK_FILE) --tags packages)

# Install packages AND upgrade any that are outdated. Kept separate from
# `apply` so a routine apply never moves versions underneath you.
.PHONY: upgrade
upgrade: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ansible-playbook -i $(ANSIBLE_INVENTORY_FILE) -l $(ANSIBLE_LIMIT) $(ANSIBLE_PLAYBOOK_FILE) --tags packages -e "brew_upgrade=true")

# Package drift, straight from brew with no Ansible in the way, plus the
# advisory agent-config/MCP-gateway drift checker (harness links, gateway
# health, profile export, secrets, oauth, harness wiring).
.PHONY: drift
drift:
	@brew bundle check --file=Brewfile --verbose --no-upgrade || true
	@./scripts/check-agent-config-drift.sh

# Rewrite the Brewfile from what is actually installed. Review the diff before
# committing — dump loses the grouping comments.
.PHONY: dump
dump:
	@brew bundle dump --file=Brewfile --describe --no-vscode --force
	@git --no-pager diff --stat Brewfile

# Validation targets

# Non-Ansible twin of roles/ai_agents/tasks/routing.yml: fails fast on a
# malformed canonical routing source before any harness renders against it.
.PHONY: validate-agent-routing
validate-agent-routing: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ./scripts/validate-agent-routing.py)

.PHONY: lint
lint: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(MAKE) validate-agent-routing
	@$(call activate, ansible-lint)
	@$(call activate, yamllint .)
	@./scripts/check-skills.sh

.PHONY: setup-git-hooks
setup-git-hooks: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, pip install pre-commit)
	@$(call activate, pre-commit install)

.PHONY: pre-commit
pre-commit: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, pre-commit run --all-files)

.PHONY: ci
ci: lint
	@$(call activate, ansible-playbook site.yml --syntax-check)
	@echo "CI checks passed!"

.PHONY: validate-opencode
validate-opencode: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ansible-playbook -i $(ANSIBLE_INVENTORY_FILE) -l $(ANSIBLE_LIMIT) --check $(ANSIBLE_PLAYBOOK_FILE) --tags ai -e '{"ai_external_skills":[]}')
	@if [ -f "$$HOME/.config/opencode/opencode.jsonc" ] && [ -f "$$HOME/.config/opencode/agents/orchestrator.md" ]; then ./scripts/validate-opencode-config.sh --config-dir "$$HOME/.config/opencode"; else echo "live OpenCode tree not installed; staged validation passed"; fi

.PHONY: test-ai-agents
test-ai-agents: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ./scripts/test-ai-agents-idempotency.sh)
	@$(call activate, ./scripts/test-codex-agent-settings-sync.sh)

.PHONY: clean
clean:
	-@rm -rf $(PYTHON_VIRTUAL_ENVIRONMENT)
