#!/usr/bin/env bash
#
# Refuse commits that would put unencrypted secrets in the repo.
#
# Two checks:
#   1. Paths that must always be vault-encrypted really are.
#   2. YAML that is not vault-encrypted does not look like it holds a credential.
#
# Everything is read from the staged blob rather than the working tree, so a
# file that is staged clean and then dirtied cannot slip past.
#
# Previously lived untracked in .git/hooks/pre-commit.legacy, where it iterated
# every staged path including deletions and so errored on any file the commit
# removed.
set -uo pipefail

fail=0

# Paths that are meaningless unless encrypted. Matched with bash globs.
must_encrypt=(
    'host_files/*/id_rsa'
    'host_files/*/id_ed25519'
    'host_files/*/vault_pass.txt'
    'host_vars/*/vault.yml'
)

# Rough credential shapes for anything else.
patterns=(
    'password[[:space:]]*[=:][[:space:]]*["'"'"'][^"'"'"' ]+["'"'"']'
    'secret[[:space:]]*[=:][[:space:]]*["'"'"'][^"'"'"' ]+["'"'"']'
    'token[[:space:]]*[=:][[:space:]]*["'"'"'][^"'"'"' ]+["'"'"']'
    'BEGIN [A-Z ]*PRIVATE KEY'
)

is_encrypted() {
    # Vault files declare themselves on the first line. The marker is a literal,
    # not a variable.
    # shellcheck disable=SC2016
    [[ "$(printf '%s' "$1" | head -c 14)" == '$ANSIBLE_VAULT' ]]
}

# --diff-filter=ACMR drops deletions, so removing a file no longer trips this.
# -z plus read -d handles paths containing spaces.
while IFS= read -r -d '' file; do
    # Staged content, not the working tree copy.
    content=$(git show ":$file" 2>/dev/null) || continue

    # Skip anything that is not text.
    if printf '%s' "$content" | LC_ALL=C grep -qP '\x00' 2>/dev/null; then
        continue
    fi

    for glob in "${must_encrypt[@]}"; do
        # shellcheck disable=SC2053  # glob match is the point
        if [[ "$file" == $glob ]]; then
            if ! is_encrypted "$content"; then
                echo "❌ $file must be vault-encrypted but is not."
                echo "   ansible-vault encrypt $file"
                fail=1
            fi
            continue 2
        fi
    done

    case "$file" in
        *.yml | *.yaml) ;;
        *) continue ;;
    esac

    is_encrypted "$content" && continue

    for pattern in "${patterns[@]}"; do
        if printf '%s' "$content" | grep -Eq "$pattern"; then
            echo "❌ Possible unencrypted secret in $file (matched: $pattern)"
            echo "   Move it into host_vars/<host>/vault.yml, or encrypt the file:"
            echo "   ansible-vault encrypt $file"
            fail=1
            break
        fi
    done
done < <(git diff --cached -z --name-only --diff-filter=ACMR)

if [[ $fail -eq 0 ]]; then
    echo "✅ No unencrypted secrets detected."
fi

exit $fail
