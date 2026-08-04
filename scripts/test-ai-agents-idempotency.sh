#!/usr/bin/env bash
# Exercise ai_agents in an isolated home, including migration and second-run state.
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
tmp_root=$(mktemp -d "${TMPDIR:-/tmp}/ai-agents.XXXXXX")
test_home="${tmp_root}/home with spaces"
backup_dir="${test_home}/.ai-config-backup"
trap 'rm -rf "$tmp_root"' EXIT
mkdir -p "${test_home}/.config/opencode/agents" "${test_home}/.config/opencode/commands"

ansible_python_interpreter="${ANSIBLE_PYTHON_INTERPRETER:-${VIRTUAL_ENV:-${repo_root}/venv}/bin/python}"
[[ -x "$ansible_python_interpreter" ]] || {
    printf 'Ansible Python interpreter not found: %s\n' "$ansible_python_interpreter" >&2
    exit 1
}

printf '%s\n' '{"$schema":"https://opencode.ai/config.json","mcp":{}}' > "${test_home}/.config/opencode/opencode.jsonc"
printf '%s\n' 'pre-existing orchestrator configuration' > "${test_home}/.config/opencode/agents/orchestrator.md"
printf '%s\n' 'pre-existing command configuration' > "${test_home}/.config/opencode/commands/review.md"

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

before_backup=$(shasum -a 256 "${backup_dir}/opencode/orchestrator.md")
first_config=$(shasum -a 256 "${test_home}/.config/opencode/opencode.jsonc")

second_output="${tmp_root}/second-run.log"
run_playbook >"$second_output" || { cat "$second_output"; exit 1; }
cat "$second_output"

after_backup=$(shasum -a 256 "${backup_dir}/opencode/orchestrator.md")
second_config=$(shasum -a 256 "${test_home}/.config/opencode/opencode.jsonc")
[[ "$before_backup" == "$after_backup" ]] || { printf 'backup changed on second run\n' >&2; exit 1; }
[[ "$first_config" == "$second_config" ]] || { printf 'generated config changed on second run\n' >&2; exit 1; }
! rg -q 'changed=[1-9]' "$second_output" || { printf 'second run still changed a task\n' >&2; exit 1; }

printf 'AI agent deployment is idempotent in isolated home: %s\n' "$test_home"
