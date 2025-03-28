# 🚀 MacBook Pro Configuration

<div align="center">

[![Python](https://img.shields.io/badge/python-3.x-blue.svg)](https://www.python.org/)
[![Ansible](https://img.shields.io/badge/ansible-latest-red.svg)](https://www.ansible.com/)
[![License](https://img.shields.io/badge/license-private-black.svg)](LICENSE)
[![Maintenance](https://img.shields.io/badge/maintained-yes-green.svg)](https://github.com/yourusername/macbook-pro/commits/main)

A powerful, automated configuration management system for MacBook Pro setup using Ansible.

[Features](#features) • [Quick Start](#quick-start) • [Documentation](#documentation)

</div>

## ✨ Features

- 🔧 **Automated Setup**: One-command configuration for your entire MacBook
- 🛠️ **Modular Design**: Organized into specialized roles for easy maintenance
- 🔄 **Idempotent**: Safe to run multiple times without side effects
- 🧪 **Validation**: Pre-commit hooks ensure code quality
- 📦 **Package Management**: Automated installation of Homebrew formulae, casks, and Python packages
- 🔐 **Security**: Secure SSH key and configuration management
- 🎨 **Development Tools**: Pre-configured Neovim and tmux setup
- 🧹 **Clean Uninstall**: Easy removal of all managed configurations

## 🚀 Quick Start

```bash
# Install configuration
make apply

# Preview changes (dry run)
make check

# Remove configuration
make delete

# Clean build environment
make clean
```

## 📚 Documentation

### 🏗️ Project Structure

The configuration is organized into specialized roles:

| Role | Description |
|------|-------------|
| `common` | Creates required directories |
| `ssh` | Manages SSH keys and configuration |
| `dotfiles` | Manages shell config files (.zshrc, .aliases) |
| `neovim` | Configures Neovim editor |
| `tmux` | Sets up tmux configuration |
| `packages` | Manages Homebrew formulae, casks, and Python packages |
| `cleanup` | Removes managed files (uninstallation) |

### 🛠️ Role-Specific Commands

```bash
make ssh        # SSH keys and config only
make dotfiles   # Shell config files only
make neovim     # Neovim config only
make tmux       # tmux config only
make packages   # Install packages only
```

### 🔍 Code Quality

The repository uses pre-commit hooks to maintain high code quality:

```bash
# Set up git hooks (run once after cloning)
make setup-git-hooks

# Run pre-commit checks manually
make pre-commit

# Run linting only
make lint
```

Pre-commit checks include:
- ✅ YAML syntax validation
- ✅ Ansible playbook linting
- ✅ Trailing whitespace and EOF fixing
- ✅ Merge conflict detection

### 🎯 Configuration Management

#### Inventory System
- `inventory`: Contains host groups (local, work, personal)
- `group_vars/macbooks.yml`: Common variables for all MacBooks
- `host_vars/`: Host-specific variables (create files like hostname.yml)

#### Adding New Hosts
1. Add the host to the inventory file
2. Create host-specific files in `host_files/hostname/`
3. Optionally add host-specific variables in `host_vars/hostname.yml`
4. Run: `ANSIBLE_LIMIT=hostname make apply`

### 📝 Adding New Configuration

1. Choose the appropriate role or create a new one
2. Add tasks to the role's `tasks/main.yml` file
3. Add templates to the role's `templates/` directory
4. Add static files to the role's `files/` directory
5. Update the README.md to document the changes

## 📋 Requirements

- Python 3.x
- Ansible
- macOS (for target machines)

## 📄 License

This project is privately maintained.

---

<div align="center">

Made with ❤️ for MacBook Pro users

</div>
