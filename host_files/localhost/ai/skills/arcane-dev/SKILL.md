---
name: arcane-dev
description: Change Arcane's own code (bugs, features, MCP tools, CLI), release it, or update the version installed on this Mac. Use when Dan says "arcane bug", "add a tool to arcane", "change memory_search", "release arcane", "bump arcane", "update arcane on my mac", or "arcane is on an old version".
---

# Arcane Dev

Arcane is Dan's personal engineering memory MCP server, developed in
`~/Projects/arcane` and installed on this Mac as a `uv` tool pinned in this repo's
`Brewfile`. A request about Arcane is one of two different flows — pick the right one
before touching anything.

## 1. Two flows — pick one

Ask: **is the change in the arcane repo's code, or in what this Mac runs?**

- Code change (fix a bug, add a tool, change behaviour) → §2, work happens in
  `~/Projects/arcane`, ends in a PR. You never push to `main` there or merge your
  own PR.
- Deploy (this Mac is running an old version, bump the pin) → §3, work happens in
  this repo (`macbook-pro`), ends in `make packages`.

Don't mix them: a code change never edits the `Brewfile` pin itself (no tag exists
for unreleased code), and a deploy never edits arcane's source.

## 2. Code change flow

```bash
cd ~/Projects/arcane
git checkout main && git pull --ff-only
git checkout -b <type>/<kebab-description>
```

1. Read `CLAUDE.md` (project priorities: no regressions, type safety, DRY, test at
   boundaries) and the contributor half of `AGENTS.md` (architecture, DI via
   `ServiceContainer`, repository boundary, testing layout, "Adding a New MCP Tool").
2. Make the change. Tests at the service/repo boundary, not deep inside — mock DB
   and network there, per `CLAUDE.md`.
3. Verify, in this order:
   ```bash
   source .venv/bin/activate
   ruff format src tests
   ruff check src tests
   mypy src/arcane
   pytest -q
   ```
   Run `ruff format` before `ruff check` so formatting fixes don't fight the linter.
4. If the change touches the MCP surface (a tool added, removed, renamed, or its
   schema changed) also run:
   ```bash
   pytest -q tests/integration/test_installed_mcp.py -m artifact
   ```
   and update `docs/mcp-tools.md` if it documents that tool.
5. Commit with Conventional Commits, then:
   ```bash
   git push -u origin <branch>
   gh pr create --title "..." --body "Summary + test plan"
   ```
   This is the one place pushing is expected — `main` on arcane is branch-protected
   (PR required, 1 review, checks: Lint, Test on 3.11/3.12/3.13, installed-artifact
   smoke test — see `.github/workflows/ci.yml`). Tell Dan the PR URL; merging is his
   call, not yours.
6. Merging to `main` triggers `.github/workflows/release.yml` automatically (`on:
   push: branches: [main]`) — it cuts the next `v0.2.0-beta.N` tag, builds, smoke
   tests the installed artifact, and publishes a GitHub prerelease. No manual
   release step. Confirm this against the real file before relying on it — it can
   change.

## 3. Deploy flow (bump the version installed on this Mac)

First check installed vs. latest:

```bash
~/.local/bin/arcane --version
gh release list --repo Edition-X/arcane --limit 3
```

If the installed version already matches the latest tag, say so and stop — nothing
to deploy.

If not, hand off to the `macbook` skill for the actual change (it owns the
`Brewfile` and `make packages` process). The specific steps within that flow:

1. Confirm the target tag exists before pinning it: `git ls-remote --tags
   https://github.com/Edition-X/arcane.git`.
2. Edit the `uv "arcane-mcp", source: "git+https://github.com/Edition-X/arcane.git@vX"`
   line in `Brewfile` to the new tag.
3. `make packages`.
4. Verify:
   ```bash
   ~/.local/bin/arcane --version
   uv tool list | grep arcane-mcp
   bash scripts/check-agent-config-drift.sh
   ```
5. One live check through the work profile that the new tools actually load:
   ```bash
   claude-work -p "How many mcp__arcane__ tools do you have available?"
   ```
   Expect 13 under the default core profile (see §4).

Never install arcane from `~/Projects/arcane` or its `.venv` directly — the Mac
always runs the `uv tool`-installed copy pinned in `Brewfile`.

## 4. Things to know

- **Tool profiles.** `ARCANE_TOOL_PROFILE` env var, `core` (default) or `full`, read
  fresh on every call by `_tool_profile()` in `src/arcane/mcp_server/server.py` —
  not cached at import, so tests can toggle it with `monkeypatch`. `core` exposes
  only `CORE_TOOLS` (13 tools, same file): `memory_save`, `memory_search`,
  `memory_context`, `memory_details`, `memory_update`, `journey_start`,
  `journey_update`, `journey_complete`, `journey_abandon`, `journey_list`,
  `journey_show`, `artifact_search`, `insights`. Everything else (`memory_delete`,
  `journey_delete`, `artifact_details`, ingestion/content/intelligence tools, …) is
  `full`-profile only; calling one under `core` returns an error telling the caller
  to start the server with `ARCANE_TOOL_PROFILE=full`.
- **Where tool handlers live.** One file per tool group under
  `src/arcane/mcp_server/tools/`: `memory_tools.py`, `journey_tools.py`,
  `artifact_tools.py`, `content_tools.py`, `ingestion_tools.py`,
  `intelligence_tools.py`, `relationship_tools.py`.
- **Where the tool list and dispatch live.** `src/arcane/mcp_server/server.py` —
  `CORE_TOOLS` frozenset, `_create_server()`, the `list_tools`/`call_tool` handlers,
  and the `handlers` dict mapping tool name to handler call.
- **Project resolution.** Arcane tools resolve `project` from the git remote of the
  working directory — do not pass `project` unless the user names a different repo
  than the one you're in, or asks about a specific project explicitly.
- **Source stamping.** `memory_save` stamps `source` from the caller's client name
  unless the caller passes one explicitly (`server.py`, the `memory_save` handler
  lambda falls back to `_client_name()`).
- **Test markers.** `pyproject.toml` defines the `artifact` pytest marker ("builds
  and tests the installed package artifact"). CI's `test` job runs `pytest -q -m
  "not artifact"`; a separate `artifact` job runs just that marker. Local full runs
  (`pytest -q`) include both.

## 5. Never

- Push to arcane's `main` directly, or merge your own PR — Dan merges.
- Pin the `Brewfile` `uv "arcane-mcp"` line to a tag that doesn't exist yet — check
  `git ls-remote --tags` first.
- Install or run arcane from `~/Projects/arcane`'s venv as the Mac's live copy —
  the Mac runs the `uv tool` install only.
