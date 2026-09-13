# Playbook: system-wide MCP servers via Docker MCP Toolkit

**Status:** ready to execute
**Written:** 2026-09-06
**Audience:** an AI coding agent (Claude Sonnet) working one ticket at a time, reviewed by a stronger model
**Repo:** `~/Projects/dotforge` (all tickets). Reads `~/Projects/Grafana_local_mcp` in M4 only.
**Companion:** `docs/playbooks/arcane-harness-hardening.md` established the conventions reused here (A3 `claude mcp` pattern, A5 settings merge pattern, A7/A8 drift checker).

---

## 0. Read this first

### Goal

One long-running Docker MCP Toolkit gateway on this Mac serves the Sunrise Robotics work servers (Grafana, Notion, Linear) over MCP Streamable HTTP at `http://127.0.0.1:8080/mcp`, authenticated with a bearer token. The toolkit profile is named `sunrise`; a `personal` profile with its own gateway and port can be added later without touching this one. Every AI harness (Claude personal, Claude work, Codex, OpenCode, Forge, Devin) points at that one URL. API keys live in the macOS Keychain via Docker Desktop's secrets API and never appear in any harness config. No browser OAuth, ever. Everything is deployed and drift-checked from this repo. Arcane is untouched: it stays a stdio uv tool because it resolves the project from the client's working directory.

### Rules that apply to every ticket

1. **One ticket, one branch, one integration branch.** Cut `integration/mcp-toolkit-gateway` from `main` once. Every ticket branch comes from it and is merged back `--no-ff` by the reviewer. `main` gets one PR at the end.
2. **Never push, tag, or open a PR** unless Dan says so in the current conversation.
3. **Never use `rm`.** `trash` for files, `git rm` for tracked files. Cleanup commands take one absolute path you have just printed with `ls -d`. Never `.`, `..`, `*`, or a variable that might be empty. `pwd` before any cleanup.
4. **Never print, log, echo, or paste a secret.** Not the Notion token, not the Grafana token, not the Linear key, not the gateway token, not vault contents. When a command would output a secret, pipe through `sed 's/./*/g'` or check only its length or its prefix (first 4 characters). Ansible tasks touching secrets carry `no_log: true`. The M0 findings file and every Arcane memory must contain no secret values.
4b. **No secret ever enters git, plaintext or history.** The only place a secret value may be written inside the repo is `host_vars/localhost/vault.yml`, and only through `ansible-vault edit`. Before every commit run the Secret hygiene checklist below. Never `git add -A` or `git add .`; add named files. If a secret was ever staged or committed, STOP and report; do not try to rewrite history yourself.
5. **Run every verification step before committing.** If one fails, stop and report the exact command and output. Do not switch to a different approach.
6. **Conventional Commits with scope**, matching this repo: `feat(mcp):`, `fix(mcp):`, `chore(mcp):`, `docs(mcp):`.
7. **After each commit, save one Arcane memory** with `/Users/dkelly/.local/bin/arcane save --project dotforge --source claude-code ...`. Describe what you actually did.
8. **Stop conditions are real stops.** Where a ticket says STOP, end your turn with the report. Do not improvise around it.
9. **`docs/` is untracked in this repo and stays that way.** Never `git add docs/`.
10. **Secret gate protocol.** When a ticket reaches a step that needs a secret or API key that is not yet in the vault, STOP and end your turn with a message to Dan in exactly this shape:
    - **What to create**, with the exact product path (menu by menu) and the exact scopes or capabilities to tick.
    - **Which account or workspace** to create it in (Sunrise Robotics workspaces, never personal).
    - **Exact vault key name** to store it under, and the exact commands to add it (`source venv/bin/activate; unset ANSIBLE_VAULT_PASSWORD_FILE; ansible-vault edit host_vars/localhost/vault.yml`), including the YAML line with a placeholder value.
    - **How you will verify** it is present without seeing it (a key-name grep on `ansible-vault view`).
    Then wait. When resumed, verify presence by name only and continue. Never ask Dan to paste a value into the chat.
11. **Docker MCP Toolkit is beta (v0.43.3 today).** Exact syntax for every subcommand is in `docs/research/mcp-toolkit-cli-2026-09.md` (M0 findings). Read it before M1 to M5. Key facts from it: `docker mcp secret set` is NOT idempotent (errors if the key exists; check `secret ls` first), `tool-name-prefix` yields `server__tool` names and needs a gateway restart, `/health` is the only unauthenticated endpoint, responses are SSE-framed even for request/response, `Accept: application/json, text/event-stream` is required. Never guess flags into a commit; test each command in the shell first.

### Environment facts

| Fact | Value |
|---|---|
| Docker | 29.7.2, Docker Desktop, MCP Toolkit CLI v0.43.3 (`docker mcp version`) |
| Toolkit state | `~/.docker/mcp/` holds `registry.yaml`, `config.yaml`, `tools.yaml`, `catalog.json`, `catalogs/docker-mcp.yaml`, `mcp-toolkit.db`. No profiles, no secrets, no servers enabled today. |
| Catalog entries | `grafana` (image `mcp/grafana@sha256:e51005e5…`, secret `grafana.api_key` → env `GRAFANA_API_KEY`, config `grafana.url` → env `GRAFANA_URL`, 50 tools). `notion-remote` (type `remote`, `https://mcp.notion.com/mcp`, OAuth provider `notion-remote`; the self-hosted `notion` image exists too but is not used). `linear` (type `remote`, `https://mcp.linear.app/mcp`, oauth provider `linear` with alternative secret `linear.personal_access_token` → env `LINEAR_PERSONAL_ACCESS_TOKEN`). |
| Gateway flags that matter | `--profile <id>`, `--transport streaming`, `--host 127.0.0.1`, `--port 8080` (never `--static` or `--long-lived`, see M2), `--block-secrets` (default on), `--verify-signatures` (default on), `--allow-unauthenticated` (we do NOT use it). Auth token read from env `MCP_GATEWAY_AUTH_TOKEN`. |
| Features | `tool-name-prefix` (off, we turn it on), `dynamic-tools` (on, we turn it off), `mcp-oauth-dcr` (on, leave), `oauth-interceptor` (off, leave), `use-embeddings` (off, leave). |
| Existing Grafana MCP | `~/Projects/Grafana_local_mcp`: compose, container `grafana-local-mcp-grafana-mcp-1` on `127.0.0.1:8000`, token in `.secrets/grafana-service-account-token`, `GRAFANA_URL` in `.env`, launchd `com.dkelly.grafana-local-mcp` running `scripts/ensure-running` every 300 s. Read-only (`--disable-write`). |
| Current harness MCP entries to replace | OpenCode template `roles/ai_agents/templates/opencode.jsonc.j2` has `grafana` (loopback 8000), `linear` and `notion` (hosted, OAuth). Codex `~/.codex/config.toml` (app-owned, hand-managed) has linear, notion, figma, grafana, playwright, node_repl. Forge `roles/dotfiles/templates/forge.mcp.json.j2` has linear (npx + `~/.env_secrets`), notion, grafana. Devin `~/.config/devin/mcp_config.json` (hand-managed) has two hosted linear entries and a hosted notion entry. Claude profiles: `notion` and `grafana` in personal `~/.claude.json`, only arcane in work. |
| OAuth state to retire | `~/.local/share/opencode/mcp-auth.json` (keys `linear`, `notion`). |
| Header support (M0 verified) | Claude: `claude mcp add --transport http <name> <url> --header "Authorization: Bearer …"`. Codex `config.toml`: `[mcp_servers.<name>] url = …` plus `http_headers = { Authorization = "Bearer …" }` (literal, works for the desktop app; `bearer_token_env_var` and `env_http_headers` also exist). OpenCode `remote`: `headers` object, `{env:VAR}` substitution supported. Devin `mcp_config.json`: `headers` object. Forge: unknown, docs unreachable; M3 tests it empirically and STOPs for Dan if headers are not honoured. |
| Vault | *Superseded 2026-09-14:* secrets now come from 1Password (`secrets_1password_items` in `group_vars/macbooks.yml`). At the time: `host_vars/localhost/vault.yml`, edited with `ansible-vault edit`. |
| Make targets | `make apply`, `make check RUN_ARGS='--tags mcp'`, `make lint`, `make ci`, `make test-ai-agents`, `make validate-opencode`. New: `make mcp`, `make mcp-test`. |
| Ansible env | Every ansible command from the repo root, venv active, `unset ANSIBLE_VAULT_PASSWORD_FILE`. `make` targets do this for you. |

### Secret hygiene checklist (run before every commit)

```bash
cd ~/Projects/dotforge
git status --short                                   # only the files you meant to change
head -c 14 host_vars/localhost/vault.yml              # must print $ANSIBLE_VAULT
git diff --cached | grep -nE 'ntn_[A-Za-z0-9]|glsa_[A-Za-z0-9]|lin_api_[A-Za-z0-9]|[0-9a-f]{64}|Bearer [A-Za-z0-9]' && echo "SECRET-LIKE STRING STAGED, STOP" || echo "staged diff clean"
pre-commit run --all-files                           # includes check-unencrypted-secrets
```
Jinja placeholders such as `Bearer {{ mcp_gateway_sunrise_token }}` are fine; the grep only fires on real-looking values. Files that legitimately hold secrets at runtime (`~/.config/mcp-gateway/sunrise/token`, rendered `opencode.jsonc`, `~/forge/.mcp.json`, `~/.claude*.json`) live outside the repo and are never copied in. If the grep fires, `git restore --staged <file>`, fix, and re-run. M6 runs a full-history scan with gitleaks.

### Ticket order

| Order | Ticket | Branch |
|---|---|---|
| 0 | M0 Spike: pin toolkit syntax, prove Linear token auth, confirm harness header support | `spike/mcp-toolkit-syntax` (findings file only, no code) |
| 1 | M1 Role `mcp_toolkit`: features, secrets, profile, tool allowlist | `feat/mcp-toolkit-role` |
| 2 | M2 Gateway as a launchd service with bearer auth | `feat/mcp-gateway-service` |
| 3 | M3 Point every harness at the gateway | `feat/mcp-harness-wiring` |
| 4 | M4 Retire the standalone Grafana MCP and OAuth state | `chore/retire-grafana-local-mcp` |
| 5 | M5 Drift checker and validator cover the gateway | `feat/mcp-drift-checks` |
| 6 | M6 End-to-end verification from three harnesses | no branch, report only |

---

## Secrets this playbook needs, and exactly how Dan provides each

All are Sunrise Robotics work credentials. Sonnet does not create any of them. When a ticket reaches a gate and the vault key is missing, Sonnet STOPs and repeats the relevant block to Dan (rule 10). Values go into the vault only:

```bash
cd ~/Projects/dotforge && source venv/bin/activate && unset ANSIBLE_VAULT_PASSWORD_FILE
ansible-vault edit host_vars/localhost/vault.yml
```

| Vault key | Needed by | Source |
|---|---|---|
| (none for Linear) | M1, M5 | **Decided 2026-09-06 after M0:** toolkit v0.43.3 ignores `linear.personal_access_token` and uses OAuth DCR. Dan ran `docker mcp oauth authorize linear` once (Sunrise workspace); the toolkit stores and refreshes the token in the Keychain. M1 checks `docker mcp oauth ls` shows `linear \| authorized` and STOPs with that one command if not. No vault key. |
| (none for Notion) | M1, M5 | **Decided 2026-09-06:** use the catalog `notion-remote` server (hosted `mcp.notion.com`) with OAuth, same as Linear. Dan runs `docker mcp oauth authorize notion-remote` once, signed in to the Sunrise Robotics workspace. It sees what Dan sees; no integration, no page sharing, no vault key. M1 checks `docker mcp oauth ls` shows `notion-remote \| authorized`. |
| `grafana_service_account_token` | M1 | Copy from `~/Projects/Grafana_local_mcp/.secrets/grafana-service-account-token` (Sunrise Grafana Cloud stack). Do not `cat` it in a shared session; `pbcopy < file`, then paste inside `ansible-vault edit`. |
| `grafana_url` | M1 | The `GRAFANA_URL=` value from `~/Projects/Grafana_local_mcp/.env`. Not secret, but lives beside its token. |
| `mcp_gateway_sunrise_token` | M2 | New. Generate locally: `openssl rand -hex 32 | pbcopy`, then paste inside `ansible-vault edit`. |

Verification Sonnet runs (names only, never values):
```bash
ansible-vault view host_vars/localhost/vault.yml | grep -oE '^(grafana_service_account_token|grafana_url|mcp_gateway_sunrise_token):' | sort
docker mcp oauth ls   # linear | authorized, notion-remote | authorized
```

---

## M0. Spike: pin toolkit syntax, prove Linear token auth, confirm harness header support

**Branch:** `spike/mcp-toolkit-syntax`. Writes one file: `docs/research/mcp-toolkit-cli-2026-09.md` (untracked dir; the file is the deliverable, later tickets read it). No other repo changes, no commit.
**Why:** The toolkit's per-subcommand `--help` is broken, and whether the hosted Linear server accepts a personal access token through the gateway is the single fact this whole plan depends on. Dan has said: no fallback for Linear. If it does not work, STOP.

All experiments happen in a scratch profile named `spike` and a scratch secret namespace so nothing here leaks into M1. Use only `ARCANE`-free, harness-free commands: do not run `docker mcp client connect`.

**Steps:**

1. **Syntax discovery.** For each command, run it with no arguments and record the exact usage line it prints:
   `docker mcp profile create`, `docker mcp profile server add`, `docker mcp profile server ls`, `docker mcp profile config`, `docker mcp profile tools`, `docker mcp profile show`, `docker mcp profile export`, `docker mcp profile import`, `docker mcp profile remove`, `docker mcp feature enable`, `docker mcp feature disable`, `docker mcp secret set`, `docker mcp secret ls`, `docker mcp secret rm`, `docker mcp oauth ls`, `docker mcp tools ls`. Also `docker mcp profile config` for how a server config value (`grafana.url`) is set.

2. **Create the scratch profile and add the three servers.** Record the exact commands that worked.

3. **Set scratch secrets** (values are throwaway strings, NOT real tokens): `notion.internal_integration_token`, `grafana.api_key`, `linear.personal_access_token`. Confirm `docker mcp secret ls` lists names only. Record whether `secret set` is idempotent (run twice) and whether `secret ls` reveals values (it must not).

4. **Gateway dry run**, streaming transport, with a throwaway `MCP_GATEWAY_AUTH_TOKEN`:
   ```bash
   MCP_GATEWAY_AUTH_TOKEN=spike-token docker mcp gateway run --profile spike --transport streaming --host 127.0.0.1 --port 8099 --dry-run
   ```
   Record: does it pull images, does signature verification pass for `mcp/grafana` and `mcp/notion`, what does it say about `linear` (remote), does it complain about missing OAuth. Then run without `--dry-run` in the background (`run_in_background`), and from another shell:
   - `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8099/mcp` → expect 401 or 403 (auth required).
   - Same with `-H "Authorization: Bearer spike-token"` and an MCP `initialize` POST body → expect 200 and a JSON-RPC result. Record the exact working curl, including the `Accept` and `Mcp-Session-Id` headers the gateway wants.
   - Is there a health endpoint (`/health`, `/healthz`, `/`)? Record status codes for each.
   - With `tool-name-prefix` enabled, list tools through the session and record the naming shape (e.g. `grafana__list_datasources` or `grafana:list_datasources`). This matters for M1's allowlist and M6's checks.
   Stop the gateway (`TaskStop` or `kill` by the PID you printed).

5. **Linear token proof, the gate.** Replace the scratch Linear secret with Dan's REAL key for this one test, without printing it:
   ```bash
   cd ~/Projects/dotforge && source venv/bin/activate && unset ANSIBLE_VAULT_PASSWORD_FILE
   ansible-vault view host_vars/localhost/vault.yml | awk -F': ' '/^linear_api_key:/{gsub(/"/,"",$2); print $2}' | docker mcp secret set linear.personal_access_token
   ```
   Start the gateway again (real token in place, throwaway gateway token is fine), and through an MCP session call one read-only Linear tool. The response must show the `sunrise-robotics-corporation` workspace or a Sunrise team; a different workspace means the vault holds the wrong key: STOP (rule 10, `linear_api_key` row). Call (whatever `tools/list` shows as the viewer or "me" style tool, or a list-teams tool). Record: did it return real data without any browser or OAuth prompt? Check `docker mcp oauth ls`: `linear` must NOT be listed as requiring authorization for the call to have worked via token.
   - **If it worked:** record the tool called and the shape of the response (no content, just field names). Continue.
   - **If it did not work** (401 from Linear, an OAuth URL printed, `oauth ls` says `linear | not authorized` and tools fail): STOP. Write the findings file with exactly what happened, then report to Dan: what the gateway said verbatim (redact tokens), and the two things he could decide between: (a) run `docker mcp oauth authorize linear` once and accept that this is a one-time browser step whose refresh token the toolkit then manages, or (b) drop Linear from the gateway. Do not pick for him. Do not proceed to M1.

   Afterwards, in either case, remove the real key from the toolkit: `docker mcp secret rm linear.personal_access_token`, and confirm with `secret ls`.

6. **Harness header support.** No config changes; read docs and current files only.
   - OpenCode: confirm `remote` entries accept `"headers": {"Authorization": "Bearer …"}` and whether `{env:VAR}` substitution works inside header values. Check the installed version's schema: `opencode --version`, then the JSON schema URL in `~/.config/opencode/opencode.jsonc` (`$schema`); fetch it and search for `headers`.
   - Codex: `~/.codex/config.toml` is read by the ChatGPT desktop app, which does not inherit shell env, so `bearer_token_env_var` is unusable there. Check whether config.toml supports a literal header table (`http_headers` or similar): `codex mcp add --help`, and grep the installed Codex docs or `codex --help` output. Record what works, or that only the env-var route exists.
   - Forge: confirm `.mcp.json` `headers` object is supported (Forge docs, or an existing example in `~/forge`).
   - Devin: confirm `mcp_config.json` header support (Devin docs). If no docs are reachable, say unknown.

7. **Cleanup.** `docker mcp profile remove spike`, `docker mcp secret rm` the two remaining scratch secrets, `docker mcp feature disable tool-name-prefix` if you enabled it. `docker mcp secret ls` and `docker mcp profile ls` must be empty. `docker ps` must show only the pre-existing Grafana container.

8. **Findings file** `docs/research/mcp-toolkit-cli-2026-09.md` with sections: Toolkit version; Exact commands (one fenced block per subcommand); Gateway HTTP contract (auth status codes, working curl, health endpoint or "none", tool-name prefix shape); Linear token result (PASS with tool name, or FAIL with verbatim redacted output); Harness header support table; Anything surprising. This file is the contract for M1 to M6.

**Report:** the findings file content, the Linear verdict in the first line, and the cleanup evidence.

---

## M1. Role `mcp_toolkit`: features, secrets, profile, tool allowlist

**Branch:** `feat/mcp-toolkit-role`
**Precondition:** M0 findings file exists with Linear PASS, and all five vault keys from the secrets table are present. Check with:
```bash
source venv/bin/activate; unset ANSIBLE_VAULT_PASSWORD_FILE
ansible-vault view host_vars/localhost/vault.yml | grep -oE '^(grafana_service_account_token|grafana_url|mcp_gateway_sunrise_token):' | sort
```
Expect three lines (`grafana_service_account_token`, `grafana_url`, `mcp_gateway_sunrise_token`). If fewer, STOP (rule 10) and repeat the exact block from the secrets table for each missing key. Also `docker mcp oauth ls` must show `linear | authorized` and `notion-remote | authorized`.

**Files:**
- `roles/mcp_toolkit/defaults/main.yml`, `roles/mcp_toolkit/tasks/main.yml`
- `group_vars/macbooks.yml` (non-secret settings), `site.yml` (add role, tags `[mcp, dot]`, after `dotfiles`), `Makefile` (`mcp`, `mcp-test`)
- `README.md` (section "MCP gateway")

**Design:**
- Everything through the `docker mcp` CLI, using the exact syntax from M0. Each mutating task is guarded by an inspect task so a second run is `changed=0`.
- Secrets are set from vault only when `docker mcp secret ls` lacks the name. A variable `mcp_toolkit_rotate_secrets: false` forces re-set when `true` (`make mcp RUN_ARGS='-e mcp_toolkit_rotate_secrets=true'`).
- Profile `sunrise` with servers `grafana`, `notion-remote`, `linear`. Config `grafana.url` from vault.
- Tool allowlist for Grafana keeps today's read-only posture. Allow exactly: `search_dashboards`, `get_dashboard_by_uid`, `get_dashboard_summary`, `get_dashboard_panel_queries`, `get_dashboard_property`, `list_datasources`, `get_datasource`, `query_prometheus`, `query_prometheus_histogram`, `list_prometheus_metric_names`, `list_prometheus_metric_metadata`, `list_prometheus_label_names`, `list_prometheus_label_values`, `query_loki_logs`, `query_loki_stats`, `query_loki_patterns`, `list_loki_label_names`, `list_loki_label_values`, `list_alert_groups`, `get_alert_group`, `list_incidents`, `get_incident`, `search_folders`, `get_annotations`, `get_annotation_tags`, `generate_deeplink`, `get_panel_image`, `list_oncall_schedules`, `list_oncall_users`, `list_oncall_teams`, `get_current_oncall_users`, `get_oncall_shift`, `list_sift_investigations`, `get_sift_investigation`, `get_sift_analysis`, `find_error_pattern_logs`, `find_slow_requests`, `query_pyroscope`, `list_pyroscope_label_names`, `list_pyroscope_label_values`, `list_pyroscope_profile_types`, `get_assertions`. Everything else (`create_*`, `update_*`, `add_activity_to_incident`, `alerting_manage_*`) stays off. Notion and Linear (both hosted): all tools.
- Features: enable `tool-name-prefix`, disable `dynamic-tools`.

**Steps:**

1. `group_vars/macbooks.yml`, new block:
   ```yaml
   # Docker MCP Toolkit: one gateway serving Grafana, Notion and Linear to every
   # harness over loopback. Secrets come from the vault and go into the macOS
   # Keychain through Docker Desktop; they never touch harness configs.
   mcp_toolkit_profile: sunrise
   mcp_toolkit_servers: [grafana, notion-remote, linear]
   mcp_toolkit_features_enabled: [tool-name-prefix]
   mcp_toolkit_features_disabled: [dynamic-tools]
   mcp_toolkit_grafana_read_tools: [ ...the list above... ]
   mcp_gateway_host: 127.0.0.1
   # One gateway process per profile. sunrise is work; a later personal profile
   # gets its own port (8081), label, token and harness entry.
   mcp_gateway_port: 8080
   mcp_gateway_url: "http://{{ mcp_gateway_host }}:{{ mcp_gateway_port }}/mcp"
   ```
   Secrets are referenced from vault variables only inside tasks, never copied into group_vars.

2. `roles/mcp_toolkit/tasks/main.yml`. Pattern for each area, with the real syntax from M0 substituted:
   - Preflight: `command: docker mcp version` (`changed_when: false`), fail with a clear message if Docker is not running (`docker info` rc != 0).
   - Features: inspect `docker mcp feature list`, enable/disable only when state differs.
   - Secrets: inspect `docker mcp secret ls` once. For `grafana.api_key` only, a `command` with `stdin: "{{ vault_value }}"` and `no_log: true`, `when: name not in listed or mcp_toolkit_rotate_secrets`. When rotating, `secret rm` first because `secret set` refuses to overwrite. Ignore the `docker/mcp/oauth-dcr/*` entries in `secret ls`; they are DCR client ids, not credentials.
   - OAuth servers: `command: docker mcp oauth ls` (`changed_when: false`); `assert` that stdout contains both `linear | authorized` and `notion-remote | authorized`, with `fail_msg` naming the missing one: "Run: docker mcp oauth authorize <provider> (sign in to the Sunrise Robotics workspace), then re-run make mcp". This is the only STOP in M1 besides the vault keys.
   - Profile: inspect `docker mcp profile ls`; create when missing. Inspect `profile show sunrise`; add each missing server. Set `grafana.url` when it differs (`no_log` not needed, the URL is not secret, but keep it out of logs anyway for tidiness).
   - Tools: apply the Grafana allowlist when `profile show` (or `profile tools`) differs.
   - Export: `docker mcp profile export sunrise` to `{{ user_dir }}/.config/mcp-gateway/sunrise/profile.export.yaml` (0600) so the drift checker can diff later. Create the dir first, mode 0700.
   Every task `tags: [mcp]`.

3. `site.yml`: add `- role: mcp_toolkit` with `tags: [mcp, dot]` after `dotfiles`, before `ai_agents`. `Makefile`: `mcp` target runs the playbook with `--tags mcp`; `mcp-test` runs `scripts/mcp-gateway-smoke.sh` (created in M2; for now the target may point at a script that does not exist yet, so add the target in M2 instead if that is cleaner).

4. Dry run then apply:
   ```bash
   make check RUN_ARGS='--tags mcp'
   make mcp
   docker mcp secret ls                 # grafana.api_key (plus DCR residuals), no values
   docker mcp oauth ls                  # linear | authorized, notion-remote | authorized
   docker mcp profile show sunrise     # three servers, grafana.url set, allowlist visible
   docker mcp feature list              # tool-name-prefix enabled, dynamic-tools disabled
   make mcp                             # changed=0
   ```

**Verify:** the block above, `make lint`, `make ci`. Also `grep -rn 'ntn_\|glsa_\|lin_api' roles/ group_vars/ site.yml` must print nothing.

**Commit:** `feat(mcp): add mcp_toolkit role for profile, secrets and features`

**Arcane memory:** category `decision`, title `Docker MCP Toolkit manages shared MCP servers`, details: alternatives (hand-rolled compose with stdio bridges), why toolkit (catalog pins, keychain secrets, one gateway), the Grafana read-only allowlist rationale.

---

## M2. Gateway as a launchd service with bearer auth

**Branch:** `feat/mcp-gateway-service`
**Why:** One gateway process, always up while Docker Desktop runs, on `127.0.0.1:8080`, requiring `Authorization: Bearer <token>`. Replaces the per-client `docker mcp client connect` model, which spawns a gateway per harness.

**Files:**
- `roles/mcp_toolkit/templates/mcp-gateway-run.sh.j2` → `~/.config/mcp-gateway/sunrise/run.sh` (0700)
- `roles/mcp_toolkit/templates/com.dkelly.mcp-gateway-sunrise.plist.j2` → `~/Library/LaunchAgents/com.dkelly.mcp-gateway-sunrise.plist` (0600)
- token file `~/.config/mcp-gateway/sunrise/token` (0600) from vault `mcp_gateway_sunrise_token`, `no_log`. Key missing: STOP, rule 10.
- `scripts/mcp-gateway-smoke.sh` (repo), `Makefile` `mcp-test`
- `roles/mcp_toolkit/tasks/main.yml` (new tasks, plus `launchctl` load/reload handler)

**Steps:**

1. `run.sh.j2`:
   ```sh
   #!/bin/sh
   # Managed by Ansible (roles/mcp_toolkit). Runs the Docker MCP gateway for
   # profile {{ mcp_toolkit_profile }} on loopback with bearer auth.
   set -eu
   TOKEN_FILE="{{ user_dir }}/.config/mcp-gateway/sunrise/token"
   [ -s "$TOKEN_FILE" ] || { echo "mcp-gateway: token file missing" >&2; exit 78; }
   # Docker Desktop may not be up yet; exit non-zero so launchd retries.
   /usr/local/bin/docker info >/dev/null 2>&1 || exit 75
   MCP_GATEWAY_AUTH_TOKEN="$(cat "$TOKEN_FILE")"
   export MCP_GATEWAY_AUTH_TOKEN
   exec /usr/local/bin/docker mcp gateway run \
     --profile {{ mcp_toolkit_profile }} \
     --transport streaming \
     --host {{ mcp_gateway_host }} \
     --port {{ mcp_gateway_port }}
   ```
   Do NOT pass `--long-lived`: it keeps one container per MCP client session and never reaps them (three Grafana containers after one afternoon). Per-call containers cost about a second. Do NOT pass `--static`: static mode connects to image servers via socat to the container hostname (`mcp-grafana:4444`), which the host cannot resolve, and every image server fails with `initialize: EOF`. Set `PATH` explicitly in the script (launchd has none) so the gateway can find `socat` and `docker-credential-desktop`; `socat` must be in the Brewfile.
   Secrets set from Ansible need `stdin_add_newline: false`, otherwise the stored value carries a newline and Grafana rejects the Authorization header.
   Confirm the docker binary path with `command -v docker` and use that path in the template (Docker Desktop usually installs `/usr/local/bin/docker`). launchd has no PATH.

2. `com.dkelly.mcp-gateway-sunrise.plist.j2`: `Label` `com.dkelly.mcp-gateway-sunrise`, `ProgramArguments` `[run.sh path]`, `RunAtLoad` true, `KeepAlive` true, `ThrottleInterval` 30, `ProcessType` Background, stdout and stderr to `~/Library/Logs/mcp-gateway-sunrise.log`. KeepAlive with the exit-75 path above gives "wait for Docker, then run forever" without a separate watchdog.

3. Tasks: create dir, write token (`copy` with `content`, `no_log`, `register`), template script and plist, then `launchctl bootout gui/$(id -u) <plist>` (ignore errors) followed by `launchctl bootstrap gui/$(id -u) <plist>` when any of the three files changed. The token counts: the gateway reads it once at start, so a rotation without restart leaves the service on the old token. Use `ansible.builtin.command` with `changed_when` tied to the template results. Record the uid with `id -u` in a fact, do not hardcode 501.

4. `scripts/mcp-gateway-smoke.sh`: reads the token file, POSTs an MCP `initialize` then `tools/list` to `http://127.0.0.1:8080/mcp` using the exact curl shape from M0, prints tool count and one tool name per server (`grafana`, `notion`, `linear` prefixes), then calls one read-only tool per server: Grafana `list_datasources`, Notion the hosted server's search or "get self" tool (names from `tools/list`, prefixed `notion-remote__`), Linear the viewer/me tool from M0. Exit non-zero on any failure. No secrets printed. `make mcp-test` runs it.

5. Apply and verify:
   ```bash
   make mcp
   launchctl print gui/$(id -u)/com.dkelly.mcp-gateway-sunrise | grep -E 'state|pid'
   tail -20 ~/Library/Logs/mcp-gateway-sunrise.log
   curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/mcp        # 401 or 403
   make mcp-test                                                              # tool counts, three successful calls
   make mcp                                                                   # changed=0
   ```
   Then kill the gateway process (`launchctl kill TERM gui/$(id -u)/com.dkelly.mcp-gateway-sunrise`) and confirm launchd restarts it within a minute (`launchctl print` shows a new pid, `make mcp-test` passes again).

**Verify:** above, plus `make lint`, `make ci`, `shellcheck scripts/mcp-gateway-smoke.sh` and the rendered `~/.config/mcp-gateway/sunrise/run.sh`. `ls -l ~/.config/mcp-gateway/sunrise/token` shows `-rw-------`.

**Commit:** `feat(mcp): run the MCP gateway as a launchd service with bearer auth`

**Arcane memory:** category `pattern`, title `launchd KeepAlive plus exit 75 waits for Docker Desktop`.

---

## M3. Point every harness at the gateway

**Branch:** `feat/mcp-harness-wiring`
**Why:** Replace per-harness `grafana`, `notion`, `linear` entries with one `mcp-sunrise` entry carrying the bearer header. Only after this do the OAuth prompts stop.

Use the M0 harness header table. If M0 recorded that a harness cannot send a literal header (likely Codex desktop), STOP before touching that harness and report the options to Dan: keep that harness on its current hosted entries, or accept `bearer_token_env_var` for CLI use only. Do the other harnesses.

**Files:**
- `roles/ai_agents/templates/opencode.jsonc.j2`: remove `grafana`, `linear`, `notion`; add
  ```jsonc
  "mcp-sunrise": {
    "type": "remote",
    "url": "{{ mcp_gateway_url }}",
    "headers": { "Authorization": "Bearer {{ mcp_gateway_sunrise_token }}" },
    "oauth": false,
    "enabled": true,
    "timeout": 30000
  }
  ```
  This puts the gateway token into `~/.config/opencode/opencode.jsonc`. Set that file's mode to 0600 in the role (check the existing copy task). `scripts/validate-opencode-config.sh` scans for `Bearer`; extend its secret scan to allow exactly the `mcp.mcp-sunrise.headers.Authorization` path, and add an assertion that `mcp.mcp-sunrise.url == mcp_gateway_url` and that no `mcp.*.oauth` object remains.
- Claude, both profiles: extend `roles/ai_agents/tasks/claude_mcp.yml` (A3/A8 pattern with `claude_argv`). Inspect `claude mcp get mcp-sunrise`; register with `claude mcp add --scope user --transport http mcp-sunrise <url> --header "Authorization: Bearer <token>"` when missing or when the URL differs. Remove `notion` and `grafana` from the personal profile (`claude mcp remove --scope user notion`, same for `grafana`) when present. `no_log: true` on the add task.
- Forge: `roles/dotfiles/templates/forge.mcp.json.j2` replace `linear`, `notion`, `grafana` with `mcp-sunrise` `{ "url": ..., "headers": {...}, "disable": false }`. Keep `arcane`. Ensure the file is written 0600.
- Codex: per M0. If literal headers are supported in `config.toml`, do NOT template the whole file (it is app-owned). Instead document the exact block for Dan to paste in the README, and add a drift-check line in M5. If only the env-var route exists, STOP as above.
- Devin: hand-managed today. Document the entry in README; drift check in M5.

**Steps:** edit the files above, `make check RUN_ARGS='--tags ai,dot'`, read the diff, `make ai && make dotfiles`, then:
```bash
env -u CLAUDE_CONFIG_DIR claude mcp get mcp-sunrise | grep -E 'Type|URL|Status'
env CLAUDE_CONFIG_DIR="$HOME/.claude-work" claude mcp get mcp-sunrise | grep -E 'Type|URL|Status'
env -u CLAUDE_CONFIG_DIR claude mcp get notion 2>&1 | head -1    # not found
jq -r '.mcp | keys' ~/.config/opencode/opencode.jsonc               # arcane, mcp-sunrise only
jq -r '.mcpServers | keys' ~/forge/.mcp.json                        # arcane, mcp-sunrise
make validate-opencode
```
Then one real call per harness that is wired:
```bash
cd ~/Projects/arcane
claude-work -p "List the MCP tools available to you whose names start with grafana, notion or linear. Reply with only the count per prefix."
env -u CLAUDE_CONFIG_DIR timeout 180 claude -p "Call the Grafana list_datasources tool via the mcp-sunrise server and reply with only the number of datasources."
opencode run "Use the notion-remote search tool to find the page titled Onboarding and reply with only the number of results." 2>&1 | tail -3
```
Expect numbers and a name, no OAuth URLs, no permission prompts for the gateway tools (add `mcp__mcp-sunrise` to `ai_claude_permission_allow` in group_vars if Claude prompts; that list is managed by A5).

**Verify:** above, `make lint`, `make ci`, `make test-ai-agents`, `make validate-opencode`. `grep -c "$(cat ~/.config/mcp-gateway/sunrise/token | cut -c1-8)" ~/.config/opencode/opencode.jsonc ~/forge/.mcp.json` shows 1 each (token present where intended) and `ls -l` shows 0600 on both.

**Commit:** `feat(mcp): route Grafana, Notion and Linear through the local MCP gateway`

**Arcane memory:** category `decision`, title `Harnesses use one gateway URL for shared MCP servers`, details include which harnesses were wired and which (if any) were left for Dan.

---

## M4. Retire the standalone Grafana MCP and OAuth state

**Branch:** `chore/retire-grafana-local-mcp`
**Precondition:** M3 verified Grafana calls succeed through the gateway.

**Steps:**
1. `cd ~/Projects/Grafana_local_mcp && make down` (stops the container and disables its watchdog, per its README). `docker ps | grep grafana` → nothing. `launchctl print gui/$(id -u)/com.dkelly.grafana-local-mcp` → either unloaded or shows the disabled marker behaviour; then `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.dkelly.grafana-local-mcp.plist` and `trash ~/Library/LaunchAgents/com.dkelly.grafana-local-mcp.plist` (absolute path, print with `ls -d` first).
2. Port 8000 is now free: `lsof -nP -iTCP:8000 -sTCP:LISTEN` → nothing.
3. OpenCode OAuth state: `trash ~/.local/share/opencode/mcp-auth.json` after `ls -d`. OpenCode will not recreate it because no `oauth` entries remain.
4. Add to `roles/ai_agents/defaults/main.yml` `ai_agents_unused_instructions`-style pruning? No: do not automate deleting the old repo. Instead add a README note under "MCP gateway": "`~/Projects/Grafana_local_mcp` is superseded; archive or delete it by hand." Dan decides.
5. Codex and Devin hand-managed configs still reference `http://127.0.0.1:8000/mcp` and the hosted servers. Write the exact replacement blocks into README so Dan can paste them, and have M5's drift check flag them until he does.

**Verify:** `make mcp-test` still passes (gateway unaffected), `make lint`, `make ci`, drift script clean except the expected Codex/Devin lines if Dan has not pasted yet.

**Commit:** `chore(mcp): retire the standalone Grafana MCP container and OpenCode OAuth state`

**Arcane memory:** category `milestone`, title `Grafana MCP moved into the Docker MCP gateway`.

---

## M5. Drift checker and validator cover the gateway

**Branch:** `feat/mcp-drift-checks`

**Files:** `scripts/check-agent-config-drift.sh`, `scripts/validate-opencode-config.sh` (if not fully done in M3), `Makefile` (`make drift` already exists; ensure it runs the drift script).

**Add to the drift script**, advisory style (`drift+=(...)`, exit 0):
- Gateway up: `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/mcp` is 401/403 (auth required, service alive). Anything else → drift `mcp-sunrise gateway: not answering on 127.0.0.1:8080`.
- Gateway service loaded: `launchctl print gui/$(id -u)/com.dkelly.mcp-gateway-sunrise` succeeds.
- Profile drift: `docker mcp profile export sunrise` to a temp file (absolute path under `mktemp -d`), diff **sorted lines** (the export orders servers non-deterministically) against `~/.config/mcp-gateway/sunrise/profile.export.yaml`; differences → drift. `trash` the temp dir by absolute path.
- Secrets present: `docker mcp secret ls` contains `grafana.api_key`. `docker mcp oauth ls` contains `linear | authorized` and `notion-remote | authorized`; a missing one → drift `<provider>: run docker mcp oauth authorize <provider>`.
- Harness entries: Claude both profiles have `mcp-sunrise` with the right URL and no `notion`/`grafana`; Forge and OpenCode point at the gateway URL; Codex `config.toml` has `[mcp_servers.mcp-sunrise]` with the URL and no `mcp_servers.linear|notion|grafana` sections; Devin `mcp_config.json` likewise. Report each mismatch by harness.
- Old Grafana: `docker ps --format '{{.Names}}' | grep -q grafana-local-mcp` → drift.

**Verify:** run clean; then prove detection by stopping the gateway (`launchctl kill TERM …`, run the script within 20 s) and by temporarily renaming the profile export file; restore both. `shellcheck` clean, `make lint`, `pre-commit run --all-files`.

**Commit:** `feat(scripts): drift checker covers the MCP gateway, profile and harness wiring`

**Arcane memory:** category `pattern`, title `Drift checks for gateway health, profile export and harness URLs`.

---

## M6. End-to-end verification, no branch

Run from the integration branch after M1 to M5 are merged. Report only.

1. Static: `make lint`, `make ci`, `pre-commit run --all-files`, `make validate-opencode`, `make test-ai-agents`, `make check RUN_ARGS='--tags mcp,ai,dot'` shows `changed=0`, drift script clean.
2. Restart resilience (note: on 2026-09-06 `osascript quit` left Docker Desktop's backend hung with the engine VM unreachable; recovery needed `pkill -f Docker.app/Contents/MacOS && open -a Docker`, after which the engine was up in 8 s and the gateway in 16 s. Budget the quit test at 6 minutes and have that recovery command ready): `launchctl kill TERM gui/$(id -u)/com.dkelly.mcp-gateway-sunrise`; within 60 s `make mcp-test` passes. Quit Docker Desktop (`osascript -e 'quit app "Docker"'`), wait for `docker info` to fail, confirm the gateway log shows exit 75 retries, reopen Docker Desktop (`open -a Docker`), wait for `docker info`, confirm `make mcp-test` passes within 2 minutes.
3. Re-provision: move `~/.config/mcp-gateway/sunrise` and the plist to `~/.ai-config-backup/verify-mcp-<timestamp>/`, `docker mcp profile remove sunrise`, `docker mcp secret rm grafana.api_key` (leave the Linear and Notion OAuth authorizations in place; they are Dan's one-time steps). Run `make mcp`. Everything returns; `make mcp-test` passes; `make mcp` again `changed=0`. Diff the regenerated `profile.export.yaml` against the backup with `diff <(sort a) <(sort b)`: empty. Raw diff may show the servers list reordered.
4. Harness calls, one each, real data:
   - Claude work: Grafana `list_datasources` count.
   - Claude personal: Notion search for a page title Dan knows, reply with count.
   - OpenCode: Linear viewer/me tool, reply with the display name.
   - Codex CLI, if wired: `codex exec "Call the Linear viewer tool via mcp-sunrise and reply with only my display name."`
   No OAuth URLs, no browser windows, no re-auth prompts in any of them.
5. History scan: `gitleaks detect --source . --log-opts="main..integration/mcp-toolkit-gateway" --no-banner` exits 0 (install with `brew install gitleaks` if missing), and `git log -p main..integration/mcp-toolkit-gateway | grep -cE 'ntn_[A-Za-z0-9]|glsa_[A-Za-z0-9]|lin_api_[A-Za-z0-9]|[0-9a-f]{64}'` prints 0. `head -c 14 host_vars/localhost/vault.yml` prints `$ANSIBLE_VAULT`.
6. Secret hygiene: `grep -rn "$(cut -c1-8 ~/.config/mcp-gateway/sunrise/token)" ~/.claude.json ~/.claude-work/.claude.json ~/.config/opencode/opencode.jsonc ~/forge/.mcp.json 2>/dev/null | wc -l` equals the number of harnesses wired (token present only where intended). `grep -rln 'ntn_\|glsa_' ~/.config ~/.claude* ~/forge ~/.codex 2>/dev/null` prints nothing (the Grafana key never left the keychain; Notion and Linear are OAuth, no key exists).

Report as a table with PASS/FAIL and verbatim output for any FAIL, then the backup dir path.

---

## Appendix: why these choices

- **Toolkit over hand-rolled compose:** catalog images are digest-pinned and signature-verified, secrets live in the Keychain via Docker Desktop, the gateway fronts stdio servers as HTTP with no bridge code to maintain, and `tool-name-prefix` prevents cross-server collisions.
- **One long-lived gateway, not `docker mcp client connect`:** connect writes a per-client stdio spawn into each harness; six harnesses would mean six gateways and six auth contexts.
- **Bearer token, not `--allow-unauthenticated`:** the gateway itself warns that unauthenticated loopback is open to DNS-rebinding from a browser tab. The token sits in 0600 files owned by the user, the same trust boundary as `~/.claude.json`.
- **Grafana read-only allowlist:** preserves the `--disable-write` posture of the retired container.
- **Profile `sunrise`, not `personal`:** all three servers are Sunrise Robotics work credentials. Personal servers later get their own profile, gateway, port, token and harness entry so work and personal never share a process or a token.
- **GitHub stays on the `gh` CLI, not the gateway.** Every harness here has a shell and `gh` is already authenticated. The catalog's `github-official` server adds around a hundred tool schemas per session for capabilities `gh` already covers with no token cost. Revisit only if a harness without a shell appears. The `github | not authorized` line in `docker mcp oauth ls` is therefore expected and not drift.
- **No Linear fallback:** Dan's call. The hosted server is the official one; if token auth is not accepted the decision is his, not the playbook's.
