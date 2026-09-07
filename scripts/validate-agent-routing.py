#!/usr/bin/env python3
"""Validate the canonical, provider-neutral agent routing policy.

This is the non-Ansible twin of ``roles/ai_agents/tasks/routing.yml``: both
load ``host_files/localhost/ai/routing/models.yml`` and ``workflow.yml`` and
fail before any harness is rendered if the policy is malformed — missing
tiers, bad efforts, unknown roles, cyclic escalation, or a provider model ID
that has leaked out of its one canonical home. This script runs the fuller
set of checks (topology, handoff contract, prompt/skill content) outside a
playbook, so pre-commit and ``make lint`` can catch drift without deploying
anything.

On success this prints exactly ``Agent routing source valid`` and exits 0.
On failure it prints one actionable line per problem to stderr and exits 1.
It never prints file contents or secrets.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ROUTING_DIR = REPO_ROOT / "host_files/localhost/ai/routing"
MODELS_FILE = ROUTING_DIR / "models.yml"
WORKFLOW_FILE = ROUTING_DIR / "workflow.yml"
AGENTS_FILE = REPO_ROOT / "host_files/localhost/ai/AGENTS.md"
SKILL_FILE = REPO_ROOT / "host_files/localhost/ai/skills/execute-playbook/SKILL.md"
SKILL_NAME = "execute-playbook"
SKILL_MAX_LINES = 300

REQUIRED_TIERS = ("utility", "worker", "senior", "lead", "rescue")
REQUIRED_ROLES = ("orchestrator", "worker", "verifier", "rescue", "documentation")

REQUIRED_STATUSES = [
    "COMPLETE",
    "CORRECTION_REQUIRED",
    "HANDOFF_REQUIRED",
    "BLOCKED_AUTHORITY",
    "BLOCKED_TRANSIENT",
]

REQUIRED_EVIDENCE_FIELDS = [
    "status",
    "ticket",
    "branch",
    "commit",
    "files",
    "checks",
    "failure_fingerprint",
    "deviations",
    "last_safe_state",
    "recommended_next",
    "unresolved_risks",
]

REQUIRED_CLAUDE_IDS = (
    "claude-haiku-4-5-20251001",
    "claude-sonnet-5",
    "claude-opus-5",
)
REQUIRED_OPENAI_IDS = (
    "gpt-5.4-mini",
    "gpt-5.6-luna",
    "gpt-5.6-terra",
    "gpt-5.6-sol",
)
REQUIRED_PROVIDER_IDS = REQUIRED_CLAUDE_IDS + REQUIRED_OPENAI_IDS

# Provider IDs this machine has deliberately stopped using. Unlike
# REQUIRED_PROVIDER_IDS -- which must appear in models.yml and nowhere else --
# a retired ID must appear NOWHERE, models.yml included, so the check below
# scans models.yml too rather than exempting it the way the leak scan does.
#
# claude-fable-5-1 bills against a separate credit pool with a per-request
# spend cap that rejected live root-delegation calls, so the Anthropic lead and
# rescue tiers moved to claude-opus-5. Dropping it from REQUIRED_CLAUDE_IDS was
# necessary (check_provider_ids_present would otherwise demand it back in
# models.yml) but that alone left nothing stopping it being reintroduced.
RETIRED_PROVIDER_IDS = ("claude-fable-5-1",)

# Every one of REQUIRED_PROVIDER_IDS must appear only in models.yml, never in
# these paths. docs/ holds the playbook itself (which legitimately names
# provider IDs) and is untracked, so it is not scanned here.
#
# R3 (OpenCode lead-worker migration) removed opencode_agent_models from
# host_vars/localhost/opencode.yml and the model IDs from
# scripts/check-opencode-source.sh, so both now carry no provider ID of their
# own and are added below alongside group_vars/macbooks.yml and
# roles/ai_agents/templates/, as promised when this tuple was first scoped.
LEAKED_ID_SCAN_PATHS = (
    ROUTING_DIR / "prompts",
    REPO_ROOT / "host_files/localhost/ai/skills/execute-playbook",
    AGENTS_FILE,
    REPO_ROOT / "group_vars/macbooks.yml",
    REPO_ROOT / "host_vars/localhost/opencode.yml",
    REPO_ROOT / "roles/ai_agents/templates",
)

# Expected role topology. Anything not listed for a given mapping takes the
# default noted alongside it.
ROLE_MODE = {"orchestrator": "primary"}  # default: subagent
ROLE_READ_ONLY = {"verifier": True}  # default: False
ROLE_NORMAL_ASSIGNMENT = {"rescue": False, "orchestrator": False}  # default: True
ROLE_MAY_DISPATCH = {
    "orchestrator": {"worker", "verifier", "rescue", "documentation"}
}  # default: empty


def is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def load_yaml(path: Path) -> tuple[dict | None, str | None]:
    if not path.exists():
        return None, f"missing required file: {path.relative_to(REPO_ROOT)}"
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        return None, f"{path.relative_to(REPO_ROOT)} is not valid YAML: {exc}"
    if not isinstance(data, dict):
        return None, f"{path.relative_to(REPO_ROOT)} must decode to a YAML mapping"
    return data, None


def check_schema_versions(models: dict, workflow: dict) -> list[str]:
    errors = []
    if models.get("schema_version") != 1:
        errors.append(
            f"models.yml schema_version must equal 1, found {models.get('schema_version')!r}"
        )
    if workflow.get("schema_version") != 1:
        errors.append(
            f"workflow.yml schema_version must equal 1, found {workflow.get('schema_version')!r}"
        )
    return errors


def check_harnesses(models: dict) -> list[str]:
    errors = []
    harnesses = models.get("harnesses") or {}
    opencode = harnesses.get("opencode") or {}
    if opencode.get("provider") != "openai":
        errors.append("models.yml harnesses.opencode.provider must equal 'openai'")
    if opencode.get("model_prefix") != "openai/":
        errors.append("models.yml harnesses.opencode.model_prefix must equal 'openai/'")
    if (harnesses.get("codex") or {}).get("provider") != "openai":
        errors.append("models.yml harnesses.codex.provider must equal 'openai'")
    if (harnesses.get("claude") or {}).get("provider") != "anthropic":
        errors.append("models.yml harnesses.claude.provider must equal 'anthropic'")
    return errors


def check_tiers(models: dict) -> list[str]:
    errors = []
    tiers = models.get("tiers") or {}
    for tier in REQUIRED_TIERS:
        entry = tiers.get(tier)
        if not isinstance(entry, dict):
            errors.append(f"models.yml tiers.{tier} is missing")
            continue
        for provider in ("openai", "anthropic"):
            provider_entry = entry.get(provider)
            if not isinstance(provider_entry, dict):
                errors.append(f"models.yml tiers.{tier}.{provider} is missing")
                continue
            model = provider_entry.get("model")
            if not isinstance(model, str) or not model:
                errors.append(f"models.yml tiers.{tier}.{provider}.model must be a non-empty string")
            if "effort" not in provider_entry:
                errors.append(f"models.yml tiers.{tier}.{provider} is missing an effort key")
    utility_anthropic = ((tiers.get("utility") or {}).get("anthropic") or {})
    if "effort" in utility_anthropic and utility_anthropic["effort"] is not None:
        errors.append(
            "models.yml tiers.utility.anthropic.effort must be null, "
            f"found {utility_anthropic['effort']!r}"
        )
    return errors


def check_provider_ids_present(models_text: str) -> list[str]:
    return [
        f"models.yml is missing required provider ID: {provider_id}"
        for provider_id in REQUIRED_PROVIDER_IDS
        if provider_id not in models_text
    ]


def check_limits(workflow: dict) -> list[str]:
    errors = []
    expected = {
        "correction_limit": 1,
        "rescue_limit": 1,
        "identical_failure_limit": 2,
        "max_parallel_workers": 3,
    }
    for key, value in expected.items():
        if workflow.get(key) != value:
            errors.append(
                f"workflow.yml {key} must equal {value}, found {workflow.get(key)!r}"
            )
    return errors


def check_statuses_and_evidence_fields(workflow: dict) -> list[str]:
    errors = []
    if workflow.get("statuses") != REQUIRED_STATUSES:
        errors.append(
            f"workflow.yml statuses must equal {REQUIRED_STATUSES} in order, "
            f"found {workflow.get('statuses')!r}"
        )
    if workflow.get("evidence_fields") != REQUIRED_EVIDENCE_FIELDS:
        errors.append(
            f"workflow.yml evidence_fields must equal {REQUIRED_EVIDENCE_FIELDS} in order, "
            f"found {workflow.get('evidence_fields')!r}"
        )
    return errors


def check_roles(models: dict, workflow: dict) -> list[str]:
    errors = []
    roles = workflow.get("roles")
    if not isinstance(roles, dict):
        return ["workflow.yml roles is missing or not a mapping"]

    if set(roles.keys()) != set(REQUIRED_ROLES):
        errors.append(
            f"workflow.yml roles must be exactly {sorted(REQUIRED_ROLES)}, "
            f"found {sorted(roles.keys())}"
        )

    tiers = models.get("tiers") or {}
    all_role_names = set(REQUIRED_ROLES)

    for name in REQUIRED_ROLES:
        role = roles.get(name)
        if not isinstance(role, dict):
            errors.append(f"workflow.yml roles.{name} is missing")
            continue

        tier = role.get("tier")
        if tier not in tiers:
            errors.append(
                f"workflow.yml roles.{name}.tier '{tier}' does not exist in models.yml tiers"
            )

        prompt = role.get("prompt")
        if not prompt or not (ROUTING_DIR / str(prompt)).is_file():
            errors.append(
                f"workflow.yml roles.{name}.prompt '{prompt}' does not resolve to an "
                f"existing file under {ROUTING_DIR.relative_to(REPO_ROOT)}"
            )

        expected_mode = ROLE_MODE.get(name, "subagent")
        if role.get("mode") != expected_mode:
            errors.append(
                f"workflow.yml roles.{name}.mode must equal '{expected_mode}', "
                f"found {role.get('mode')!r}"
            )

        expected_read_only = ROLE_READ_ONLY.get(name, False)
        if role.get("read_only") is not expected_read_only:
            errors.append(
                f"workflow.yml roles.{name}.read_only must be {expected_read_only}, "
                f"found {role.get('read_only')!r}"
            )

        expected_normal_assignment = ROLE_NORMAL_ASSIGNMENT.get(name, True)
        if role.get("normal_assignment") is not expected_normal_assignment:
            errors.append(
                f"workflow.yml roles.{name}.normal_assignment must be "
                f"{expected_normal_assignment}, found {role.get('normal_assignment')!r}"
            )

        may_dispatch = role.get("may_dispatch")
        expected_may_dispatch = ROLE_MAY_DISPATCH.get(name, set())
        if not isinstance(may_dispatch, list) or set(may_dispatch) != expected_may_dispatch:
            errors.append(
                f"workflow.yml roles.{name}.may_dispatch must be exactly "
                f"{sorted(expected_may_dispatch)}, found {may_dispatch!r}"
            )
        elif name in may_dispatch:
            errors.append(f"workflow.yml roles.{name}.may_dispatch must not include itself")

        limits = role.get("limits")
        if not isinstance(limits, dict):
            errors.append(f"workflow.yml roles.{name}.limits is missing")
        else:
            if not is_positive_int(limits.get("opencode_steps")):
                errors.append(
                    f"workflow.yml roles.{name}.limits.opencode_steps must be a positive int, "
                    f"found {limits.get('opencode_steps')!r}"
                )
            if "claude_max_turns" not in limits:
                errors.append(f"workflow.yml roles.{name}.limits.claude_max_turns is missing")
            else:
                turns = limits["claude_max_turns"]
                if turns is None:
                    if name != "orchestrator":
                        errors.append(
                            f"workflow.yml roles.{name}.limits.claude_max_turns must not be "
                            "null (null is reserved for orchestrator)"
                        )
                elif not is_positive_int(turns):
                    errors.append(
                        f"workflow.yml roles.{name}.limits.claude_max_turns must be a positive "
                        f"int or null, found {turns!r}"
                    )

    # No cyclic escalation: nothing may dispatch the orchestrator, including itself.
    for name in REQUIRED_ROLES:
        role = roles.get(name)
        if not isinstance(role, dict):
            continue
        may_dispatch = role.get("may_dispatch")
        if isinstance(may_dispatch, list) and "orchestrator" in may_dispatch:
            errors.append(f"workflow.yml roles.{name}.may_dispatch must not dispatch orchestrator")
        if isinstance(may_dispatch, list) and not set(may_dispatch) <= all_role_names:
            errors.append(f"workflow.yml roles.{name}.may_dispatch references an unknown role")

    return errors


def check_prompt_contents(workflow: dict) -> list[str]:
    errors = []
    roles = workflow.get("roles")
    if not isinstance(roles, dict):
        return errors
    for name in REQUIRED_ROLES:
        role = roles.get(name)
        if not isinstance(role, dict):
            continue
        prompt = role.get("prompt")
        if not prompt:
            continue
        prompt_path = ROUTING_DIR / str(prompt)
        if not prompt_path.is_file():
            continue  # already reported by check_roles
        text = prompt_path.read_text()
        for status in REQUIRED_STATUSES:
            if status not in text:
                errors.append(f"{prompt_path.relative_to(REPO_ROOT)} is missing status marker: {status}")
        for field in REQUIRED_EVIDENCE_FIELDS:
            if field not in text:
                errors.append(
                    f"{prompt_path.relative_to(REPO_ROOT)} is missing evidence field marker: {field}"
                )
    return errors


def check_skill_file() -> list[str]:
    errors = []
    if not SKILL_FILE.is_file():
        return [f"missing required file: {SKILL_FILE.relative_to(REPO_ROOT)}"]

    lines = SKILL_FILE.read_text().splitlines()
    rel = SKILL_FILE.relative_to(REPO_ROOT)

    if len(lines) >= SKILL_MAX_LINES:
        errors.append(f"{rel} is {len(lines)} lines, must be under {SKILL_MAX_LINES}")

    if not lines or lines[0].strip() != "---":
        errors.append(f"{rel} has no opening frontmatter delimiter")
        return errors

    close_index = next((i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    if close_index is None:
        errors.append(f"{rel} has no closing frontmatter delimiter")
        return errors

    name_value = None
    for line in lines[1:close_index]:
        if line.startswith("name:"):
            name_value = line.split(":", 1)[1].strip().strip("'\"")
            break

    if name_value != SKILL_NAME:
        errors.append(f"{rel} frontmatter name must equal '{SKILL_NAME}', found {name_value!r}")

    return errors


def iter_scan_files(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(p for p in path.rglob("*") if p.is_file())
    if path.is_file():
        return [path]
    return []


def check_retired_provider_ids() -> list[str]:
    """Retired IDs must not reappear anywhere, models.yml included."""
    errors = []
    scan_paths = LEAKED_ID_SCAN_PATHS + (MODELS_FILE,)
    for scan_path in scan_paths:
        for file_path in iter_scan_files(scan_path):
            try:
                text = file_path.read_text()
            except (UnicodeDecodeError, OSError):
                continue
            for provider_id in RETIRED_PROVIDER_IDS:
                if provider_id in text:
                    errors.append(
                        f"{file_path.relative_to(REPO_ROOT)} uses retired provider ID "
                        f"'{provider_id}'; it was deliberately removed from this machine "
                        "and must not be reintroduced (see RETIRED_PROVIDER_IDS)"
                    )
    return errors


def check_leaked_provider_ids() -> list[str]:
    errors = []
    for scan_path in LEAKED_ID_SCAN_PATHS:
        for file_path in iter_scan_files(scan_path):
            try:
                text = file_path.read_text()
            except (UnicodeDecodeError, OSError):
                continue
            for provider_id in REQUIRED_PROVIDER_IDS:
                if provider_id in text:
                    errors.append(
                        f"{file_path.relative_to(REPO_ROOT)} leaks provider ID '{provider_id}'; "
                        "provider IDs belong only in models.yml"
                    )
    return errors


def main() -> int:
    errors: list[str] = []

    models, models_error = load_yaml(MODELS_FILE)
    workflow, workflow_error = load_yaml(WORKFLOW_FILE)

    if models_error:
        errors.append(models_error)
    if workflow_error:
        errors.append(workflow_error)

    if models is not None and workflow is not None:
        errors.extend(check_schema_versions(models, workflow))
        errors.extend(check_harnesses(models))
        errors.extend(check_tiers(models))
        errors.extend(check_provider_ids_present(MODELS_FILE.read_text()))
        errors.extend(check_limits(workflow))
        errors.extend(check_statuses_and_evidence_fields(workflow))
        errors.extend(check_roles(models, workflow))
        errors.extend(check_prompt_contents(workflow))

    errors.extend(check_skill_file())
    errors.extend(check_leaked_provider_ids())
    errors.extend(check_retired_provider_ids())

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("Agent routing source valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
