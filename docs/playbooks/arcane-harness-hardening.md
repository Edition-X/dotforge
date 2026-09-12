# Playbook: Arcane harness hardening

**Status:** ready to execute
**Written:** 2026-09-05, from a usage audit of Arcane across Claude Code, Codex, OpenCode, T3 Code and Forge
**Audience:** an AI coding agent (Claude Sonnet, medium reasoning) working one ticket at a time
**Repos touched:** `~/Projects/dotforge` (this repo) and `~/Projects/arcane`

---

## 0. Read this first

### What you are fixing

Arcane is Dan's engineering-memory MCP server. It holds 1,497 memories across 74 projects. It is heavily used from OpenCode and Codex, lightly used from Claude Code, and **not wired at all** into the `claude-work` Claude profile that T3 Code drives. Several smaller defects reduce recall quality. This playbook fixes them as a series of small, independently verifiable tickets.

### Rules that apply to every ticket

1. **One ticket, one branch, one integration branch per repo.** Each repo has a long-lived integration branch, `integration/arcane-harness-hardening`, cut from `main`. Every ticket branch is created from the integration branch and, once reviewed, merged back into it with `--no-ff`. `main` is untouched until Dan reviews one PR from the integration branch. Never commit directly to `main` or to the integration branch.
2. **Never push, tag, or open a PR unless Dan explicitly says so in the current conversation.** Finish the ticket, verify, commit locally, then stop and report. Merging a ticket branch into the integration branch is the reviewer's job, not the implementer's.
3. **Never use `rm`.** Use `trash` for files that must go. For tracked files use `git rm`.
4. **Run the verification block before committing.** If any verification step fails, stop and report the exact failing command and output. Do not "fix forward" into a different ticket.
5. **Commit messages follow Conventional Commits** with a scope, matching each repo's history. Examples: `feat(ai): wire claude-work profile into ai_harnesses`, `fix(mcp): collapse worktree project variants`.
6. **After each commit, save one Arcane memory** using the CLI shown at the end of each ticket. The MCP tools may not be available in your session; the CLI always is. Never invent facts for the memory; describe what you actually did.
7. **Do not touch unrelated files.** Both repos have pre-existing untracked files (`docs/` here, `.scratch/` in arcane). Leave them alone unless a ticket says otherwise.
8. **Never write secrets** into any file, log, or memory. `~/.claude.json`, `~/.claude-work/.claude.json` and `~/.t3/userdata/settings.json` contain auth material. Only ever edit them through the commands given here.
9. **Ask before anything irreversible.** Deleting live data in `~/.arcane/index.db`, uninstalling tools, and rewriting user config files count as irreversible. Phase C spells out where to pause.

### Environment facts you can rely on

| Fact | Value |
|---|---|
| Installed Arcane binary | `/Users/dkelly/.local/bin/arcane` (symlink into the `arcane-mcp` uv tool, version `0.2.0b18`) |
| Dev checkout | `/Users/dkelly/Projects/arcane`, venv at `.venv`, version `0.2.0b19.dev0` |
| Arcane data | `~/.arcane/index.db` (SQLite, WAL mode) and `~/.arcane/vault/` |
| Personal Claude profile | `~/.claude` (`CLAUDE.md`, `settings.json`, `skills/`), state in `~/.claude.json` |
| Work Claude profile | `~/.claude-work`, launched via `~/.local/bin/claude-work` which exports `CLAUDE_CONFIG_DIR` |
| T3 Code | Drives Claude through `claude-work`; drives Codex through `~/.codex/config.toml` |
| Ansible entry points | `make ai` (apply the `ai` tag), `make check RUN_ARGS='--tags ai'` (dry run), `make lint`, `make ci`, `make test-ai-agents`, `make validate-opencode` |
| Arcane test entry points | `cd ~/Projects/arcane && source .venv/bin/activate && pytest -q && mypy src/arcane && ruff check src tests && ruff format --check src tests` |

### Integration branches

Create these once, before ticket A1 and B1 respectively. They already exist if `git branch --list 'integration/*'` prints them.

```bash
cd ~/Projects/dotforge && git checkout main && git pull --ff-only && git checkout -b integration/arcane-harness-hardening
cd ~/Projects/arcane      && git checkout main && git pull --ff-only && git checkout -b integration/arcane-harness-hardening
```

Lifecycle of one ticket:

1. Implementer: `git checkout integration/arcane-harness-hardening && git checkout -b <ticket-branch>`, do the work, verify, commit.
2. Reviewer: inspect `git diff integration/arcane-harness-hardening...<ticket-branch>`, re-run the ticket's verification block. Feedback goes back to the implementer on the same branch.
3. Reviewer, once satisfied: `git checkout integration/arcane-harness-hardening && git merge --no-ff <ticket-branch>` and re-run the repo's generic verification on the integration branch.
4. When every ticket in a phase is merged, Dan opens one PR: `integration/arcane-harness-hardening` into `main`.

Exception: B1's `spike/opencode-model-routing` is a parking branch, not a ticket branch. It is never merged anywhere. B1's effect on `main` is nil, so B2 onward branch from the integration branch as normal.

### Execution order

Phase A (this repo) and Phase B (arcane repo) are independent of each other. Within a phase, follow the numbered order. Phase C is live-data hygiene and runs last.

All ticket branches are cut from, and merge back into, `integration/arcane-harness-hardening` in their repo.

| Order | Ticket | Repo | Branch |
|---|---|---|---|
| 1 | A1 Remove echovault | dotforge | `chore/remove-echovault` |
| 2 | A2 Wire the `claude-work` profile | dotforge | `feat/claude-work-harness` |
| 3 | A3 Manage Claude MCP registration | dotforge | `feat/claude-mcp-registration` |
| 4 | A4 One Arcane path everywhere, pin the install | dotforge | `fix/arcane-install-path` |
| 5 | A5 SessionStart hook for Claude | dotforge | `feat/claude-session-start-hook` |
| 6 | A6 Tighten AGENTS.md rules | dotforge | `docs/agents-memory-rules` |
| 7 | A7 Drift checker covers MCP config | dotforge | `fix/drift-check-mcp` |
| 7b | A8 Test isolation and drift gaps from verification | dotforge | `fix/claude-mcp-test-isolation` |
| 7c | A9 Auto-bump Brewfile pin on Arcane release | both | `feat/arcane-release-dispatch`, `feat/auto-bump-arcane` |
| 8 | B1 Park the OpenCode analytics spike | arcane | `spike/opencode-model-routing` |
| 9 | B2 Collapse worktree project variants | arcane | `fix/collapse-worktree-projects` |
| 10 | B3 Stamp `source` from the MCP client | arcane | `feat/source-from-client-info` |
| 11 | B4 Stale journeys in `memory_context` | arcane | `feat/context-stale-journeys` |
| 12 | B5 Tool profiles | arcane | `feat/tool-profiles` |
| 13 | B6 Slimmer `memory_search` payload | arcane | `feat/search-detail-levels` |
| 14 | C  Live data hygiene | none (live DB) | no branch |

---

## Phase A: dotforge repo

Before every Phase A ticket:

```bash
cd ~/Projects/dotforge
git checkout integration/arcane-harness-hardening
git status --short        # expect only "?? docs/"
git checkout -b <branch-from-table>
```

After every Phase A ticket, the generic verification is:

```bash
make lint                 # ansible-lint + yamllint, must exit 0
make ci                   # lint + syntax-check, must exit 0
make check RUN_ARGS='--tags ai'   # dry run; read the diff, confirm only intended changes
```

---

### A1. Remove echovault

**Branch:** `chore/remove-echovault`
**Why:** echovault is a dead predecessor. The skill directory `host_files/localhost/ai/skills/echovault` declares `name: arcane` and teaches a CLI-flavoured memory discipline that competes with the MCP-flavoured one in `AGENTS.md`. Both load in every harness. The `uv "echovault"` tool also collides with Arcane on the `memory` entrypoint.

**Files:**
- `Brewfile` line ~310: `uv "echovault", source: "git+https://github.com/mraza007/echovault.git"`
- `host_files/localhost/ai/skills/echovault/` (whole directory)
- `roles/ai_agents/tasks/main.yml` (add a stale-symlink cleanup task)
- `host_files/localhost/ai/README.md` (only if it mentions echovault; grep first)

**Steps:**

1. Confirm the skill is the only echovault reference besides the Brewfile:
   ```bash
   grep -rn echovault --exclude-dir=.git --exclude-dir=venv --exclude-dir=node_modules .
   ```
   Expected: exactly two hits, `Brewfile` and `host_files/localhost/ai/skills/echovault/SKILL.md`. If there are others, read them and decide whether they are references to remove or unrelated.

2. Remove the Brewfile line for echovault. Do not touch the `uv "arcane"` line here; A4 handles it.

3. Remove the skill directory from git:
   ```bash
   git rm -r host_files/localhost/ai/skills/echovault
   ```

4. The role creates per-skill symlinks but never removes symlinks whose source has disappeared. Add a cleanup task to `roles/ai_agents/tasks/main.yml`, directly **after** the "Skills" symlink loop (around line 157, after the task that links each discovered skill) and **before** the external-skills tasks. Use this exact shape:

   ```yaml
   - name: AI agents - Find deployed skill links
     ansible.builtin.find:
       paths: "{{ item.skills }}"
       file_type: link
       depth: 1
     loop: "{{ ai_harnesses }}"
     loop_control:
       label: "{{ item.name }}"
     register: ai_agents_deployed_skill_links
     tags: [ai]

   # Ansible's `is exists` test does not follow symlinks, so it cannot tell a
   # dangling link from a live one. stat with follow=true can.
   - name: AI agents - Stat unmanaged skill links
     ansible.builtin.stat:
       path: "{{ item.1.path }}"
       follow: true
     loop: "{{ ai_agents_deployed_skill_links.results | subelements('files', skip_missing=True) }}"
     loop_control:
       label: "{{ item.1.path }}"
     when:
       - item.1.path | basename not in ai_agents_skills
     register: ai_agents_unmanaged_skill_links
     tags: [ai]

   - name: AI agents - Remove skill links whose target is gone
     ansible.builtin.file:
       path: "{{ item.item.1.path }}"
       state: absent
     loop: "{{ ai_agents_unmanaged_skill_links.results }}"
     loop_control:
       label: "{{ item.item.1.path if item.item is defined else 'skipped' }}"
     when:
       - item.skipped is not defined
       - not item.stat.exists
     tags: [ai]
   ```

   Only links whose name is not a known repo or external skill are stat'ed, and only those whose target no longer exists are removed. Skills Dan installed by hand are untouched: real directories are never returned by `file_type: link`, and live links to other locations pass the `exists` check.

5. Uninstall the tool. This is the one irreversible step in this ticket and it is intended:
   ```bash
   uv tool uninstall echovault
   uv tool list | grep -i echovault   # expect no output
   ls -la ~/.local/bin/memory          # expect a symlink into .../uv/tools/arcane-mcp/...
   ```
   If `~/.local/bin/memory` is missing after the uninstall, run `uv tool install --reinstall arcane-mcp --from "git+https://github.com/Edition-X/arcane.git@v0.2.0-beta.18"` to restore it, then re-check.

6. Apply and verify the dangling links are gone:
   ```bash
   make ai
   for d in ~/.claude/skills ~/.codex/skills ~/forge/skills ~/.config/opencode/skills ~/.config/devin/skills; do
     test -L "$d/echovault" -o -e "$d/echovault" && echo "STILL PRESENT: $d/echovault"
   done
   ```
   Expected: no `STILL PRESENT` lines. `test -L` matters: `test -e` follows the link and reports a dangling link as absent. Run `make ai` a second time and confirm `changed=0` in the recap for the ai_agents role.

**Verify:** generic block above, plus step 6.

**Commit:**
```
chore(ai): remove echovault skill and uv tool

The echovault skill declared itself as `arcane` and taught a CLI memory
discipline that competed with the MCP one in AGENTS.md. The uv tool also
collided with arcane-mcp on the `memory` entrypoint. Adds a cleanup task
so skill symlinks whose repo source disappears are removed on apply.
```

**Arcane memory:**
```bash
/Users/dkelly/.local/bin/arcane save --project dotforge --source claude-code --category decision \
  --title "Removed echovault skill and tool" \
  --what "Deleted host_files/localhost/ai/skills/echovault, the Brewfile uv entry, and the installed uv tool. Added an Ansible task that removes dangling skill symlinks." \
  --why "echovault was a predecessor of Arcane; its skill loaded in every harness with instructions that conflicted with AGENTS.md, and its uv tool competed for the memory entrypoint." \
  --impact "One memory discipline (AGENTS.md, MCP tools) instead of two. Skill removal is now safe: the role cleans up stale links." \
  --tags "echovault,arcane,skills,ansible"
```

---

### A2. Wire the `claude-work` profile

**Branch:** `feat/claude-work-harness`
**Why:** `~/.claude-work` is created empty by `roles/ai_agents/tasks/t3.yml`. It has no `CLAUDE.md`, no skills. Every T3 Code thread that uses Claude, and every terminal session started with `claude-work`, runs with no Arcane discipline and no shared skills. Adding it to `ai_harnesses` fixes instructions and skills. MCP registration is A3.

**Files:**
- `group_vars/macbooks.yml` (`ai_harnesses` list, around lines 65-85)
- `scripts/check-agent-config-drift.sh` (the two hardcoded arrays, lines ~20-34)
- `host_files/localhost/ai/README.md` (the list of link targets, lines ~10-14 and ~23-27)
- `README.md` (the T3 / claude-work section, lines ~170-184)

**Steps:**

1. Add a sixth entry to `ai_harnesses` in `group_vars/macbooks.yml`, after the `Claude Code` entry:
   ```yaml
     - name: Claude Code (work)
       dir: "{{ config_paths.claude_work_config }}"
       instructions: "{{ config_paths.claude_work_config }}/CLAUDE.md"
       skills: "{{ config_paths.claude_work_config }}/skills"
   ```

2. No task change is needed: the existing `Harness - Config directory` task already creates `item.dir` (mode 0700) for every harness before the symlink loop, so the new entry is covered.

3. In `scripts/check-agent-config-drift.sh`, add `"${HOME}/.claude-work/CLAUDE.md"` to `instruction_files` and `"${HOME}/.claude-work/skills"` to `skills_dirs`.

4. Update `host_files/localhost/ai/README.md`: add `~/.claude-work/CLAUDE.md` to the link-target list and, in the T3 paragraph, state that the work profile receives the same `AGENTS.md` and skills as the personal one. Update the root `README.md` T3 section the same way. Keep the wording short.

5. Apply and inspect:
   ```bash
   make check RUN_ARGS='--tags ai'    # expect new symlink for ~/.claude-work/CLAUDE.md and ~21 skill links
   make ai
   readlink ~/.claude-work/CLAUDE.md  # expect /Users/dkelly/Projects/dotforge/host_files/localhost/ai/AGENTS.md
   ls ~/.claude-work/skills | wc -l   # expect the same count as: ls ~/.claude/skills | wc -l
   diff <(ls ~/.claude/skills) <(ls ~/.claude-work/skills)   # expect no output
   make ai                            # second run: ai_agents changed=0
   ```

6. Prove Claude actually loads it. This spends a few tokens, that is fine:
   ```bash
   cd ~/Projects/arcane
   claude-work -p "Reply with only the first markdown heading of your global CLAUDE.md, nothing else."
   ```
   Expected output contains `Agent Instructions`. If it does not, stop and report; do not proceed to A3.

**Verify:** generic block, plus steps 5 and 6, plus `bash scripts/check-agent-config-drift.sh` reports no drift for `~/.claude-work`.

**Commit:**
```
feat(ai): wire claude-work profile into ai_harnesses

The isolated work profile that T3 Code drives had no CLAUDE.md and no
skills, so anything run through it had none of the canonical agent
instructions. Adds it as a sixth harness, ensures harness directories
exist before linking, and teaches the drift checker about it.
```

**Arcane memory:** category `bug`, project `dotforge`, title `claude-work profile had no instructions`. In `--what` state that `~/.claude-work` lacked `CLAUDE.md` and skills since the profile split on 2026-09-04, and that it is now a member of `ai_harnesses`. In `--why` state the root cause: `t3.yml` created the directory but the profile was never added to the harness list. Add `--details "Recognise it by: claude-work sessions never call memory_context and have no /skills. Check: readlink ~/.claude-work/CLAUDE.md."`

---

### A3. Manage Claude MCP registration

**Branch:** `feat/claude-mcp-registration`
**Why:** Arcane's MCP registration for Claude lives in `~/.claude.json` (personal, hand-edited, command is bare `arcane`) and is entirely absent from `~/.claude-work/.claude.json`. Nothing in the repo owns it. This ticket makes Ansible register Arcane in both profiles, using the absolute installed path, idempotently, through the `claude mcp` CLI. We use the CLI rather than templating `.claude.json` because that file is large, mutated constantly by Claude, and contains auth state.

**Files:**
- `group_vars/macbooks.yml` (new vars)
- `roles/ai_agents/tasks/claude_mcp.yml` (new file)
- `roles/ai_agents/tasks/main.yml` (include the new file)

**Steps:**

1. Add to `group_vars/macbooks.yml`, near `ai_harnesses`:
   ```yaml
   # Arcane MCP server binary. Every harness must use this exact path.
   ai_arcane_bin: "{{ config_paths.local_bin }}/arcane"

   # Claude Code profiles that receive managed MCP registrations and hooks.
   # config_dir holds settings.json, CLAUDE.md and skills. MCP state lives in
   # .claude.json, which for the personal profile is $HOME/.claude.json, NOT
   # ~/.claude/.claude.json, so the personal profile must run `claude` with
   # CLAUDE_CONFIG_DIR *unset* (the invoking shell may have it set, e.g. under
   # claude-work). claude_cmd encodes that per profile.
   ai_claude_profiles:
     - name: personal
       config_dir: "{{ user_dir }}/.claude"
       claude_cmd: "env -u CLAUDE_CONFIG_DIR claude"
     - name: work
       config_dir: "{{ config_paths.claude_work_config }}"
       claude_cmd: "env CLAUDE_CONFIG_DIR={{ config_paths.claude_work_config }} claude"
   ```

2. Create `roles/ai_agents/tasks/claude_mcp.yml`:
   ```yaml
   ---
   # Registers the arcane MCP server in each Claude Code profile through the
   # `claude mcp` CLI. We do not template ~/.claude.json: Claude rewrites that
   # file constantly and it carries auth state. The CLI is the supported path.
   #
   # Idempotency: `claude mcp get arcane` prints the current registration. We
   # only remove and re-add when it is missing or points at the wrong command.
   # Each profile's claude_cmd sets or unsets CLAUDE_CONFIG_DIR explicitly, so
   # the result does not depend on the shell that runs ansible.

   - name: Claude MCP - Inspect arcane registration
     ansible.builtin.command:
       cmd: "{{ item.claude_cmd }} mcp get arcane"
     loop: "{{ ai_claude_profiles }}"
     loop_control:
       label: "{{ item.name }}"
     register: ai_agents_claude_mcp_current
     failed_when: false
     changed_when: false
     check_mode: false
     tags: [ai, claude]

   - name: Claude MCP - Remove stale arcane registration
     ansible.builtin.command:
       cmd: "{{ item.item.claude_cmd }} mcp remove --scope user arcane"
     loop: "{{ ai_agents_claude_mcp_current.results }}"
     loop_control:
       label: "{{ item.item.name }}"
     when:
       - item.rc == 0
       - '("Command: " ~ ai_arcane_bin) not in item.stdout'
     changed_when: true
     tags: [ai, claude]

   - name: Claude MCP - Register arcane
     ansible.builtin.command:
       cmd: "{{ item.item.claude_cmd }} mcp add --scope user --transport stdio arcane -- {{ ai_arcane_bin }} mcp"
     loop: "{{ ai_agents_claude_mcp_current.results }}"
     loop_control:
       label: "{{ item.item.name }}"
     when: 'item.rc != 0 or ("Command: " ~ ai_arcane_bin) not in item.stdout'
     changed_when: true
     tags: [ai, claude]
   ```

3. Include it from `roles/ai_agents/tasks/main.yml`, directly after the existing `include_tasks: t3.yml` block, with the same `tags: [ai, claude]`.

4. Before applying, record the current state so you can prove the change:
   ```bash
   env -u CLAUDE_CONFIG_DIR claude mcp get arcane                      # personal: expect "Command: arcane"
   env CLAUDE_CONFIG_DIR=~/.claude-work claude mcp get arcane          # work: expect a "not found" error
   ```

5. Apply and verify:
   ```bash
   make ai
   env -u CLAUDE_CONFIG_DIR claude mcp get arcane | grep -E 'Command|Scope'
   env CLAUDE_CONFIG_DIR=~/.claude-work claude mcp get arcane | grep -E 'Command|Scope'
   ```
   Expected for both: `Scope: User config` and `Command: /Users/dkelly/.local/bin/arcane`. Then run `make ai` again and confirm the three Claude MCP tasks report `ok`, not `changed`.

6. Prove the tools are reachable in the work profile:
   ```bash
   cd ~/Projects/arcane
   claude-work -p "Call the arcane memory_context tool for this project and reply with only the number in its 'total' field."
   ```
   Expected: an integer. If the reply says the tool does not exist, stop and report.

**Verify:** generic block, plus steps 5 and 6.

**Commit:**
```
feat(ai): register arcane MCP in both Claude profiles via claude mcp

Registration was hand-managed in ~/.claude.json with a PATH-relative
command and missing entirely from the work profile. Ansible now inspects
and reconciles both profiles through the claude CLI, using the absolute
installed binary.
```

**Arcane memory:** category `decision`, project `dotforge`, title `Claude MCP registration managed via claude CLI`. `--details` must record the alternative considered (templating `.claude.json`) and why it was rejected (file is app-owned and holds auth state).

---

### A4. One Arcane path everywhere, pin the install

**Branch:** `fix/arcane-install-path`
**Why:** Four harnesses spell the Arcane command three different ways. Forge points at the dev venv (`/Users/dkelly/Projects/arcane/.venv/bin/arcane`) which runs uncommitted code. The Brewfile installs `uv "arcane"` from the local working tree, unpinned, and the package has since been renamed `arcane-mcp`, so `brew bundle check` cannot even see the installed tool.

**Files:**
- `roles/dotfiles/templates/forge.mcp.json.j2` line 4
- `roles/dotfiles/templates/zshrc.j2` (PATH export; see step 3a)
- `Brewfile` line ~309
- `README.md` (installation notes, if arcane is mentioned; grep first)

**Steps:**

1. In `forge.mcp.json.j2` replace the hardcoded venv path with `{{ ai_arcane_bin }}` (the variable from A3; if A3 is not merged into your branch, use `{{ config_paths.local_bin }}/arcane`).

2. In `Brewfile` replace the `uv "arcane"` line with:
   ```ruby
   uv "arcane-mcp", source: "git+https://github.com/Edition-X/arcane.git@v0.2.0-beta.18"
   ```
   The tag `v0.2.0-beta.18` is what is currently installed. Do not pick a newer tag; Phase B has not been released yet.

3a. `~/.local/bin` was only on PATH because the ForgeCode installer hand-edited `.zshrc`; the templated `.zshrc` would drop it on apply. Add to `roles/dotfiles/templates/zshrc.j2`, directly after the banner comment and before `plugins=(virtualenv)`:
   ```
   # uv tools, claude-work shim, arcane. Managed here so installers do not
   # have to hand-edit this file.
   export PATH="{{ config_paths.local_bin }}:$PATH"
   ```
   Then `make check RUN_ARGS='--tags dot'` and confirm the `.zshrc` diff shows only the installer line replaced by the managed export, plus the `~/forge/.mcp.json` change.

3. Check what brew bundle thinks:
   ```bash
   brew bundle check --file=Brewfile 2>&1 | grep -i arcane || echo "arcane-mcp satisfied"
   ```
   Expected: `arcane-mcp satisfied`. If brew bundle reports it missing, run `uv tool list | grep arcane-mcp` and report the discrepancy rather than reinstalling.

4. Apply the dotfiles role and verify Forge:
   ```bash
   make dotfiles
   jq -r '.mcpServers.arcane.command' ~/forge/.mcp.json
   zsh -lic 'command -v arcane'
   ```
   Expected: `/Users/dkelly/.local/bin/arcane` from both.

5. Confirm all harnesses now agree. This is read-only:
   ```bash
   jq -r '.mcpServers.arcane.command' ~/forge/.mcp.json
   grep -A2 'mcp_servers.arcane' ~/.codex/config.toml | grep command
   grep -o '"command": \[[^]]*\]' ~/.config/opencode/opencode.jsonc | head -1
   env -u CLAUDE_CONFIG_DIR claude mcp get arcane | grep Command
   env CLAUDE_CONFIG_DIR=~/.claude-work claude mcp get arcane | grep Command
   ```
   All five must show `/Users/dkelly/.local/bin/arcane`. Codex's `config.toml` is app-owned and not templated; if it disagrees, report it for Dan to fix by hand rather than editing it yourself.

**Verify:** generic block, plus steps 3 to 5.

**Commit:**
```
fix(ai): use the installed arcane binary everywhere and pin it

Forge's MCP template hardcoded the dev venv path, so Forge ran
uncommitted code while every other harness ran the release. The Brewfile
entry used the pre-rename package name and an unpinned local source.
Both now point at arcane-mcp v0.2.0-beta.18 via ~/.local/bin/arcane.
```

**Arcane memory:** category `decision`, project `dotforge`, title `Single arcane binary path across harnesses`. State the path, the pinned tag, and that the pin must be bumped after each Arcane release.

---

### A5. SessionStart hook for Claude

**Branch:** `feat/claude-session-start-hook`
**Why:** Claude Code sessions call `memory_context` in only 7 of 34 Arcane-using sessions over 60 days, versus near-universal use in OpenCode. A `SessionStart` hook injects the project context deterministically, so recall no longer depends on the model remembering to call the tool. Output is ~700 characters.

Also: A3's end-to-end check showed the work profile stops at a permission prompt for `mcp__arcane__memory_context` because its `settings.json` has no `permissions.allow` entry. This ticket adds `mcp__arcane` to `permissions.allow` in both profiles, as a set union so hand-added entries survive.

**Files:**
- `roles/ai_agents/tasks/claude_settings.yml` (new)
- `roles/ai_agents/tasks/main.yml` (include)
- `group_vars/macbooks.yml` (hook definition)

**Steps:**

1. Add to `group_vars/macbooks.yml`, below `ai_claude_profiles`:
   ```yaml
   # Managed Claude Code hooks. This list REPLACES the SessionStart list in each
   # profile's settings.json; all other settings keys are preserved.
   ai_claude_hooks:
     SessionStart:
       - matcher: "startup|resume|clear|compact"
         hooks:
           - type: command
             command: "{{ ai_arcane_bin }} context --project 2>/dev/null || true"
             timeout: 15

   # Tool permissions every Claude profile must pre-approve.
   ai_claude_permission_allow:
     - mcp__arcane
   ```

2. Create `roles/ai_agents/tasks/claude_settings.yml`. Follow the slurp-merge-write pattern already used in `t3.yml`:
   ```yaml
   ---
   # Merges managed hooks into each Claude profile's settings.json while
   # preserving every other key Dan has set by hand.

   - name: Claude settings - Check settings file
     ansible.builtin.stat:
       path: "{{ item.config_dir }}/settings.json"
     loop: "{{ ai_claude_profiles }}"
     loop_control:
       label: "{{ item.name }}"
     register: ai_agents_claude_settings_stat
     tags: [ai, claude]

   - name: Claude settings - Read existing settings
     ansible.builtin.slurp:
       src: "{{ item.stat.path }}"
     loop: "{{ ai_agents_claude_settings_stat.results }}"
     loop_control:
       label: "{{ item.item.name }}"
     when: item.stat.exists
     register: ai_agents_claude_settings_raw
     no_log: true
     tags: [ai, claude]

   - name: Claude settings - Build merged document
     ansible.builtin.set_fact:
       ai_agents_claude_settings_desired: >-
         {{ ai_agents_claude_settings_desired | default({}) | combine({
              item.item.item.name: (
                _existing | combine({'hooks': ai_claude_hooks}, recursive=True)
                          | combine({'permissions': {'allow': (
                              _existing_allow + (ai_claude_permission_allow | difference(_existing_allow))
                            )}}, recursive=True)
              )
            }) }}
     vars:
       _existing: "{{ (item.content | b64decode | from_json) if (item.content is defined) else {} }}"
       # Concat, not `union`: union goes through a Python set and reorders the
       # list on every run, which breaks idempotency.
       _existing_allow: "{{ (_existing.permissions | default({})).allow | default([]) }}"
     loop: "{{ ai_agents_claude_settings_raw.results }}"
     loop_control:
       label: "{{ item.item.item.name }}"
     no_log: true
     tags: [ai, claude]

   - name: Claude settings - Install merged settings
     ansible.builtin.copy:
       content: "{{ ai_agents_claude_settings_desired[item.name] | to_nice_json }}"
       dest: "{{ item.config_dir }}/settings.json"
       mode: "0600"
     loop: "{{ ai_claude_profiles }}"
     loop_control:
       label: "{{ item.name }}"
     no_log: true
     tags: [ai, claude]
   ```
   Note on the nested `item.item.item`: the slurp loop iterated over the stat results, which iterated over the profiles. If `ansible-lint` or a dry run complains about the path, print `item` with `debug` once (with `no_log` removed temporarily) to confirm the nesting, then restore `no_log`.

3. Include it from `main.yml` after the `claude_mcp.yml` include, tags `[ai, claude]`.

4. Dry-run first and read the diff carefully:
   ```bash
   make check RUN_ARGS='--tags claude'
   ```
   The diff for `~/.claude/settings.json` must show **only** a new `hooks` key. If any existing key (permissions, model, plugins) is removed or altered, stop and fix the merge before applying.

5. Apply and verify:
   ```bash
   make ai
   jq '.hooks.SessionStart[0].hooks[0].command' ~/.claude/settings.json
   jq '.hooks.SessionStart[0].hooks[0].command' ~/.claude-work/settings.json
   jq 'keys' ~/.claude/settings.json   # must still contain permissions, model, enabledPlugins, etc.
   jq '.permissions.allow | length' ~/.claude/settings.json      # unchanged from before (mcp__arcane was already present)
   jq '.permissions.allow' ~/.claude-work/settings.json          # ["mcp__arcane"]
   cd ~/Projects/arcane && /Users/dkelly/.local/bin/arcane context --project | head -3
   ```
   The last command is the hook body run by hand; expect `Available memories (N total, showing N):`.

6. End-to-end:
   ```bash
   cd ~/Projects/arcane
   claude-work -p "Your session-start hook injected a list of memories. Reply with only the count from its first line."
   claude-work -p "Call the arcane memory_context tool for this project and reply with only the number in its 'total' field."
   ```
   Expected: an integer from each, not a statement that nothing was injected and not a permission prompt.

**Verify:** generic block, steps 4 to 6, and `make ai` twice with the second run reporting no changes for the Claude settings task.

**Commit:**
```
feat(ai): inject arcane context at Claude session start

Claude Code called memory_context far less often than OpenCode or Codex.
A managed SessionStart hook now runs `arcane context --project` in both
profiles, so recall no longer depends on the model choosing to call it.
Hooks are merged into settings.json; all other keys are preserved.
```

**Arcane memory:** category `decision`, project `dotforge`, title `SessionStart hook injects Arcane context`. Note in `--details` that the managed list replaces `hooks.SessionStart` wholesale, so any hand-added SessionStart hook must move into `ai_claude_hooks`.

---

### A6. Tighten AGENTS.md rules

**Branch:** `docs/agents-memory-rules`
**Why:** Three instructions in `host_files/localhost/ai/AGENTS.md` cause measurable damage:
- "Project name: the current working directory name" makes agents pass worktree directory names (`sunrise-robot-sw-inf613`) as `project`, overriding Arcane's git-remote resolution and hiding the 538 main-project memories from those sessions.
- "Every git commit is a save trigger" produced 266 milestone memories, many of them `PR opened`, `routing committed`, `branch ready`. Git already holds these.
- No rule says what a milestone is.

**Files:** `host_files/localhost/ai/AGENTS.md` only.

**Steps:**

1. Replace the entire `### Project name` subsection with:
   ```markdown
   ### Project name

   Do not pass `project` to Arcane tools. Arcane resolves it from the git remote of the
   working directory, so worktrees, renamed checkouts, and underscore/hyphen variants all
   land on one project. Pass `project` only when the user names one, or when saving
   knowledge about a different repo than the one you are working in.
   ```

2. In the `### Save` subsection, replace the paragraph beginning `**Every git commit is a save trigger.**` with:
   ```markdown
   **A commit is a save trigger only when it carries a decision or a bug fix.** Save the
   decision or the bug, not the commit. Opening a PR, pushing, tagging a branch as ready, or
   updating a ticket are not memories; git and Linear already hold them.
   ```

3. In the save-trigger table, change the `milestone` row to:
   ```markdown
   | Feature merged to main, migration completed, or release shipped | `milestone` |
   ```

4. Add one sentence after the table:
   ```markdown
   Before saving, run `memory_search` on the title. If a near-identical memory exists,
   call `memory_update` on it instead of saving a duplicate.
   ```

5. Verify the file still reads cleanly and the caveman and safety sections are untouched:
   ```bash
   git diff --stat            # expect exactly one file
   git diff | grep '^[-+]' | grep -v '^[-+][-+]' | wc -l   # expect roughly 15 to 25 changed lines
   pre-commit run --all-files # includes the drift checker and secret scan
   ```

**Verify:** `make lint` and `pre-commit run --all-files` exit 0. Because `AGENTS.md` is symlinked, the change is live immediately; confirm with `head -5 ~/.claude/CLAUDE.md`.

**Commit:**
```
docs(ai): stop passing project, scope commit saves, define milestone

Agents were passing worktree directory names as `project`, splitting
memories away from the main repo. "Every commit is a save trigger"
produced commit-level milestones that duplicate git history. Arcane
resolves project from the git remote; instructions now say to omit it.
```

**Arcane memory:** category `decision`, project `dotforge`, title `AGENTS.md: omit project, milestone means shipped`. In `--details` cite the numbers: six worktree-variant projects holding 38 memories, 266 milestones before the rule.

---

### A7. Drift checker covers MCP config

**Branch:** `fix/drift-check-mcp`
**Why:** `scripts/check-agent-config-drift.sh` only checks instruction and skill symlinks. Every defect in A2 to A4 was invisible to it. It also has a stale command list (`linear.md`, `plan.md` missing), as does `scripts/check-opencode-source.sh`.

**Files:**
- `scripts/check-agent-config-drift.sh`
- `scripts/check-opencode-source.sh`

**Steps:**

1. In both scripts, add `linear.md` and `plan.md` wherever the other eight command files are listed (`opencode_managed_files` in the drift script, the command list around lines 26-28 in the source checker). Cross-check against `opencode_commands` in `group_vars/macbooks.yml`; the lists must match exactly.

2. In the drift script, add an MCP section after the OpenCode block and before the final summary. Keep the script's advisory contract: report, never fail.
   ```bash
   # --- Arcane MCP registration -------------------------------------------
   # Every harness must launch arcane through the installed binary. Keep in
   # step with ai_arcane_bin in group_vars/macbooks.yml.
   arcane_bin="${HOME}/.local/bin/arcane"

   check_mcp_command() {
       local label="$1" actual="$2"
       if [[ -z "${actual}" ]]; then
           drift "${label}: arcane MCP not registered"
       elif [[ "${actual}" != "${arcane_bin}" ]]; then
           drift "${label}: arcane MCP command is '${actual}', expected '${arcane_bin}'"
       fi
   }

   if command -v jq >/dev/null 2>&1; then
       if [[ -f "${HOME}/forge/.mcp.json" ]]; then
           check_mcp_command "Forge" "$(jq -r '.mcpServers.arcane.command // empty' "${HOME}/forge/.mcp.json")"
       fi
       if [[ -f "${HOME}/.config/opencode/opencode.jsonc" ]]; then
           # opencode.jsonc may contain comments; strip whole-line // comments only.
           # An unanchored pattern would also truncate URLs inside strings.
           check_mcp_command "OpenCode" "$(sed -E 's|^[[:space:]]*//.*$||' "${HOME}/.config/opencode/opencode.jsonc" | jq -r '.mcp.arcane.command[0] // empty')"
       fi
   fi
   if [[ -f "${HOME}/.codex/config.toml" ]]; then
       check_mcp_command "Codex" "$(awk '/^\[mcp_servers\.arcane\]/{f=1;next} /^\[/{f=0} f && /^command/{gsub(/.*= *"|"$/,""); print; exit}' "${HOME}/.codex/config.toml")"
   fi
   if command -v claude >/dev/null 2>&1; then
       # Personal profile state is $HOME/.claude.json, read only when
       # CLAUDE_CONFIG_DIR is unset. The work profile needs it set.
       check_mcp_command "Claude (personal)" \
           "$(env -u CLAUDE_CONFIG_DIR claude mcp get arcane 2>/dev/null | awk -F': ' '/^ *Command:/{print $2; exit}')"
       if [[ -d "${HOME}/.claude-work" ]]; then
           check_mcp_command "Claude (work)" \
               "$(env CLAUDE_CONFIG_DIR="${HOME}/.claude-work" claude mcp get arcane 2>/dev/null | awk -F': ' '/^ *Command:/{print $2; exit}')"
       fi
   fi
   ```
   Use whatever the script's existing reporting function is called (read the top of the file; it accumulates drift lines and prints them at the end). If there is no such function, add `drift() { drift_found=1; echo "drift: $*"; }` near the top and keep `exit 0` at the bottom.

3. Run it:
   ```bash
   bash scripts/check-agent-config-drift.sh
   ```
   If A2 to A4 are applied, expect no arcane drift lines. If you are running A7 before them, expect drift lines for exactly the defects those tickets fix; that is the script working.

4. Prove the checker catches a regression without changing live config: temporarily point `arcane_bin` in the script at a wrong path, run it, confirm every harness is reported, then revert.

**Verify:** `make lint`, `pre-commit run --all-files`, `shellcheck scripts/check-agent-config-drift.sh scripts/check-opencode-source.sh` (install shellcheck with brew if missing; report if you cannot).

**Commit:**
```
fix(scripts): drift checker validates arcane MCP wiring

The checker only looked at instruction and skill symlinks, so a missing
or mis-pathed arcane MCP registration in any harness went unnoticed.
Also adds the linear and plan commands to both stale command lists.
```

**Arcane memory:** category `pattern`, project `dotforge`, title `Drift checker must cover MCP config, not just symlinks`.

---

### A8. Test isolation and drift gaps from verification

**Branch:** `fix/claude-mcp-test-isolation`
**Why:** A full re-provision test of A1 to A7 found two defects.
1. `make test-ai-agents` runs the role against a fixture home (`user_dir` overridden to a temp dir with spaces). A3's personal-profile command, `env -u CLAUDE_CONFIG_DIR claude`, ignores `user_dir` and writes the **real** `$HOME/.claude.json`. The test run pointed Dan's live arcane registration at the fixture path. The work-profile command then failed with `rc=127` because the string form of `cmd` splits on the spaces in the fixture path. CI also runs this test on a runner with no `claude` binary at all.
2. The drift checker skips targets that are missing entirely (`[[ -e "$f" ]] || continue`, and `if [[ -f ~/forge/.mcp.json ]]`), so a torn-down `~/.claude-work/CLAUDE.md` or `~/forge/.mcp.json` is reported as clean.

Verified facts you can rely on: `claude` honours `HOME`; `env -u CLAUDE_CONFIG_DIR HOME=<dir> claude mcp add ...` writes `<dir>/.claude.json` and leaves the real one alone, including when `<dir>` contains spaces.

**Files:**
- `group_vars/macbooks.yml` (`ai_claude_profiles`)
- `roles/ai_agents/tasks/claude_mcp.yml`
- `scripts/check-agent-config-drift.sh`

**Steps:**

1. In `group_vars/macbooks.yml`, replace each profile's `claude_cmd` string with a `claude_argv` list, and update the comment above it:
   ```yaml
   # Claude Code profiles that receive managed MCP registrations and hooks.
   # config_dir holds settings.json, CLAUDE.md and skills. MCP state lives in
   # .claude.json: $HOME/.claude.json for the personal profile, and
   # <CLAUDE_CONFIG_DIR>/.claude.json for the work profile. claude_argv pins
   # both to user_dir so the idempotency test's fixture home never leaks into
   # the real one, and is a list so paths with spaces survive.
   ai_claude_profiles:
     - name: personal
       config_dir: "{{ user_dir }}/.claude"
       claude_argv:
         - env
         - -u
         - CLAUDE_CONFIG_DIR
         - "HOME={{ user_dir }}"
         - claude
     - name: work
       config_dir: "{{ config_paths.claude_work_config }}"
       claude_argv:
         - env
         - "CLAUDE_CONFIG_DIR={{ config_paths.claude_work_config }}"
         - claude
   ```

2. Rewrite `roles/ai_agents/tasks/claude_mcp.yml` so every command uses `argv`, and all three MCP tasks are skipped when `claude` is not installed (CI runners):
   ```yaml
   ---
   # Registers the arcane MCP server in each Claude Code profile through the
   # `claude mcp` CLI. We do not template ~/.claude.json: Claude rewrites that
   # file constantly and it carries auth state. The CLI is the supported path.
   #
   # Idempotency: `claude mcp get arcane` prints the current registration. We
   # only remove and re-add when it is missing or points at the wrong command.
   # Each profile's claude_argv pins HOME or CLAUDE_CONFIG_DIR to user_dir, so
   # neither the invoking shell nor the test fixture can redirect the write.

   - name: Claude MCP - Locate claude binary
     ansible.builtin.command:
       argv: [command, -v, claude]
     register: ai_agents_claude_binary
     failed_when: false
     changed_when: false
     check_mode: false
     tags: [ai, claude]

   - name: Claude MCP - Inspect arcane registration
     ansible.builtin.command:
       argv: "{{ item.claude_argv + ['mcp', 'get', 'arcane'] }}"
     loop: "{{ ai_claude_profiles }}"
     loop_control:
       label: "{{ item.name }}"
     register: ai_agents_claude_mcp_current
     failed_when: false
     changed_when: false
     check_mode: false
     when: ai_agents_claude_binary.rc == 0
     tags: [ai, claude]

   - name: Claude MCP - Remove stale arcane registration
     ansible.builtin.command:
       argv: "{{ item.item.claude_argv + ['mcp', 'remove', '--scope', 'user', 'arcane'] }}"
     loop: "{{ ai_agents_claude_mcp_current.results | default([]) }}"
     loop_control:
       label: "{{ item.item.name | default('skipped') }}"
     when:
       - ai_agents_claude_binary.rc == 0
       - item.skipped is not defined
       - item.rc == 0
       - '("Command: " ~ ai_arcane_bin) not in item.stdout'
     changed_when: true
     tags: [ai, claude]

   - name: Claude MCP - Register arcane
     ansible.builtin.command:
       argv: "{{ item.item.claude_argv + ['mcp', 'add', '--scope', 'user', '--transport', 'stdio', 'arcane', '--', ai_arcane_bin, 'mcp'] }}"
     loop: "{{ ai_agents_claude_mcp_current.results | default([]) }}"
     loop_control:
       label: "{{ item.item.name | default('skipped') }}"
     when:
       - ai_agents_claude_binary.rc == 0
       - item.skipped is not defined
       - 'item.rc != 0 or ("Command: " ~ ai_arcane_bin) not in item.stdout'
     changed_when: true
     tags: [ai, claude]
   ```
   Note `command -v` is a shell builtin; if `ansible.builtin.command` cannot run it, use `argv: [which, claude]` instead and say so.

3. In `scripts/check-agent-config-drift.sh`:
   - Instruction loop: replace `[[ -e "$f" ]] || continue` with logic that reports a missing file when its harness directory exists:
     ```bash
     if [[ ! -e "$f" ]]; then
         [[ -d "$(dirname "$f")" ]] && drift+=("${f/#$HOME/\~} is missing; harness dir exists but was never provisioned")
         continue
     fi
     ```
   - Forge MCP check: if `~/forge` exists but `~/forge/.mcp.json` does not, add drift `"Forge: .mcp.json missing"`. Keep the existing check when the file exists.
   - Work-profile MCP check: keep as is (it already reports "not registered" when the profile dir exists).

4. Verify, in this order:
   ```bash
   make lint && make ci
   make test-ai-agents          # must pass; watch for 'Claude MCP' tasks running against the fixture
   env -u CLAUDE_CONFIG_DIR claude mcp get arcane | grep -E 'Status|Command'   # real profile still Connected, real path
   make check RUN_ARGS='--tags ai'                                              # changed=0
   make ai                                                                       # changed=0
   ```
   Then prove the isolation directly: inspect the fixture. The test deletes its temp dir on exit, so temporarily run the playbook the way the script does but keep the dir: copy the `run_playbook` invocation from `scripts/test-ai-agents-idempotency.sh` into a one-off shell with `test_home=$(mktemp -d)/"home with spaces"`, run it once, then `jq -c '.mcpServers.arcane.command' "$test_home/.claude.json"` must print the fixture's `.local/bin/arcane`, and the real `env -u CLAUDE_CONFIG_DIR claude mcp get arcane` must still show `/Users/dkelly/.local/bin/arcane`. `trash` the temp dir after.

   Drift checker: `mv ~/forge/.mcp.json ~/.ai-config-backup/` and `mv ~/.claude-work/CLAUDE.md ~/.ai-config-backup/`, run the script, expect two drift lines naming both, then `make ai && make dotfiles` restores them and the script is clean again. Finally `shellcheck scripts/check-agent-config-drift.sh`.

**Commit:**
```
fix(ai): isolate claude mcp tasks to user_dir and use argv

The personal-profile command ignored user_dir, so the idempotency test
rewrote the real ~/.claude.json, and the string cmd split on spaces in
the fixture path. Both profiles now pin HOME or CLAUDE_CONFIG_DIR to
user_dir via argv lists, and all MCP tasks skip when claude is absent.
The drift checker now reports instruction files and Forge .mcp.json
that are missing outright, not only ones with wrong content.
```

**Arcane memory:** category `bug`, project `dotforge`, title `Idempotency test rewrote real ~/.claude.json`. `--details` must state how to recognise it (`claude mcp get arcane` shows a `/var/folders/.../ai-agents.*` path and `Failed to connect`) and the fix (`make ai`).

---

### A9. Auto-bump the Brewfile pin when Arcane releases

**Branches:** `feat/arcane-release-dispatch` in arcane, `feat/auto-bump-arcane` in dotforge
**Why:** Every merge to arcane `main` cuts a tag. The Brewfile pin in dotforge then lags until someone edits it. Dan wants this fully automatic with no manual PR. The install on the Mac itself stays manual (`git pull && make packages`); CI cannot run brew here.

**Design:** arcane's release workflow sends a `repository_dispatch` event to dotforge after the GitHub release exists. A new dotforge workflow receives it, verifies the tag is real, rewrites one Brewfile line, runs the repo's pre-commit hooks on that file, and commits straight to `main` as `github-actions[bot]` using the workflow's own `GITHUB_TOKEN`. Only the dispatch needs a cross-repo secret: a fine-grained PAT scoped to dotforge with Contents read/write, stored as the Actions secret `MACBOOK_PRO_DISPATCH_TOKEN` in the **arcane** repo. Not Ansible vault: CI cannot read vault, and the Mac never needs this token. The dispatch step is skipped, not failed, when the secret is absent so releases keep working before the secret exists.

**Part 1, arcane repo (`.github/workflows/release.yml`):**

Append after the "Create GitHub release" step:
```yaml
      - name: Notify dotforge to bump the Brewfile pin
        if: steps.version.outputs.skip != 'true' && env.DISPATCH_TOKEN != ''
        env:
          DISPATCH_TOKEN: ${{ secrets.MACBOOK_PRO_DISPATCH_TOKEN }}
          TAG: ${{ steps.version.outputs.tag }}
        run: |
          # Fine-grained PAT scoped to Edition-X/dotforge, Contents: read/write.
          # Skipped (not failed) when the secret is missing so releases never block on it.
          gh api --method POST repos/Edition-X/dotforge/dispatches \
            -H "Authorization: Bearer ${DISPATCH_TOKEN}" \
            -f event_type=arcane-released \
            -f "client_payload[tag]=${TAG}"
```
Note `gh api` normally uses `GH_TOKEN`; the explicit `Authorization` header overrides it. If `gh` refuses because no `GH_TOKEN` is set, set `GH_TOKEN: ${{ secrets.MACBOOK_PRO_DISPATCH_TOKEN }}` instead of the header and drop the `-H`. Do not print the token. Validate with `actionlint` if available (`brew install actionlint`), else `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/release.yml'))"`.

**Part 2, dotforge repo, new file `.github/workflows/bump-arcane.yml`:**
```yaml
name: Bump arcane pin

"on":
  repository_dispatch:
    types: [arcane-released]
  workflow_dispatch:
    inputs:
      tag:
        description: "Arcane release tag, e.g. v0.2.0-beta.19"
        required: true

permissions:
  contents: write

concurrency:
  group: bump-arcane
  cancel-in-progress: false

jobs:
  bump:
    name: Update Brewfile arcane-mcp pin
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
        with:
          ref: main

      - name: Resolve tag
        id: tag
        env:
          DISPATCH_TAG: ${{ github.event.client_payload.tag }}
          MANUAL_TAG: ${{ inputs.tag }}
        run: |
          TAG="${DISPATCH_TAG:-$MANUAL_TAG}"
          [[ "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-beta\.[0-9]+)?$ ]] || { echo "bad tag: $TAG" >&2; exit 1; }
          # Only accept tags that really exist upstream.
          git ls-remote --exit-code --tags https://github.com/Edition-X/arcane.git "refs/tags/$TAG" >/dev/null
          echo "tag=$TAG" >> "$GITHUB_OUTPUT"

      - name: Rewrite Brewfile pin
        id: edit
        env:
          TAG: ${{ steps.tag.outputs.tag }}
        run: |
          sed -i -E "s|^(uv \"arcane-mcp\", source: \"git\+https://github.com/Edition-X/arcane.git@)v[0-9][^\"]*(\")|\1${TAG}\2|" Brewfile
          grep -F "arcane.git@${TAG}\"" Brewfile
          if git diff --quiet -- Brewfile; then
            echo "changed=false" >> "$GITHUB_OUTPUT"
          else
            echo "changed=true" >> "$GITHUB_OUTPUT"
          fi

      - name: Run pre-commit on the Brewfile
        if: steps.edit.outputs.changed == 'true'
        run: |
          pipx run pre-commit run --files Brewfile

      - name: Commit and push
        if: steps.edit.outputs.changed == 'true'
        env:
          TAG: ${{ steps.tag.outputs.tag }}
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add Brewfile
          git commit -m "chore(brewfile): bump arcane-mcp to ${TAG}" \
                     -m "Automated by bump-arcane.yml from an arcane release. Apply locally with: git pull && make packages"
          git push origin HEAD:main
```
The `sed` must match the exact Brewfile line from A4. Test the regex locally first against a copy of the Brewfile with `sed -E ... | grep arcane`. `pipx run pre-commit` avoids a Python setup step; if the hooks in `.pre-commit-config.yaml` need tools the runner lacks (ansible-lint, yamllint are pip-installed by pre-commit itself; the local shell hooks only need bash), fall back to running just the secret-scan hook by id, and say so. Commits pushed with `GITHUB_TOKEN` do not trigger other workflows, so this cannot loop and will not fire `release.yml`.

Also add to `scripts/check-agent-config-drift.sh`, in the MCP section: if `brew` exists, `brew bundle check --file="${repo_root}/Brewfile" --no-upgrade 2>&1 | grep -qi arcane && drift+=("arcane-mcp: installed version does not match the Brewfile pin; run make packages")`. Read `brew bundle check` output format first to get the match right.

Validate with `actionlint` and `make lint`. Then test the dotforge workflow **manually** once it is on `main`: `gh workflow run bump-arcane.yml -f tag=v0.2.0-beta.18` (current pin, so it must exit with `changed=false` and no commit), then `gh run watch`.

**Commits:** arcane `ci(release): dispatch a Brewfile bump to dotforge after tagging`; dotforge `ci: auto-bump arcane-mcp Brewfile pin on release dispatch`.

**Arcane memory:** category `decision`, project `dotforge`, title `Arcane release auto-bumps Brewfile via repository_dispatch`, details covering why direct commit not PR, why PAT lives in arcane Actions secrets not vault, and the renewal date of the PAT.

---

## Phase B: arcane repo

Before every Phase B ticket:

```bash
cd ~/Projects/arcane
source .venv/bin/activate
git checkout integration/arcane-harness-hardening
git status --short    # expect clean (B1 must be done first; it removes the dirty tree)
git checkout -b <branch-from-table>
```

B1 is the exception: it starts from the dirty `main`, not from the integration branch. See its steps.

Generic verification for every Phase B ticket:

```bash
pytest -q                          # 464 passed after B1 (544 included the parked spike's 80 tests); must not decrease
mypy src/arcane                    # "Success: no issues found"
ruff check src tests && ruff format --check src tests
```

---

### B1. Park the OpenCode analytics spike

**Branch:** `spike/opencode-model-routing`
**Why:** The working tree has 636 lines of uncommitted changes plus two new plugins (`opencode_ingest.py`, `model_routing.py`) from 2026-08-13. Tests pass and the code is careful, but the feature is off-mission for a memory server: OpenCode-only cost analytics, a hand-maintained price table that goes stale, and an escalation heuristic that the design notes in `.scratch/wayfinder/` already call dead signal. Dan's decision is to remove it from `main`. We keep it recoverable on a branch.

**Steps:**

1. Confirm the dirty state matches expectations:
   ```bash
   git status --short
   ```
   Expected: 16 modified files and untracked `.scratch/`, `src/arcane/plugins/builtin/model_routing.py`, `src/arcane/plugins/builtin/opencode_ingest.py`, `tests/plugins/test_model_routing.py`, `tests/plugins/test_opencode_ingest.py`. If the list differs materially, stop and report.

2. Create the spike branch **from the dirty tree** and commit everything to it, including the design notes:
   ```bash
   git checkout -b spike/opencode-model-routing
   git add -A
   git status --short          # everything should now be staged (A/M), nothing untracked
   git commit -m "spike(analytics): OpenCode usage ingest and model-routing plugin

   Parked, not merged. Ingests ~/.local/share/opencode/opencode.db read-only
   into opencode_session artifacts and summarises cost per (agent, model,
   variant). Design notes and open questions are in .scratch/wayfinder/.
   Removed from main because it is off-mission for a memory server and
   carries a hand-maintained pricing table."
   ```

3. Return to `main`, confirm it is clean and green, then cut the integration branch if it does not exist yet:
   ```bash
   git checkout main
   git status --short          # expect NO output
   git branch --list 'integration/*' | grep -q arcane-harness-hardening || git checkout -b integration/arcane-harness-hardening
   git checkout main
   pytest -q                   # expect 480 passed (544 minus the 64 spike tests)
   mypy src/arcane && ruff check src tests
   ```
   The exact count may differ by a few; what matters is that it passes and that no `test_model_routing` or `test_opencode_ingest` file exists.

4. Confirm the docs on `main` do not mention the removed tools:
   ```bash
   grep -rn 'opencode_usage\|opencode-usage\|model-routing\|model_routing' README.md docs/ src/ pyproject.toml
   ```
   Expected: no output. If there are hits, they came from a committed change and need a separate small fix; report them.

**Verify:** step 3 and 4.

**Commit:** the single commit in step 2, on the spike branch. `main` receives no commit in this ticket.

**Arcane memory:**
```bash
/Users/dkelly/.local/bin/arcane save --project arcane --source claude-code --category decision \
  --title "Parked OpenCode model-routing analytics on a branch" \
  --what "Moved the uncommitted opencode_ingest and model_routing plugins, their 64 tests, and .scratch/wayfinder notes to branch spike/opencode-model-routing. main is clean." \
  --why "Off-mission for a memory server: OpenCode-only cost analytics with a hand-maintained price table and an escalation heuristic already judged dead signal." \
  --impact "main has 16 fewer modified files and no dirty tree. Work is recoverable from the branch if the idea returns." \
  --tags "spike,opencode,model-routing,cleanup" \
  --details "Options: merge as-is, finish the two open wayfinder tickets first, delete outright, park on branch. Chose park: zero maintenance cost, nothing lost. Forge previously ran this code live via the dev venv path; A4 in the dotforge playbook moves Forge to the installed binary."
```

---

### B2. Collapse worktree project variants

**Branch:** `fix/collapse-worktree-projects`
**Why:** `resolve_scope` already derives the project from the git remote, but when a caller passes `project` explicitly, the explicit value wins. Agents pass directory names, so worktrees produce `sunrise-robot-sw-inf613`, `sunrise-robot-sw-inf615v2`, etc. A6 tells agents to stop passing `project`; this ticket makes the server robust when they do anyway.

**Rule:** if an explicit project, after canonicalisation, equals the git-resolved project plus a `-` and a suffix, collapse it to the git-resolved project. Anything else is left alone, so a genuinely different explicit project still wins.

**Files:**
- `src/arcane/domain/scope.py`
- `src/arcane/services/memory.py` (lines ~311 and ~403, the two `canonicalize_project(project, ...)` calls in search and list/context)
- `tests/unit/test_scope.py`
- `tests/mcp/test_tool_handlers.py`

**Steps:**

1. In `scope.py`, add after `canonicalize_project`:
   ```python
   def collapse_project_variant(explicit: str, resolved: str) -> str:
       """Collapse a worktree-style variant of *resolved* back to *resolved*.

       Agents often pass the working-directory name as the project. For a git
       worktree that is ``<repo>-<suffix>`` (``sunrise-robot-sw-inf613``), which
       would split memories away from ``sunrise-robot-sw``. When *explicit* is
       ``resolved + "-" + anything`` we return *resolved*; otherwise *explicit*
       is returned untouched so a deliberately different project still wins.
       """
       if not explicit or not resolved or explicit == resolved:
           return explicit
       if explicit.startswith(resolved + "-"):
           return resolved
       return explicit
   ```

2. In `resolve_write_scope`, change the final return to apply the collapse:
   ```python
   slug = canonicalize_project(project, config.projects.aliases)
   return Scope(org=resolved.org, project=collapse_project_variant(slug, resolved.project))
   ```

3. Add a read-side helper in `scope.py`:
   ```python
   def resolve_read_project(project: str | None, config: ArcaneConfig, cwd: str | None = None) -> str | None:
       """Canonicalise an explicit *project* for reads, collapsing worktree variants.

       Returns ``None`` when *project* is ``None`` so callers keep their existing
       "no filter" behaviour.
       """
       if project is None:
           return None
       resolved = resolve_scope(cwd or os.getcwd(), config)
       slug = canonicalize_project(project, config.projects.aliases)
       return collapse_project_variant(slug, resolved.project)
   ```

4. In `services/memory.py`, at both places where `project = canonicalize_project(project, self.c.config.projects.aliases)` appears inside `search` and the list/context method, replace with `project = resolve_read_project(project, self.c.config)`. Update the import line at the top of the file. Be careful: only replace calls where `project` is the caller-supplied filter, not calls that canonicalise a stored value.

5. Tests. Add to `tests/unit/test_scope.py`:
   - `collapse_project_variant("sunrise-robot-sw-inf613", "sunrise-robot-sw") == "sunrise-robot-sw"`
   - `collapse_project_variant("sunrise-robot-sw", "sunrise-robot-sw") == "sunrise-robot-sw"`
   - `collapse_project_variant("monitoring-config", "sunrise-robot-sw") == "monitoring-config"`
   - `collapse_project_variant("sunrise-robot-sw2", "sunrise-robot-sw") == "sunrise-robot-sw2"` (no dash, no collapse)
   - `collapse_project_variant("", "x") == ""` and `collapse_project_variant("x", "") == "x"`
   - `resolve_write_scope("sunrise_robot_sw-inf613", config, _remote=("Sunrise-Robotics", "sunrise-robot-sw")).project == "sunrise-robot-sw"` (uses the existing `_remote` test seam; look at neighbouring tests for how `config` is built)
   - `resolve_write_scope("monitoring-config", config, _remote=("Sunrise-Robotics", "sunrise-robot-sw")).project == "monitoring-config"`

   Add to `tests/mcp/test_tool_handlers.py` one save test: with the remote seam or a monkeypatched `resolve_scope` returning project `repo`, `handle_save(..., project="repo-inf999")` stores project `repo`. Copy the fixture style of the surrounding save tests.

6. Update `docs/mcp-tools.md`: in the `project` parameter description for `memory_save`, `memory_search`, `memory_context`, add one sentence: "Worktree-style variants of the current repo (`<repo>-<suffix>`) collapse to `<repo>`."

**Verify:** generic block. Then an end-to-end check from a real worktree, read-only. The CLI's `--project` is a boolean flag, so use the service directly:
```bash
cd "$(ls -d ~/Projects/sunrise_robot_sw-* | head -1)"
~/Projects/arcane/.venv/bin/python -c "
from arcane.services.container import ServiceContainer
from arcane.services.memory import MemoryService
svc = MemoryService(ServiceContainer())
hits = svc.search('simulation CI', limit=3, project='sunrise-robot-sw-inf613')
print(len(hits), sorted({h['project'] for h in hits}))"
```
Expected: `3 ['sunrise-robot-sw']`, not zero results and not a shadow project.

**Commit:**
```
fix(scope): collapse worktree project variants to the repo project

Agents pass the working-directory name as `project`; in a git worktree
that is `<repo>-<suffix>`, which split memories into six shadow projects
and hid the main project's memories from those sessions. An explicit
project that is a dashed suffix of the git-resolved project now collapses
to it, on both write and read paths.
```

**Arcane memory:** category `bug`, project `arcane`, title `Worktree dir names fragmented projects`. `--details` must include how to recognise it (projects like `<repo>-inf123` in `arcane projects`), the root cause (explicit project overriding git-remote resolution), and that Phase C merges the six existing shadow projects.

---

### B3. Stamp `source` from the MCP client

**Branch:** `feat/source-from-client-info`
**Why:** `memories.source` is empty on 1,419 of 1,497 rows. The MCP `initialize` handshake carries the client name (`claude-code`, `codex`, `opencode`, etc.), so the server can stamp it on every save without asking the model to. This turns "which harness saved what" into a SQL query.

**Files:**
- `src/arcane/mcp_server/server.py` (`call_tool` around line 473)
- `src/arcane/mcp_server/tools/memory_tools.py` (`handle_save`, the `source=None` at line ~101)
- `tests/mcp/test_tool_handlers.py`

**Steps:**

1. In `server.py`, inside `call_tool`, before dispatch, derive the client name defensively. The low-level `Server` exposes it as `server.request_context.session.client_params.clientInfo.name`. Any attribute may be missing in tests, so wrap it:
   ```python
   def _client_name() -> str | None:
       try:
           params = server.request_context.session.client_params
           name = params.clientInfo.name if params and params.clientInfo else None
       except (LookupError, AttributeError):
           return None
       return slugify(name) if name else None
   ```
   Import `slugify` from `arcane.domain.scope`. Place the helper inside `create_server` (or whatever the enclosing function is) so it can see `server`.

2. Where `memory_save` is dispatched, pass `source=_client_name()` through to `handle_save`. Add a `source: str | None = None` keyword parameter to `handle_save` and use it in `RawMemoryInput(source=source, ...)` instead of the current `source=None`. If the caller passes a non-empty `source` in the tool arguments, the argument wins; otherwise use the client name. Do **not** add `source` to the tool's public JSON schema; it is server-derived.

3. Tests. In `tests/mcp/test_tool_handlers.py`:
   - `handle_save(..., source="codex")` results in a stored memory whose `source == "codex"` (look up via the service or repo the neighbouring tests use).
   - `handle_save(...)` with no source stores `None` or empty, unchanged from before.
   - A unit test for `_client_name` is awkward because it needs a request context. Instead, test the dispatch path: monkeypatch the name helper (or `server.request_context`) to return a fake client with `clientInfo.name = "Claude Code"` and assert the saved memory has `source == "claude-code"`. If the server module structure makes this impractical within 30 minutes, keep the two `handle_save` tests and note the gap in the commit body.

**Verify:** generic block. Then live, read-only after a real save from any harness:
```bash
sqlite3 ~/.arcane/index.db "SELECT source, COUNT(*) FROM memories WHERE created_at > date('now','-1 day') GROUP BY 1;"
```
Only meaningful once the release is installed; for now the unit tests are the proof.

**Commit:**
```
feat(mcp): stamp memory source from the MCP client name

`memories.source` was empty on 95% of rows because nothing set it. The
initialize handshake's clientInfo.name is now slugified and stored on
every memory_save unless the caller supplies source explicitly.
```

**Arcane memory:** category `decision`, project `arcane`, title `source stamped from MCP clientInfo`.

---

### B4. Stale journeys in `memory_context`

**Branch:** `feat/context-stale-journeys`
**Why:** 25 journeys are active, 18 of them untouched for more than 14 days. Nothing surfaces this to the agent. `memory_context` already appends unacknowledged insights; adding stale journeys there costs one small list and prompts the model to complete or abandon them.

**Files:**
- `src/arcane/mcp_server/tools/memory_tools.py` (`handle_context`, lines ~247-269)
- `src/arcane/infra/db/journey_repo.py` already has `list_stale_active(days, project)`; reuse it
- `tests/mcp/test_tool_handlers.py`
- `docs/mcp-tools.md`

**Steps:**

1. In `handle_context`, after the insights block, when `detail != "minimal"` and a project resolved:
   ```python
   stale = svc.c.journey_repo.list_stale_active(14, project=project_final)[:5]
   if stale:
       result["stale_journeys"] = [
           {"id": j["id"], "title": j["title"], "last_update": (j.get("updated_at") or "")[:10]}
           for j in stale
       ]
       result["message"] = (result.get("message") or "") + (
           f" {len(stale)} active journey(s) idle >14 days: call journey_complete or journey_abandon."
       )
   ```
   Check how `handle_context` reaches the journey repo; if the memory service container does not expose `journey_repo` under that name, grep `container.py` for the attribute and use it.

2. Tests: one that seeds an active journey with `updated_at` 20 days ago and asserts `stale_journeys` has length 1; one that seeds a fresh journey and asserts the key is absent; one with `detail="minimal"` asserting the key is absent.

3. Document the new field in `docs/mcp-tools.md` under `memory_context`.

**Verify:** generic block.

**Commit:**
```
feat(mcp): surface idle journeys in memory_context

Active journeys idle for more than 14 days are now listed (max 5) in
memory_context output with a one-line prompt to complete or abandon
them. 18 of 25 active journeys were stale at the time of writing.
```

**Arcane memory:** category `decision`, project `arcane`, title `memory_context lists idle journeys`.

---

### B5. Tool profiles

**Branch:** `feat/tool-profiles`
**Why:** The server registers 26 tools, about 2,200 tokens of schema per session. Across every harness and all time, `link`, `trace`, `insights_ack`, `draft_blog`, `draft_adr`, `ingest_git`, `ingest_gha`, `ingest_linear`, `analyze`, `artifact_details`, `journey_delete`, and `memory_delete` were each called fewer than ten times. A `core` profile drops them by default; `ARCANE_TOOL_PROFILE=full` restores them.

**Files:**
- `src/arcane/mcp_server/server.py` (`list_tools` at line ~80, dispatch table at ~478)
- `tests/mcp/` (new test file `test_tool_profiles.py`)
- `docs/mcp-tools.md`, `README.md`, `CLAUDE.md` environment table

**Steps:**

1. Define in `server.py`, module level:
   ```python
   CORE_TOOLS = frozenset({
       "memory_save", "memory_search", "memory_context", "memory_details", "memory_update",
       "journey_start", "journey_update", "journey_complete", "journey_abandon",
       "journey_list", "journey_show", "artifact_search", "insights",
   })

   def _tool_profile() -> str:
       value = os.environ.get("ARCANE_TOOL_PROFILE", "core").strip().lower()
       return value if value in {"core", "full"} else "core"
   ```

2. In `list_tools`, after the full list is built, filter: if `_tool_profile() == "core"`, return only tools whose `name` is in `CORE_TOOLS`. Preserve order.

3. In `call_tool`, if the profile is `core` and the requested name is registered but not in `CORE_TOOLS`, return an error result whose text is: `Tool '<name>' is not enabled. Start the server with ARCANE_TOOL_PROFILE=full to use it.` Use the same error-result construction the dispatcher already uses for unknown tools.

4. Tests in `tests/mcp/test_tool_profiles.py`:
   - default (env unset, use `monkeypatch.delenv(..., raising=False)`) lists exactly `len(CORE_TOOLS)` tools and every name is in `CORE_TOOLS`.
   - `ARCANE_TOOL_PROFILE=full` lists 26 tools (or whatever the full count is on `main` after B1; assert against the length of the dispatch table rather than a literal).
   - `ARCANE_TOOL_PROFILE=bogus` behaves as `core`.
   - calling `trace` under `core` returns the not-enabled error; under `full` it dispatches.
   Look at `tests/mcp/test_resource_handlers.py` for how the server is instantiated in tests.

5. Docs: add `ARCANE_TOOL_PROFILE` to the environment table in `CLAUDE.md` and `README.md`; in `docs/mcp-tools.md` mark each tool `core` or `full`.

**Verify:** generic block. Then a stdio smoke test that the full profile still advertises everything:
```bash
ARCANE_TOOL_PROFILE=full pytest -q tests/integration/test_installed_mcp.py -m artifact 2>&1 | tail -3
```
If that test is marked to skip locally, say so in your report rather than forcing it.

**Commit:**
```
feat(mcp): add core/full tool profiles, default core

26 tools cost ~2.2k tokens of schema per session while half were almost
never called. ARCANE_TOOL_PROFILE=core (default) advertises the 13
memory, journey, artifact-search and insights tools; full restores the
rest. Calling a hidden tool returns a clear error naming the flag.
```

**Arcane memory:** category `decision`, project `arcane`, title `Tool profiles: core by default`. `--details` lists the core set and the usage numbers that justified it.

---

### B6. Slimmer `memory_search` payload

**Branch:** `feat/search-detail-levels`
**Why:** In OpenCode, `memory_search` output averages 9,000 characters and peaks at 50,000, because every hit carries full `what`, `why`, and `impact`. `memory_context` already has `detail=minimal|standard|full`. Give `memory_search` the same, with `standard` dropping `why` and `impact` (fetch via `memory_details`).

**Files:**
- `src/arcane/mcp_server/server.py` (`memory_search` schema)
- `src/arcane/mcp_server/tools/memory_tools.py` (`handle_search`, lines ~119-161)
- `tests/mcp/test_tool_handlers.py`
- `docs/mcp-tools.md`

**Steps:**

1. Add `detail` to the `memory_search` input schema: `{"type": "string", "enum": ["minimal", "standard", "full"], "default": "standard", "description": "minimal: id, title, category, score. standard: adds what, tags, project, date, has_details. full: adds why and impact."}`.

2. In `handle_search`, accept `detail: str = "standard"` and shape each hit accordingly. Reuse the field-selection approach in `handle_context` (lines ~213-245) rather than duplicating; if the two shapes can share one helper, extract it. Unknown `detail` falls back to `standard`, matching `handle_context`.

3. Tests: three cases (one per level) asserting exact key sets on a hit; one asserting `full` equals the pre-change shape so existing consumers can opt back in.

4. Update `docs/mcp-tools.md`. Also update the `memory_search` description constant in `memory_tools.py` (`SEARCH_DESCRIPTION`) with one sentence: "Results omit why/impact by default; call memory_details for the full body."

**Verify:** generic block.

**Commit:**
```
feat(mcp): add detail levels to memory_search, default standard

Search results carried full why/impact for every hit, averaging 9k
characters per call in OpenCode. standard now returns id, title, what,
category, tags, project, date, score and has_details; full restores the
previous shape.
```

**Arcane memory:** category `decision`, project `arcane`, title `memory_search returns standard detail by default`.

---

### After Phase B: release

Do **not** tag or push. When Dan merges the integration PR into `main`, the release workflow on `main` cuts the tag. After that release exists, update the Brewfile pin from A4 to the new tag in a one-line commit on a `chore/bump-arcane-pin` branch, then `brew bundle install` and re-run the A4 step 5 checks.

---

## Phase C: live data hygiene

No branch. This operates on `~/.arcane/index.db`. Take a backup first. Do the reversible parts, then **stop and present the journey list to Dan** before touching journeys.

1. Backup:
   ```bash
   sqlite3 ~/.arcane/index.db "PRAGMA wal_checkpoint(TRUNCATE);"
   cp ~/.arcane/index.db ~/.arcane/index.db.bak-hygiene-$(date +%Y%m%d-%H%M%S)
   ```

2. Merge the six shadow projects. Dry-run each first, read the count, then apply:
   ```bash
   A=/Users/dkelly/.local/bin/arcane
   for src in sunrise-robot-sw-inf613 sunrise-robot-sw-inf615v2 sunrise-robot-sw-inf597 sunrise-robot-sw-inf615-nightly; do
     $A merge-projects "$src" sunrise-robot-sw          # dry run, shows N memories
     $A merge-projects "$src" sunrise-robot-sw --apply
   done
   $A merge-projects sunrise-gha-runner-aws-nightly-sim sunrise-gha-runner-aws
   $A merge-projects sunrise-gha-runner-aws-nightly-sim sunrise-gha-runner-aws --apply
   $A merge-projects sunrise-gha-runner-aws-inf-579 sunrise-gha-runner-aws
   $A merge-projects sunrise-gha-runner-aws-inf-579 sunrise-gha-runner-aws --apply
   $A merge-projects inf501-attempt5-ws sunrise-robot-sw
   $A merge-projects inf501-attempt5-ws sunrise-robot-sw --apply
   ```
   Verify: `$A projects | grep -E 'inf6|inf5|nightly|attempt'` prints nothing.

3. Health check:
   ```bash
   $A analyze health
   ```
   Expected: the "fragmented project" finding is gone. Duplicate-title and empty-project findings remain; handle next.

4. The seven memories with an empty project are mixed (personal, dotforge, sunrise-robot-sw). `merge-projects '' <dest>` would move all seven to one project, which is wrong for some. List them for Dan and let him assign:
   ```bash
   sqlite3 -header -column ~/.arcane/index.db "SELECT id, substr(created_at,1,10) d, title FROM memories WHERE project='';"
   ```
   **Stop here and ask.** Apply the assignments Dan gives with:
   ```bash
   sqlite3 ~/.arcane/index.db "UPDATE memories SET project='<dest>', updated_at=strftime('%Y-%m-%dT%H:%M:%f+00:00','now') WHERE id='<id>';"
   ```
   The FTS index updates via trigger. The vault markdown stays where it is; that is acceptable.

5. Three duplicate titles (`Cache-pack-suite stretch complete vs EDD` x3, `surface_gripper packed green on sim_core pin` x2, `INF-598 sim_integration land merged` x2). For each group, show Dan `what` and `created_at` for every copy and let him pick the survivor. Delete extras with `$A delete <id>`.

6. Stale journeys. Print the list and **stop**:
   ```bash
   sqlite3 -header -column ~/.arcane/index.db "SELECT id, project, substr(updated_at,1,10) upd, title FROM journeys WHERE status='active' AND updated_at < date('now','-14 days') ORDER BY updated_at;"
   ```
   For each one Dan marks done: `$A journey complete <id> --summary "<his words>"`. For each one he marks dropped there is no CLI abandon; use the `journey_abandon` MCP tool from a harness that has Arcane (OpenCode or Codex), or ask Dan to. Never abandon or complete without his per-journey answer.

7. Old backups: `trash ~/.arcane/index.db.bak-orgscope-20260620-134235 ~/.arcane/index.db.bak-orphanfix-20260711-011420` once Dan confirms.

8. Final: `$A analyze health` and paste the output into the report. Save one memory, category `milestone`, project `arcane`, title `Vault hygiene pass Sep 2026`, stating counts before and after.

---

## Appendix: numbers from the 2026-09-05 audit

Kept here so future work can measure against them.

| Metric | Value |
|---|---|
| Memories / projects / journeys | 1,497 / 74 / 168 (137 completed, 25 active, 6 abandoned) |
| Categories | decision 411, bug 302, milestone 266, learning 258, context 221, pattern 24, poc 14 |
| `source` populated | 78 of 1,497 |
| Active journeys idle >14 days | 18 |
| OpenCode, last 60 days | 439 of 526 sessions used Arcane; 538 search, 486 context, 286 save |
| Codex, last 60 days | 52 of 89 sessions; 87 search, 57 context, 69 save |
| Claude Code personal, last 60 days | 34 of 56 sessions; 14 search, 7 context, 25 save; 36% of searches empty |
| Claude Code work / T3 via Claude | 0 (no MCP registered) |
| Tool schema per session | 26 tools, ~8.7k chars, ~2.2k tokens |
| `memory_search` output in OpenCode | avg 9,049 chars, max 50,885 |
| `memory_context` output in OpenCode | avg 3,803 chars, max 31,582 |
| Shadow projects from worktree names | 6 projects, 38 memories |
