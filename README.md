# MacBook Pro Configuration

An Ansible-based configuration management system for MacBook Pro setup.

## Structure

The configuration is organized into roles:

- **common**: Creates required directories
- **ssh**: Manages SSH keys and configuration
- **dotfiles**: Manages shell config files (.zshrc, .aliases, etc.)
- **neovim**: Configures Neovim editor
- **tmux**: Sets up tmux configuration
- **packages**: Manages Homebrew formulae, casks, and Python packages
- **cleanup**: Removes managed files (used for uninstallation)

## Inventory and Variables

The setup uses Ansible's inventory system:

- **inventory**: Contains host groups (local, work, personal)
- **group_vars/macbooks.yml**: Common variables for all MacBooks
- **host_vars/**: Host-specific variables (create files like hostname.yml)

## Usage

```bash
# Install configuration
make apply

# Check what would be changed (dry run)
make check

# Remove all managed configuration
make delete

# Clean up build environment
make clean

# Apply specific roles
make ssh        # SSH keys and config only
make dotfiles   # Shell config files only
make neovim     # Neovim config only
make tmux       # tmux config only
make packages   # Install packages only
```

## Code Validation

The repository uses pre-commit hooks to validate code quality:

```bash
# Set up git hooks (run once after cloning)
make setup-git-hooks

# Run pre-commit checks manually on all files
make pre-commit

# Run linting only
make lint
```

Pre-commit will automatically run these checks before each commit:
- YAML syntax validation
- Ansible playbook linting
- Trailing whitespace and EOF fixing
- Merge conflict detection

## For Different Hosts

To configure a different MacBook:

1. Add the host to the inventory file
2. Create host-specific files in host_files/hostname/
3. Optionally add host-specific variables in host_vars/hostname.yml
4. Run: `ANSIBLE_LIMIT=hostname make apply`

## Adding New Configuration

1. Choose the appropriate role or create a new one
2. Add tasks to the role's `tasks/main.yml` file
3. Add templates to the role's `templates/` directory
4. Add static files to the role's `files/` directory
5. Update the README.md to document the changes

## Requirements

- Python 3
- Ansible

## License

This project is privately maintained.
