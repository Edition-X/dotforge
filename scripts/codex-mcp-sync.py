#!/usr/bin/env python3
"""Surgically manage the ``[mcp_servers.*]`` sections of Codex's config.toml.

``~/.codex/config.toml`` is owned by the ChatGPT desktop app: it holds
hand-managed servers (figma, playwright, node_repl), ``[projects.*]`` trust
levels, plugins, marketplaces, and desktop settings that this script must
never touch. Only the ``mcp_servers`` entries this repo manages (``arcane``,
``mcp-sunrise``) and the ones it retires (``linear``, ``notion``, ``grafana``)
are within scope.

tomlkit is used instead of the stdlib ``tomllib``/``tomli-w`` pair because it
is format-preserving: comments, key order, and whitespace in every section
this script does not touch round-trip byte-for-byte.

The desired server definitions are read from stdin (or a file, for local
testing) rather than a CLI argument so that a bearer token never appears on
the command line or in ``ps``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import tomlkit
from tomlkit.items import Table


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
            "Path to a JSON file mapping server name -> table of key/values, "
            "or '-' to read that JSON from stdin."
        ),
    )
    parser.add_argument(
        "--remove",
        default="",
        help="Comma-separated list of server names to delete if present.",
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
    return data


def build_table(values: dict) -> Table:
    """Build a brand-new tomlkit table from plain values.

    A fresh table (rather than mutating an existing one) is what makes this
    a replace: stale keys left over from a previous shape of the same server
    are dropped instead of lingering alongside the new ones.
    """
    table = tomlkit.table()
    for key, value in values.items():
        table[key] = value
    return table


def sync(config_path: Path, desired: dict, remove: list[str]) -> tuple[str, str]:
    """Return (original_text, new_text) after applying desired/remove."""
    original_text = config_path.read_text()
    doc = tomlkit.parse(original_text)

    if "mcp_servers" not in doc or not isinstance(doc["mcp_servers"], Table):
        doc["mcp_servers"] = tomlkit.table()
    mcp_servers = doc["mcp_servers"]

    for name, values in desired.items():
        mcp_servers[name] = build_table(values)

    for name in remove:
        if name in mcp_servers:
            del mcp_servers[name]

    new_text = tomlkit.dumps(doc)
    return original_text, new_text


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    desired = load_desired(args.desired)
    remove = [name.strip() for name in args.remove.split(",") if name.strip()]

    original_text, new_text = sync(args.config, desired, remove)

    if new_text == original_text:
        print("unchanged")
        return 0

    if not args.check:
        args.config.write_text(new_text)

    print("changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
