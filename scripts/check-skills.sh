#!/usr/bin/env bash
#
# Lint host_files/localhost/ai/skills/<name>/SKILL.md files.
#
# Checks, per skill directory:
#   - SKILL.md exists
#   - frontmatter block (--- ... ---) present
#   - name: equals the directory name
#   - description: non-empty and under 600 characters
#   - file under 300 lines
#   - no line matches a secret pattern
#
# Prints one line per failure, exits 1 if any failure was found.
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
skills_dir="${repo_root}/host_files/localhost/ai/skills"

# Real PEM header, not any prose that merely mentions "PRIVATE KEY" (e.g. a
# footer like "-----END OPENSSH PRIVATE KEY-----" quoted in a skill's prose).
patterns=(
    'ntn_[A-Za-z0-9]'
    'glsa_[A-Za-z0-9]'
    'lin_api_[A-Za-z0-9]'
    '[0-9a-f]{64}'
    'Bearer [A-Za-z0-9]{16,}'
    '\-\-\-\-\-BEGIN [A-Z ]*PRIVATE KEY\-\-\-\-\-'
)

fail=0

for dir in "${skills_dir}"/*/; do
    name=$(basename "${dir}")
    file="${dir}SKILL.md"

    if [[ ! -f "${file}" ]]; then
        echo "FAIL ${name}: SKILL.md not found"
        fail=1
        continue
    fi

    rel_file="host_files/localhost/ai/skills/${name}/SKILL.md"

    # Frontmatter: file must start with a --- line, then a closing --- line.
    if [[ "$(sed -n '1p' "${file}")" != "---" ]]; then
        echo "FAIL ${name}: no frontmatter block (missing leading ---)"
        fail=1
        continue
    fi

    close_line=$(awk 'NR>1 && /^---$/ {print NR; exit}' "${file}")
    if [[ -z "${close_line}" ]]; then
        echo "FAIL ${name}: no frontmatter block (missing closing ---)"
        fail=1
        continue
    fi

    frontmatter=$(sed -n "2,$((close_line - 1))p" "${file}")

    fm_name=$(printf '%s\n' "${frontmatter}" | sed -n 's/^name:[[:space:]]*//p' | head -n1)
    fm_name="${fm_name%\"}"
    fm_name="${fm_name#\"}"
    fm_name="${fm_name%\'}"
    fm_name="${fm_name#\'}"
    if [[ "${fm_name}" != "${name}" ]]; then
        echo "FAIL ${name}: name: '${fm_name}' does not match directory name '${name}'"
        fail=1
    fi

    fm_description=$(printf '%s\n' "${frontmatter}" | sed -n 's/^description:[[:space:]]*//p' | head -n1)
    fm_description="${fm_description%\"}"
    fm_description="${fm_description#\"}"
    fm_description="${fm_description%\'}"
    fm_description="${fm_description#\'}"
    if [[ -z "${fm_description}" ]]; then
        echo "FAIL ${name}: description: is empty or missing"
        fail=1
    elif [[ "${#fm_description}" -ge 600 ]]; then
        echo "FAIL ${name}: description: is ${#fm_description} characters, must be under 600"
        fail=1
    fi

    line_count=$(wc -l <"${file}")
    if [[ "${line_count}" -ge 300 ]]; then
        echo "FAIL ${name}: SKILL.md is ${line_count} lines, must be under 300"
        fail=1
    fi

    for pattern in "${patterns[@]}"; do
        if grep -nE "${pattern}" "${file}" >/dev/null 2>&1; then
            echo "FAIL ${name}: ${rel_file} matches secret pattern: ${pattern}"
            fail=1
        fi
    done
done

if [[ "${fail}" -eq 0 ]]; then
    echo "OK: all skills passed"
fi

exit "${fail}"
