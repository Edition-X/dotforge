#!/usr/bin/env bash
# Exercise ai_agents in an isolated home, including migration and second-run state.
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
tmp_root=$(mktemp -d "${TMPDIR:-/tmp}/ai-agents.XXXXXX")
test_home="${tmp_root}/home with spaces"
backup_dir="${test_home}/.ai-config-backup"

cleanup() {
    ls -d "$tmp_root"
    trash "$tmp_root"
}
trap cleanup EXIT

mkdir -p "${test_home}/.config/opencode/agents" "${test_home}/.config/opencode/commands"

ansible_python_interpreter="${ANSIBLE_PYTHON_INTERPRETER:-${VIRTUAL_ENV:-${repo_root}/venv}/bin/python}"
[[ -x "$ansible_python_interpreter" ]] || {
    printf 'Ansible Python interpreter not found: %s\n' "$ansible_python_interpreter" >&2
    exit 1
}

printf '%s\n' '{"$schema":"https://opencode.ai/config.json","mcp":{}}' > "${test_home}/.config/opencode/opencode.jsonc"
printf '%s\n' 'pre-existing orchestrator configuration' > "${test_home}/.config/opencode/agents/orchestrator.md"
printf '%s\n' 'pre-existing command configuration' > "${test_home}/.config/opencode/commands/review.md"
# One retired managed agent file, standing in for the old nine-agent chain.
# First apply must back it up under .../opencode/retired/ and remove it;
# second apply must leave it absent and report changed=0.
printf '%s\n' 'retired architect configuration' > "${test_home}/.config/opencode/agents/architect.md"

# Fixture app-owned Codex config.toml: stale root model/effort, a pre-existing
# colliding agent file standing in for a genuinely user-owned one, and an
# unrelated mcp_servers entry that must survive codex_agents.yml untouched.
mkdir -p "${test_home}/.codex/agents"
cat > "${test_home}/.codex/config.toml" <<'EOF'
model = "gpt-5.4-mini"
model_reasoning_effort = "low"

[mcp_servers.playwright]
command = "/usr/bin/true"
args = ["mcp"]
EOF
printf '%s\n' 'pre-existing worker configuration' > "${test_home}/.codex/agents/worker.toml"

run_playbook() {
    ansible-playbook \
        -i "${repo_root}/inventory" \
        -l local \
        "${repo_root}/tests/ai_agents.yml" \
        -e "{\"user_dir\":\"${test_home}\",\"project_dir\":\"${repo_root}\",\"ai_backup_dir\":\"${backup_dir}\",\"ansible_python_interpreter\":\"${ansible_python_interpreter}\",\"ai_external_skills\":[],\"ai_agents_prune_unused\":false}"
}

first_output="${tmp_root}/first-run.log"
run_playbook >"$first_output" || { cat "$first_output"; exit 1; }
cat "$first_output"

[[ -L "${test_home}/.config/opencode/AGENTS.md" ]] || { printf 'AGENTS.md was not linked\n' >&2; exit 1; }
[[ -f "${test_home}/.config/opencode/opencode.jsonc" ]] || { printf 'OpenCode config missing\n' >&2; exit 1; }
[[ -f "${backup_dir}/opencode/opencode.jsonc" ]] || { printf 'existing config was not backed up\n' >&2; exit 1; }
[[ -f "${backup_dir}/opencode/orchestrator.md" ]] || { printf 'existing agent was not backed up\n' >&2; exit 1; }
[[ -f "${backup_dir}/opencode/review.md" ]] || { printf 'existing command was not backed up\n' >&2; exit 1; }
[[ -f "${backup_dir}/opencode/retired/architect.md" ]] || { printf 'retired agent was not backed up\n' >&2; exit 1; }
[[ ! -e "${test_home}/.config/opencode/agents/architect.md" ]] || { printf 'retired agent file still present after first apply\n' >&2; exit 1; }
[[ -x "${test_home}/.local/bin/claude-work" ]] || { printf 'claude-work wrapper missing or not executable\n' >&2; exit 1; }
[[ -d "${test_home}/.claude-work" ]] || { printf 'claude-work config directory missing\n' >&2; exit 1; }
grep -Fq 'export CLAUDE_CONFIG_DIR="$HOME/.claude-work"' "${test_home}/.local/bin/claude-work" || {
    printf 'claude-work wrapper does not set isolated config directory\n' >&2
    exit 1
}
jq -e --arg binary "${test_home}/.local/bin/claude-work" \
    '.providers.claudeAgent.binaryPath == $binary and (.providers.claudeAgent | has("homePath") | not)' \
    "${test_home}/.t3/userdata/settings.json" >/dev/null || {
    printf 'T3 Claude provider is not isolated through claude-work\n' >&2
    exit 1
}

# Both Claude profiles must receive byte-identical rendered agents: same
# canonical routing policy, same tier resolution, no profile-specific drift.
for agent in worker verifier rescue documentation; do
    personal_agent="${test_home}/.claude/agents/${agent}.md"
    work_agent="${test_home}/.claude-work/agents/${agent}.md"
    [[ -f "${personal_agent}" ]] || { printf 'Claude personal agent missing: %s\n' "$agent" >&2; exit 1; }
    [[ -f "${work_agent}" ]] || { printf 'Claude work agent missing: %s\n' "$agent" >&2; exit 1; }
    diff -q "${personal_agent}" "${work_agent}" >/dev/null || {
        printf 'Claude personal/work agent differs: %s\n' "$agent" >&2
        exit 1
    }
done

jq -e '.model == "claude-opus-5" and .effortLevel == "medium"' "${test_home}/.claude/settings.json" >/dev/null || {
    printf 'Claude personal settings missing managed model/effortLevel\n' >&2
    exit 1
}
jq -e '.model == "claude-opus-5" and .effortLevel == "medium"' "${test_home}/.claude-work/settings.json" >/dev/null || {
    printf 'Claude work settings missing managed model/effortLevel\n' >&2
    exit 1
}

# Codex custom agents, rendered from the same canonical routing policy.
for agent in worker verifier rescue documentation; do
    codex_agent_file="${test_home}/.codex/agents/${agent}.toml"
    [[ -f "${codex_agent_file}" ]] || { printf 'Codex agent missing: %s\n' "$agent" >&2; exit 1; }
    grep -Fq 'developer_instructions' "${codex_agent_file}" || {
        printf 'Codex agent %s missing developer_instructions\n' "$agent" >&2
        exit 1
    }
done

[[ -f "${backup_dir}/codex/worker.toml" ]] || { printf 'pre-existing Codex agent was not backed up\n' >&2; exit 1; }
grep -Fq 'pre-existing worker configuration' "${backup_dir}/codex/worker.toml" || {
    printf 'Codex agent backup content mismatch\n' >&2
    exit 1
}

# Codex's app-owned config.toml: managed defaults synced, unrelated
# mcp_servers entry preserved untouched. Uses the already-resolved
# ansible_python_interpreter (validated executable above) rather than
# ambient python3: tomlkit lives in requirements.txt, installed only into
# the project venv, so a bare shell's python3 (e.g. a pyenv shim) would
# raise ModuleNotFoundError here the same way it did in
# scripts/test-codex-agent-settings-sync.sh before that hook was fixed to
# resolve the venv interpreter explicitly.
"${ansible_python_interpreter}" - "${test_home}/.codex/config.toml" <<'PY'
import sys
import tomlkit

doc = tomlkit.parse(open(sys.argv[1]).read())
assert doc["model"] == "gpt-5.6-sol", doc["model"]
assert doc["model_reasoning_effort"] == "medium", doc["model_reasoning_effort"]
assert doc["agents"]["enabled"] is True
assert doc["agents"]["max_concurrent_threads_per_session"] == 3
assert doc["agents"]["default_subagent_model"] == "gpt-5.6-luna"
assert doc["agents"]["default_subagent_reasoning_effort"] == "medium"
assert doc["mcp_servers"]["playwright"]["command"] == "/usr/bin/true"
print("Codex config.toml managed defaults synced, unrelated mcp_servers preserved")
PY

before_backup=$(shasum -a 256 "${backup_dir}/opencode/orchestrator.md")
before_retired_backup=$(shasum -a 256 "${backup_dir}/opencode/retired/architect.md")
first_config=$(shasum -a 256 "${test_home}/.config/opencode/opencode.jsonc")
before_codex_backup=$(shasum -a 256 "${backup_dir}/codex/worker.toml")
first_codex_config=$(shasum -a 256 "${test_home}/.codex/config.toml")

# T3/Forge inheritance (R6): T3 Code has no native agent files of its own —
# it reaches Claude only through claude-work and Codex only through the
# shared ~/.codex tree checked above. So the generated Claude work-profile
# agents and Codex agents rendered here are exactly what a T3 session
# inherits; capture their first-run hashes to prove second run re-renders
# them byte-identical rather than merely leaving them present.
declare -A first_claude_work_agent_hash first_codex_agent_hash
for agent in worker verifier rescue documentation; do
    first_claude_work_agent_hash[$agent]=$(shasum -a 256 "${test_home}/.claude-work/agents/${agent}.md")
    first_codex_agent_hash[$agent]=$(shasum -a 256 "${test_home}/.codex/agents/${agent}.toml")
done

second_output="${tmp_root}/second-run.log"
run_playbook >"$second_output" || { cat "$second_output"; exit 1; }
cat "$second_output"

after_backup=$(shasum -a 256 "${backup_dir}/opencode/orchestrator.md")
after_retired_backup=$(shasum -a 256 "${backup_dir}/opencode/retired/architect.md")
second_config=$(shasum -a 256 "${test_home}/.config/opencode/opencode.jsonc")
after_codex_backup=$(shasum -a 256 "${backup_dir}/codex/worker.toml")
second_codex_config=$(shasum -a 256 "${test_home}/.codex/config.toml")
[[ "$before_backup" == "$after_backup" ]] || { printf 'backup changed on second run\n' >&2; exit 1; }
[[ "$before_retired_backup" == "$after_retired_backup" ]] || { printf 'retired agent backup changed on second run\n' >&2; exit 1; }
[[ "$first_config" == "$second_config" ]] || { printf 'generated config changed on second run\n' >&2; exit 1; }
[[ "$before_codex_backup" == "$after_codex_backup" ]] || { printf 'Codex agent backup changed on second run\n' >&2; exit 1; }
[[ "$first_codex_config" == "$second_codex_config" ]] || { printf 'Codex config.toml changed on second run\n' >&2; exit 1; }
[[ ! -e "${test_home}/.config/opencode/agents/architect.md" ]] || { printf 'retired agent file reappeared after second apply\n' >&2; exit 1; }
! rg -q 'changed=[1-9]' "$second_output" || { printf 'second run still changed a task\n' >&2; exit 1; }

for agent in worker verifier rescue documentation; do
    [[ -f "${test_home}/.claude-work/agents/${agent}.md" ]] || { printf 'Claude work agent missing after second run: %s\n' "$agent" >&2; exit 1; }
    second_claude_work_agent_hash=$(shasum -a 256 "${test_home}/.claude-work/agents/${agent}.md")
    [[ "${first_claude_work_agent_hash[$agent]}" == "$second_claude_work_agent_hash" ]] || {
        printf 'Claude work agent %s not byte-identical after second run (T3 inherits this file)\n' "$agent" >&2
        exit 1
    }
    [[ -f "${test_home}/.codex/agents/${agent}.toml" ]] || { printf 'Codex agent missing after second run: %s\n' "$agent" >&2; exit 1; }
    second_codex_agent_hash=$(shasum -a 256 "${test_home}/.codex/agents/${agent}.toml")
    [[ "${first_codex_agent_hash[$agent]}" == "$second_codex_agent_hash" ]] || {
        printf 'Codex agent %s not byte-identical after second run (T3 inherits this file)\n' "$agent" >&2
        exit 1
    }
done

printf 'AI agent deployment is idempotent in isolated home: %s\n' "$test_home"
