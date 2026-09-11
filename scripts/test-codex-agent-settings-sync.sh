#!/usr/bin/env bash
# Exercise scripts/codex-agent-settings-sync.py against a fixture config.toml
# that stands in for the real ChatGPT-desktop-owned ~/.codex/config.toml:
# comments, an MCP server, a project trust setting, a plugin table, and an
# unknown key already sitting inside [agents] that this script does not
# manage. Every one of those must round-trip byte-for-byte; only the six
# managed keys may change.
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
sync_script="${repo_root}/scripts/codex-agent-settings-sync.py"
tmp_root=$(mktemp -d "${TMPDIR:-/tmp}/codex-agent-settings.XXXXXX")

# This hook is `language: script`, so it inherits whatever shell invoked
# pre-commit; a bare `pre-commit run --all-files` has not necessarily
# activated the project venv. tomlkit lives in requirements.txt and is only
# guaranteed to be importable there, so resolve that interpreter explicitly
# instead of trusting ambient `python3` on PATH (which may be a pyenv shim
# with no project dependencies at all). Falls back to ambient python3 only
# if the venv is genuinely absent; if that ambient interpreter also lacks
# tomlkit, fail with one clear actionable message instead of a traceback.
python_bin="${VIRTUAL_ENV:-${repo_root}/venv}/bin/python3"
[[ -x "$python_bin" ]] || python_bin="python3"
if ! "$python_bin" -c 'import tomlkit' >/dev/null 2>&1; then
    printf 'tomlkit not importable via %s\n' "$python_bin" >&2
    printf 'Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt\n' >&2
    printf '(or just: source venv/bin/activate, if the venv already exists)\n' >&2
    exit 1
fi

cleanup() {
    ls -d "$tmp_root"
    rm -rf "$tmp_root"  # self-created mktemp dir, not user data
}
trap cleanup EXIT

config_path="${tmp_root}/config.toml"

cat >"$config_path" <<'EOF'
# Desktop-managed Codex config. Comments and section order here must survive
# byte-for-byte; codex-agent-settings-sync.py only ever touches six keys.
model = "gpt-5.4-mini"
model_reasoning_effort = "low"
personality = "pragmatic"

[mcp_servers.playwright]
command = "npx"
args = ["@playwright/mcp@latest"]

[agents]
# Unknown key this script has never heard of; must survive untouched.
some_future_flag = true
enabled = false
max_concurrent_threads_per_session = 1
default_subagent_model = "stale-model"
default_subagent_reasoning_effort = "low"

[projects."/Users/dkelly/Projects/dotforge"]
trust_level = "trusted"

[plugins."documents@openai-primary-runtime"]
enabled = true
EOF

desired_json="${tmp_root}/desired.json"
cat >"$desired_json" <<'EOF'
{
  "model": "gpt-5.6-sol",
  "model_reasoning_effort": "medium",
  "agents": {
    "enabled": true,
    "max_concurrent_threads_per_session": 3,
    "default_subagent_model": "gpt-5.6-luna",
    "default_subagent_reasoning_effort": "medium"
  }
}
EOF

before_hash=$(shasum -a 256 "$config_path" | awk '{print $1}')

# --check must report "changed" without writing anything.
check_out=$("$python_bin" "$sync_script" --config "$config_path" --desired "$desired_json" --check)
[[ "$check_out" == "changed" ]] || { printf '--check on a dirty file did not report changed: %s\n' "$check_out" >&2; exit 1; }
after_check_hash=$(shasum -a 256 "$config_path" | awk '{print $1}')
[[ "$before_hash" == "$after_check_hash" ]] || { printf -- '--check mode wrote to the file\n' >&2; exit 1; }

# Real run must report "changed" and actually write.
run_out=$("$python_bin" "$sync_script" --config "$config_path" --desired "$desired_json")
[[ "$run_out" == "changed" ]] || { printf 'first real run did not report changed: %s\n' "$run_out" >&2; exit 1; }

# Managed keys took the desired values.
"$python_bin" - "$config_path" <<'PY'
import sys
import tomlkit

doc = tomlkit.parse(open(sys.argv[1]).read())
assert doc["model"] == "gpt-5.6-sol", doc["model"]
assert doc["model_reasoning_effort"] == "medium", doc["model_reasoning_effort"]
agents = doc["agents"]
assert agents["enabled"] is True, agents["enabled"]
assert agents["max_concurrent_threads_per_session"] == 3, agents["max_concurrent_threads_per_session"]
assert agents["default_subagent_model"] == "gpt-5.6-luna", agents["default_subagent_model"]
assert agents["default_subagent_reasoning_effort"] == "medium", agents["default_subagent_reasoning_effort"]
# Unmanaged slices survive untouched.
assert agents["some_future_flag"] is True
assert doc["personality"] == "pragmatic"
assert doc["mcp_servers"]["playwright"]["command"] == "npx"
assert doc["projects"]["/Users/dkelly/Projects/dotforge"]["trust_level"] == "trusted"
assert doc["plugins"]["documents@openai-primary-runtime"]["enabled"] is True
print("managed keys changed, unrelated slices preserved")
PY

# Comments must survive verbatim.
grep -qF '# Desktop-managed Codex config.' "$config_path" || { printf 'leading comment lost\n' >&2; exit 1; }
grep -qF '# Unknown key this script has never heard of; must survive untouched.' "$config_path" || {
    printf 'comment inside [agents] lost\n' >&2
    exit 1
}

after_first_hash=$(shasum -a 256 "$config_path" | awk '{print $1}')

# Second run against already-desired state must report "unchanged" and write nothing.
second_check_out=$("$python_bin" "$sync_script" --config "$config_path" --desired "$desired_json" --check)
[[ "$second_check_out" == "unchanged" ]] || { printf 'second --check did not report unchanged: %s\n' "$second_check_out" >&2; exit 1; }

second_run_out=$("$python_bin" "$sync_script" --config "$config_path" --desired "$desired_json")
[[ "$second_run_out" == "unchanged" ]] || { printf 'second real run did not report unchanged: %s\n' "$second_run_out" >&2; exit 1; }

after_second_hash=$(shasum -a 256 "$config_path" | awk '{print $1}')
[[ "$after_first_hash" == "$after_second_hash" ]] || { printf 'second run changed the file\n' >&2; exit 1; }

printf 'codex-agent-settings-sync.py is surgical and idempotent\n'
