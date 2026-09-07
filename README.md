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
| `mcp_toolkit` | Docker MCP Toolkit `sunrise` profile: features, Grafana secret, server membership, Grafana read-only tool allowlist, profile export |
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
make mcp        # Docker MCP Toolkit profile/secrets/features only
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

## MCP gateway

The `mcp_toolkit` role converges the Docker MCP Toolkit's `sunrise` profile —
one gateway, on this Mac, intended to serve Grafana, Notion and Linear over
MCP Streamable HTTP to every AI harness. It manages:

- **Features**: enables `tool-name-prefix`, disables `dynamic-tools`.
- **Secrets**: sets `grafana.api_key` from the vault the first time it is
  missing from `docker mcp secret ls`; never overwrites an existing value
  unless `mcp_toolkit_rotate_secrets=true` is passed explicitly.
- **Profile membership**: adds `grafana`, `notion-remote` and `linear` to the
  `sunrise` profile (`docker mcp profile server add`), and sets
  `grafana.url` from the vault.
- **Tool allowlist**: restricts Grafana to a fixed read-only set of tools
  (dashboards, datasources, Prometheus/Loki/Pyroscope queries, alerting and
  on-call reads, Sift investigations) — no `create_*`/`update_*`/alert
  management. Notion and Linear, both hosted, keep every tool.
- **Export**: writes `docker mcp profile export sunrise` to
  `~/.config/mcp-gateway/sunrise/profile.export.yaml` (0600) for a later
  drift checker to diff against.

Linear and Notion authenticate via OAuth-DCR, authorized once by hand
(`docker mcp oauth authorize <provider>`) — the toolkit's alternative
personal-access-token secret path was found not to work for Linear in this
toolkit version, so no vault key is used for either. The role only verifies
`docker mcp oauth ls` shows both `authorized` and fails with the exact
command to run if not.

No secret value is ever templated into a harness config — the API key lives
in the macOS Keychain via Docker Desktop, and every harness will eventually
point at the gateway's HTTP endpoint instead of holding its own credentials.

`~/Projects/Grafana_local_mcp` (the standalone compose stack and launchd
watchdog that used to serve Grafana on `127.0.0.1:8000`) is superseded by the
gateway's `grafana` server; its container and launchd job have been stopped,
but the repo itself is left for Dan to archive or delete by hand.

```bash
make mcp                                          # converge the sunrise profile
make mcp RUN_ARGS='-e mcp_toolkit_rotate_secrets=true'   # force-rotate grafana.api_key
```

### Harness wiring

Every harness that can send a custom HTTP header points at the gateway
through one `mcp-sunrise` entry instead of separate `grafana`/`notion`/
`linear` registrations. The bearer token is `mcp_gateway_sunrise_token`
(vault-managed) and is rendered with `no_log: true`; it never appears in a
repo file, only in the runtime config files below (each `0600`).

- **OpenCode** (`~/.config/opencode/opencode.jsonc`, role-templated): a
  `mcp-sunrise` entry of `type: "remote"`, `url: mcp_gateway_url`, and a
  `headers.Authorization` bearer header. `scripts/validate-opencode-config.sh`
  asserts the URL and header shape and that no `mcp.*.oauth` object remains,
  and redacts the one legitimate bearer value before its blanket secret scan.
- **Claude Code** (both `personal` and `work` profiles): registered via
  `claude mcp add --scope user --transport http mcp-sunrise <url> --header
  "Authorization: Bearer <token>"` (see `roles/ai_agents/tasks/claude_mcp.yml`).
  The personal profile's old direct `notion` and `grafana` registrations are
  removed the same way. `mcp__mcp-sunrise` is pre-approved via
  `ai_claude_permission_allow` in `group_vars/macbooks.yml`.
- **Forge** (`~/forge/.mcp.json`, role-templated): `mcp-sunrise` with a `url`
  and `headers.Authorization`, replacing its `linear`, `notion` and `grafana`
  entries. `arcane` is untouched.
- **Codex CLI** (`~/.codex/config.toml`) — managed by
  `roles/ai_agents/tasks/codex_mcp.yml` via `scripts/codex-mcp-sync.py`. The
  file is otherwise app-owned (ChatGPT desktop), so the sync script uses
  `tomlkit` to surgically replace only the `arcane` and `mcp-sunrise`
  `mcp_servers` entries and remove `linear`, `notion`, `grafana`, leaving
  every other section (other servers, `[projects.*]` trust levels, plugins,
  marketplaces, desktop settings) byte-for-byte untouched. A one-time backup
  of the pre-sync file is kept at
  `~/.ai-config-backup/codex-config.toml.pre-mcp-sync`.

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
- `/plan <request>` — read-only implementation or technical plan, owned directly by `orchestrator`; no verdict boilerplate.
- `/grill <plan or idea>` — explicit one-question-at-a-time decision grilling; `/grilling` is an alias.

OpenCode routing boundary: explicit `/linear` binds deterministically to
`documentation`; natural-language Linear requests are prompted to it too.
Non-documentation agents cannot call Linear MCP tools; the direct-API and
shell-fallback prohibition remains prompt-enforced. `/plan` and `/wayfinder`
stay orchestrator-owned, read-only planning; every implementation ticket is
delegated whole to `worker`, never implemented by orchestrator itself. This is
prompted and permission-enforced routing, not a native semantic router.

Model policy is canonical and provider-neutral under
`host_files/localhost/ai/routing/models.yml`; no harness hardcodes a model ID
of its own. Current tiers: `gpt-5.6-sol`/`claude-opus-5` medium for lead,
`gpt-5.6-luna`/`claude-sonnet-5` medium for worker, `gpt-5.6-sol`/
`claude-opus-5` high for rescue, `gpt-5.6-terra`/`claude-opus-5` high for a
senior tier mapped for completeness but outside default routing, and
`gpt-5.4-mini`/`claude-haiku-4-5` low for a utility tier outside the normal
engineering path. No `*-fast` model IDs are configured. Change one tier in
`host_files/localhost/ai/routing/models.yml`, run `make ai`, then restart
OpenCode.

### Cross-harness lead-worker routing

Normal engineering work follows one workflow on every harness that supports
it: a lead (medium reasoning) delegates one whole ticket at a time to a
worker (medium reasoning), reviews the real diff and check evidence, allows
one correction back to the same worker, escalates a second materially similar
failure to a fresh rescue (high reasoning), and runs a fresh verifier before a
batch merges. See `host_files/localhost/ai/README.md` for the full
per-harness support matrix, the `documentation`/Linear permission boundary,
and how a T3 composer or CLI-flag override for one session differs from
drift. Summary:

| Harness | Support |
|---|---|
| OpenCode | Full native lead (`orchestrator`) / worker / verifier / rescue, plus command-only `documentation` |
| Claude Code (personal + work) | Full native worker / verifier / rescue / documentation; root profile selected at lead tier (Opus 5 medium) is the lead, no custom orchestrator agent |
| Codex CLI | Full native worker / verifier / rescue / documentation; root CLI pinned to lead tier is the lead |
| T3 Code (Claude and Codex providers) | Inherited from `claude-work` and `~/.codex` respectively; no duplicate T3 agent definitions |
| Forge 2.13.21 | Shared instructions and skill only; built-in Forge/Muse/Sage agents remain Forge-owned, no native Luna/Sonnet worker |

### Claude profiles and T3 Code

`claude` is the personal/default Claude Code profile. Its existing executable,
authentication, and `~/.claude` state remain untouched. `claude-work` is a
managed wrapper around that same executable; it sets `CLAUDE_CONFIG_DIR` to
`~/.claude-work` and keeps work authentication separate. T3 Code's Claude
provider invokes `claude-work` through `~/.t3/userdata/settings.json`. The work
profile is a member of `ai_harnesses` like every other harness, so it receives
the same `AGENTS.md` instructions and skills as the personal profile, and the
same four native worker/verifier/rescue/documentation agents, rendered
byte-identical to the personal profile's.

```bash
claude             # personal/default profile
claude-work        # isolated work profile used by T3 Code
```

Run `claude-work` once to authenticate work profile when needed. Restart T3
Code after applying configuration changes. A T3 composer setting or an
explicit CLI flag can override the root/lead model for one session only; it
does not change which model a delegated native worker agent runs under, since
those agent files pin their own model independent of the root selection.

### Live routing canaries

Static checks (`make validate-opencode`, `make test-ai-agents`,
`scripts/check-agent-config-drift.sh`, `scripts/validate-agent-routing.py`)
only prove rendered config is well formed; they cannot prove a model actually
reads a delegation prompt and calls a worker. `scripts/test-agent-routing-live.sh`
makes real, billed calls against installed harnesses to capture that evidence:

```bash
scripts/test-agent-routing-live.sh --harness opencode|claude-personal|claude-work|codex|forge|all
```

It is opt-in only — never wired into `make lint`, `make ci` or a pre-commit
hook, since every run spends real model usage. Each requested harness prints
one `PASS harness: evidence`, `FAIL harness: reason`, or
`UNAVAILABLE harness: reason` line; `UNAVAILABLE` means the provider rejected
the call for quota/credit/auth reasons (for example OpenAI workspace credits
depleted, which affects every openai-backed harness — OpenCode, Codex, and
Forge, since `forge agent list` confirms Forge's built-in agents also run on
Codex — or an Anthropic per-request spend cap) and is never printed as `PASS`.
It still makes the overall exit code non-zero, because no routing evidence was
actually obtained. T3 cannot be driven non-interactively, so the script only
prints the two manual T3 prompts and a read-only evidence query; it never
automates the T3 UI or writes to T3's SQLite state. `--self-test` relaxes the
pre/post worktree check to also allow this runner's own pending changes, for
verifying the script against itself.

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
