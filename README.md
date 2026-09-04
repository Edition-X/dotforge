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
- 📦 **Package Management**: Declarative `Brewfile` covering formulae, casks, taps and go/uv/npm globals
- 🔐 **Security**: Secure SSH key and configuration management
- 🎨 **Development Tools**: Pre-configured Neovim and tmux setup
- 🧹 **Clean Uninstall**: Easy removal of all managed configurations

## 🧭 First-time Setup

The playbook decrypts secrets with an Ansible Vault password that is
deliberately **not** in the repo (`credentials.txt` is gitignored). A fresh
clone cannot run until you put it back:

```bash
# 1. Restore the vault password (from your password manager)
echo 'THE-VAULT-PASSWORD' > credentials.txt

# 2. Build the venv and apply
make apply
```

`ansible.cfg` points `vault_password_file` at `./credentials.txt`. Note that
`~/.env_vars` also exports `ANSIBLE_VAULT_PASSWORD_FILE`; having both set makes
`ansible-vault` ambiguous about which vault id to use, which is why the Makefile
unsets the environment variable before every run. Do the same if you invoke
`ansible-vault` by hand.

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
| `dotfiles` | Shell config (`.zshrc`, `.aliases`, `.functions`, env vars and secrets), git config, Ghostty, Forge MCP/skills, and skhd |
| `ai_agents` | Shared harness instructions and skills plus managed OpenCode agents, model routing, commands, permissions, Claude profiles, T3 Code integration, and validation |
| `neovim` | Configures Neovim editor |
| `tmux` | Sets up tmux configuration |
| `packages` | Applies the root `Brewfile` via `brew bundle` |
| `macos` | Applies `defaults` captured from the machine (Dock, Finder, typing, F-keys) |
| `cleanup` | Removes managed files (uninstallation) |

### 🛠️ Role-Specific Commands

```bash
make ssh        # SSH keys and config only
make dotfiles   # Shell config files only
make neovim     # Neovim config only
make tmux       # tmux config only
make packages   # Install missing packages
make upgrade    # Install missing packages AND upgrade outdated ones
make ai         # Shared AI harness and OpenCode configuration only
```

### 📦 Packages

Everything installable lives in the root [`Brewfile`](Brewfile) — taps, formulae,
casks, and go/uv/npm globals. It is the single source of truth, and works with or
without Ansible:

```bash
make drift      # what has drifted from the Brewfile
make dump       # rewrite the Brewfile from what is actually installed
```

Things worth knowing:

- **`make apply` never upgrades.** `brew bundle` runs with `--no-upgrade` so an
  apply only fills in what is missing. Use `make upgrade` to move versions.
- **Third-party taps need trust.** Homebrew refuses to load formulae from
  untrusted taps, and that refusal is fatal — it aborts the whole run. Run
  `brew trust <tap>` for each tap in the Brewfile on a new machine.
- **`brew bundle dump` lies about untrusted taps.** It omits their packages
  silently rather than erroring, so a dump taken before trusting every tap will
  quietly drop packages from this file. Trust first, then dump, then check the
  diff both ways — `make drift` only tells you what is declared-but-missing, not
  what is installed-but-undeclared.
- **GUI apps are adopted, not reinstalled.** `scripts/adopt-casks.sh` hands
  existing `/Applications` entries to Homebrew without replacing them. It needs
  an interactive sudo password, so it is a manual one-off rather than an Ansible
  task. App Store apps go through `mas` instead, since their receipts are tied
  to the purchasing Apple ID.

Python packages are *not* managed here. Machine-wide tools belong in the
Brewfile; anything project-specific belongs to that project's own uv/poetry
environment.

### OpenCode

OpenCode configuration is repo-managed by `ai_agents`. Source templates live
under `roles/ai_agents/templates/`, model assignments live in
`host_vars/localhost/opencode.yml`, and generated files deploy under
`~/.config/opencode/`. Existing config is backed up once under
`~/.ai-config-backup/opencode/`; auth, OAuth state, sessions, caches, package
files, and user-owned agents or commands remain outside repository ownership.
Normal bash commands, `git push`, and `~/Projects/**` are preapproved by repo
policy. Other user-selected external directories prompt. Runtime OpenCode skill
or tool-output directories may still carry internal allows. Destructive command
patterns are guardrails, not a sandbox: exact text rules block the listed forms,
but wrapper or option variants can still evade text-pattern matching. The
current deny/ask list covers `git reset --hard`, `git clean`, `git checkout --`,
`rm -rf`, `gh pr merge`, `terraform destroy`, and `kubectl delete` stays
approval-gated.

```bash
make ai                 # Apply shared AI and OpenCode configuration
make validate-opencode  # Render in check mode and validate OpenCode discovery
make test-ai-agents     # Temporary-home migration and idempotency test
```

Restart OpenCode after applying configuration. Native commands:

- `/orchestrate <goal>` — acceptance criteria, task graph, delegation, review, correction, and final verification.
- `/implement-reviewed <feature or fix>` — bounded implementation with independent review and correction loop.
- `/load-test-loop <target and safe environment>` — bounded performance loop; never production by default.
- `/review <changes or revision range>` — read-only review and deterministic checks.
- `/debug-loop <failure or defect>` — reproduce, prove root cause, apply smallest fix, verify.
- `/wayfinder <destination>` — explicit long-horizon decision mapping with the installed Wayfinder skill.
- `/linear <request>` — complete Linear read/write operation owned by `documentation`, with inspection and approval gates.
- `/plan <request>` — user-facing implementation or technical plan owned by `reviewer`; read-only, no verdict boilerplate.
- `/grill <plan or idea>` — explicit one-question-at-a-time decision grilling; `/grilling` is an alias.

OpenCode routing boundary: explicit `/linear` and `/plan` commands bind deterministically to existing specialists. Natural-language Linear requests are prompted to `documentation`; natural-language planning requests are prompted to `reviewer`. Non-documentation agents cannot call Linear MCP tools; the direct-API and shell-fallback prohibition remains prompt-enforced. `/wayfinder` remains orchestrator-owned because subagent depth is one: reviewer planning runs first, then documentation performs any Linear issue-tracker work as sibling tasks. This is prompted and permission-enforced routing, not a native semantic router.

Model policy uses `openai/gpt-5.6-terra` high for orchestration and hard
debugging, `openai/gpt-5.6-sol` high for architecture and independent review,
`openai/gpt-5.6-luna` medium for implementation, and
`openai/gpt-5.4-mini` low for exploration, mechanical work, tests, and docs.
No `*-fast` model IDs are configured. Change one assignment in
`host_vars/localhost/opencode.yml`, run `make ai`, then restart OpenCode.

### Claude profiles and T3 Code

`claude` is the personal/default Claude Code profile. Its existing executable,
authentication, and `~/.claude` state remain untouched. `claude-work` is a
managed wrapper around that same executable; it sets `CLAUDE_CONFIG_DIR` to
`~/.claude-work` and keeps work authentication separate. T3 Code's Claude
provider invokes `claude-work` through `~/.t3/userdata/settings.json`.

```bash
claude             # personal/default profile
claude-work        # isolated work profile used by T3 Code
```

Run `claude-work` once to authenticate work profile when needed. Restart T3
Code after applying configuration changes.

### ⌨️ F-keys

Bare F1-F10 open specific apps and F11 switches between light and dark
appearance (see `host_files/localhost/skhdrc` for the mapping); holding Fn
gives the normal volume/brightness/media row. That is the
opposite of the factory default, where F-keys are media keys by default and Fn
gives F1-F12.

F11 disables macOS automatic appearance switching, then toggles the current
appearance. Re-enable **Auto** in **System Settings → Appearance** to return to
scheduled light/dark changes.

F12 runs a Shortcuts action named `Toggle Focus`. Create it once in **Shortcuts**:
make a shortcut with that exact name, add **Set Focus**, select **Do Not Disturb**,
and choose **Toggle**. This uses Apple's supported Focus action rather than
fragile Control Center UI scripting.

Two pieces make it work:

- `com.apple.keyboard.fnState` (in the `macos` role) flips which behaviour is
  the bare press and which needs Fn.
- [skhd](https://github.com/koekeishiya/skhd) (in the `dotfiles` role) is a
  hotkey daemon that binds each bare F-key to `open -b <bundle-id>` for the
  app it should launch.

Raycast is not involved — its hotkey-to-app bindings live in an encrypted
SQLite database (`~/Library/Application Support/com.raycast.macos/`), not a
plist or text config, so there is no safe way to manage them from this repo.

**One step Ansible cannot do for you:** skhd needs Accessibility access, and
macOS will not grant that non-interactively. After `make apply`, go to
**System Settings → Privacy & Security → Accessibility** and add
`/opt/homebrew/bin/skhd`. Until then, F-keys keep behaving as media keys and
`/tmp/skhd_<user>.err.log` will show `must be run with accessibility access`.
`make apply` installs and starts the skhd service either way, so once the
permission is granted it takes effect on its own — no re-run needed.

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
- `inventory`: Contains the host groups `local` and `macbooks`
- `group_vars/macbooks.yml`: Common variables for all MacBooks, including the
  `config_paths` map that every role deploys against
- `host_vars/<hostname>/`: Host-specific variables. Use the **directory** form —
  `vars.yml` for plain values and `vault.yml` for secrets. A sibling
  `host_vars/<hostname>.yml` file is silently ignored when the directory exists,
  so do not create both.
- `host_files/<hostname>/`: The actual dotfiles that get linked or copied into
  place. Jinja templates belong in a role's `templates/` directory, not here —
  Ansible does not search `host_files/` for them.

#### Adding New Hosts
1. Add the host to the inventory file
2. Create host-specific files in `host_files/hostname/`
3. Add host-specific variables in `host_vars/hostname/vars.yml`
4. Run: `ANSIBLE_LIMIT=hostname make apply`

### 📝 Adding New Configuration

1. Choose the appropriate role or create a new one
2. Add tasks to the role's `tasks/main.yml` file
3. Add templates to the role's `templates/` directory
4. Add static files to the role's `files/` directory
5. Add the deployed path to `config_paths` in `group_vars/macbooks.yml`, and to
   the `cleanup` role so `make delete` stays a genuine uninstall
6. Update the README.md to document the changes

#### Link vs copy vs template

- **Link** anything you might edit by hand. Local edits then show up as a git
  diff in this repo instead of drifting silently until the next apply overwrites
  them. Used for `.aliases`, `.gitconfig`, `ghostty.config`, `tmux.conf.local`.
- **Copy** vendored files you never touch, e.g. the oh-my-tmux `tmux.conf`.
- **Template** anything that needs a variable or a secret, e.g. `.zshrc`,
  `.env_vars`, `.env_secrets`.

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
