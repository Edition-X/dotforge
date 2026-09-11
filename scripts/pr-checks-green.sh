#!/usr/bin/env bash
#
# Exit 0 only when every check on a pull request has completed successfully.
#
# `gh pr checks --watch --fail-fast` returns while a sibling workflow run is
# still pending and does not reliably carry a failure in its exit status, so a
# merge chained on it once landed a red pull request. This reads the rollup
# itself and refuses anything that is not COMPLETED + SUCCESS/NEUTRAL/SKIPPED.
#
# Usage: scripts/pr-checks-green.sh <pr-number> [timeout-seconds]
set -euo pipefail

number="${1:?pull request number}"
timeout="${2:-1800}"
deadline=$(( $(date +%s) + timeout ))

while :; do
    rollup=$(gh pr view "$number" --json statusCheckRollup --jq '.statusCheckRollup[] | "\(.name // .context)\t\(.status // "COMPLETED")\t\(.conclusion // .state // "")"')
    if [[ -z "$rollup" ]]; then
        echo "pr $number: no checks reported yet"
    else
        pending=$(printf '%s\n' "$rollup" | awk -F'\t' '$2 != "COMPLETED"' || true)
        failed=$(printf '%s\n' "$rollup" | awk -F'\t' '$2 == "COMPLETED" && $3 !~ /^(SUCCESS|NEUTRAL|SKIPPED)$/' || true)
        if [[ -n "$failed" ]]; then
            printf 'pr %s: failed checks\n%s\n' "$number" "$failed"
            exit 1
        fi
        if [[ -z "$pending" ]]; then
            printf 'pr %s: green (%s checks)\n' "$number" "$(printf '%s\n' "$rollup" | wc -l | tr -d ' ')"
            exit 0
        fi
        printf 'pr %s: waiting on %s check(s)\n' "$number" "$(printf '%s\n' "$pending" | wc -l | tr -d ' ')"
    fi
    if (( $(date +%s) >= deadline )); then
        echo "pr $number: timed out after ${timeout}s"
        exit 2
    fi
    sleep 30
done
