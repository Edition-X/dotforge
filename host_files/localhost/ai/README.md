# AI agent configuration

Source of truth for every AI harness on this machine. Deployed by the
`ai_agents` role as symlinks:

```bash
ansible-playbook site.yml --tags ai
```

- `AGENTS.md` — one canonical instruction file, linked to `~/.claude/CLAUDE.md`,
  `~/.codex/AGENTS.md`, `~/forge/AGENTS.md` and `~/.config/opencode/AGENTS.md`.
- `skills/` — one skill set, linked into all four harnesses.

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
is Claude-only, and the point of this directory is that all four harnesses get
the same set. The tradeoff is that upstream updates are a manual re-copy.

`wayfinder` depends on `grilling`, `domain-modeling`, `research` and
`prototype`; they are all here for that reason. It also expects a per-repo
tracker config — run `/setup-matt-pocock-skills` once in a repo before using
`/wayfinder` there.

The paperclip skills are not here at all: they live in `Projects/paperclip` and
are linked straight from it, so that repo stays their source of truth.
