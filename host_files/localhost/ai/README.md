# AI agent configuration

Source of truth for every AI harness on this machine. Deployed by the
`ai_agents` role as symlinks:

```bash
ansible-playbook site.yml --tags ai
```

- `AGENTS.md` — one canonical instruction file, linked to `~/.claude/CLAUDE.md`,
  `~/.codex/AGENTS.md`, `~/forge/AGENTS.md`, `~/.config/opencode/AGENTS.md`, and
  `~/.config/devin/AGENTS.md` (Devin's own global-rules convention — it also
  reads `~/.claude/CLAUDE.md` as a fallback, but this makes it explicit rather
  than incidental).
- `skills/` — one skill set, linked into all five harnesses.
- OpenCode config, agents, commands, and routing policy are rendered by the
  `ai_agents` role from `host_vars/localhost/opencode.yml` and source files here.

Edit here, never in the harness directories. Those are links back to this
directory, and `scripts/check-agent-config-drift.sh` reports it when they stop
being.

T3 Code needs no entry of its own: it drives the `claude` and `codex` binaries
with default home paths, so it picks up whatever those two have.

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

## OpenCode

OpenCode is managed by `make ai` or the full `make apply` path. Source files
deploy into `~/.config/opencode/`; auth, sessions, caches, package files, and
MCP OAuth state remain unmanaged. Restart OpenCode after applying changes.
Templates live under `roles/ai_agents/templates`; OpenCode command source files
live under `host_files/localhost/ai/opencode/commands`.

Central model policy lives in `host_vars/localhost/opencode.yml`. Current
assignments use `openai/gpt-5.6-terra` high for orchestration and hard debugging,
`openai/gpt-5.6-sol` high for architecture and independent review,
`openai/gpt-5.6-luna` medium for implementation, and
`openai/gpt-5.4-mini` low for exploration, mechanical work, deterministic tests,
and documentation. No `*-fast` model IDs are used.

Native commands:

- `/orchestrate <goal>` — full plan, delegation, review, correction, and acceptance loop.
- `/implement-reviewed <feature or fix>` — bounded implementation with independent review.
- `/load-test-loop <target and safe environment>` — bounded, evidence-based performance loop.
- `/review <changes or revision range>` — read-only review plus deterministic checks.
- `/debug-loop <failure or defect>` — reproduce, prove root cause, fix, and verify.
- `/wayfinder <destination>` — explicitly load Wayfinder for long-horizon decision mapping.
- `/linear <request>` — delegate complete Linear reads or writes to `documentation`.
- `/plan <request>` — delegate user-visible implementation or technical planning to `reviewer`.
- `/grill <plan or idea>` — explicitly load the grilling skill; `/grilling` is an alias.

Routing boundary: explicit commands bind deterministically to existing specialists. Natural-language Linear requests are prompted to `documentation`; user-visible plans are prompted to `reviewer`. Non-documentation agents cannot call Linear MCP tools; the direct-API and shell-fallback prohibition remains prompt-enforced. `/wayfinder` stays orchestrator-owned because subagent depth is one; it must delegate reviewer planning first, then documentation Linear issue-tracker work as sibling tasks. This is prompted and permission-enforced routing, not a native deterministic semantic router.

Run `make validate-opencode` for config validation and `make test-ai-agents` for
deployment idempotency checks. Existing files are backed up once under
`~/.ai-config-backup/opencode/` before replacement.
