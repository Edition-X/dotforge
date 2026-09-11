# Docker MCP Toolkit CLI — spike findings (2026-09-06)

M0 of `docs/playbooks/mcp-toolkit-gateway.md`. All experiments ran in a scratch
profile `spike` on gateway port 8099. No repo changes besides this file (untracked
`docs/`). This is the contract for M1–M6.

**Linear token verdict: FAIL — STOP.** See "Linear token result" below.

## Toolkit version

```
$ docker mcp version
v0.43.3
```

State store moved from the empty `~/.docker/mcp/{registry,config,tools}.yaml` files
to `~/.docker/mcp/mcp-toolkit.db` (SQLite). The catalog itself is still read from
`~/.docker/mcp/catalogs/docker-mcp.yaml` (312 servers) plus `catalog.json`.

## `docker mcp <sub> --help` vs no-args

Contrary to the playbook's assumption, **`docker mcp <subcommand> --help` works
correctly for every two/three-word subcommand tested** (`profile create --help`,
`secret set --help`, etc.) — each printed its own usage, flags, and examples, not
the top-level help. What *does* print the top-level help is running a *bare*
group with no further subcommand and no args in some shells' word-splitting —
that turned out to be a red herring from an early batched-loop bug on our side,
not a toolkit defect. Running a subcommand with genuinely missing required args
(e.g. `docker mcp profile create` with no `--name`) prints a targeted one-line
error, not full help. Recommendation for M1: use `--help`, it is reliable.

## Exact commands (usage text, one block per subcommand)

```
$ docker mcp profile create --help
Usage: docker mcp profile create [--name <name>] [--id <id>] [--server <ref> ...] [--from-template <template-id>] [--connect <client> ...]
Flags:
      --connect stringArray                      Clients to connect to (claude-code, claude-desktop, cline, codex, continue, crush, cursor, gemini, goose, gordon, kiro, lmstudio, opencode, sema4, vscode, zed)
      --from-template docker mcp template list   Create profile from a starter template
      --id string                                ID of the profile (defaults to slugified name)
      --name string                              Name of the profile (required unless --from-template)
      --server stringArray                       Server via https:// (MCP Registry), docker:// (OCI image), catalog:// (catalog ref), file:// (local, resolves under ~/.docker/mcp/catalogs)
```

```
$ docker mcp profile server add --help
Usage: docker mcp profile server add <profile-id> [--server <ref1> --server <ref2> ...]
Flags:
      --server stringArray   Server ref, same URI schemes as profile create
```

```
$ docker mcp profile server ls --help
Usage: docker mcp profile server ls
Flags:
  -f, --filter stringArray   Filter (e.g., name=github, profile=my-dev-env)
      --format string        json|yaml|human (default human)
```

```
$ docker mcp profile config --help
Usage: docker mcp profile config <profile-id> [--set <config-arg1> <config-arg2> ...] [--get <config-key1> <config-key2> ...] [--del <config-arg1> <config-arg2> ...]
Flags:
      --del stringArray   Delete config values: <key>
      --format string     json|yaml|human
      --get stringArray   Get config values: <key>
      --get-all           Get all config values
      --set stringArray   Set config values: <key>=<value> (JSON allowed for typed values)
```
Example used for a server config value: `docker mcp profile config spike --set grafana.url=https://example.grafana.net`
(not actually run in the spike — recorded from flag shape; M1 should verify against the real value).

```
$ docker mcp profile tools --help
Usage: docker mcp profile tools <profile-id> [--enable <tool> ...] [--disable <tool> ...] [--enable-all <server> ...] [--disable-all <server> ...]
Flags:
      --disable stringArray       Disable tools: <serverName>.<toolName>
      --disable-all stringArray   Disable all tools for a server: <serverName>
      --enable stringArray        Enable tools: <serverName>.<toolName>
      --enable-all stringArray    Enable all tools for a server: <serverName>
```

```
$ docker mcp profile show --help
Usage: docker mcp profile show <profile-id>
Flags:
      --clients         Include client info
      --format string   json|yaml|human
      --yq string       YQ expression applied to output
```

```
$ docker mcp profile export --help
Usage: docker mcp profile export <profile-id> <output-file>
```

```
$ docker mcp profile import --help
Usage: docker mcp profile import <input-file>
```

```
$ docker mcp profile remove --help
Usage: docker mcp profile remove <profile-id>
```

```
$ docker mcp feature enable --help
Usage: docker mcp feature enable <feature-name>
```

```
$ docker mcp feature disable --help
Usage: docker mcp feature disable <feature-name>
```

```
$ docker mcp secret set --help
Usage: docker mcp secret set key[=value]
(also accepts a value piped on stdin: `echo my-secret | docker mcp secret set KEY`)
```

```
$ docker mcp secret ls --help
Usage: docker mcp secret ls
Flags:
      --json   Print as JSON.
```

```
$ docker mcp secret rm --help
Usage: docker mcp secret rm name1 name2 ...
Flags:
      --all   Remove all secrets
```

```
$ docker mcp oauth ls --help
Usage: docker mcp oauth ls
Flags:
      --json   Print as JSON.
```

```
$ docker mcp tools ls --help
Usage: docker mcp tools ls
```
(no args needed; lists gateway-session tools when a session is active, or the 8
"toolkit-internal" tools — `code-mode`, `mcp-activate-profile`, `mcp-add`,
`mcp-config-set`, `mcp-create-profile`, `mcp-exec`, `mcp-find`, `mcp-remove` —
outside of one.)

## Profile creation (exact commands that worked)

```
docker mcp profile create --name spike
docker mcp profile server add spike --server catalog://mcp/docker-mcp-catalog/grafana
docker mcp profile server add spike --server catalog://mcp/docker-mcp-catalog/notion
docker mcp profile server add spike --server catalog://mcp/docker-mcp-catalog/linear
```
`docker mcp profile server ls -f profile=spike` confirmed all three
(`grafana`=image, `notion`=image, `linear`=remote).

## Secrets

```
echo "throwaway-notion-1" | docker mcp secret set notion.internal_integration_token
echo "throwaway-grafana-1" | docker mcp secret set grafana.api_key
echo "throwaway-linear-1" | docker mcp secret set linear.personal_access_token
```
All three succeeded. **`secret set` is NOT idempotent**: re-running it against an
existing key fails hard:
```
$ echo "throwaway-notion-2" | docker mcp secret set notion.internal_integration_token
could not store secret: The specified item already exists in the keychain. (-25299)
exit status 1
```
M1's Ansible task must `docker mcp secret rm <key>` (ignore-errors) before every
`secret set`, or check `secret ls` first — it cannot be a plain idempotent "set".

`docker mcp secret ls` (no `--json`) prints **names and provider only, never
values**:
```
docker/mcp/grafana.api_key               | docker-pass
docker/mcp/linear.personal_access_token  | docker-pass
docker/mcp/notion.internal_integration_… | docker-pass
```
`--json` form gives the same (name + provider, no value).

## Gateway HTTP contract

Command:
```
MCP_GATEWAY_AUTH_TOKEN=<token> docker mcp gateway run --profile spike \
  --transport streaming --host 127.0.0.1 --port 8099 --long-lived
```

**Dry run** (`--dry-run` appended) pulled and verified both container images
(`mcp/grafana`, `mcp/notion` — signature verification passed for both), started
each stdio container to enumerate tools (grafana 65 tools, notion 24 tools before
prefixing/internal tools), and for the remote `linear` server it did **not** use
the `linear.personal_access_token` secret at all — it attempted OAuth token
lookup first, found none, and failed (see Linear section below). Dynamic-tools
feature added 9 internal tools (`mcp-find`, `mcp-add`, `mcp-remove`, `code-mode`,
`mcp-exec`, `mcp-config-set`, `mcp-create-profile`, `mcp-activate-profile`,
`mcp-discover`).

**Auth status codes** (no `Authorization` header):
```
$ curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8099/mcp
401
```

**Working curl** for `initialize` (note: `Accept` must include both
`application/json` and `text/event-stream`, or the streaming gateway rejects the
request; the session id comes back as an `Mcp-Session-Id` response header, not in
the body):
```bash
curl -s -D - -o resp.json -X POST http://127.0.0.1:8099/mcp \
  -H "Authorization: Bearer $MCP_GATEWAY_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"spike-test","version":"0.1"}}}'
```
→ `HTTP/1.1 200 OK`, header `Mcp-Session-Id: <id>`, body
`{"jsonrpc":"2.0","id":1,"result":{"capabilities":{...},"protocolVersion":"2025-06-18","serverInfo":{"name":"Docker AI MCP Gateway","version":"2.0.1"}}}`.

Follow-up calls must repeat `Authorization` and add `Mcp-Session-Id: <id>`; a
`notifications/initialized` post (fire-and-forget) returns `202 Accepted` with an
empty body, then `tools/list` returns `200` with the tool array over an SSE
`event: message` / `data: {...}` frame (`Content-Type: text/event-stream`, not a
plain JSON body — clients must parse SSE framing even for request/response
calls).

**Health endpoint:**
| Path | Status (no auth) |
|---|---|
| `/` | 401 |
| `/health` | **200** |
| `/healthz` | 401 |

`/health` is the only unauthenticated liveness endpoint; `/healthz` is not
special-cased (it falls through to the same auth-required MCP routing as `/`).

**Tool-name-prefix shape.** With the feature off (default), tool names are bare
(`API-create-a-comment`, `add_activity_to_incident`, …). Enabling it
(`docker mcp feature enable tool-name-prefix`) requires a **gateway restart** to
take effect — it is not picked up by the running gateway's `--watch` file
reconfiguration. After restart, the actual shape is a **double underscore**,
e.g. `grafana__add_activity_to_incident`, `grafana__alerting_manage_routing` —
**not** the colon shape (`github:search`) shown in the feature's own
`--help`/enable-confirmation text. M1's tool allowlist and M6's checks must use
`<server>__<tool>`, not `<server>:<tool>` or `<server>.<tool>` (that dotted form
is only the CLI's own addressing syntax for `profile tools --enable/--disable`,
not the wire tool name).

## Linear token result — FAIL, STOP

Steps taken:
1. Set the scratch `linear.personal_access_token` to a throwaway string — dry
   run and live gateway both reported (redacted, no real token ever printed):
   ```
   Failed to get OAuth token for linear: OAuth token not found for linear. Run 'docker mcp oauth authorize linear' to authenticate
   > Can't start linear: failed to connect: calling "initialize": sending "initialize": Unauthorized
   ```
2. Replaced the secret with Dan's real `linear_api_key` from the vault, via the
   exact required pipe (`ansible-vault view ... | awk ... | docker mcp secret set
   linear.personal_access_token`, no value ever echoed/printed). Restarted the
   gateway. **Identical failure** — the gateway never attempted to use the
   secret-backed token at all; it went straight to the OAuth-DCR path and failed
   with the same "OAuth token not found" / "Unauthorized" message.
3. `docker mcp oauth ls` confirmed: `linear | not authorized` both before and
   after setting the real secret — i.e. the call did not work via token, per the
   ticket's explicit stop condition.
4. Diagnostic-only (no `oauth authorize` run): disabled the `mcp-oauth-dcr`
   feature and restarted the gateway to see whether that made the toolkit fall
   back to the `linear.personal_access_token` secret. **Same failure again** —
   disabling DCR did not change the behavior. Re-enabled `mcp-oauth-dcr`
   afterward to restore its original (enabled) state.

**Conclusion:** in toolkit v0.43.3, the catalog's declared alternative auth path
for `linear` (`secret: linear.personal_access_token` → env
`LINEAR_PERSONAL_ACCESS_TOKEN`) does not appear to be reachable through the
gateway at all — every code path tried goes to OAuth-DCR first and fails when no
token is authorized, regardless of whether a PAT secret is present. This may be
a toolkit bug/limitation, or there may be an undiscovered activation step (e.g.
a profile config key) that this spike did not find in the `--help` text or
catalog schema.

Real key was removed immediately after the test:
```
docker mcp secret rm linear.personal_access_token
docker mcp secret ls   # confirms gone
```

**Per rule 10 / ticket step 5, this is a real STOP.** Two options for Dan (see
`STOP: Linear` section in the chat report; do not proceed to M1 for Linear until
one is chosen).

## Harness header support

| Harness | Supports custom `headers` for remote/HTTP MCP? | Field / mechanism | Source |
|---|---|---|---|
| **Claude Code** | Yes | `claude mcp add --transport http <name> <url> --header "Authorization: Bearer …"` | Environment facts (verified previously) |
| **OpenCode** | Yes | `mcp.<name>.headers` object (`{"Authorization": "Bearer …"}`); `{env:VAR}` substitution **is** supported inside header values | `https://opencode.ai/config.json` schema (`McpRemoteConfig.headers`, `object`/`additionalProperties: string`) and `https://opencode.ai/docs/mcp-servers/` (shows `"{env:MY_MCP_CLIENT_SECRET}"` example). Installed version `opencode 1.18.20`, `$schema` in `~/.config/opencode/opencode.jsonc` points at `https://opencode.ai/config.json`. |
| **Codex CLI** (`config.toml`) | Yes — more than the playbook assumed | Multiple fields on an http-type `mcp_servers.<name>` entry: `bearer_token_env_var` (env-var only, as previously known), plus **`http_headers`** (`map<string,string>`, static/literal headers) and **`env_http_headers`** (`map<string,string>`, headers populated from environment variables when present), and `http_headers_helper` (a command that emits JSON header key/values). `codex mcp add --help` only exposes `--bearer-token-env-var` at the CLI level; `http_headers`/`env_http_headers` appear to be config.toml-only (hand-edit), not reachable via `codex mcp add` flags. | `https://learn.chatgpt.com/docs/config-file/config-reference` (redirect target of `developers.openai.com/codex/config-reference`); `codex mcp add --help` (installed Codex CLI) confirmed no header flags exist there. |
| **Forge** (`.mcp.json`) | Unknown — could not confirm from docs | n/a | `https://antinomy.ai/docs` and subpaths (e.g. `/docs/mcp`) are a JS-rendered SPA; `curl`/WebFetch returned empty bodies or hung — doc content not retrievable in this session. The installed `~/forge/.mcp.json` has no existing example of a `headers` field on any entry (its `linear`, `notion`, `grafana` entries use `command`/`url` only), so no local precedent either. Do not assume support until confirmed in M3. |
| **Devin** (`mcp_config.json`) | Yes | `headers` object, e.g. `{"Authorization": "Bearer your-api-token"}`; for HTTP/SSE (Streamable HTTP) remote servers. Devin also documents an "Auth Header" method where both the header key (default `Authorization`) and value are customizable. | `https://docs.devin.ai/work-with-devin/mcp` (verified reachable, HTTP 200) |

## Anything surprising

- **`docker mcp <sub> --help` is reliable** for the subcommands tested; the
  playbook's premise that it prints only top-level help did not hold up once
  tested cleanly (see note above — our first pass had a shell-loop bug, not a
  toolkit bug).
- **`secret set` is not idempotent** — re-running it errors instead of
  overwriting. Ansible role must `rm` (ignoring "not found") before every `set`.
- **Tool-name-prefix needs a gateway restart**, is not live-reloaded, and its
  actual separator (`__` double underscore) does not match the colon example
  shown in the feature's own help text.
- **Linear's PAT secret path could not be exercised at all** through the
  gateway in this toolkit version — OAuth-DCR is always tried first and there
  was no observed way to force the PAT path (tried: setting the secret alone,
  and setting the secret with `mcp-oauth-dcr` disabled — both failed
  identically). This blocks M1 for Linear until Dan decides between one-time
  browser OAuth or dropping Linear from the gateway.
- **An OAuth-DCR client-registration residual for `linear`** (`docker/mcp/oauth-dcr/linear`,
  provider `docker-desktop-mcp-dcr`) appeared in `docker mcp secret ls` output
  during this spike and could **not** be removed by `docker mcp secret rm` (no
  effect, no error) or by `docker mcp oauth revoke linear` (fails: "could not
  unmarshal token: secret not found" — because no token was ever issued, only a
  public DCR client id/registration). `docker mcp oauth ls` confirms `linear` as
  `not authorized`, i.e. this residual carries no credential/secret value, only
  client-registration metadata. Cleanup could not fully clear it; flagging for
  M1/M6 so it isn't mistaken for a leaked secret during drift checks. Everything
  else (`profile ls`, the three scratch secrets) came back empty as required.
- Codex's real header story is richer than the playbook assumed:
  `http_headers`/`env_http_headers` exist in `config.toml` even though
  `codex mcp add` doesn't expose them as flags — M3 will need to hand-edit
  `config.toml` (as the playbook already notes it's hand-managed) rather than
  relying on `codex mcp add --bearer-token-env-var`, especially since the
  ChatGPT desktop app doesn't inherit shell env for the env-var route anyway.
