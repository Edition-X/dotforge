#!/usr/bin/env bash
# Fast source-only checks for pre-commit. Full rendered validation uses Ansible.
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
routing_file="${repo_root}/host_files/localhost/ai/routing/models.yml"
required_models=(
    'gpt-5.6-terra'
    'gpt-5.6-sol'
    'gpt-5.6-luna'
    'gpt-5.4-mini'
)

for model in "${required_models[@]}"; do
    rg -Fq "$model" "$routing_file" || {
        printf 'missing selected model from routing policy: %s\n' "$model" >&2
        exit 1
    }
done

if rg -n --fixed-strings -- '-fast' "$routing_file" >/dev/null; then
    printf 'fast OpenCode model IDs are prohibited\n' >&2
    exit 1
fi

for command_file in \
    orchestrate.md implement-reviewed.md load-test-loop.md review.md debug-loop.md \
    wayfinder.md linear.md plan.md grill.md grilling.md execute-playbook.md; do
    [[ -f "${repo_root}/host_files/localhost/ai/opencode/commands/${command_file}" ]] || {
        printf 'missing OpenCode command source: %s\n' "$command_file" >&2
        exit 1
    }
done

printf 'OpenCode source policy valid\n'
