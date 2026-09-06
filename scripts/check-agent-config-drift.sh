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
    "${HOME}/.config/devin/AGENTS.md"
)

declare -a skills_dirs=(
    "${HOME}/.claude/skills"
    "${HOME}/.claude-work/skills"
    "${HOME}/.codex/skills"
    "${HOME}/forge/skills"
    "${HOME}/.config/opencode/skills"
    "${HOME}/.config/devin/skills"
)

declare -a opencode_managed_files=(
    "${HOME}/.config/opencode/opencode.jsonc"
    "${HOME}/.config/opencode/ROUTING.md"
    "${HOME}/.config/opencode/agents/orchestrator.md"
    "${HOME}/.config/opencode/agents/architect.md"
    "${HOME}/.config/opencode/agents/explorer.md"
    "${HOME}/.config/opencode/agents/worker-fast.md"
    "${HOME}/.config/opencode/agents/implementer.md"
    "${HOME}/.config/opencode/agents/debugger.md"
    "${HOME}/.config/opencode/agents/reviewer.md"
    "${HOME}/.config/opencode/agents/test-runner.md"
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
)

drift=()

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
