#!/usr/bin/env bash
#
# Pin monitoring-config's inventory submodule to an exact, already-merged
# sunrise_ansible_inventory commit and commit the pointer move.
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage: bump-inventory.sh <inventory-sha> [inventory-pr-url]

Pin monitoring-config's inventory submodule (ansible/inventory) to an exact,
already-merged sunrise_ansible_inventory commit and commit the pointer move.

`make -C ansible submodule-update` moves the pointer to whatever the remote
main is at that second, which hides what a branch was actually tested
against. This pins a SHA you name (the one the inventory PR merged as, from
`gh pr view <n> --json mergeCommit`) so the monitoring-config PR records it.
Refuses a SHA that is not on the inventory's main.

Run from inside a monitoring-config checkout or worktree.
USAGE
}

case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    "") usage >&2; exit 2 ;;
esac

sha="$1"
pr_url="${2:-}"
submodule="ansible/inventory"

root=$(git rev-parse --show-toplevel)
cd "$root"
if [[ "$(git config -f .gitmodules --get submodule.ansible/inventory.path 2>/dev/null || true)" != "$submodule" ]]; then
    echo "not a monitoring-config checkout: ${submodule} is not a submodule here" >&2
    exit 1
fi

git submodule update --init "$submodule"
git -C "$submodule" fetch --quiet origin main
full_sha=$(git -C "$submodule" rev-parse --verify "${sha}^{commit}")
if ! git -C "$submodule" merge-base --is-ancestor "$full_sha" origin/main; then
    echo "refusing: ${full_sha} is not on sunrise_ansible_inventory main (merge the inventory PR first)" >&2
    exit 1
fi

before=$(git rev-parse "HEAD:${submodule}")
if [[ "$before" == "$full_sha" ]]; then
    echo "submodule already at ${full_sha}"
    exit 0
fi

git -C "$submodule" checkout --quiet "$full_sha"
git add "$submodule"
subject=$(git -C "$submodule" log -1 --format=%s "$full_sha")
body="sunrise_ansible_inventory: ${subject}"
[[ -n "$pr_url" ]] && body+=$'\n'"Inventory PR: ${pr_url}"
git commit --quiet -m "Bump inventory submodule to merged main (${full_sha:0:7})" -m "$body"
echo "submodule ${before:0:7} -> ${full_sha:0:7}, committed $(git rev-parse --short HEAD)"
