---
name: macbook
description: Make any change to this Mac go through the macbook-pro repo instead of by hand — install, remove or upgrade an app, CLI, font or tool; change shell, git, ghostty, skhd, neovim, tmux or ssh config; change AI harness (Claude, Codex, OpenCode, Forge, T3) instructions, skills, MCP servers, hooks or the MCP gateway; change browser policy, extensions or bookmark catalogs (Chrome, Edge, Brave, Firefox, Vivaldi). Triggers: "install", "uninstall", "add to my mac", "update my dotfiles", "add an MCP", "my Claude config", "my bookmarks", or naming any tool or setting on this machine.
---

# Macbook

This machine's state is code. A change that isn't in `~/Projects/macbook-pro` will
be silently clobbered by the next `make apply`, so every request in the table below
routes through the repo, not through a one-off `brew install` or hand-edited dotfile.

## 1. Where it lives

| Request | Exact location |
|---|---|
| Cask (GUI app) | `Brewfile`, `cask "name"` under the right `##` heading |
| CLI / formula | `Brewfile`, `brew "name"` |
| Python tool (uv-installed) | `Brewfile`, `uv "name"` — pin a version or `source:` git ref, e.g. `uv "arcane-mcp", source: "git+https://github.com/Edition-X/arcane.git@vX"` |
| npm global | `Brewfile`, `npm "name"` |
| Shell alias | `host_files/localhost/aliases` |
| Shell function | `host_files/localhost/functions` |
| Env var (non-secret) | `roles/dotfiles/templates/env_vars.j2` |
| Secret env var | vault (`host_vars/localhost/vault.yml`) + `roles/dotfiles/templates/env_secrets.j2` |
| zshrc, gitconfig, ghostty config, skhdrc, tmux/nvim conf, ssh config | matching file under `host_files/localhost/` (see `group_vars/macbooks.yml` `config_paths` for the exact dest each one deploys to) |
| Claude Code hook | `ai_claude_hooks` in `group_vars/macbooks.yml`, applied by `roles/ai_agents/tasks/claude_settings.yml` (merges into each profile's `settings.json`) |
| Claude Code permission pre-approval | `ai_claude_permission_allow` in `group_vars/macbooks.yml`, same task |
| Codex MCP server | `ai_codex_mcp_servers` in `group_vars/macbooks.yml`, applied by `roles/ai_agents/tasks/codex_mcp.yml` |
| OpenCode MCP server / config | `roles/ai_agents/templates/opencode.jsonc.j2` |
| Docker MCP gateway server | `mcp_toolkit_servers` in `group_vars/macbooks.yml`, applied by `roles/mcp_toolkit/tasks/main.yml` |
| Browser extension presence (Chrome, Edge, Brave, Firefox) | `host_files/localhost/browsers/<browser>/extensions.yml` `required:` list — vendor id + store `update_url`, `enforcement: report_only` |
| Browser policy (mandatory only) | `host_files/localhost/browsers/<browser>/policies.yml` — never a bookmark or extension key, the role renders those |
| Browser bookmarks | `host_files/localhost/browsers/<browser>/bookmarks.yml` is a **record** of the profile, captured by `make browser-capture RUN_ARGS='--enable-capture --isolated'`, never hand-edited and never pushed back into the browser as managed bookmarks. To change a bookmark, change it in the browser; the next capture records it |
| New skill | new directory `host_files/localhost/ai/skills/<name>/SKILL.md` — no role edit needed, `roles/ai_agents` discovers skill directories with `find` |

Confirm the mapping against the real tasks before writing anything down — `group_vars/macbooks.yml`
and `roles/*/tasks/main.yml` are the source of truth, this table is a pointer to them.

## 2. The process

First check whether the request is already satisfied (`brew list <name>`, `grep` the
Brewfile, `claude mcp get`, and so on). If it is, say so with the evidence and stop:
no branch, no commit for a zero-diff change.

Run these in order. Do not skip the verify step or the second dry run.

```bash
cd ~/Projects/macbook-pro
git checkout main && git pull --ff-only
git checkout -b <type>/<kebab-description>
```

1. Edit the file(s) from the table above.
2. `make lint` — ansible-lint + yamllint, must exit 0.
3. `make check RUN_ARGS='--tags <tag>'` — dry run scoped to the area you touched
   (`packages`, `dotfiles`, `ai`, `mcp`, `neovim`, `tmux`, `ssh`, `browsers`). Read the diff it
   reports. Stop and investigate if anything unexpected would change.
4. `make <target>` — the matching apply target (`make packages`, `make dotfiles`,
   `make ai`, `make mcp`, `make neovim`, `make tmux`, `make ssh`, `make browsers`). Only fall back to
   `make apply` (every tag) when the change genuinely spans areas.
5. Area-specific verify:
   - packages: `brew list | grep <name>`, `command -v <name>`
   - dotfiles: open a new shell (`zsh -lic 'exit'` or a fresh terminal tab) and
     confirm the change is live
   - ai: `bash scripts/check-agent-config-drift.sh`, `claude mcp get <name>` for a
     new Claude MCP server, `make validate-opencode` for OpenCode changes
   - mcp: `make mcp-test`
   - browsers: `make browser-test RUN_ARGS='--all-installed --isolated --policy --extensions --capture-read-only'`
     (real browsers, GUI session; needs `make browsers-authorize` once), then check the
     bookmark bar in one browser — no `Managed by macbook-pro` folder must appear
6. Run the same `make <target>` again. Expect `changed=0` — a non-zero second run
   means the task isn't idempotent.
7. `pre-commit run --all-files`.
8. Commit, Conventional Commits, scope `skills`, `ai`, or the area touched
   (`packages`, `dotfiles`, `mcp`), e.g. `feat(ai): add MCP server for X`.
9. Land it with the `ship` skill: push the branch, open the PR, self-review, wait for
   CI, merge with a merge commit, then pull `main` and re-apply. Never push to `main`
   directly.
10. Save an Arcane memory (`decision` for a new tool/config choice, `context` for a
    routine addition) describing what changed and why.
11. Tell Dan what changed and the exact command to verify it himself.

## 3. Removals

- Delete the `Brewfile` line.
- `brew uninstall <name>` (add `--cask` for a cask).
- Trash config directories the app left behind: `ls -d <path>` first to confirm it's
  real and exactly what you mean, then `trash <that absolute path>`. Never `rm`.
- If the removed thing is a harness, drop it from every array that lists harnesses
  (`ai_harnesses`, `ai_claude_profiles`, drift-checker arrays in
  `scripts/check-agent-config-drift.sh`).
- Update any README or doc that names it.

## 4. Secrets

- Edit secrets only through `ansible-vault edit host_vars/localhost/vault.yml`
  (`source venv/bin/activate; unset ANSIBLE_VAULT_PASSWORD_FILE` first).
- Any task that writes a secret carries `no_log: true`.
- Run the pre-commit secret scan before committing; never echo a secret value in a
  command, a file, or chat.
- If a request needs a secret that doesn't exist yet, stop and tell Dan exactly
  which vault key to create and where it's consumed — do not guess a value or
  invent a placeholder that could get committed.

## 5. Never

- `git add -A` — name files explicitly.
- `rm` — use `trash` with an absolute path you just printed with `ls -d`.
- Hand-editing `~/.zshrc`, `~/.claude.json`, `~/.codex/config.toml`, or
  `~/.config/opencode/opencode.jsonc` directly — the repo owns these, edit the
  source template/file and apply.
- `make apply` when a single `--tags` target covers the change.
- Pushing to `main` at all — every change lands through a pull request (`ship` skill).

## Verify

Deploy check — confirm every harness got the skill via symlink, not a copy:

```bash
make ai
ls -la ~/.claude/skills/macbook ~/.codex/skills/macbook \
       ~/.config/opencode/skills/macbook ~/forge/skills/macbook \
       ~/.claude-work/skills/macbook
```

Live check — a natural request should route through this process on its own:

```bash
cd ~/Projects/macbook-pro
timeout 240 claude-work -p "Install the jq CLI on my mac."
```

Expect the reply to describe (or perform) editing the `Brewfile`, running
`make check`, then `make packages` — the process matters even if `jq` turns out to
already be installed (check with `brew list jq` before treating this as a no-op).
If the reply doesn't show this process, tighten the frontmatter `description` and
retry once.

Finally: `make lint`, `pre-commit run --all-files`.
