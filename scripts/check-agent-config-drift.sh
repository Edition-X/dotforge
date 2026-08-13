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
    "${HOME}/.codex/AGENTS.md"
    "${HOME}/forge/AGENTS.md"
    "${HOME}/.config/opencode/AGENTS.md"
    "${HOME}/.config/devin/AGENTS.md"
)

declare -a skills_dirs=(
    "${HOME}/.claude/skills"
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
    "${HOME}/.config/opencode/commands/grill.md"
    "${HOME}/.config/opencode/commands/grilling.md"
)

drift=()

for f in "${instruction_files[@]}"; do
    [[ -e "$f" ]] || continue
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

if (( ${#drift[@]} > 0 )); then
    echo "agent config drift — these are not links into this repo:"
    printf '  - %s\n' "${drift[@]}"
    echo
    echo "run 'ansible-playbook site.yml --tags ai' to re-link,"
    echo "after copying across anything worth keeping."
fi

exit 0
