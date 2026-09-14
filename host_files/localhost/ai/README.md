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
  `ai_agents` role from `group_vars/macbooks.yml`, `host_files/localhost/ai/routing/`
  and source files here.

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

## Encrypted skills

A skill that names an employer's customers, sites or hosts is vault-encrypted
(`ansible-vault encrypt skills/<name>/SKILL.md`) and listed in
`ai_encrypted_skills` in `group_vars/macbooks.yml`. Those deploy as a decrypted
copy rather than a link, so edit them with `ansible-vault edit` and re-apply;
`check-unencrypted-secrets.py` refuses a plaintext commit of them, and
`check-skills.sh` lints their plaintext when the vault password is present.

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

## Lead-only skills

Every skill still deploys to every harness, but the skills listed in
`ai_lead_only_skills` (`group_vars/macbooks.yml`) are lead procedures: `build`
dispatches, `ship` pushes and merges, `macbook` applies to this Mac. The
OpenCode renderer denies them to the worker, verifier, rescue, documentation
and scout agents through each agent's `permission.skill` map, because the
worker contract in `routing/prompts/worker.md` forbids exactly those acts. The
OpenCode orchestrator keeps the full set, so driving OpenCode directly still
routes "install jq" through `macbook`. Codex has no per-agent skill permission
and is unchanged.

## Claude Code plugins (per profile)

Each Claude profile declares its own `marketplaces` and `plugins` in
`ai_claude_profiles`. Plugins are per `CLAUDE_CONFIG_DIR`, so each profile
installs its own copy. Personal (`~/.claude`, the Claude Code app) carries
`caveman` only; work (`~/.claude-work`, what T3 Code launches) carries
`caveman` plus the Sunrise company plugins, so personal Claude holds no work
material. Skills under `skills/` still deploy to both.
`roles/ai_agents/tasks/claude_plugins.yml` adds each marketplace and installs
each plugin when missing, and `claude_settings.yml` enables the declared
plugins in `enabledPlugins` (additively: retiring one is
`claude plugin uninstall <name>` in that profile plus removing it from the list). `grafana-usage-report` moved there from `skills/` because the
two copies were byte-identical and the plugin carries the eval suite. Check a
plugin's projected token cost with `claude-work plugin details <name>` before
declaring a new one.

The paperclip skills are not here at all: they live in `Projects/paperclip` and
are linked straight from it (`ai_external_skills`), so that repo stays their
source of truth. They, `pdf`, `figma` and `notion-knowledge-capture` were
retired on 2026-09-12 and restored on 2026-09-14 when T3 Code became the
primary harness; `create-linear-ticket` and `fetch-linear-context` stay folded
into `linear`.

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

| Harness | Lead | Worker / verifier / rescue / documentation / scout | Notes |
|---|---|---|---|
| OpenCode | Native `orchestrator` primary agent (Sol medium) | Native subagents, one file each | Full native support; six managed agents plus managed commands. |
| Claude Code (personal, `~/.claude`) | Root/default profile, selected at Opus 5 medium | Native subagents under `~/.claude/agents/*.md` | Full native support; no custom `orchestrator` agent — the root profile *is* the lead. |
| Claude Code (work, `~/.claude-work`) | Same as personal | Native subagents under `~/.claude-work/agents/*.md`, byte-identical to personal | Same policy, isolated auth/state; this is what T3 Code's Claude provider runs. |
| Codex CLI (`~/.codex`) | Root CLI, `config.toml` top-level `model`/`model_reasoning_effort` pinned to lead tier | Native subagents under `~/.codex/agents/*.toml` | Full native support; `agents.default_subagent_model`/`default_subagent_reasoning_effort` in `config.toml` default new subagent threads to the worker tier. |
| T3 Code (Claude provider) | Inherited: same root profile as `claude-work`; primary harness, plans and implements | Native subagents under `~/.claude-work/agents/*.md`; OpenCode bridge (`build` skill → `oc-ticket`) only on explicit request (see "Claude plans, OpenCode builds" below) | No duplicate T3 agent definitions, and no live canary row (see below). T3 launches `~/.local/bin/claude-work`, which points `CLAUDE_CONFIG_DIR` at `~/.claude-work`; see `roles/ai_agents/tasks/t3.yml`. |
| T3 Code (Codex provider) | Inherited: same `~/.codex` as the CLI | Inherited: same `~/.codex/agents/*.toml` | No separate T3 entry needed, and no live canary row (see below); T3's Codex provider reads the same app-owned `config.toml`. |
| Forge 2.13.21 | N/A — Forge-owned built-in agents (Forge, Muse, Sage) | N/A | Shared `AGENTS.md` instructions and skills only. Forge 2.13.21 exposes no supported custom-agent authoring surface (`forge agent` only lists the three built-ins, no create/config subcommand), so it cannot host a native Luna worker. Do not claim parity with the other four harnesses. |

### Claude plans, OpenCode builds (opt-in)

T3 Code is the primary harness and Claude implements in it directly. The bridge
to OpenCode's builder is kept for when Dan asks for it by name:

- `workflow.yml` `bridges` declares the one bridge (`claude` → `opencode` via
  `oc-ticket`, roles worker/rescue/verifier, resume for the single correction);
  `scripts/validate-agent-routing.py` and `tasks/routing.yml` fail if it drifts.
- `host_files/localhost/bin/oc-ticket` wraps `opencode run --agent <role> --format
  json`, reads the final message back with `opencode export`, parses the eleven-field
  handoff, and exits 0 only on `COMPLETE`. OpenCode's worker, verifier and rescue are
  rendered `mode: all` so `--agent` can address them; a headless run never prompts
  (an `ask` permission is auto-rejected and reported as `BLOCKED_AUTHORITY`).
- `skills/build` is the procedure: plan mode, one self-contained ticket file per
  ticket, dispatch, review the real diff, one correction to the same OpenCode
  session, rescue on a repeated fingerprint, report. Its description only triggers
  on an explicit OpenCode request.
- `claude-edit-guard` and `claude-dispatch-guard` (`host_files/localhost/bin`) still
  deploy to `~/.local/bin` and keep their offline tests, but no profile hooks them.
  Re-enabling the enforced split means adding them back as `PreToolUse` hooks under
  `ai_claude_profiles[].hooks`.

`scripts/harness-usage-report.py` prints the numbers this design is judged by
(sessions per harness, dispatches by agent, models actually used, step-cap hits,
corrections, compactions); `make test-bridge` covers the bridge and guard offline.

### Documentation exception and Linear boundary

OpenCode keeps a command-only `documentation` agent alongside its delivery
roles and optional scout; Claude and Codex render `documentation` natively too. It is not part of the normal lead -> worker -> verifier ->
rescue engineering path — it exists to preserve the existing Linear MCP
permission boundary: only `documentation` (and the `linear` skill/command it
backs) may call Linear MCP tools or read/write Linear issues, projects,
comments and relations. Every other role — including lead/orchestrator and
worker — must delegate Linear reads and writes to `documentation` rather than
calling Linear MCP tools directly. Do not fold Linear access into the general
worker role; that would widen the permission boundary the split exists to
hold.

### T3 inheritance and runtime evidence

T3 launches `claude-work` for Claude and reads the shared `~/.codex` tree for
Codex. Static drift and idempotency checks prove that configuration inheritance.
CLI canaries exercise those providers, but do not prove identical T3 runtime
permissions or startup behavior. A fresh T3 thread supplies separate runtime
evidence; never infer it from a CLI result. Full access can override the Codex
scout's requested read-only sandbox. Existing sessions may retain old settings.

### Optional factual scout

The native `scout` uses worker tier with medium reasoning, does not preload
`execute-playbook`, and returns only findings, evidence, coverage, and unknowns.
Use it when broad repository discovery justifies a child call; keep small reads
direct. OpenCode denies tools by default and allows read/search; Claude exposes
only Read/Grep/Glob. Codex requests a read-only sandbox; MCP/delegation restrictions
remain prompt instructions rather than a complete tool allowlist.

Run `make test-scout` for offline accounting/correlation tests. The opt-in
`scripts/test-scout-routing-live.py --harness opencode|codex|claude-work` makes one
paid discovery call and checks actual child records. It does not prove economic
savings or write-denial enforcement. See the repository rollout document for
measured evidence and limitations.

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
hardcode a model ID anywhere else. Current tiers: `gpt-5.6-sol` / `claude-opus-5`
medium for lead, `gpt-5.6-luna` / `claude-sonnet-5` medium for worker,
`gpt-5.6-sol` / `claude-opus-5` high for rescue, `gpt-5.6-terra` /
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
T3 Code) both receive the same five native subagents — `worker`, `verifier`,
`rescue`, `documentation`, `scout` — rendered byte-identical from the same canonical
routing policy; `scripts/test-ai-agents-idempotency.sh` asserts the diff is
empty. Neither profile renders a custom `orchestrator` agent: the T3 execution
trace this design is based on used Claude's normal root profile at the lead
tier (Opus 5 medium) with explicit Sonnet-medium workers, not a custom primary
agent (`workflow.yml`'s `roles.orchestrator.limits.claude_max_turns` is `null`
for this reason). `execute-playbook` is preloaded into every rendered delivery agent
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
