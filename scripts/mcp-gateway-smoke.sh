#!/usr/bin/env bash
# Smoke-test the sunrise MCP gateway over Streamable HTTP: initialize, list
# tools, then call one read-only tool per server. Exits non-zero on any
# failure. Never prints the bearer token; tool call responses are only
# checked for an error, never printed, since Notion/Linear results can
# contain workspace content.
#
# HTTP contract pinned in docs/research/mcp-toolkit-cli-2026-09.md (M0):
# Accept must include both application/json and text/event-stream, the
# session id comes back as an Mcp-Session-Id response header, and every
# response (including initialize) is SSE-framed (`event: message` /
# `data: {...}`), not a plain JSON body.
set -euo pipefail

gateway_url="${MCP_GATEWAY_URL:-http://127.0.0.1:8080/mcp}"
token_file="${MCP_GATEWAY_TOKEN_FILE:-$HOME/.config/mcp-gateway/sunrise/token}"

command -v curl >/dev/null || { printf 'curl not found\n' >&2; exit 1; }
command -v python3 >/dev/null || { printf 'python3 not found\n' >&2; exit 1; }
[[ -s "$token_file" ]] || { printf 'token file missing or empty: %s\n' "$token_file" >&2; exit 1; }

token=$(<"$token_file")
tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/mcp-gateway-smoke.XXXXXX")
trap 'rm -rf "$tmp_dir"' EXIT

# Pulls the JSON-RPC object out of an SSE-framed response body ("event:
# message\ndata: {...}"). Prints the JSON on stdout, exits 1 if no data
# line with a parseable JSON object is found.
extract_result() {
    python3 - "$1" <<'PY'
import json, re, sys
body = open(sys.argv[1], encoding="utf-8").read()
match = re.search(r"^data: (\{.*\})\s*$", body, re.MULTILINE)
if not match:
    sys.exit(1)
json.loads(match.group(1))  # validate it parses
print(match.group(1))
PY
}

fail() {
    printf 'FAIL: %s\n' "$1" >&2
    exit 1
}

headers_file="$tmp_dir/init-headers.txt"
body_file="$tmp_dir/init-body.json"
http_code=$(curl -s -D "$headers_file" -o "$body_file" -w '%{http_code}' -X POST "$gateway_url" \
    -H "Authorization: Bearer $token" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"mcp-gateway-smoke","version":"1.0"}}}')
[[ "$http_code" == "200" ]] || fail "initialize returned HTTP $http_code"

session_id=$(tr -d '\r' <"$headers_file" | sed -n 's/^Mcp-Session-Id: *//Ip')
[[ -n "$session_id" ]] || fail "initialize response carried no Mcp-Session-Id header"

init_result=$(extract_result "$body_file") || fail "initialize response was not SSE-framed JSON"
python3 -c 'import json,sys; d=json.loads(sys.argv[1]); sys.exit(0 if "result" in d else 1)' "$init_result" \
    || fail "initialize response had no result (error: $(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("error"))' "$init_result"))"

# Fire-and-forget notification; gateway replies 202 with no body.
notif_code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$gateway_url" \
    -H "Authorization: Bearer $token" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -H "Mcp-Session-Id: $session_id" \
    -d '{"jsonrpc":"2.0","method":"notifications/initialized"}')
[[ "$notif_code" == "202" ]] || fail "notifications/initialized returned HTTP $notif_code (expected 202)"

call_rpc() {
    local id="$1" method="$2" params="$3" out="$4"
    local code
    code=$(curl -s -o "$out" -w '%{http_code}' -X POST "$gateway_url" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -H "Mcp-Session-Id: $session_id" \
        -d "{\"jsonrpc\":\"2.0\",\"id\":${id},\"method\":\"${method}\",\"params\":${params}}")
    [[ "$code" == "200" ]]
}

tools_file="$tmp_dir/tools.json"
call_rpc 2 "tools/list" "{}" "$tools_file" || fail "tools/list did not return HTTP 200"
tools_result=$(extract_result "$tools_file") || fail "tools/list response was not SSE-framed JSON"

names_file="$tmp_dir/tool-names.txt"
python3 -c '
import json, sys
d = json.loads(sys.argv[1])
for t in d["result"]["tools"]:
    print(t["name"])
' "$tools_result" >"$names_file" || fail "tools/list result had no tools array"

total=$(wc -l <"$names_file" | tr -d ' ')
printf 'tools/list: %s tools total\n' "$total"

for prefix in grafana notion-remote linear; do
    count=$(grep -c "^${prefix}__" "$names_file" || true)
    sample=$(grep -m1 "^${prefix}__" "$names_file" || true)
    printf '%s: %s tools (e.g. %s)\n' "$prefix" "$count" "${sample:-none}"
    [[ "$count" -gt 0 ]] || fail "no ${prefix}__ tools found in tools/list"
done

# One read-only call per server. Response bodies are never printed (Notion
# and Linear results carry real workspace content) — only whether the
# gateway reported an error, at the JSON-RPC level or the tool-result level.
call_tool() {
    local server="$1" tool="$2" args="$3"
    local out="$tmp_dir/call-${server}.json"
    call_rpc 9 "tools/call" "{\"name\":\"${tool}\",\"arguments\":${args}}" "$out" \
        || { printf '%s: FAIL (tools/call for %s did not return HTTP 200)\n' "$server" "$tool" >&2; return 1; }
    local result
    result=$(extract_result "$out") || { printf '%s: FAIL (tools/call response for %s was not SSE-framed JSON)\n' "$server" "$tool" >&2; return 1; }
    if ! python3 -c '
import json, sys
d = json.loads(sys.argv[1])
if "error" in d:
    sys.exit(1)
if d.get("result", {}).get("isError"):
    sys.exit(1)
' "$result"; then
        printf '%s: FAIL (%s reported an error; not printing response body)\n' "$server" "$tool" >&2
        return 1
    fi
    printf '%s: ok (%s)\n' "$server" "$tool"
}

overall_rc=0

# Grafana: list_datasources is the stable read-only tool named in the
# ticket and present in the allowlist (roles/mcp_toolkit/defaults/main.yml).
grafana_tool="grafana__list_datasources"
grep -qx "$grafana_tool" "$names_file" || fail "expected tool ${grafana_tool} not present in tools/list"
call_tool grafana "$grafana_tool" '{}' || overall_rc=1

# Notion: prefer the plain search tool; fall back to the AI-search variant
# if the catalog ever renames/removes it. Both take a required "query".
notion_tool=$(grep -m1 -E '^notion-remote__(notion-search|notion-ai-search)$' "$names_file" || true)
[[ -n "$notion_tool" ]] || fail "no notion-remote search tool found among notion-remote__* tools"
call_tool notion-remote "$notion_tool" '{"query":"self"}' || overall_rc=1

# Linear: no dedicated "viewer"/"me" tool exists in this catalog version
# (confirmed against a live tools/list during M2) — get_workspace ("retrieve
# the connected Linear workspace") is the closest read-only, no-argument
# equivalent. Falls back to list_users (limit 1) if it's ever removed.
linear_tool=$(grep -m1 -E '^linear__get_workspace$' "$names_file" || true)
linear_args='{}'
if [[ -z "$linear_tool" ]]; then
    linear_tool=$(grep -m1 -E '^linear__list_users$' "$names_file" || true)
    linear_args='{"limit":1}'
fi
[[ -n "$linear_tool" ]] || fail "no linear viewer/workspace tool found among linear__* tools"
call_tool linear "$linear_tool" "$linear_args" || overall_rc=1

exit "$overall_rc"
