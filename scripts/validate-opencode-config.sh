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
    orchestrate implement-reviewed load-test-loop review debug-loop wayfinder grill grilling
)

for agent in architect explorer worker-fast implementer debugger reviewer test-runner documentation; do
    jq -e --arg agent "$agent" '.agent[$agent] != null' "$resolved_file" >/dev/null || {
        printf 'missing agent: %s\n' "$agent" >&2
        exit 1
    }
done

for command_name in "${required_commands[@]}"; do
    jq -e --arg command "$command_name" '.command[$command].template != null' "$resolved_file" >/dev/null || {
        printf 'missing command: %s\n' "$command_name" >&2
        exit 1
    }
    jq -e --arg command "$command_name" '.command[$command].agent == "orchestrator"' "$resolved_file" >/dev/null || {
        printf 'command does not use orchestrator: %s\n' "$command_name" >&2
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

for agent in architect explorer worker-fast implementer debugger reviewer test-runner documentation; do
    jq -e '[.permission[]? | select(.permission == "task" and .action == "allow")] | length == 0' "${tmp_dir}/${agent}.json" >/dev/null || {
        printf 'subagent delegation permission unexpectedly allowed: %s\n' "$agent" >&2
        exit 1
    }
done

managed_scan_paths=(
    "$config_file"
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
