#!/usr/bin/env bash
# Opt-in, read-only, usage-consuming live canaries for cross-harness lead ->
# worker routing (docs/playbooks/cross-harness-lead-worker-routing.md, R7).
#
# Static renderer/validator checks (make validate-opencode, make test-ai-agents,
# check-agent-config-drift.sh, validate-agent-routing.py) prove config is well
# formed. None of them prove a model actually reads a delegation prompt and
# calls a worker. This script makes real, billed calls against installed
# harnesses to capture that evidence, then asserts the working tree is
# byte-identical afterward.
#
# Never wire this into make lint, make ci or pre-commit: every run spends real
# model usage against live provider accounts.
set -uo pipefail

# Associative arrays below need bash 4+; macOS ships bash 3.2 at /bin/bash.
# Degrade to one clear advisory line instead of a `declare -A` traceback.
if (( ${BASH_VERSINFO[0]} < 4 )); then
    printf 'advisory: running under bash %s (need bash 4+); rerun with Homebrew bash on PATH\n' \
        "${BASH_VERSION%%[^0-9.]*}" >&2
    exit 2
fi

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

# Canonical, provider-neutral routing policy -- same source check-agent-config-
# drift.sh's policy-marker check reads. Never hardcode a model id here.
routing_dir="${repo_root}/host_files/localhost/ai/routing"

timeout_s=300
self_test=0
harness_arg=""
overall_rc=0

# One line per harness result, appended as "LABEL harness: evidence/reason".
# LABEL is one of PASS, FAIL, UNAVAILABLE. UNAVAILABLE means the harness
# rejected the call for quota/credits/auth reasons unrelated to routing
# correctness; it is never printed as PASS, and it still makes the overall
# exit code non-zero because live routing evidence was not actually obtained.
declare -a result_lines=()

usage() {
    cat <<'EOF'
Usage: scripts/test-agent-routing-live.sh --harness <name> [--self-test]
       scripts/test-agent-routing-live.sh --help

  --harness NAME   One of: opencode, claude-personal, claude-work, codex,
                   forge, all. Required unless --help is given.
  --self-test      Additionally allow the pending README.md and runner script
                   changes in the pre-flight worktree check, for use while
                   this ticket is itself being verified. Otherwise only
                   "?? docs/" is allowed, before and after every harness.
  --help           Print this message and exit 0. Read-only, no harness call.

Opt-in, read-only, usage-consuming canaries that prove a lead model actually
delegates to a worker model in each installed harness. Every call is billed
against a live provider account -- never run this from CI, make lint, make ci
or a pre-commit hook. See docs/playbooks/cross-harness-lead-worker-routing.md
(R7) for the full behavior contract.

Prints one "PASS harness: evidence", "FAIL harness: reason" or
"UNAVAILABLE harness: reason" line per requested harness, plus one fixed T3
informational block (two manual prompts and a read-only evidence query --
T3 threads cannot be created non-interactively, so this script only prints
them; it never drives the T3 UI or writes to T3's SQLite state).

Exit code is non-zero if any requested harness result is FAIL or UNAVAILABLE.
EOF
}

while (( $# > 0 )); do
    case "$1" in
        --harness)
            harness_arg="${2:-}"
            shift 2
            ;;
        --self-test)
            self_test=1
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            printf 'unknown argument: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ -z "$harness_arg" ]]; then
    printf -- '--harness is required\n' >&2
    usage >&2
    exit 2
fi

case "$harness_arg" in
    opencode|claude-personal|claude-work|codex|forge|all) ;;
    *)
        printf 'unknown --harness value: %s\n' "$harness_arg" >&2
        exit 2
        ;;
esac

# --- worktree status guard (behavior 1, 10) --------------------------------

capture_status() {
    git status --porcelain
}

status_allowed() {
    # $1: status text to check. Returns 0 if every line is on the allowlist.
    local status_text="$1" line
    local -a allow=('?? docs/')
    if (( self_test )); then
        allow+=('?? scripts/test-agent-routing-live.sh' ' M README.md' 'M  README.md' 'A  scripts/test-agent-routing-live.sh' '?? README.md')
    fi
    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        local ok=0 candidate
        for candidate in "${allow[@]}"; do
            [[ "$line" == "$candidate" ]] && { ok=1; break; }
        done
        (( ok )) || return 1
    done <<<"$status_text"
    return 0
}

before_status=$(capture_status)
if ! status_allowed "$before_status"; then
    printf 'FAIL preflight: worktree has unexpected tracked changes before start:\n%s\n' "$before_status" >&2
    exit 1
fi
# Baseline tracked diff. In self-test mode this is not empty (the pending
# README.md/runner changes this ticket is verifying), so the postflight
# check below asserts no *change* from this baseline rather than a literal
# zero diff; in normal mode the baseline is already empty because
# status_allowed only accepts "?? docs/", so the two checks coincide.
before_diff=$(git diff)

# --- temp workspace + cleanup (behavior 9) ----------------------------------

log_dir=$(mktemp -d "${TMPDIR:-/tmp}/agent-routing-live.XXXXXX")

cleanup() {
    ls -d "$log_dir"
    trash "$log_dir"
}
trap cleanup EXIT

# --- shared helpers ----------------------------------------------------------

pass_line() { result_lines+=("PASS $1: $2"); }
fail_line() { result_lines+=("FAIL $1: $2"); overall_rc=1; }
unavailable_line() { result_lines+=("UNAVAILABLE $1: $2"); overall_rc=1; }

# Matches provider quota/credit/auth exhaustion text, not a routing failure.
# Observed live on 2026-09-07: OpenAI workspace credits depleted
# ("usage_limit_reached") affects every openai-backed harness (OpenCode,
# Codex, and Forge, which forge agent list confirms all run on Codex);
# separately, an Anthropic per-request spend cap ("individual spend limit")
# can reject a root-delegation call even when a plain worker call on the same
# account just succeeded. Both are unavailable-harness conditions, not script
# bugs, and neither is printed as PASS.
is_unavailable_text() {
    grep -qiE 'usage_limit_reached|usage limit|credits_depleted|out of credits|no credits|spend limit|insufficient_quota|429 |"429"| 429$|rate.?limit' <<<"$1"
}

first_line_matching() {
    grep -ioE ".{0,40}(${2}).{0,120}" <<<"$1" | head -n1
}

# --- OpenCode ----------------------------------------------------------------

check_opencode() {
    local harness="opencode"
    local out="${log_dir}/opencode.jsonl" err="${log_dir}/opencode.err"
    local before_ms
    before_ms=$(( $(date +%s) * 1000 ))
    local prompt='Read-only routing canary. Delegate to your worker subagent exactly this task: return only the first heading line of README.md, with no edits. Report back the workers answer verbatim. Do not edit any file yourself.'
    timeout "$timeout_s" opencode run --agent orchestrator --dir "$repo_root" --format json "$prompt" \
        >"$out" 2>"$err"
    local rc=$?
    local combined
    combined=$(cat "$out" "$err" 2>/dev/null)
    if is_unavailable_text "$combined"; then
        unavailable_line "$harness" "$(first_line_matching "$combined" 'usage_limit_reached|usage limit|credits|spend limit|quota|rate.?limit')"
        return
    fi
    if (( rc != 0 )); then
        fail_line "$harness" "opencode run exited $rc: $(tail -c 300 "$err")"
        return
    fi
    if ! grep -q '"role":"assistant"' "$out" 2>/dev/null && ! grep -q '"type":"message"' "$out" 2>/dev/null; then
        fail_line "$harness" "no assistant/message evidence in JSON output"
        return
    fi
    # Read-only DB query for the parent (orchestrator) -> child (worker)
    # session pair created by this run. Never write to opencode.db.
    local db="${HOME}/.local/share/opencode/opencode.db"
    if [[ ! -f "$db" ]]; then
        fail_line "$harness" "opencode.db not found at $db"
        return
    fi
    local child
    child=$(sqlite3 -readonly "$db" "
        select s.id || '|' || s.agent || '|' || s.model
        from session s
        join session p on p.id = s.parent_id
        where p.agent = 'orchestrator'
          and s.agent = 'worker'
          and p.directory = '${repo_root}'
          and p.time_created >= ${before_ms}
        order by s.time_created desc
        limit 1;
    " 2>/dev/null)
    if [[ -z "$child" ]]; then
        fail_line "$harness" "no orchestrator -> worker child session recorded in opencode.db since $before_ms"
        return
    fi
    pass_line "$harness" "JSON shows assistant turn; opencode.db child session ${child}"
}

# --- Claude (personal + work share this shape) -------------------------------

check_claude() {
    local harness="$1" bin="$2"
    local worker_model="claude-sonnet-5" root_model="claude-opus-5"
    local out_a="${log_dir}/${harness}-worker.json" err_a="${log_dir}/${harness}-worker.err"
    local direct_prompt='Read-only self-test canary. Return only the first heading line of README.md. Do not edit any file.'
    timeout "$timeout_s" "$bin" --agent worker --model "$worker_model" --output-format json -p "$direct_prompt" \
        >"$out_a" 2>"$err_a"
    local rc_a=$?
    local combined_a
    combined_a=$(cat "$out_a" "$err_a" 2>/dev/null)
    if is_unavailable_text "$combined_a"; then
        unavailable_line "$harness" "direct worker call: $(first_line_matching "$combined_a" 'usage_limit_reached|usage limit|credits|spend limit|quota|rate.?limit')"
        return
    fi
    if (( rc_a != 0 )); then
        fail_line "$harness" "direct worker call exited $rc_a: $(tail -c 300 "$err_a")"
        return
    fi
    local worker_keys
    worker_keys=$(python3 -c '
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception as exc:
    print("PARSE_ERROR:" + str(exc)); sys.exit(0)
if d.get("is_error"):
    print("API_ERROR:" + str(d.get("result", ""))[:200]); sys.exit(0)
print(",".join(sorted(d.get("modelUsage", {}).keys())))
' "$out_a")
    if [[ "$worker_keys" == PARSE_ERROR:* || "$worker_keys" == API_ERROR:* ]]; then
        if is_unavailable_text "$worker_keys"; then
            unavailable_line "$harness" "direct worker call: $worker_keys"
        else
            fail_line "$harness" "direct worker call: $worker_keys"
        fi
        return
    fi
    if [[ "$worker_keys" != *"$worker_model"* ]]; then
        fail_line "$harness" "direct worker call did not report model key $worker_model (got: $worker_keys)"
        return
    fi

    local out_b="${log_dir}/${harness}-root.json" err_b="${log_dir}/${harness}-root.err"
    local delegate_prompt='Read-only self-test canary. Delegate to your worker subagent exactly this task: return only the first heading line of README.md, with no edits. Report back the workers answer verbatim. Do not edit any file yourself.'
    timeout "$timeout_s" "$bin" --output-format json -p "$delegate_prompt" \
        >"$out_b" 2>"$err_b"
    local rc_b=$?
    local combined_b
    combined_b=$(cat "$out_b" "$err_b" 2>/dev/null)
    if is_unavailable_text "$combined_b"; then
        unavailable_line "$harness" "worker direct call passed ($worker_keys); root delegation call unavailable: $(first_line_matching "$combined_b" 'usage_limit_reached|usage limit|credits|spend limit|quota|rate.?limit')"
        return
    fi
    if (( rc_b != 0 )); then
        fail_line "$harness" "root delegation call exited $rc_b: $(tail -c 300 "$err_b")"
        return
    fi
    local root_result
    root_result=$(python3 -c '
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception as exc:
    print("PARSE_ERROR:" + str(exc)); sys.exit(0)
if d.get("is_error"):
    print("API_ERROR:" + str(d.get("result", ""))[:200]); sys.exit(0)
keys = sorted(d.get("modelUsage", {}).keys())
spawned = d.get("subagent_stats", {}).get("spawned", 0)
print("keys=" + ",".join(keys) + " spawned=" + str(spawned))
' "$out_b")
    if [[ "$root_result" == PARSE_ERROR:* || "$root_result" == API_ERROR:* ]]; then
        if is_unavailable_text "$root_result"; then
            unavailable_line "$harness" "worker direct call passed ($worker_keys); root delegation: $root_result"
        else
            fail_line "$harness" "root delegation call: $root_result"
        fi
        return
    fi
    if [[ "$root_result" != *"$worker_model"* ]]; then
        fail_line "$harness" "root delegation did not show worker model $worker_model in modelUsage ($root_result)"
        return
    fi
    pass_line "$harness" "direct worker modelUsage=[$worker_keys]; root delegation $root_result (expected root $root_model, worker $worker_model)"
}

# --- Codex --------------------------------------------------------------------

# Resolves the worker tier's OpenAI model/effort from the canonical routing
# policy (models.yml + workflow.yml), the same files and the same graceful-
# degradation style check-agent-config-drift.sh's policy-marker check uses:
# every precondition below is reported as a single-line failure to the caller
# (via return 1 + stderr) rather than a bash traceback, since bash 3.2, a
# missing python3, missing PyYAML, missing policy files, or malformed YAML are
# all normal states on some machine, not this script's bug.
resolve_codex_worker_model() {
    if ! command -v python3 >/dev/null 2>&1; then
        echo "python3 not found on PATH" >&2
        return 1
    fi
    if ! python3 -c 'import yaml' >/dev/null 2>&1; then
        echo "$(command -v python3) has no PyYAML installed" >&2
        return 1
    fi
    if [[ ! -f "${routing_dir}/models.yml" || ! -f "${routing_dir}/workflow.yml" ]]; then
        echo "${routing_dir}/models.yml or workflow.yml missing" >&2
        return 1
    fi
    local resolved
    if ! resolved=$(python3 - "${routing_dir}/models.yml" "${routing_dir}/workflow.yml" 2>&1 <<'PY'
import sys
import yaml

models_path, workflow_path = sys.argv[1], sys.argv[2]
models = yaml.safe_load(open(models_path))
workflow = yaml.safe_load(open(workflow_path))

tier_name = workflow["roles"]["worker"]["tier"]
tier = models["tiers"][tier_name]
openai = tier["openai"]
print(openai["model"])
print(openai.get("effort") or "")
PY
    ); then
        echo "routing policy YAML failed to parse (models.yml/workflow.yml): ${resolved}" >&2
        return 1
    fi
    printf '%s\n' "$resolved"
}

check_codex() {
    local harness="codex"
    local out="${log_dir}/codex.jsonl" err="${log_dir}/codex.err"
    local prompt='Read-only routing canary. Delegate to your configured worker subagent exactly this task: return only the first heading line of README.md, with no edits. Report back the workers answer verbatim. Do not edit any file yourself.'
    timeout "$timeout_s" codex exec --json -C "$repo_root" "$prompt" \
        >"$out" 2>"$err"
    local rc=$?
    local combined
    combined=$(cat "$out" "$err" 2>/dev/null)
    if is_unavailable_text "$combined"; then
        unavailable_line "$harness" "$(first_line_matching "$combined" 'usage_limit_reached|usage limit|credits|spend limit|quota|rate.?limit')"
        return
    fi
    if (( rc != 0 )); then
        fail_line "$harness" "codex exec exited $rc: $(tail -c 300 "$err")"
        return
    fi

    # The parent (lead) rollout's own "model" field is the LEAD's model, not
    # the worker's -- proving worker-tier routing means following the parent's
    # SubAgentActivity to the child (worker) rollout and reading *its* model.
    local session_id
    session_id=$(grep -oE '"(session_id|conversation_id|thread_id)":"[a-f0-9-]+"' "$out" | head -n1 | cut -d'"' -f4)
    if [[ -z "$session_id" ]]; then
        fail_line "$harness" "no session id found in codex exec --json output to locate the parent rollout"
        return
    fi
    local rollout
    rollout=$(find "${HOME}/.codex/sessions" -type f -name "*${session_id}*" 2>/dev/null | head -n1)
    if [[ -z "$rollout" ]]; then
        fail_line "$harness" "no on-disk rollout found for session $session_id"
        return
    fi

    codex_verify_worker_delegation "$harness" "$rollout"
}

# Split out so the offline fixture check (used by this ticket's own
# verification, never by a live run) can call the same parsing logic against
# an on-disk rollout pair without re-running `codex exec`.
codex_verify_worker_delegation() {
    local harness="$1" rollout="$2"

    local subagent_lines
    subagent_lines=$(grep -F '"type":"SubAgentActivity"' "$rollout" 2>/dev/null)
    if [[ -z "$subagent_lines" ]]; then
        fail_line "$harness" "no SubAgentActivity found in parent rollout $rollout -- worker delegation cannot be confirmed"
        return
    fi
    local agent_thread_id
    agent_thread_id=$(grep -oE '"agent_thread_id":"[a-f0-9-]+"' <<<"$subagent_lines" | tail -n1 | cut -d'"' -f4)
    if [[ -z "$agent_thread_id" ]]; then
        fail_line "$harness" "SubAgentActivity in $rollout has no agent_thread_id"
        return
    fi

    if ! grep -qF '\"agent_type\":\"worker\"' "$rollout"; then
        fail_line "$harness" "spawn_agent call in $rollout does not carry agent_type=worker"
        return
    fi

    local child_rollout
    child_rollout=$(find "${HOME}/.codex/sessions" -type f -name "*${agent_thread_id}*" ! -path "$rollout" 2>/dev/null | head -n1)
    if [[ -z "$child_rollout" ]]; then
        fail_line "$harness" "SubAgentActivity names child thread $agent_thread_id but no rollout file was found for it under ~/.codex/sessions"
        return
    fi

    local worker_policy
    if ! worker_policy=$(resolve_codex_worker_model 2>&1); then
        fail_line "$harness" "cannot resolve expected worker model from routing policy: $worker_policy"
        return
    fi
    local expected_model
    expected_model=$(sed -n '1p' <<<"$worker_policy")
    if [[ -z "$expected_model" ]]; then
        fail_line "$harness" "routing policy resolved no worker model for openai"
        return
    fi

    if ! grep -qF "\"model\":\"${expected_model}\"" "$child_rollout"; then
        local observed
        observed=$(grep -oE '"model":"[^"]*"' "$child_rollout" | sort -u | tr '\n' ' ')
        fail_line "$harness" "child rollout $child_rollout (thread $agent_thread_id) never shows expected worker model \"${expected_model}\"; models actually observed: ${observed:-none}"
        return
    fi

    pass_line "$harness" "SubAgentActivity child thread ${agent_thread_id}; child rollout $child_rollout confirms worker model \"${expected_model}\""
}

# --- Forge ----------------------------------------------------------------------

check_forge() {
    # Forge 2.13.21 exposes only built-in forge/muse/sage agents (provider
    # Codex, per `forge agent list`); there is no custom-agent authoring
    # surface, so this only proves Forge understands the shared instructions
    # and states its reduced native-delegation support honestly -- it is not
    # evidence of native lead -> worker delegation the way the other harnesses
    # provide it (behavior 7).
    local harness="forge"
    local out="${log_dir}/forge.out" err="${log_dir}/forge.err"
    local prompt='Read-only self-test canary. State honestly: do you support defining or delegating to a custom named subagent the way Claude, Codex or OpenCode do? Then return only the first heading line of README.md. Do not edit any file.'
    timeout "$timeout_s" forge --prompt "$prompt" \
        >"$out" 2>"$err"
    local rc=$?
    local combined
    combined=$(cat "$out" "$err" 2>/dev/null)
    if is_unavailable_text "$combined"; then
        unavailable_line "$harness" "$(first_line_matching "$combined" 'usage_limit_reached|usage limit|credits|spend limit|quota|rate.?limit')"
        return
    fi
    if (( rc != 0 )); then
        fail_line "$harness" "forge --prompt exited $rc: $(tail -c 300 "$err")"
        return
    fi
    if [[ ! -s "$out" ]]; then
        fail_line "$harness" "forge --prompt produced no output"
        return
    fi
    pass_line "$harness" "reduced-mode answer received (no native custom-agent delegation claimed): $(head -c 200 "$out" | tr '\n' ' ')"
}

# --- T3 (print-only, behavior 8) ---------------------------------------------

print_t3_info() {
    cat <<'EOF'

T3 (informational only -- cannot be created non-interactively; never automated):

  Manual prompt, fresh T3 Claude thread:
    Read-only routing canary. Return your role, configured model tier, and the
    first README heading. Do not edit any file.

  Manual prompt, fresh T3 Codex thread:
    Read-only routing canary. Return your role, configured model tier, and the
    first README heading. Do not edit any file.
EOF
    local db="${HOME}/.t3/userdata/state.sqlite"
    if [[ -f "$db" ]]; then
        echo "  Read-only evidence query (run by hand after a manual thread above):"
        echo "    sqlite3 -readonly '${db}' \\"
        echo "      \"select t.thread_id, t.title, r.provider_name, r.status, r.last_seen_at"
        echo "       from projection_threads t join provider_session_runtime r on r.thread_id = t.thread_id"
        echo "       order by t.updated_at desc limit 5;\""
    else
        echo "  T3 state.sqlite not found at ${db}; skip the evidence query."
    fi
}

# --- dispatch -----------------------------------------------------------------

run_harness() {
    case "$1" in
        opencode) check_opencode ;;
        claude-personal) check_claude claude-personal claude ;;
        claude-work) check_claude claude-work claude-work ;;
        codex) check_codex ;;
        forge) check_forge ;;
    esac
}

# Rolling baseline, advanced after every harness so the next harness's check
# only covers what happened during its own run. A mutation is always caught
# immediately after the harness that caused it -- including one that a later
# harness would otherwise revert before an end-of-run-only check could see it
# -- and is attributed to that harness by name rather than to the whole run.
current_status="$before_status"
current_diff="$before_diff"

assert_worktree_unchanged() {
    # $1: harness label to attribute any detected mutation to.
    local harness="$1" status_now diff_now
    status_now=$(capture_status)
    diff_now=$(git diff)
    if [[ "$status_now" != "$current_status" || "$diff_now" != "$current_diff" ]]; then
        fail_line "$harness" "mutated the worktree (git status or git diff changed after this harness ran)"
    fi
    current_status="$status_now"
    current_diff="$diff_now"
}

if [[ "$harness_arg" == all ]]; then
    for h in opencode claude-personal claude-work codex forge; do
        run_harness "$h"
        assert_worktree_unchanged "$h"
    done
else
    run_harness "$harness_arg"
    assert_worktree_unchanged "$harness_arg"
fi

print_t3_info

printf '\n'
for line in "${result_lines[@]}"; do
    printf '%s\n' "$line"
done

# --- post-flight worktree guard (behavior 10), final backstop ---------------
# Per-harness attribution already happened in assert_worktree_unchanged above;
# this is a final check against the original pre-run baseline in case
# anything slipped past it (e.g. a mutation during print_t3_info's read-only
# T3 query, which runs no harness command but is cheap insurance to also
# cover here).

after_status=$(capture_status)
if [[ "$before_status" != "$after_status" ]]; then
    printf 'FAIL postflight: worktree status changed during run:\nbefore:\n%s\nafter:\n%s\n' \
        "$before_status" "$after_status" >&2
    overall_rc=1
fi
after_diff=$(git diff)
if [[ "$before_diff" != "$after_diff" ]]; then
    printf 'FAIL postflight: tracked file content changed during run (git diff differs from pre-run baseline)\n' >&2
    overall_rc=1
elif (( ! self_test )); then
    # Normal mode's baseline is already empty, so this is the literal
    # "git diff --exit-code" ticket wording as a direct, real invocation.
    if ! git diff --exit-code >/dev/null 2>&1; then
        printf 'FAIL postflight: tracked files were modified during run (git diff --exit-code)\n' >&2
        overall_rc=1
    fi
fi

exit "$overall_rc"
