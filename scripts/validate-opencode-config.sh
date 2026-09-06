#!/usr/bin/env bash
# Validate one complete OpenCode config tree without contacting model APIs.
set -euo pipefail

config_dir="${HOME}/.config/opencode"
while (($# > 0)); do
    case "$1" in
        --config-dir)
            config_dir=${2:?missing value for --config-dir}
            shift 2
            ;;
        -h|--help)
            printf 'usage: %s [--config-dir PATH]\n' "$0"
            exit 0
            ;;
        *)
            printf 'unknown argument: %s\n' "$1" >&2
            exit 2
            ;;
    esac
done

command -v opencode >/dev/null || { printf 'opencode not found\n' >&2; exit 1; }
command -v jq >/dev/null || { printf 'jq not found\n' >&2; exit 1; }
command -v rg >/dev/null || { printf 'rg not found\n' >&2; exit 1; }

config_file="${config_dir}/opencode.jsonc"
[[ -f "$config_file" ]] || { printf 'missing %s\n' "$config_file" >&2; exit 1; }

tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/validate-opencode.XXXXXX")
trap 'rm -rf "$tmp_dir"' EXIT
resolved_file="${tmp_dir}/resolved.json"

if ! OPENCODE_CONFIG="$config_file" \
    OPENCODE_CONFIG_DIR="$config_dir" \
    OPENCODE_DISABLE_PROJECT_CONFIG=1 \
    OPENCODE_DISABLE_EXTERNAL_SKILLS=1 \
    OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 \
    OPENCODE_PURE=1 \
    opencode debug config >"$resolved_file"; then
    printf 'OpenCode rejected config: %s\n' "$config_file" >&2
    exit 1
fi

jq empty "$resolved_file" >/dev/null

required_agents=(
    orchestrator architect explorer worker-fast implementer debugger reviewer
    test-runner documentation
)
required_commands=(
    orchestrate implement-reviewed load-test-loop review debug-loop wayfinder grill grilling linear plan
)

for agent in architect explorer worker-fast implementer debugger reviewer test-runner documentation; do
    jq -e --arg agent "$agent" '.agent[$agent] != null' "$resolved_file" >/dev/null || {
        printf 'missing agent: %s\n' "$agent" >&2
        exit 1
    }
done

for command_name in linear plan; do
    expected_agent=$([[ "$command_name" == linear ]] && printf documentation || printf reviewer)
    jq -e --arg command "$command_name" --arg agent "$expected_agent" \
        '.command[$command].agent == $agent and .command[$command].subtask == true' \
        "$resolved_file" >/dev/null || {
        printf 'specialist command routing is incorrect: %s\n' "$command_name" >&2
        exit 1
    }
done

for command_name in "${required_commands[@]}"; do
    jq -e --arg command "$command_name" '.command[$command].template != null' "$resolved_file" >/dev/null || {
        printf 'missing command: %s\n' "$command_name" >&2
        exit 1
    }
    expected_agent=orchestrator
    case "$command_name" in
        linear) expected_agent=documentation ;;
        plan) expected_agent=reviewer ;;
    esac
    jq -e --arg command "$command_name" --arg agent "$expected_agent" \
        '.command[$command].agent == $agent' "$resolved_file" >/dev/null || {
        printf 'command uses unexpected agent: %s\n' "$command_name" >&2
        exit 1
    }
done

jq -e '.default_agent == "orchestrator" and .subagent_depth == 1 and .snapshot == true and .share == "disabled"' "$resolved_file" >/dev/null || {
    printf 'runtime safety defaults are incorrect\n' >&2
    exit 1
}

jq -e '(.plugin // []) | length == 0' "$resolved_file" >/dev/null || {
    printf 'unexpected OpenCode plugin configured\n' >&2
    exit 1
}

jq -e '
    (.permission.bash) as $bash |
    ($bash | keys | sort) == (["*", "git status*", "git diff*", "git log*", "git show*", "git rev-parse*", "git ls-files*", "git check-ignore*", "make validate-opencode*", "make test-ai-agents*", "make lint*", "make ci*", "pytest*", "npm test*", "npm run test*", "pnpm test*", "yarn test*", "go test*", "cargo test*", "git push*", "git reset --hard*", "git clean*", "git checkout --*", "rm -rf*", "gh pr merge*", "terraform destroy*", "kubectl delete*", "command *", "true *", "devcontainer *", "git worktree *", "git ls-tree *", "printf *", "ansible-playbook *"] | sort) and
    ($bash["*"] == "allow") and
    (["command *", "true *", "devcontainer *", "git worktree *", "git status*", "git diff*", "git log*", "git show*", "git rev-parse*", "git ls-files*", "git check-ignore*", "git ls-tree *", "make validate-opencode*", "make test-ai-agents*", "make lint*", "make ci*", "pytest*", "npm test*", "npm run test*", "pnpm test*", "yarn test*", "go test*", "cargo test*", "git push*", "printf *", "ansible-playbook *"] | all(.[]; . as $key | $bash[$key] == "allow")) and
    ($bash["git push*"] == "allow") and
    ($bash["git reset --hard*"] == "deny") and
    ($bash["git clean*"] == "deny") and
    ($bash["git checkout --*"] == "deny") and
    ($bash["rm -rf*"] == "deny") and
    ($bash["gh pr merge*"] == "deny") and
    ($bash["terraform destroy*"] == "deny") and
    ($bash["kubectl delete*"] == "ask")
' "$resolved_file" >/dev/null || {
    printf 'global bash policy ordering is incorrect\n' >&2
    exit 1
}

jq -e '
    (.permission | keys_unsorted) as $keys |
    (($keys | index("linear_*")) != null) and
    (.permission["linear_*"] == "allow")
' "$resolved_file" >/dev/null || {
    printf 'global Linear policy is incorrect\n' >&2
    exit 1
}

jq -e '
    (.permission.external_directory | keys_unsorted) == ["*", "~/Projects/**"] and
    (.permission.external_directory["*"] == "ask") and
    (.permission.external_directory["~/Projects/**"] == "allow")
' "$resolved_file" >/dev/null || {
    printf 'global command or external-directory policy is incorrect\n' >&2
    exit 1
}

available_models_file="${tmp_dir}/models.txt"
available_model_details_file="${tmp_dir}/models-verbose.txt"
opencode models openai >"$available_models_file"
opencode models openai --verbose >"$available_model_details_file"

for agent in "${required_agents[@]}"; do
    model=$(jq -r --arg agent "$agent" '.agent[$agent].model // empty' "$resolved_file")
    variant=$(jq -r --arg agent "$agent" '.agent[$agent].variant // empty' "$resolved_file")
    [[ "$model" == openai/* ]] || { printf 'unsupported model provider for %s: %s\n' "$agent" "$model" >&2; exit 1; }
    [[ "$model" != *-fast ]] || { printf 'fast model prohibited for %s: %s\n' "$agent" "$model" >&2; exit 1; }
    [[ -n "$variant" ]] || { printf 'missing model variant for %s\n' "$agent" >&2; exit 1; }

    jq -e --arg agent "$agent" '
        (.agent[$agent].permission.external_directory | keys_unsorted) == ["*", "~/Projects/**"] and
        (.agent[$agent].permission.external_directory["*"] == "ask") and
        (.agent[$agent].permission.external_directory["~/Projects/**"] == "allow")
    ' "$resolved_file" >/dev/null || {
        printf 'agent external-directory policy incorrect: %s\n' "$agent" >&2
        exit 1
    }

    if ! rg -Fqx "$model" "$available_models_file"; then
        printf 'unrecognised model for %s: %s\n' "$agent" "$model" >&2
        exit 1
    fi

    if ! awk -v target="$model" -v wanted="$variant" '
        $0 == target { in_model = 1; next }
        in_model && $0 ~ /^[^[:space:]]+\/[^[:space:]]+$/ { exit found ? 0 : 1 }
        in_model && $0 ~ "    \\\"" wanted "\\\":" { found = 1 }
        END { exit found ? 0 : 1 }
    ' "$available_model_details_file"; then
        printf 'unrecognised variant for %s: %s (%s)\n' "$agent" "$variant" "$model" >&2
        exit 1
    fi

    agent_debug_file="${tmp_dir}/${agent}.json"
    OPENCODE_CONFIG="$config_file" \
        OPENCODE_CONFIG_DIR="$config_dir" \
        OPENCODE_DISABLE_PROJECT_CONFIG=1 \
        OPENCODE_DISABLE_EXTERNAL_SKILLS=1 \
        OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 \
        OPENCODE_PURE=1 \
        opencode debug agent "$agent" >"$agent_debug_file"
done

jq -e '
    def matches_linear($rule; $permission):
        ($rule.permission == $permission) or ($rule.permission == "linear_*");
    def final_action($rules; $permission; $pattern):
        [ $rules[]? | select(matches_linear(.; $permission) and .pattern == $pattern) | .action ] | last;
    (final_action(.permission; "linear_get_issue"; "*") == "allow") and
    (final_action(.permission; "linear_merge_diff"; "*") == "allow") and
    (final_action(.permission; "linear_save_issue"; "*") == "allow") and
    (final_action(.permission; "linear_save_comment"; "*") == "allow")
' "${tmp_dir}/documentation.json" >/dev/null || {
    printf 'documentation final Linear policy is incorrect\n' >&2
    exit 1
}

for agent in orchestrator architect explorer worker-fast implementer debugger reviewer test-runner; do
    jq -e '
        def matches_linear($rule; $permission):
            ($rule.permission == $permission) or ($rule.permission == "linear_*");
        def final_action($rules; $permission; $pattern):
            [ $rules[]? | select(matches_linear(.; $permission) and .pattern == $pattern) | .action ] | last;
        (final_action(.permission; "linear_get_issue"; "*") == "deny") and
        (final_action(.permission; "linear_merge_diff"; "*") == "deny") and
        (final_action(.permission; "linear_save_issue"; "*") == "deny") and
        (final_action(.permission; "linear_save_comment"; "*") == "deny")
    ' "${tmp_dir}/${agent}.json" >/dev/null || {
        printf 'non-documentation final Linear policy is incorrect: %s\n' "$agent" >&2
        exit 1
    }
done

if jq -e '.agent.orchestrator.mode == "primary" and ([.agent | to_entries[] | select(.key != "orchestrator") | .value.mode] | all(. == "subagent"))' "$resolved_file" >/dev/null; then
    :
else
    printf 'agent modes are incorrect\n' >&2
    exit 1
fi

for agent in architect explorer reviewer test-runner; do
    jq -e '[.permission[]? | select(.permission == "edit" and .action == "allow")] | length == 0' "${tmp_dir}/${agent}.json" >/dev/null || {
        printf 'read-only agent has edit permission: %s\n' "$agent" >&2
        exit 1
    }
done

for agent in "${required_agents[@]}"; do
    jq -e --arg home "$HOME" \
        '
            def pattern_matches($pattern; $actual):
                ($pattern == $actual) or
                ($pattern == ($home + "/Projects/**") and $actual == "~/Projects/**");
            def final_index($rules; $permission; $pattern):
                ([ $rules | to_entries[] | select(.value.permission == $permission and pattern_matches($pattern; .value.pattern)) | .key ] | last);
            def final_action($rules; $permission; $pattern):
                [ $rules[]? | select(.permission == $permission and pattern_matches($pattern; .pattern)) | .action ] | last;

            (final_action(.permission; "external_directory"; ($home + "/Projects/**")) == "allow") and
            (final_action(.permission; "external_directory"; "*") == "ask") and
            (final_index(.permission; "external_directory"; "*") < final_index(.permission; "external_directory"; ($home + "/Projects/**"))) and
            (final_action(.permission; "bash"; "*") == "allow") and
            (final_index(.permission; "bash"; "*") < final_index(.permission; "bash"; "git push*")) and
            (final_action(.permission; "bash"; "git push*") == "allow") and
            (final_index(.permission; "bash"; "*") < final_index(.permission; "bash"; "git reset --hard*")) and
            (final_action(.permission; "bash"; "git reset --hard*") == "deny") and
            (final_index(.permission; "bash"; "*") < final_index(.permission; "bash"; "git clean*")) and
            (final_action(.permission; "bash"; "git clean*") == "deny") and
            (final_index(.permission; "bash"; "*") < final_index(.permission; "bash"; "git checkout --*")) and
            (final_action(.permission; "bash"; "git checkout --*") == "deny") and
            (final_index(.permission; "bash"; "*") < final_index(.permission; "bash"; "rm -rf*")) and
            (final_action(.permission; "bash"; "rm -rf*") == "deny") and
            (final_index(.permission; "bash"; "*") < final_index(.permission; "bash"; "gh pr merge*")) and
            (final_action(.permission; "bash"; "gh pr merge*") == "deny") and
            (final_index(.permission; "bash"; "*") < final_index(.permission; "bash"; "terraform destroy*")) and
            (final_action(.permission; "bash"; "terraform destroy*") == "deny") and
            (final_index(.permission; "bash"; "*") < final_index(.permission; "bash"; "kubectl delete*")) and
            (final_action(.permission; "bash"; "kubectl delete*") == "ask")
        ' \
        "${tmp_dir}/${agent}.json" >/dev/null || {
        printf 'agent final-action policy incorrect: %s\n' "$agent" >&2
        exit 1
    }
done

for agent in architect explorer worker-fast implementer debugger reviewer test-runner documentation; do
    jq -e '[.permission[]? | select(.permission == "task" and .action == "allow")] | length == 0' "${tmp_dir}/${agent}.json" >/dev/null || {
        printf 'subagent delegation permission unexpectedly allowed: %s\n' "$agent" >&2
        exit 1
    }
done

# The gateway entry legitimately carries a bearer token at
# mcp["mcp-sunrise"].headers.Authorization; every other Bearer-shaped string
# anywhere in the config tree is still a hard failure. Assert the one
# allowed path has the expected shape, then redact its value before the
# blanket secret scan below so it doesn't trip the same rule it is exempt
# from.
#
# These two assertions read the staged $config_file directly rather than
# $resolved_file: `opencode debug config` merges in whatever is already
# installed at the real (non-staged) $HOME/.config/opencode/opencode.jsonc
# regardless of OPENCODE_CONFIG_DIR, so right up until this staged file is
# actually deployed, $resolved_file can still carry the old grafana/linear/
# notion oauth entries from the file being replaced. The staged file itself
# has no comments, so plain `jq` parses it directly.
mcp_gateway_url_expected="${MCP_GATEWAY_URL:-http://127.0.0.1:8080/mcp}"

jq -e --arg url "$mcp_gateway_url_expected" '
    .mcp["mcp-sunrise"].url == $url and
    (.mcp["mcp-sunrise"].headers.Authorization // "" | test("^Bearer .+"))
' "$config_file" >/dev/null || {
    printf 'mcp-sunrise entry missing, wrong URL, or missing bearer header\n' >&2
    exit 1
}

jq -e '[.mcp[]? | select(has("oauth")) | select((.oauth // false) != false)] | length == 0' "$config_file" >/dev/null || {
    printf 'unexpected oauth object remains on an mcp server entry\n' >&2
    exit 1
}

mcp_sunrise_auth=$(jq -r '.mcp["mcp-sunrise"].headers.Authorization // empty' "$config_file")
redacted_config_file="${tmp_dir}/config.redacted.jsonc"
if [[ -n "$mcp_sunrise_auth" ]]; then
    escaped_auth=$(printf '%s' "$mcp_sunrise_auth" | sed -e 's/[\/&]/\\&/g')
    sed "s/${escaped_auth}/<redacted>/g" "$config_file" >"$redacted_config_file"
else
    cp "$config_file" "$redacted_config_file"
fi

managed_scan_paths=(
    "$redacted_config_file"
    "${config_dir}/ROUTING.md"
    "${config_dir}/agents"
    "${config_dir}/commands"
)
if rg -n --hidden --glob '!*.lock' --glob '!node_modules/**' \
    'BEGIN [A-Z ]*PRIVATE KEY|Bearer[[:space:]]+[A-Za-z0-9._-]+' \
    "${managed_scan_paths[@]}" >/dev/null || \
    rg -n --hidden --glob '!*.lock' --glob '!node_modules/**' \
    "apiKey[[:space:]]*:[[:space:]]*[\"']" "${managed_scan_paths[@]}" >/dev/null; then
    printf 'possible secret found in OpenCode config tree\n' >&2
    exit 1
fi

printf 'OpenCode config valid: %s\n' "$config_dir"
printf 'Agents: %s\n' "${required_agents[*]}"
printf 'Commands: %s\n' "${required_commands[*]}"
