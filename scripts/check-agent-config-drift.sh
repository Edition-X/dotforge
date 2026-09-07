#!/usr/bin/env bash
#
# Warn when deployed AI agent config has drifted away from this repo.
#
# Every harness gets its instruction file and skills as symlinks back into
# host_files/localhost/ai/. If one of them is a real file instead, someone
# edited the live copy directly and the next `make apply` will silently clobber
# it — which is exactly how the per-harness files drifted apart in the first
# place.
#
# Advisory, not blocking: an unprovisioned or partly-provisioned machine is a
# normal state to commit from, and this hook has no way to tell that apart from
# real drift. It reports and exits 0.
set -uo pipefail

repo_root=$(git rev-parse --show-toplevel)
ai_dir="${repo_root}/host_files/localhost/ai"

# Keep in step with ai_harnesses in group_vars/macbooks.yml.
declare -a instruction_files=(
    "${HOME}/.claude/CLAUDE.md"
    "${HOME}/.claude-work/CLAUDE.md"
    "${HOME}/.codex/AGENTS.md"
    "${HOME}/forge/AGENTS.md"
    "${HOME}/.config/opencode/AGENTS.md"
)

declare -a skills_dirs=(
    "${HOME}/.claude/skills"
    "${HOME}/.claude-work/skills"
    "${HOME}/.codex/skills"
    "${HOME}/forge/skills"
    "${HOME}/.config/opencode/skills"
)

declare -a claude_agent_files=(
    "${HOME}/.claude/agents/worker.md"
    "${HOME}/.claude/agents/verifier.md"
    "${HOME}/.claude/agents/rescue.md"
    "${HOME}/.claude/agents/documentation.md"
    "${HOME}/.claude-work/agents/worker.md"
    "${HOME}/.claude-work/agents/verifier.md"
    "${HOME}/.claude-work/agents/rescue.md"
    "${HOME}/.claude-work/agents/documentation.md"
)

declare -a codex_agent_files=(
    "${HOME}/.codex/agents/worker.toml"
    "${HOME}/.codex/agents/verifier.toml"
    "${HOME}/.codex/agents/rescue.toml"
    "${HOME}/.codex/agents/documentation.toml"
)

declare -a opencode_managed_files=(
    "${HOME}/.config/opencode/opencode.jsonc"
    "${HOME}/.config/opencode/ROUTING.md"
    "${HOME}/.config/opencode/agents/orchestrator.md"
    "${HOME}/.config/opencode/agents/worker.md"
    "${HOME}/.config/opencode/agents/verifier.md"
    "${HOME}/.config/opencode/agents/rescue.md"
    "${HOME}/.config/opencode/agents/documentation.md"
    "${HOME}/.config/opencode/commands/orchestrate.md"
    "${HOME}/.config/opencode/commands/implement-reviewed.md"
    "${HOME}/.config/opencode/commands/load-test-loop.md"
    "${HOME}/.config/opencode/commands/review.md"
    "${HOME}/.config/opencode/commands/debug-loop.md"
    "${HOME}/.config/opencode/commands/wayfinder.md"
    "${HOME}/.config/opencode/commands/linear.md"
    "${HOME}/.config/opencode/commands/plan.md"
    "${HOME}/.config/opencode/commands/grill.md"
    "${HOME}/.config/opencode/commands/grilling.md"
    "${HOME}/.config/opencode/commands/execute-playbook.md"
)

drift=()

# --- MCP gateway liveness -------------------------------------------------
# Cheap and time-sensitive (launchd's KeepAlive restarts a killed gateway in
# well under a minute), so check it before the slower per-harness CLI calls
# below have a chance to eat the detection window.
mcp_gateway_url="http://127.0.0.1:8080/mcp"
mcp_gateway_label="com.dkelly.mcp-gateway-sunrise"

if command -v curl >/dev/null 2>&1; then
    gateway_status=$(curl -s -o /dev/null -w '%{http_code}' "${mcp_gateway_url}" 2>/dev/null)
    if [[ "${gateway_status}" != "401" && "${gateway_status}" != "403" ]]; then
        drift+=("mcp-sunrise gateway: not answering on 127.0.0.1:8080")
    fi
fi

if command -v launchctl >/dev/null 2>&1; then
    if ! launchctl print "gui/$(id -u)/${mcp_gateway_label}" >/dev/null 2>&1; then
        drift+=("mcp-sunrise gateway: launchd service ${mcp_gateway_label} not loaded")
    fi
fi

for f in "${instruction_files[@]}"; do
    if [[ ! -e "$f" ]]; then
        [[ -d "$(dirname "$f")" ]] && drift+=("${f/#$HOME/\~} is missing; harness dir exists but was never provisioned")
        continue
    fi
    if [[ ! -L "$f" ]]; then
        drift+=("${f/#$HOME/\~} is a real file, not a link into this repo")
    elif [[ "$(readlink "$f")" != "${ai_dir}/AGENTS.md" ]]; then
        drift+=("${f/#$HOME/\~} links to $(readlink "$f"), not ${ai_dir}/AGENTS.md")
    fi
done

# Only flags skills this repo owns. A harness holding extra skills installed by
# other means is fine and is not drift.
while IFS= read -r skill_path; do
    skill=$(basename "$skill_path")
    for d in "${skills_dirs[@]}"; do
        deployed="${d}/${skill}"
        [[ -e "$deployed" ]] || continue
        if [[ ! -L "$deployed" ]]; then
            drift+=("${deployed/#$HOME/\~} is a real directory, not a link into this repo")
        fi
    done
done < <(find "$ai_dir/skills" -mindepth 1 -maxdepth 1 -type d 2>/dev/null)

# Generated OpenCode files are not symlinks, so validation owns their content.
# This advisory check catches partial deployments without touching user-owned
# agents, commands, auth, history, caches, or package state.
if [[ -e "${HOME}/.config/opencode/AGENTS.md" ]]; then
    for f in "${opencode_managed_files[@]}"; do
        [[ -e "$f" ]] || drift+=("${f/#$HOME/\~} is missing from managed OpenCode setup")
    done
fi

# Generated Claude subagent files, same rationale as the OpenCode block above:
# not symlinks, so only checked for presence once the profile is provisioned.
if [[ -e "${HOME}/.claude/CLAUDE.md" ]]; then
    for f in "${claude_agent_files[@]}"; do
        [[ "$f" == *"/.claude-work/"* && ! -d "${HOME}/.claude-work" ]] && continue
        [[ -e "$f" ]] || drift+=("${f/#$HOME/\~} is missing from managed Claude agents")
    done
fi

# Generated Codex custom agent files, same rationale: not symlinks, only
# checked once Codex's app-owned config.toml is actually present.
if [[ -e "${HOME}/.codex/config.toml" ]]; then
    for f in "${codex_agent_files[@]}"; do
        [[ -e "$f" ]] || drift+=("${f/#$HOME/\~} is missing from managed Codex agents")
    done
fi

# --- Arcane MCP registration -------------------------------------------
# Every harness must launch arcane through the installed binary. Keep in
# step with ai_arcane_bin in group_vars/macbooks.yml.
arcane_bin="${HOME}/.local/bin/arcane"

check_mcp_command() {
    local label="$1" actual="$2"
    if [[ -z "${actual}" ]]; then
        drift+=("${label}: arcane MCP not registered")
    elif [[ "${actual}" != "${arcane_bin}" ]]; then
        drift+=("${label}: arcane MCP command is '${actual}', expected '${arcane_bin}'")
    fi
}

if command -v jq >/dev/null 2>&1; then
    if [[ -f "${HOME}/forge/.mcp.json" ]]; then
        check_mcp_command "Forge" "$(jq -r '.mcpServers.arcane.command // empty' "${HOME}/forge/.mcp.json")"
    elif [[ -d "${HOME}/forge" ]]; then
        drift+=("Forge: .mcp.json missing")
    fi
    if [[ -f "${HOME}/.config/opencode/opencode.jsonc" ]]; then
        # opencode.jsonc may contain full-line comments; strip only lines whose
        # first non-blank content is "//" so "https://" values survive.
        check_mcp_command "OpenCode" "$(sed -E 's|^[[:space:]]*//.*$||' "${HOME}/.config/opencode/opencode.jsonc" | jq -r '.mcp.arcane.command[0] // empty')"
    fi
fi
if [[ -f "${HOME}/.codex/config.toml" ]]; then
    check_mcp_command "Codex" "$(awk '/^\[mcp_servers\.arcane\]/{f=1;next} /^\[/{f=0} f && /^command/{gsub(/.*= *"|"$/,""); print; exit}' "${HOME}/.codex/config.toml")"
fi
if command -v claude >/dev/null 2>&1; then
    # Personal profile state is $HOME/.claude.json, read only when
    # CLAUDE_CONFIG_DIR is unset. The work profile needs it set.
    check_mcp_command "Claude (personal)" \
        "$(env -u CLAUDE_CONFIG_DIR claude mcp get arcane 2>/dev/null | awk -F': ' '/^ *Command:/{print $2; exit}')"
    if [[ -d "${HOME}/.claude-work" ]]; then
        check_mcp_command "Claude (work)" \
            "$(env CLAUDE_CONFIG_DIR="${HOME}/.claude-work" claude mcp get arcane 2>/dev/null | awk -F': ' '/^ *Command:/{print $2; exit}')"
    fi
fi

# --- MCP gateway profile, secrets and old Grafana MCP -------------------
# Gateway liveness (curl/launchctl) is checked near the top of this script,
# before the slower per-harness CLI calls, so a killed gateway is still
# caught inside launchd's KeepAlive restart window.
mcp_gateway_profile_export="${HOME}/.config/mcp-gateway/sunrise/profile.export.yaml"

if command -v docker >/dev/null 2>&1; then
    if [[ -f "${mcp_gateway_profile_export}" ]]; then
        mcp_toolkit_drift_dir=$(mktemp -d)
        if docker mcp profile export sunrise "${mcp_toolkit_drift_dir}/profile.export.yaml" >/dev/null 2>&1 &&
            # `profile export` serialises the servers list in non-deterministic order,
            # so compare sorted lines rather than raw files.
            ! diff -q <(sort "${mcp_toolkit_drift_dir}/profile.export.yaml") <(sort "${mcp_gateway_profile_export}") >/dev/null 2>&1; then
            drift+=("mcp-sunrise profile: docker mcp profile export sunrise no longer matches ${mcp_gateway_profile_export/#$HOME/\~}")
        fi
        trash "${mcp_toolkit_drift_dir}"
    else
        drift+=("mcp-sunrise profile: ${mcp_gateway_profile_export/#$HOME/\~} is missing")
    fi

    secret_list=$(docker mcp secret ls 2>/dev/null)
    echo "${secret_list}" | grep -q 'grafana\.api_key' || drift+=("mcp-sunrise secrets: grafana.api_key not present, run docker mcp secret set")

    oauth_list=$(docker mcp oauth ls 2>/dev/null)
    for provider in linear notion-remote; do
        echo "${oauth_list}" | grep -qE "^${provider}[[:space:]]*\|[[:space:]]*authorized" ||
            drift+=("${provider}: run docker mcp oauth authorize ${provider}")
    done

    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q grafana-local-mcp; then
        drift+=("old Grafana MCP: grafana-local-mcp container is still running, retire it")
    fi
fi

check_mcp_sunrise_command() {
    local label="$1" actual="$2"
    if [[ -z "${actual}" ]]; then
        drift+=("${label}: mcp-sunrise not registered")
    elif [[ "${actual}" != "${mcp_gateway_url}" ]]; then
        drift+=("${label}: mcp-sunrise URL is '${actual}', expected '${mcp_gateway_url}'")
    fi
}

if command -v jq >/dev/null 2>&1; then
    if [[ -f "${HOME}/forge/.mcp.json" ]]; then
        check_mcp_sunrise_command "Forge" "$(jq -r '.mcpServers["mcp-sunrise"].url // empty' "${HOME}/forge/.mcp.json")"
        for stale in linear notion grafana; do
            jq -e --arg s "$stale" '.mcpServers[$s] // empty | length > 0' "${HOME}/forge/.mcp.json" >/dev/null 2>&1 &&
                drift+=("Forge: stale mcpServers.${stale} entry, should route through mcp-sunrise")
        done
    fi
    if [[ -f "${HOME}/.config/opencode/opencode.jsonc" ]]; then
        opencode_stripped=$(sed -E 's|^[[:space:]]*//.*$||' "${HOME}/.config/opencode/opencode.jsonc")
        check_mcp_sunrise_command "OpenCode" "$(echo "${opencode_stripped}" | jq -r '.mcp["mcp-sunrise"].url // empty')"
        for stale in linear notion grafana; do
            echo "${opencode_stripped}" | jq -e --arg s "$stale" '.mcp[$s] // empty | length > 0' >/dev/null 2>&1 &&
                drift+=("OpenCode: stale mcp.${stale} entry, should route through mcp-sunrise")
        done
    fi
fi

if [[ -f "${HOME}/.codex/config.toml" ]]; then
    check_mcp_sunrise_command "Codex" "$(awk '/^\[mcp_servers\.mcp-sunrise\]/{f=1;next} /^\[/{f=0} f && /^url/{gsub(/.*= *"|"$/,""); print; exit}' "${HOME}/.codex/config.toml")"
    for stale in linear notion grafana; do
        grep -qE "^\[mcp_servers\.${stale}\]" "${HOME}/.codex/config.toml" &&
            drift+=("Codex: stale mcp_servers.${stale} entry, should route through mcp-sunrise")
    done
fi

if command -v claude >/dev/null 2>&1; then
    check_mcp_sunrise_command "Claude (personal)" \
        "$(env -u CLAUDE_CONFIG_DIR claude mcp get mcp-sunrise 2>/dev/null | awk -F': ' '/^ *URL:/{print $2; exit}')"
    if [[ -d "${HOME}/.claude-work" ]]; then
        check_mcp_sunrise_command "Claude (work)" \
            "$(env CLAUDE_CONFIG_DIR="${HOME}/.claude-work" claude mcp get mcp-sunrise 2>/dev/null | awk -F': ' '/^ *URL:/{print $2; exit}')"
    fi
    for profile_env in "" "${HOME}/.claude-work"; do
        label="Claude (personal)"
        cmd=(env -u CLAUDE_CONFIG_DIR claude mcp list)
        if [[ -n "${profile_env}" ]]; then
            label="Claude (work)"
            cmd=(env CLAUDE_CONFIG_DIR="${profile_env}" claude mcp list)
        fi
        [[ "${label}" == "Claude (work)" && ! -d "${HOME}/.claude-work" ]] && continue
        claude_list=$("${cmd[@]}" 2>/dev/null)
        for stale in notion grafana; do
            echo "${claude_list}" | grep -qE "^${stale}:" &&
                drift+=("${label}: stale ${stale} MCP entry, should route through mcp-sunrise")
        done
    done
fi

# --- Arcane MCP Brewfile pin -------------------------------------------
# Catches an installed arcane-mcp that no longer matches the Brewfile pin
# (e.g. after a manual `uv tool upgrade` or before running `make packages`
# following an automated Brewfile bump). `brew bundle check` only names
# individual packages with --verbose; without it, the output never mentions
# "arcane" even when arcane-mcp is the one unsatisfied dependency.
if command -v brew >/dev/null 2>&1; then
    if brew bundle check --file="${repo_root}/Brewfile" --no-upgrade --verbose 2>&1 | grep -qi arcane; then
        drift+=("arcane-mcp: installed version does not match the Brewfile pin; run make packages")
    fi
fi

if (( ${#drift[@]} > 0 )); then
    echo "agent config drift — these are not links into this repo:"
    printf '  - %s\n' "${drift[@]}"
    echo
    echo "run 'ansible-playbook site.yml --tags ai' to re-link,"
    echo "after copying across anything worth keeping."
fi

exit 0
