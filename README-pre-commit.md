# Pre-commit Configuration for Ansible Projects

This repository uses pre-commit hooks to ensure code quality and consistency. The configuration is set up to work with Ansible projects, including playbooks with encrypted vault files.

## Initial Setup

1. Install pre-commit:
   ```bash
   pip install pre-commit
   ```

2. Install the hooks in your local repository:
   ```bash
   pre-commit install
   ```

## Running Pre-commit

There are two ways to run the pre-commit hooks:

1. **Standard way** - Will run all hooks including ansible-lint:
   ```bash
   ./pre-commit-run.sh run --all-files
   ```

2. **During commits** - Pre-commit hooks will run automatically when you commit.

## Handling Vault Files and Ansible Linting

The configuration excludes vault files from ansible-lint checks. The `pre-commit-run.sh` script sets environment variables to help ansible-lint handle vault files without needing the actual vault password.

If you need to bypass ansible-lint during a commit, you can use:
```bash
SKIP=ansible-lint git commit -m "Your commit message"
```

## Custom Configuration Files

- `.pre-commit-config.yaml` - Main pre-commit configuration
- `.ansible-lint` - Settings for ansible-lint
- `.yamllint` - Settings for YAML linting
- `.pre-commit-config-skip.yaml` - Patterns for files to exclude from checks

## Common Issues and Solutions

1. **Ansible-lint failing on vault files**:
   - Check that your vault files match the exclusion pattern in `.ansible-lint`
   - Use the `pre-commit-run.sh` script to set proper environment variables

2. **YAML linting issues in third-party files**:
   - The configuration excludes files in `host_files/localhost/nvim/autoload/plugged/` and `collections/`
   - If needed, add additional patterns to `.pre-commit-config-skip.yaml` 