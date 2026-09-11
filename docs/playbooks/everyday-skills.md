# Playbook: everyday skills (macbook, arcane-dev, sunrise-cells)

**Status:** ready to execute
**Written:** 2026-09-06
**Audience:** Claude Sonnet executing one ticket at a time, reviewed by a stronger model
**Repo:** `~/Projects/dotforge`. Reads `~/Projects/arcane`, `~/Projects/sunrise_ansible_inventory`, `~/Projects/sunrise-cell-deploy-ansible` for facts.

---

## 0. Read this first

### Goal

Dan says one plain sentence in any harness and the right procedure runs. Three procedures, three skills, one routing section in the canonical `AGENTS.md`:

| Dan says | Skill |
|---|---|
| "install jq", "remove Slack", "change my zshrc", "add an MCP server", "update my Claude hooks" | `macbook` |
| "fix this bug in arcane", "add a tool to arcane", "bump arcane on my mac" | `arcane-dev` |
| "what is running on moon", "which cells are at <customer>", "restart alloy on bg4's IPC" | `sunrise-cells` |

Skills live in `host_files/localhost/ai/skills/<name>/SKILL.md`, are discovered by `roles/ai_agents` and symlinked into every harness. Procedure goes in skills; `AGENTS.md` only routes. Skills load on demand, `AGENTS.md` loads every turn.

### Rules for every ticket

1. Integration branch `integration/everyday-skills` from `main`, cut once. Ticket branches from it, merged back `--no-ff` by the reviewer. Never commit to `main` or the integration branch directly. Never push.
2. Never `rm`. `trash` with one absolute path after `ls -d` and `pwd`. Never `git add -A`.
3. `?? docs/` stays untracked.
4. Facts in skills come from reading the real repos and running the real commands, not from memory. Every command a skill tells the model to run, you run once yourself first and paste the output in your report.
5. No secrets anywhere: skill files must not contain tokens, vault values, passwords, or the contents of `.vault_pass.txt`. Paths to secret files are fine.
6. Conventional Commits with scope `skills` or `ai`. Arcane memory after each commit via `/Users/dkelly/.local/bin/arcane save --project dotforge --source claude-code ...`.
7. Verification for each skill ends with a live harness call: a natural sentence through `claude-work -p` (and once through `opencode run`) that should trigger the skill. Run each prompt once, `timeout 240`. Report the reply verbatim. A skill that does not fire from a natural sentence is not done: tighten the `description` and retry once.
8. Skill file conventions (check existing skills first, e.g. `resume-branch-work`, `gh-fix-ci`): YAML frontmatter with `name` (equals directory name) and `description` (one paragraph, states what it does AND the exact phrases that should trigger it), then Markdown. Under 250 lines. Imperative voice. Commands in fenced blocks. No harness-specific tool names; say "the Arcane memory_save tool", not `mcp__arcane__memory_save`.

### Environment facts

| Fact | Value |
|---|---|
| Canonical instructions | `host_files/localhost/ai/AGENTS.md`, 117 lines, sections: Caveman Mode, Arcane, Planning Large Work, Safety, Completion discipline. Symlinked to `~/.claude/CLAUDE.md`, `~/.claude-work/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/forge/AGENTS.md`, `~/.config/opencode/AGENTS.md`. |
| Skills dir | `host_files/localhost/ai/skills/` (20 skills). Discovered by `find` in `roles/ai_agents/tasks/main.yml`; adding a directory needs no role edit. `make ai` deploys. |
| dotforge process | `main` unprotected. `make lint`, `make ci`, `make check RUN_ARGS='--tags <tag>'`, `make apply`, per-role targets `make packages|dotfiles|ai|mcp|neovim|tmux|ssh`, `make drift`, `make mcp-test`, `make validate-opencode`, `make test-ai-agents`. Pre-commit runs secret scan, ansible-lint, yamllint, drift checker. Vault: `host_vars/localhost/vault.yml` via `ansible-vault edit` with `source venv/bin/activate; unset ANSIBLE_VAULT_PASSWORD_FILE`. |
| Where things live | Apps/CLIs: `Brewfile` (`cask`, `brew`, `uv`, `npm`, `go`). Shell, git, ghostty, skhd, Forge MCP: `roles/dotfiles`. Harness instructions, skills, Claude MCP registration and hooks, Codex MCP sync, OpenCode config/agents/commands, T3 settings: `roles/ai_agents`. Gateway profile/secrets/service: `roles/mcp_toolkit`. macOS defaults: `roles/macos`. Neovim, tmux, ssh: their roles. |
| Arcane | `~/Projects/arcane`, `main` protected (PR, 1 review, checks Lint + Test 3.11/3.12/3.13 + installed-artifact smoke). Release workflow cuts `v0.2.0-beta.N` on push to `main`. Installed on this Mac as uv tool `arcane-mcp`, pinned in `Brewfile` (`uv "arcane-mcp", source: "git+https://github.com/Edition-X/arcane.git@vX"`), binary `~/.local/bin/arcane`. Tests: `source .venv/bin/activate && pytest -q && mypy src/arcane && ruff check src tests && ruff format --check src tests`. `ARCANE_TOOL_PROFILE=core` default (13 tools). |
| Cell inventory | `~/Projects/sunrise_ansible_inventory`, `ansible.cfg` sets `inventory = ./inventory/hosts.yml`, `vault_password_file = ./.vault_pass.txt` (present). `ansible` is `~/.pyenv/shims/ansible`. `group_vars/all/all.yml` defines `ansible_user`, `ansible_become_pass` (vaulted), `ansible_python_interpreter`, image versions, Grafana Alloy settings. Hosts `R0xx-BG-NNN-{IPC,Orin,RTC}.<fleet-domain>`, groups per cell (`r021_bg_004`), plus `production_cells`, `development_cells`, `warehouse_cells`, `monitored_cells`, `maintenance_cells`, `hw_*`, `customer_*`, `location_*`, `ipc_nodes`, `orin_nodes`, `rtc_nodes`, `infrastructure_nodes`. `hostname_alias` per cell in `hosts.yml` (moon, mars, metis, mimas, minerva, usainbolt, …); the README's alias table is stale, hosts.yml is truth. |
| Cell playbooks | `~/Projects/sunrise-cell-deploy-ansible` (read its README and playbook list in S3). |

### Ticket order

| # | Ticket | Branch |
|---|---|---|
| S1 | `macbook` skill | `feat/skill-macbook` |
| S2 | `arcane-dev` skill | `feat/skill-arcane-dev` |
| S3 | `sunrise-cells` skill | `feat/skill-sunrise-cells` |
| S4 | AGENTS.md routing, skill linter, deploy, end-to-end | `feat/agents-routing-skill-lint` |

---

## S1. `macbook` skill

**Branch:** `feat/skill-macbook`. **File:** `host_files/localhost/ai/skills/macbook/SKILL.md`.

**Description (frontmatter) must cover:** installing, removing or upgrading any app, CLI, font or tool on this Mac; changing shell, git, terminal (ghostty), skhd, neovim, tmux, ssh config; changing anything about the AI harnesses (Claude, Codex, OpenCode, Forge, T3), their instructions, skills, MCP servers, hooks or the MCP gateway; anything else managed by the dotforge repo. Triggers: "install", "uninstall", "remove", "add to my mac", "update my dotfiles", "change my zshrc", "add an MCP", "my Claude/Codex/OpenCode config".

**Body sections, in this order:**
1. **Where it lives.** The table from Environment facts, expanded with the exact file per common request: a cask → `Brewfile` under the right `##` heading; a CLI → `brew "x"`; a Python tool → `uv "x"` pinned; an npm global → `npm "x"`; a shell alias → `host_files/localhost/aliases`; env var → `roles/dotfiles/templates/env_vars.j2`; secret → vault + `env_secrets.j2`; Claude hook → `ai_claude_hooks` in `group_vars`; Claude permission → `ai_claude_permission_allow`; Codex MCP server → `ai_codex_mcp_servers`; OpenCode MCP → `opencode.jsonc.j2`; gateway server → `mcp_toolkit_servers`; skill → `host_files/localhost/ai/skills/<name>/`. Read `roles/*/tasks/main.yml` and `group_vars/macbooks.yml` to confirm each mapping before writing it down.
2. **The process.** Numbered, exact:
   `cd ~/Projects/dotforge && git checkout main && git pull --ff-only && git checkout -b <type>/<kebab>` → edit → `make lint` → `make check RUN_ARGS='--tags <tag>'` and read the diff, stop if anything unexpected changes → `make <target>` → area-specific verify (table: packages → `brew list | grep`, `command -v`; dotfiles → open a new `zsh -lic` and test; ai → `bash scripts/check-agent-config-drift.sh`, `claude mcp get`, `make validate-opencode`; mcp → `make mcp-test`) → run the same `make` again, expect `changed=0` → `pre-commit run --all-files` → commit conventional with scope → `git checkout main && git merge --no-ff <branch> && git push origin main` → Arcane `memory_save` (decision or context) → tell Dan what changed and how to verify.
3. **Removals.** Brewfile line, `brew uninstall [--cask]`, trash config dirs by absolute path after listing, drift arrays if a harness, README mention.
4. **Secrets.** Only via `ansible-vault edit`; tasks that write them carry `no_log: true`; hygiene grep before commit; never echo values; never paste values in chat; when a new secret is needed, stop and tell Dan exactly what to create and which vault key to use.
5. **Never.** `git add -A`; `rm`; editing `~/.zshrc`, `~/.claude.json`, `~/.codex/config.toml`, `~/.config/opencode/opencode.jsonc` by hand (the repo owns them; edit the source and apply); `make apply` when a single tag will do; pushing without the verify step passing.

**Verify:**
- Deploy: `make ai`, `ls -la ~/.claude/skills/macbook ~/.codex/skills/macbook ~/.config/opencode/skills/macbook ~/forge/skills/macbook ~/.claude-work/skills/macbook` all symlinks into the repo.
- Live: `cd ~/Projects/dotforge && timeout 240 claude-work -p "Install the jq CLI on my mac."` Expect the reply to describe or perform the Brewfile edit → `make check` → `make packages` path (jq may already be installed; the point is the process). Read the transcript summary in the reply; if it did not consult the skill, tighten the description and retry once. Then `git status --short` and undo anything the model changed that you did not intend to keep (`git checkout -- <file>`, `git branch -D` any branch it made) and report what happened.
- `make lint`, `pre-commit run --all-files`.

**Commit:** `feat(skills): add macbook skill for changes managed by this repo`. **Arcane:** `decision`, title `macbook skill routes machine changes through the repo`.

---

## S2. `arcane-dev` skill

**Branch:** `feat/skill-arcane-dev`. **File:** `host_files/localhost/ai/skills/arcane-dev/SKILL.md`.

**Description must cover:** changing Arcane's code (bugs, features, MCP tools, CLI), releasing it, and updating the installed version on this Mac. Triggers: "arcane bug", "add a tool to arcane", "change memory_search", "release arcane", "bump arcane", "update arcane on my mac", "arcane is on an old version".

**Body:**
1. **Two flows, pick one.** Code change vs deploy. State the tell: "is the change in the arcane repo, or in what this Mac runs?"
2. **Code change flow.** `cd ~/Projects/arcane && git checkout main && git pull --ff-only && git checkout -b <type>/<kebab>` → read `CLAUDE.md` and `AGENTS.md` (contributor half) → change with tests at the boundary → `source .venv/bin/activate && pytest -q && mypy src/arcane && ruff check src tests && ruff format --check src tests` (run `ruff format` first) → `pytest -q tests/integration/test_installed_mcp.py -m artifact` when the MCP surface changed → `docs/mcp-tools.md` updated if tools changed → commit → `git push -u origin <branch>` and `gh pr create` with summary and test plan (this is the one place pushing is expected; `main` is protected) → tell Dan the PR URL; merging is his → note that the merge cuts the next `v0.2.0-beta.N` automatically. Read the actual `.github/workflows/release.yml` to confirm the trigger before writing this.
3. **Deploy flow.** Check installed vs latest: `~/.local/bin/arcane --version` and `gh release list --repo Edition-X/arcane --limit 3`. Then hand off to the `macbook` skill: edit the `uv "arcane-mcp" ... @vX` line in `Brewfile`, `make packages`, verify `arcane --version`, `uv tool list | grep arcane-mcp`, `bash scripts/check-agent-config-drift.sh`, and one live tool count through the work profile (`claude-work -p "..."` asking for the number of `mcp__arcane__` tools; expect 13 under the core profile). Never install from `~/Projects/arcane` or the venv path.
4. **Things to know.** Tool profiles (`ARCANE_TOOL_PROFILE`), `memory_search` detail levels, project resolves from git remote (do not pass `project`), source stamping, where handlers live (`src/arcane/mcp_server/tools/`), where the tool list lives (`server.py`), `CORE_TOOLS`. Confirm each by reading the code; cite file paths.
5. **Never.** Push to `main`; merge your own PR; edit the Brewfile pin without a release tag that exists (`git ls-remote --tags`).

**Verify:** deploy symlinks as in S1; live: `cd ~/Projects/arcane && timeout 240 claude-work -p "Is arcane on my mac up to date with the latest release? Just check, do not change anything."` Expect the installed version and the latest tag compared, no edits. `git -C ~/Projects/arcane status --short` and `git -C ~/Projects/dotforge status --short` unchanged apart from your skill file and `?? docs/`.

**Commit:** `feat(skills): add arcane-dev skill for code changes and deploys`. **Arcane:** `decision`.

---

## S3. `sunrise-cells` skill

**Branch:** `feat/skill-sunrise-cells`. **File:** `host_files/localhost/ai/skills/sunrise-cells/SKILL.md`.

**Research first, paste findings in the report:**
- `cd ~/Projects/sunrise_ansible_inventory && ansible-inventory --graph | head -60` and `ansible-inventory --list | python3 -c "import json,sys; d=json.load(sys.stdin); print(sorted(d.keys()))"` for the full group list.
- Alias table from truth: `python3 - <<'PY'` that loads `inventory/hosts.yml` with PyYAML and prints `cell_group → hostname_alias` for every cell with a non-empty alias. Paste it.
- `ansible-inventory --host <one IPC> --yaml` with secret-looking values redacted: note which vars exist (`ansible_user`, `ansible_python_interpreter`, image versions). Never print `ansible_become_pass`.
- Connectivity check on ONE development cell that the inventory marks Running in the office (pick from `development_cells` ∩ `monitored_cells`): `ansible <host> -m ping` and `ansible <host> -m command -a 'uptime' -b`. If unreachable, try one more; if none reachable, record it and write the skill anyway.
- `~/Projects/sunrise-cell-deploy-ansible`: list playbooks (`ls *.yml playbooks/ 2>/dev/null`), read README, note which cover restart/deploy/update of cell services so the skill can point writes at them.
- Which harness directories exist with `ansible` on PATH: `zsh -lic 'command -v ansible'`.

**Description must cover:** any question or task about Sunrise robot cells, their IPC/Orin/RTC nodes, groups, customers, locations, aliases; running commands on them via Ansible. Triggers: cell aliases and serials (moon, mars, metis, mimas, minerva, usainbolt, bg4, <serial>, r02b), "cell", "IPC", "Orin", "RTC", "which cells", "on the cell", "on moon".

**Body:**
1. **Inventory is truth, look before you speak.** Always `cd ~/Projects/sunrise_ansible_inventory` first (ansible.cfg lives there). Commands: `ansible-inventory --graph`, `--graph <group>`, `--host <fqdn> --yaml`, `--list`. Resolve alias → cell group → three FQDNs from `hosts.yml` (`hostname_alias`); never rely on the README's alias table. Print the alias table you derived as a quick reference with the note "regenerate from hosts.yml if unsure".
2. **Read-only by default.** Allowed without asking: `-m ping`, `-m setup` (with `-a 'filter=...'`), `-m service_facts`, `-m stat`, `-m slurp` (small files), `-m command -a` with read-only commands: `uptime`, `df -h`, `free -m`, `systemctl status <unit>`, `systemctl list-units --failed`, `journalctl -u <unit> -n 200 --no-pager`, `docker ps`, `docker logs --tail 200 <c>`, `nvidia-smi`, `ip -br a`, `cat /etc/os-release`, `ls`, `cat` of config files. Always `--limit` to the fewest hosts, prefer one node. Use `-b` only when the read needs root (journalctl, some docker). One host at a time for output readability; use `-o` for one-line summaries across a group.
3. **Writes only when Dan explicitly asks, in that message.** Before running: say exactly what will run, on exactly which hosts, and wait for a yes. Prefer an existing playbook from `sunrise-cell-deploy-ansible` with `--check --diff` first, then for real with `--limit`. Ad-hoc writes limited to `-m systemd -a 'name=<unit> state=restarted'`, `-m copy`, `-m lineinfile`, `-m docker_container` with explicit args. Never: `reboot`, `shutdown`, `rm -rf`, `apt upgrade`, `docker system prune`, anything touching `production_cells` or `customer_*` groups unless Dan named that cell in the same message. Never a write against a group wildcard.
4. **After a write.** Re-run the read that proves it (status, logs). Save an Arcane memory (`context` or `bug`) with cell, host, what changed, why.
5. **Sudo.** `become` works via the vaulted `ansible_become_pass`; never print it, never `ansible-vault view` the secrets file, never copy `.vault_pass.txt`.
6. **When the inventory looks wrong** (cell missing, alias mismatch, status stale): say so, do not guess, offer to open a change in the inventory repo.

**Verify:** deploy symlinks; live read: `cd ~/Projects/sunrise_ansible_inventory && timeout 240 claude-work -p "What is the uptime of moon's IPC?"` expect a real uptime and no write; live refusal: `timeout 240 claude-work -p "Restart the alloy service on moon."` expect the model to state the command and host and ask for confirmation, not execute (the `-p` run cannot receive a yes, so the reply must be a question). Paste both replies. `make lint`, `pre-commit run --all-files`.

**Commit:** `feat(skills): add sunrise-cells skill, read-only Ansible by default`. **Arcane:** `decision`, details include the alias table and the reachable test host.

---

## S4. AGENTS.md routing, skill linter, deploy, end-to-end

**Branch:** `feat/agents-routing-skill-lint`. **Precondition:** S1 to S3 merged into the integration branch.

1. **AGENTS.md.** Insert a new section `## Everyday work — use the skill` after `## Planning Large Work` and before `## Safety`, at most 12 lines:
   ```markdown
   ## Everyday work — use the skill

   These requests have a fixed procedure. Load the skill first, then follow it.

   | Request | Skill |
   |---|---|
   | Install, remove or change anything on this Mac, dotfiles, harness config, MCP servers | `macbook` |
   | Change Arcane's code, release it, or update it on this Mac | `arcane-dev` |
   | Anything about a Sunrise robot cell (moon, mars, bg4, IPC, Orin, RTC) or running commands on one | `sunrise-cells` |

   Do not improvise these from memory. If a skill and this file disagree, the skill wins for that task.
   ```
   Also fix the `/wayfinder` line if it still says `/setup-matt-pocock-skills` must be run first only when true; leave otherwise.
2. **Skill linter** `scripts/check-skills.sh`, wired into `.pre-commit-config.yaml` as a local hook scoped to `^host_files/localhost/ai/skills/`, and into `make lint`. Checks per `SKILL.md`: file exists; frontmatter block present; `name:` equals directory name; `description:` non-empty and under 600 characters; file under 300 lines; no line matches the secret patterns (`ntn_[A-Za-z0-9]`, `glsa_[A-Za-z0-9]`, `lin_api_[A-Za-z0-9]`, `[0-9a-f]{64}`, `Bearer [A-Za-z0-9]{16,}`, `BEGIN .*PRIVATE KEY`). Prints one line per failure, exit 1 on any. Run it against all 23 skills; fix only the three new ones if they fail; report pre-existing failures without fixing (out of scope) unless trivial and safe (a `name` mismatch is safe to fix; say so).
3. **Deploy:** `make ai`, `make ai` again `changed=0`, drift script clean, all five skills dirs show the three new symlinks.
4. **End-to-end, natural sentences, once each, `timeout 240`:**
   - `cd ~/Projects/dotforge && claude-work -p "Add the tree CLI to my mac."` Expect the macbook process (branch, Brewfile edit, make check, make packages, verify, merge, push is NOT allowed in this test: add to the prompt "do everything except the final push and tell me the branch name"). Afterwards inspect `git log --oneline -3`, `git status --short`, `brew list | grep '^tree$'`. Then revert what it did: `git checkout main && git branch -D <branch>` if it created one, `git reset --hard origin/main` ONLY if the model committed to main (check `git log origin/main..main` first and report), `brew uninstall tree` if it installed it. Report exactly what the model did versus the skill.
   - `cd ~/Projects/arcane && claude-work -p "Which version of arcane is installed here and is it the latest release?"` Expect versions compared, nothing changed.
   - `cd ~/Projects/sunrise_ansible_inventory && opencode run "Which cells are at the Ljubljana office and are they all running?"` Expect an inventory-derived answer, no writes.
   - `cd ~/Projects/sunrise_ansible_inventory && claude-work -p "Show me the failed systemd units on mars's Orin."` Expect one read-only ad-hoc command against one host.
5. **Commit:** `feat(ai): route everyday requests to skills and lint skill files`. **Arcane:** `milestone`, title `Everyday skills live in every harness`, details listing the four end-to-end results.

---

## Appendix: why skills, not more AGENTS.md

- `AGENTS.md` is in every prompt of every harness; a skill costs tokens only when triggered.
- Skills can carry long, exact command sequences without bloating the always-on instructions.
- Skills are per-task testable through a single natural sentence, which is how they are verified here.
- The routing table in `AGENTS.md` is what makes them fire reliably; without it, models improvise.
