# The interpreter the venv is built from. `python3` is not a contract: on this
# machine it resolves to a pyenv shim on 3.10, which cannot install the pinned
# ansible-core at all — the venv was only ever 3.13 by accident of PATH.
# Override for a different minor: make PYTHON=python3.14 venv
PYTHON                     ?= python3.13
PYTHON_MINIMUM             := 3.12
PYTHON_VIRTUAL_ENVIRONMENT := venv
PYTHON_REQUIREMENTS_FILE   := requirements.txt
PYTHON_LOCK_FILE           := requirements.lock
ANSIBLE_REQUIREMENTS_FILE  := requirements.yml
ANSIBLE_PLAYBOOK_FILE      := site.yml
ANSIBLE_INVENTORY_FILE     := inventory
ANSIBLE_LIMIT              := local

# `make` with no argument prints what is available. There are around thirty
# targets and no way to discover them short of reading this file.
.DEFAULT_GOAL := help

.PHONY: help
help:
	@awk 'BEGIN {FS = ":.*##"; print "Targets:\n"} \
	  /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 } \
	  /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)

# Plain variable, not a `call` macro: GNU make splits macro arguments on
# commas, so `$(call activate, cmd --flag a,b)` would silently lose everything
# after the comma.
VENV = . $(PYTHON_VIRTUAL_ENVIRONMENT)/bin/activate &&
PLAYBOOK = ansible-playbook -i $(ANSIBLE_INVENTORY_FILE) -l $(ANSIBLE_LIMIT) $(ANSIBLE_PLAYBOOK_FILE)

# Installs the hash-pinned lock, not the loose requirements file, so two
# clones resolve to the same toolchain. Regenerate the lock with `make lock`
# after changing requirements.txt.
$(PYTHON_VIRTUAL_ENVIRONMENT): $(PYTHON_LOCK_FILE) $(ANSIBLE_REQUIREMENTS_FILE)
	@$(PYTHON) -c 'import sys; minimum = tuple(int(p) for p in "$(PYTHON_MINIMUM)".split(".")); \
	  sys.exit(0) if sys.version_info[:2] >= minimum else sys.exit( \
	  print(f"$(PYTHON) is {sys.version.split()[0]}, need >= $(PYTHON_MINIMUM)") or 1)'
	@$(PYTHON) -m venv $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(VENV) pip install --upgrade pip
	@$(VENV) pip install --require-hashes -r $(PYTHON_LOCK_FILE)
	@$(MAKE) collections
	@touch $(PYTHON_VIRTUAL_ENVIRONMENT)

# Collections install into one place. ansible.cfg points collections_path here,
# and installing ansible-core rather than the `ansible` bundle means no second
# copy of community.general competes with the pinned one.
.PHONY: collections
collections:  ## Install Ansible collections
	@$(VENV) ansible-galaxy collection install -r $(ANSIBLE_REQUIREMENTS_FILE) -p collections --force

.PHONY: lock
lock:  ## Regenerate requirements.lock
	@uv pip compile --universal --generate-hashes $(PYTHON_REQUIREMENTS_FILE) -o $(PYTHON_LOCK_FILE)

.PHONY: apply
apply: $(PYTHON_VIRTUAL_ENVIRONMENT)  ## Apply every role to this machine
	@$(VENV) $(PLAYBOOK) --skip-tags cleanup

.PHONY: delete
delete: $(PYTHON_VIRTUAL_ENVIRONMENT)  ## Remove repo-managed configuration
	@$(VENV) $(PLAYBOOK) --tags cleanup -e "cleanup=true"

.PHONY: check
check: $(PYTHON_VIRTUAL_ENVIRONMENT)  ## Dry run: show what apply would change
	@$(VENV) ansible-playbook -i $(ANSIBLE_INVENTORY_FILE) -l $(ANSIBLE_LIMIT) --check $(ANSIBLE_PLAYBOOK_FILE) $(RUN_ARGS)

# Role-specific targets. One pattern rule rather than a dozen copies of the
# same line — adding a role meant copy-pasting a 100-character invocation, and
# a typo in any copy was invisible.
ROLE_TARGETS := ai dotfiles mcp neovim packages ssh tmux
.PHONY: $(ROLE_TARGETS)
$(ROLE_TARGETS): $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(VENV) $(PLAYBOOK) --tags $@ $(RUN_ARGS)






# Docker MCP Toolkit: profile, secrets, features and the Grafana tool
# allowlist for the shared `sunrise` gateway. mcp-test (gateway smoke test)
# arrives in M2 alongside the launchd service it exercises.
# Gateway smoke test: initialize, tools/list, and one read-only call per
# server against the running launchd-managed gateway (make mcp starts it).
.PHONY: mcp-test
mcp-test:  ## MCP gateway smoke test
	@./scripts/mcp-gateway-smoke.sh


# Browsers are managed by hand. The role is gated off in site.yml
# (browsers_managed: false) and these two targets refuse rather than silently
# running a play that skips every task. The catalogs, scripts and offline
# fixture tests below are kept for reference and still run under `make ci`;
# none of them installs anything.
.PHONY: browsers browsers-authorize
browsers browsers-authorize:  ## Disabled: browsers are managed by hand
	@echo "browsers: disabled - managed by hand (browsers_managed=false in group_vars/macbooks.yml)"; exit 1

.PHONY: validate-browser-catalog
validate-browser-catalog: $(PYTHON_VIRTUAL_ENVIRONMENT)  ## Validate browser catalog schemas
	@$(VENV) python scripts/validate-browser-catalog.py --all

.PHONY: browser-test
browser-test: $(PYTHON_VIRTUAL_ENVIRONMENT)  ## Browser smokes (needs real browsers)
	@$(VENV) python scripts/browser-smoke.py $(RUN_ARGS)

.PHONY: browser-drift
browser-drift: validate-browser-catalog  ## Bookmark additions-only comparison
	@$(VENV) python scripts/browser-capture.py --dry-run --isolated
	@$(VENV) python scripts/browser-git-automation.py --check --isolated-root "$(HOME)/.local/state"
	@$(VENV) python scripts/check-browser-privacy.py --all
	@echo "browser drift: additions-only comparison complete"

.PHONY: browser-capture
browser-capture: $(PYTHON_VIRTUAL_ENVIRONMENT)  ## Capture bookmark additions
	@$(VENV) python scripts/browser-capture.py $(RUN_ARGS)

# Publishing side of capture: isolated clone, private-repo recheck, one PR with
# auto-merge. `--check` is a contract audit with no network and no clone.
.PHONY: browser-automation
browser-automation: $(PYTHON_VIRTUAL_ENVIRONMENT)  ## Publishing contract check or run
	@$(VENV) python scripts/browser-git-automation.py $(RUN_ARGS)

# Install packages AND upgrade any that are outdated. Kept separate from
# `apply` so a routine apply never moves versions underneath you.
.PHONY: upgrade
upgrade: $(PYTHON_VIRTUAL_ENVIRONMENT)  ## Install and upgrade packages
	@$(VENV) $(PLAYBOOK) --tags packages -e "brew_upgrade=true"

# Package drift, straight from brew with no Ansible in the way, plus the
# advisory agent-config/MCP-gateway drift checker (harness links, gateway
# health, profile export, secrets, oauth, harness wiring).
.PHONY: drift
drift:  ## Report package and agent-config drift
	@brew bundle check --file=Brewfile --verbose --no-upgrade
	@./scripts/check-agent-config-drift.sh

# Rewrite the Brewfile from what is actually installed. Review the diff before
# committing — dump loses the grouping comments.
.PHONY: dump
dump:  ## Rewrite the Brewfile from what is installed
	@brew bundle dump --file=Brewfile --describe --no-vscode --force
	@git --no-pager diff --stat Brewfile

# Validation targets

# Non-Ansible twin of roles/ai_agents/tasks/routing.yml: fails fast on a
# malformed canonical routing source before any harness renders against it.
.PHONY: validate-agent-routing
validate-agent-routing: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(VENV) ./scripts/validate-agent-routing.py

# Every static check lives in .pre-commit-config.yaml and `make lint` runs that
# file, so a local pass and a CI pass mean the same thing. This target used to
# list a hand-picked subset (ansible-lint, yamllint, skills, routing) while CI
# ran pre-commit instead — two definitions of "lint" that had already drifted.
.PHONY: lint
lint: $(PYTHON_VIRTUAL_ENVIRONMENT)  ## Static checks (every pre-commit hook)
	@$(VENV) pre-commit run --all-files

.PHONY: setup-git-hooks
setup-git-hooks: $(PYTHON_VIRTUAL_ENVIRONMENT)  ## Install the git hooks
	@$(VENV) pip install pre-commit
	@$(VENV) pre-commit install

.PHONY: pre-commit
pre-commit: $(PYTHON_VIRTUAL_ENVIRONMENT)  ## Run pre-commit over all files
	@$(VENV) pre-commit run --all-files

# The single definition of "CI". .github/workflows/ci.yml runs exactly this, so
# the two cannot drift: anything added here is picked up there for free.
# A second copy of a collection makes resolution depend on path order, which
# is how the pinned 10.5.0 ended up shadowed by a bundled 10.4.0.
.PHONY: check-collections
check-collections: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(VENV) ansible-galaxy collection list community.general 2>/dev/null \
	  | grep -c 'community.general' \
	  | xargs -I{} sh -c 'test {} -eq 1 || { echo "community.general resolves to {} copies"; exit 1; }'
	@echo "collections: one community.general"

.PHONY: ci
ci: lint check-collections test  ## Everything CI runs, locally
	@$(VENV) ansible-playbook site.yml --syntax-check
	@echo "CI checks passed!"

.PHONY: validate-opencode
validate-opencode: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(VENV) ./scripts/test-ai-agents-idempotency.sh --validate-only

.PHONY: test-ai-agents
test-ai-agents: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(VENV) ./scripts/test-ai-agents-idempotency.sh
	@$(VENV) ./scripts/test-codex-agent-settings-sync.sh

# Everything offline and machine-independent. This is what CI can run, and it
# is the whole of what `make ci` tests.
.PHONY: test
test: test-scout test-bridge test-review-pr-feedback test-ai-agents test-browser-fixtures  ## Offline tests

# Offline checks for the Claude -> OpenCode bridge (oc-ticket against a fake
# opencode), the work-profile edit guard hook, and the usage report. No billed calls.
.PHONY: test-bridge
test-bridge: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(VENV) python scripts/test-oc-ticket.py
	@$(VENV) python scripts/test-claude-edit-guard.py
	@$(VENV) python scripts/test-claude-dispatch-guard.py
	@$(VENV) python scripts/test-harness-usage-report.py

# Offline scout evidence checks. No billed calls.
.PHONY: test-scout
test-scout: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(VENV) python scripts/test-scout-usage-report.py
	@$(VENV) python scripts/test-scout-routing-evidence.py

# Offline checks for the read-only PR review skill: line verification, head-SHA
# pinning and the read-only gh contract, against a fake gh. No billed calls.
.PHONY: test-review-pr-feedback
test-review-pr-feedback: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(VENV) python host_files/localhost/ai/skills/review-pr-feedback/scripts/test_verify_lines.py

# Browser checks that need no browser: schema, reconciliation fixtures and the
# publishing contract against fake remotes. The evidence that needs real
# installed browsers, isolated profiles and a GUI session lives in
# `make browser-test`, which a hosted runner cannot execute.
.PHONY: test-browser-fixtures
test-browser-fixtures: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(VENV) python scripts/validate-browser-catalog.py --all
	@$(VENV) python scripts/browser-capture.py --fixtures tests/fixtures/browsers --check-only
	@$(VENV) python scripts/browser-reconcile.py --fixtures tests/fixtures/browsers --additions-only --check-only
	@$(VENV) python scripts/browser-automation-smoke.py --fake --no-network
	@$(VENV) python scripts/browser-git-automation.py --check --isolated-root "$(HOME)/.local/state"
	@$(VENV) python scripts/check-browser-privacy.py --all

.PHONY: clean
# `trash`, not `rm -rf`: AGENTS.md asks for recoverable removal, and this
# target used to be the one place in the repo that ignored it.
clean:  ## Remove the virtualenv
	@test ! -d $(PYTHON_VIRTUAL_ENVIRONMENT) || trash $(PYTHON_VIRTUAL_ENVIRONMENT)
