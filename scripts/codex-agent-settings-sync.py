#!/usr/bin/env python3
"""Surgically manage Codex's root model default and native-agent defaults.

``~/.codex/config.toml`` is owned by the ChatGPT desktop app: it holds
hand-managed MCP servers, ``[projects.*]`` trust levels, plugins,
marketplaces, and desktop settings that this script must never touch. Only
six keys are within scope:

- top-level ``model``
- top-level ``model_reasoning_effort``
- ``agents.enabled``
- ``agents.max_concurrent_threads_per_session``
- ``agents.default_subagent_model``
- ``agents.default_subagent_reasoning_effort``

tomlkit is used instead of the stdlib ``tomllib``/``tomli-w`` pair because it
is format-preserving: comments, key order, and whitespace in every section
this script does not touch round-trip byte-for-byte. Unlike
``codex-mcp-sync.py`` (which replaces whole named sub-tables), this script
edits individual scalar keys in place so any *other* key already present
under ``[agents]`` — including one this repo does not know about yet —
survives untouched.

The desired settings are read from stdin (or a file, for local testing)
rather than a CLI argument, matching codex-mcp-sync.py's convention even
though these particular values carry no secret.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import tomlkit
from tomlkit.items import Table

MANAGED_TOP_LEVEL_KEYS = ("model", "model_reasoning_effort")
MANAGED_AGENTS_KEYS = (
    "enabled",
    "max_concurrent_threads_per_session",
    "default_subagent_model",
    "default_subagent_reasoning_effort",
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to config.toml to update.",
    )
    parser.add_argument(
        "--desired",
        required=True,
        help=(
            "Path to a JSON file with top-level 'model'/'model_reasoning_effort' "
            "and an 'agents' object carrying the four managed agents.* keys, or "
            "'-' to read that JSON from stdin."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report what would change without writing the file.",
    )
    return parser.parse_args(argv)


def load_desired(desired_arg: str) -> dict:
    if desired_arg == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(desired_arg).read_text()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("--desired must decode to a JSON object")
    unknown_top = set(data) - {"model", "model_reasoning_effort", "agents"}
    if unknown_top:
        raise ValueError(f"--desired carries unmanaged top-level keys: {sorted(unknown_top)}")
    unknown_agents = set(data.get("agents", {})) - set(MANAGED_AGENTS_KEYS)
    if unknown_agents:
        raise ValueError(f"--desired carries unmanaged agents.* keys: {sorted(unknown_agents)}")
    return data


def sync(config_path: Path, desired: dict) -> tuple[str, str]:
    """Return (original_text, new_text) after applying desired settings."""
    original_text = config_path.read_text()
    doc = tomlkit.parse(original_text)

    for key in MANAGED_TOP_LEVEL_KEYS:
        if key in desired:
            doc[key] = desired[key]

    desired_agents = desired.get("agents", {})
    if desired_agents:
        if "agents" not in doc or not isinstance(doc["agents"], Table):
            doc["agents"] = tomlkit.table()
        agents_table = doc["agents"]
        for key in MANAGED_AGENTS_KEYS:
            if key in desired_agents:
                agents_table[key] = desired_agents[key]

    new_text = tomlkit.dumps(doc)
    return original_text, new_text


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    desired = load_desired(args.desired)

    original_text, new_text = sync(args.config, desired)

    if new_text == original_text:
        print("unchanged")
        return 0

    if not args.check:
        args.config.write_text(new_text)

    print("changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
