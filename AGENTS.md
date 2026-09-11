# dotforge repository rules

## Repository shape

- `site.yml` is Ansible playbook entry point.
- `make apply` installs configuration; `make check` previews it.
- `roles/ai_agents` owns shared harness instructions, skills, and OpenCode setup.
- `host_files/localhost/ai/` is source for shared AI files and OpenCode command files.
- `host_files/localhost/ai/routing/` is central, provider-neutral model-routing policy; `group_vars/macbooks.yml` holds OpenCode-specific install settings.

## Engineering rules

- Preserve pre-existing worktree changes. Inspect `git status` and diff before broad edits.
- Link hand-edited static files; template files that contain variables or secrets.
- Never commit credentials, OAuth state, machine caches, `node_modules`, or session databases.
- Run focused checks before broad checks. Do not report success when a command failed or was skipped.
- Keep OpenCode changes in bounded batches. Inspect actual diff before review and after corrections.
- Use `make validate-opencode` for config checks and `make test-ai-agents` for temporary-home idempotency checks.

## OpenCode deployment

- Source files deploy to `~/.config/opencode/` through `roles/ai_agents`; do not edit live generated files.
- Existing OpenCode config and colliding managed files are backed up once under `~/.ai-config-backup/opencode/`.
- OpenCode auth, caches, sessions, MCP OAuth state, and package files remain outside repository ownership.
- Native agents, variants, commands, task permissions, snapshots, and `subagent_depth` provide workflow behavior. Do not add Forge-named plugins without explicit approval.

## Verification order

1. `make validate-opencode`
2. `make test-ai-agents`
3. `make lint`
4. `make ci`
5. `make check RUN_ARGS='--tags ai'`
6. `make ai`
7. `make check RUN_ARGS='--tags ai'`

Restart OpenCode after configuration changes. OpenCode loads config at startup.
