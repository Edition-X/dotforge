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

.PHONY: packages
packages: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ansible-playbook -i $(ANSIBLE_INVENTORY_FILE) -l $(ANSIBLE_LIMIT) $(ANSIBLE_PLAYBOOK_FILE) --tags packages)

# Validation targets
.PHONY: lint
lint: $(PYTHON_VIRTUAL_ENVIRONMENT)
	@$(call activate, ansible-lint)
	@$(call activate, yamllint .)

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

.PHONY: clean
clean:
	-@rm -rf $(PYTHON_VIRTUAL_ENVIRONMENT)
