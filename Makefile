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

.DEFAULT_GOAL := $(PYTHON_VIRTUAL_ENVIRONMENT)

define activate
	(. $(PYTHON_VIRTUAL_ENVIRONMENT)/bin/activate && $1;)
endef

# Installs the hash-pinned lock, not the loose requirements file, so two
# clones resolve to the same toolchain. Regenerate the lock with `make lock`
# after changing requirements.txt.
$(PYTHON_VIRTUAL_ENVIRONMENT): $(PYTHON_LOCK_FILE) $(ANSIBLE_REQUIREMENTS_FILE)
	@$(PYTHON) -c 'import sys; minimum = tuple(int(p) for p in "$(PYTHON_MINIMUM)".split(".")); \
	  sys.exit(0) if sys.version_info[:2] >= minimum else sys.exit( \
	  print(f"$(PYTHON) is {sys.version.split()[0]}, need >= $(PYTHON_MINIMUM)") or 1)'
	@$(PYTHON) -m venv $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, pip install --upgrade pip)
	@$(call activate, pip install --require-hashes -r $(PYTHON_LOCK_FILE))
	@$(MAKE) collections
	@touch $(PYTHON_VIRTUAL_ENVIRONMENT)

# Collections install into one place. ansible.cfg points collections_path here,
# and installing ansible-core rather than the `ansible` bundle means no second
# copy of community.general competes with the pinned one.
.PHONY: collections
collections:
	@$(call activate, ansible-galaxy collection install -r $(ANSIBLE_REQUIREMENTS_FILE) -p collections --force)

.PHONY: lock
lock:
	@uv pip compile --universal --generate-hashes $(PYTHON_REQUIREMENTS_FILE) -o $(PYTHON_LOCK_FILE)

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

.PHONY: browsers
browsers: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ansible-playbook -i $(ANSIBLE_INVENTORY_FILE) -l $(ANSIBLE_LIMIT) $(ANSIBLE_PLAYBOOK_FILE) --tags browsers $(RUN_ARGS))

# One-time, interactive: installs the root-owned policy helper and a NOPASSWD
# rule scoped to it, so every later apply — and the capture service — installs
# managed preferences without a dialog. Asks for an administrator password once.
.PHONY: browsers-authorize
browsers-authorize: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ansible-playbook -i $(ANSIBLE_INVENTORY_FILE) -l $(ANSIBLE_LIMIT) $(ANSIBLE_PLAYBOOK_FILE) --tags browsers -e browsers_authorize=true)

.PHONY: validate-browser-catalog
validate-browser-catalog: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, python scripts/validate-browser-catalog.py --all)

.PHONY: browser-test
browser-test: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, python scripts/browser-smoke.py $(RUN_ARGS))

.PHONY: browser-drift
browser-drift: validate-browser-catalog
	@$(call activate, python scripts/browser-capture.py --dry-run --isolated)
	@$(call activate, python scripts/browser-git-automation.py --check --isolated-root "$(HOME)/.local/state")
	@$(call activate, python scripts/check-browser-privacy.py --all)
	@echo "browser drift: additions-only comparison complete"

.PHONY: browser-capture
browser-capture: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, python scripts/browser-capture.py $(RUN_ARGS))

# Publishing side of capture: isolated clone, private-repo recheck, one PR with
# auto-merge. `--check` is a contract audit with no network and no clone.
.PHONY: browser-automation
browser-automation: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, python scripts/browser-git-automation.py $(RUN_ARGS))

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

# Every static check lives in .pre-commit-config.yaml and `make lint` runs that
# file, so a local pass and a CI pass mean the same thing. This target used to
# list a hand-picked subset (ansible-lint, yamllint, skills, routing) while CI
# ran pre-commit instead — two definitions of "lint" that had already drifted.
.PHONY: lint
lint: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, pre-commit run --all-files)

.PHONY: setup-git-hooks
setup-git-hooks: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, pip install pre-commit)
	@$(call activate, pre-commit install)

.PHONY: pre-commit
pre-commit: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, pre-commit run --all-files)

# The single definition of "CI". .github/workflows/ci.yml runs exactly this, so
# the two cannot drift: anything added here is picked up there for free.
# A second copy of a collection makes resolution depend on path order, which
# is how the pinned 10.5.0 ended up shadowed by a bundled 10.4.0.
.PHONY: check-collections
check-collections: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ansible-galaxy collection list community.general 2>/dev/null \
	  | grep -c 'community.general' \
	  | xargs -I{} sh -c 'test {} -eq 1 || { echo "community.general resolves to {} copies"; exit 1; }')
	@echo "collections: one community.general"

.PHONY: ci
ci: lint check-collections test
	@$(call activate, ansible-playbook site.yml --syntax-check)
	@echo "CI checks passed!"

.PHONY: validate-opencode
validate-opencode: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ./scripts/test-ai-agents-idempotency.sh --validate-only)

.PHONY: test-ai-agents
test-ai-agents: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ./scripts/test-ai-agents-idempotency.sh)
	@$(call activate, ./scripts/test-codex-agent-settings-sync.sh)

# Everything offline and machine-independent. This is what CI can run, and it
# is the whole of what `make ci` tests.
.PHONY: test
test: test-scout test-review-pr-feedback test-ai-agents test-browser-fixtures

# Offline scout evidence checks. No billed calls.
.PHONY: test-scout
test-scout: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, python scripts/test-scout-usage-report.py)
	@$(call activate, python scripts/test-scout-routing-evidence.py)

# Offline checks for the read-only PR review skill: line verification, head-SHA
# pinning and the read-only gh contract, against a fake gh. No billed calls.
.PHONY: test-review-pr-feedback
test-review-pr-feedback: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, python host_files/localhost/ai/skills/review-pr-feedback/scripts/test_verify_lines.py)

# Browser checks that need no browser: schema, reconciliation fixtures and the
# publishing contract against fake remotes. The evidence that needs real
# installed browsers, isolated profiles and a GUI session lives in
# `make browser-test`, which a hosted runner cannot execute.
.PHONY: test-browser-fixtures
test-browser-fixtures: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, python scripts/validate-browser-catalog.py --all)
	@$(call activate, python scripts/browser-capture.py --fixtures tests/fixtures/browsers --check-only)
	@$(call activate, python scripts/browser-reconcile.py --fixtures tests/fixtures/browsers --additions-only --check-only)
	@$(call activate, python scripts/browser-automation-smoke.py --fake --no-network)
	@$(call activate, python scripts/browser-git-automation.py --check --isolated-root "$(HOME)/.local/state")
	@$(call activate, python scripts/check-browser-privacy.py --all)

.PHONY: clean
clean:
	-@rm -rf $(PYTHON_VIRTUAL_ENVIRONMENT)
