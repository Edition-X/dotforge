# MacBook Pro Configuration

An Ansible-based configuration management system for MacBook Pro setup.

## Structure

The configuration is organized into roles:

- **common**: Creates required directories
- **ssh**: Manages SSH keys and configuration
- **dotfiles**: Manages shell config files (.zshrc, .aliases, etc.)
- **neovim**: Configures Neovim editor
- **tmux**: Sets up tmux configuration
- **cleanup**: Removes managed files (used for uninstallation)

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
```

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