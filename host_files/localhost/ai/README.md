# AI agent configuration

Source of truth for every AI harness on this machine. Deployed by the
`ai_agents` role as symlinks:

```bash
ansible-playbook site.yml --tags ai
```

- `AGENTS.md` — one canonical instruction file, linked to `~/.claude/CLAUDE.md`,
  `~/.claude-work/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/forge/AGENTS.md`, and
  `~/.config/opencode/AGENTS.md`.
- `skills/` — one skill set, linked into all five harnesses.
- OpenCode config, agents, commands, and routing policy are rendered by the
  `ai_agents` role from `host_vars/localhost/opencode.yml` and source files here.

Edit here, never in the harness directories. Those are links back to this
directory, and `scripts/check-agent-config-drift.sh` reports it when they stop
being.

T3 Code uses the managed `~/.local/bin/claude-work` executable for its Claude
provider. `claude` remains the personal/default profile and keeps using
`~/.claude`; `claude-work` sets `CLAUDE_CONFIG_DIR` to `~/.claude-work`.
The work profile is a harness like any other: it receives the same
`AGENTS.md` and skills as the personal profile. T3's provider settings are
preserved and updated by the `ai_agents` role in `~/.t3/userdata/settings.json`.
T3 must be restarted after applying changes.

## Adding a skill

Drop a directory under `skills/` and re-apply. The role discovers them with
`find` rather than from a list, so there is no role edit.

## Vendored skills

Some skills here are third-party, copied in rather than authored. Update them by
re-copying from upstream, not by editing in place.

| Skill | Upstream | Licence |
|---|---|---|
| `wayfinder` | [mattpocock/skills](https://github.com/mattpocock/skills) | MIT |
| `grilling` | [mattpocock/skills](https://github.com/mattpocock/skills) | MIT |
| `domain-modeling` | [mattpocock/skills](https://github.com/mattpocock/skills) | MIT |
| `research` | [mattpocock/skills](https://github.com/mattpocock/skills) | MIT |
| `prototype` | [mattpocock/skills](https://github.com/mattpocock/skills) | MIT |
| `setup-matt-pocock-skills` | [mattpocock/skills](https://github.com/mattpocock/skills) | MIT |

Vendored rather than installed as a Claude Code plugin because the plugin route
is Claude-only, and the point of this directory is that all five harnesses get
the same set. The tradeoff is that upstream updates are a manual re-copy.

`wayfinder` depends on `grilling`, `domain-modeling`, `research` and
`prototype`; they are all here for that reason. It also expects a per-repo
tracker config — run `/setup-matt-pocock-skills` once in a repo before using
`/wayfinder` there.

The paperclip skills are not here at all: they live in `Projects/paperclip` and
are linked straight from it, so that repo stays their source of truth.

## Lead-worker routing

Every harness follows the same provider-neutral policy under `routing/`
(`models.yml` for tiers/model IDs, `workflow.yml` for roles/limits,
`prompts/*.md` for the exact instructions each role gets). Harness renderers
in `roles/ai_agents` compile that one policy into native OpenCode, Claude Code
and Codex artefacts; `scripts/validate-agent-routing.py` and
`roles/ai_agents/tasks/routing.yml` both fail fast if it is malformed before
anything renders. The normal path is lead (medium) delegates one whole ticket
to worker (medium); lead reviews the real diff and evidence and can send one
correction back to the same worker; a second materially similar failure goes
to a fresh rescue (high) dispatch; a fresh verifier (medium) checks an
integrated batch before merge. See `execute-playbook` under `skills/` for the
full procedure.

### Support matrix

| Harness | Lead | Worker / verifier / rescue / documentation | Notes |
|---|---|---|---|
| OpenCode | Native `orchestrator` primary agent (Sol medium) | Native subagents, one file each | Full native support; five managed agents plus managed commands. |
| Claude Code (personal, `~/.claude`) | Root/default profile, selected at Fable medium | Native subagents under `~/.claude/agents/*.md` | Full native support; no custom `orchestrator` agent — the root profile *is* the lead. |
| Claude Code (work, `~/.claude-work`) | Same as personal | Native subagents under `~/.claude-work/agents/*.md`, byte-identical to personal | Same policy, isolated auth/state; this is what T3 Code's Claude provider runs. |
| Codex CLI (`~/.codex`) | Root CLI, `config.toml` top-level `model`/`model_reasoning_effort` pinned to lead tier | Native subagents under `~/.codex/agents/*.toml` | Full native support; `agents.default_subagent_model`/`default_subagent_reasoning_effort` in `config.toml` default new subagent threads to the worker tier. |
| T3 Code (Claude provider) | Inherited: same root profile as `claude-work` | Inherited: same files as Claude work profile | No duplicate T3 agent definitions. T3 launches `~/.local/bin/claude-work`, which points `CLAUDE_CONFIG_DIR` at `~/.claude-work`; see `roles/ai_agents/tasks/t3.yml`. |
| T3 Code (Codex provider) | Inherited: same `~/.codex` as the CLI | Inherited: same `~/.codex/agents/*.toml` | No separate T3 entry needed; T3's Codex provider reads the same app-owned `config.toml`. |
| Forge 2.13.21 | N/A — Forge-owned built-in agents (Forge, Muse, Sage) | N/A | Shared `AGENTS.md` instructions and skills only. Forge 2.13.21 exposes no supported custom-agent authoring surface (`forge agent` only lists the three built-ins, no create/config subcommand), so it cannot host a native Luna worker. Do not claim parity with the other four harnesses. |

### Documentation exception and Linear boundary

OpenCode keeps a fifth, command-only `documentation` agent alongside
worker/verifier/rescue; Claude and Codex render `documentation` as a fourth
native agent too. It is not part of the normal lead -> worker -> verifier ->
rescue engineering path — it exists to preserve the existing Linear MCP
permission boundary: only `documentation` (and the `linear` skill/command it
backs) may call Linear MCP tools or read/write Linear issues, projects,
comments and relations. Every other role — including lead/orchestrator and
worker — must delegate Linear reads and writes to `documentation` rather than
calling Linear MCP tools directly. Do not fold Linear access into the general
worker role; that would widen the permission boundary the split exists to
hold.

### T3 composer and CLI-flag overrides

T3's composer, or an explicit CLI flag passed for one session, can override
the root profile's selected model/effort for that session only (T3's
`state.sqlite` `model_selection_json` column records the actual per-thread
selection, and it can and does differ from the managed default — see
`projection_threads`). This is expected and not drift: it changes only which
model answers in the primary/root role for that one session. It does not
change what a *worker* subagent runs, because native worker agent files (for
Claude and Codex) pin their own `model`/effort fields independent of the root
selection — a session-level override to the root model never silently
changes which model a delegated ticket runs under.

## OpenCode

OpenCode is managed by `make ai` or the full `make apply` path. Source files
deploy into `~/.config/opencode/`; auth, sessions, caches, package files, and
MCP OAuth state remain unmanaged. Restart OpenCode after applying changes.
Templates live under `roles/ai_agents/templates`; OpenCode command source files
live under `host_files/localhost/ai/opencode/commands`.

Central, provider-neutral model policy lives in `routing/models.yml`; do not
hardcode a model ID anywhere else. Current tiers: `gpt-5.6-sol` / `claude-fable-5-1`
medium for lead, `gpt-5.6-luna` / `claude-sonnet-5` medium for worker,
`gpt-5.6-sol` / `claude-fable-5-1` high for rescue, `gpt-5.6-terra` /
`claude-opus-5` high for a senior tier mapped for provider completeness but not
part of default routing, and `gpt-5.4-mini` / `claude-haiku-4-5` low for a
utility tier outside the normal engineering path. No `*-fast` model IDs are
used.

Native agents: `orchestrator` (lead, primary), `worker`, `verifier`, `rescue`,
`documentation` (all subagents). Native commands:

- `/orchestrate <goal>` — full plan, delegation, review, correction, and acceptance loop.
- `/implement-reviewed <feature or fix>` — bounded implementation with independent review.
- `/load-test-loop <target and safe environment>` — bounded, evidence-based performance loop.
- `/review <changes or revision range>` — read-only review plus deterministic checks.
- `/debug-loop <failure or defect>` — reproduce, prove root cause, fix, and verify.
- `/wayfinder <destination>` — explicitly load Wayfinder for long-horizon decision mapping.
- `/linear <request>` — delegate complete Linear reads or writes to `documentation`.
- `/plan <request>` — read-only implementation or technical plan, owned directly by `orchestrator`.
- `/grill <plan or idea>` — explicitly load the grilling skill; `/grilling` is an alias.

Routing boundary: explicit commands bind deterministically to existing agents.
Natural-language Linear requests are prompted to `documentation`; `orchestrator`
plans and delegates every implementation ticket to `worker`, never implementing
one itself. Non-documentation agents cannot call Linear MCP tools; the
direct-API and shell-fallback prohibition remains prompt-enforced. This is
prompted and permission-enforced routing, not a native deterministic semantic
router.

Run `make validate-opencode` for config validation and `make test-ai-agents` for
deployment idempotency checks. Existing files are backed up once under
`~/.ai-config-backup/opencode/` before replacement.

## Claude Code and T3 Code

`claude` (personal, `~/.claude`) and `claude-work` (`~/.claude-work`, used by
T3 Code) both receive the same four native subagents — `worker`, `verifier`,
`rescue`, `documentation` — rendered byte-identical from the same canonical
routing policy; `scripts/test-ai-agents-idempotency.sh` asserts the diff is
empty. Neither profile renders a custom `orchestrator` agent: the T3 execution
trace this design is based on used Claude's normal root profile at the lead
tier (Fable medium) with explicit Sonnet-medium workers, not a custom primary
agent (`workflow.yml`'s `roles.orchestrator.limits.claude_max_turns` is `null`
for this reason). `execute-playbook` is preloaded into every rendered agent
through its `skills:` frontmatter key, so agent bodies carry only that role's
prompt rather than the full procedure.

T3 Code's Claude provider is pointed at the managed `~/.local/bin/claude-work`
executable with no `homePath` override in `~/.t3/userdata/settings.json`; this
is exactly how T3 inherits the work profile's agents rather than needing its
own. T3 must be restarted after applying changes.

## Codex

`~/.codex/agents/{worker,verifier,rescue,documentation}.toml` are rendered
from the same canonical policy (`routing/models.yml`, `routing/workflow.yml`),
mirroring the Claude agents above. `~/.codex/config.toml` is app-owned
(ChatGPT desktop); `scripts/codex-agent-settings-sync.py` surgically replaces
only the top-level `model`/`model_reasoning_effort` (pinned to the lead tier)
and `agents.*` keys (`enabled`, `max_concurrent_threads_per_session`,
`default_subagent_model`, `default_subagent_reasoning_effort`, pinned to the
worker tier), leaving every other section — `mcp_servers`, `[projects.*]`
trust levels, plugins, marketplaces, desktop settings — untouched, the same
way `scripts/codex-mcp-sync.py` already handles MCP server entries.

T3 Code's Codex provider reads this same `~/.codex` tree, so it needs no
separate agent files or config sync of its own.

## Forge

Forge 2.13.21 gets the shared `AGENTS.md` instructions and skill set like every
other harness, but no rendered custom agent: `forge agent` only lists the
built-in `Forge`, `Muse` and `Sage` agents, and this version exposes no
create/config subcommand or other supported custom-agent authoring surface.
Forge cannot host a native Luna/Sonnet worker; delegation inside Forge stays
prompt-level through the shared `execute-playbook` skill rather than a native
agent file. Do not claim Forge has parity with the other four harnesses.
