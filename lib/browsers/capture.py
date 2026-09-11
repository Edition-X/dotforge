#!/usr/bin/env python3
"""Capture browser bookmark additions through bounded read-only snapshots."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import ModuleType

import yaml

from browsers import BROWSERS, CHROMIUM_PROFILES, REPO
from browsers import catalog as catalog_module
from browsers import quarantine as quarantine_module
from browsers import reconcile as reconcile_module
from browsers import snapshot as snapshot_module


def chromium_records(data: dict[str, object]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []

    def walk(node: object, folder: list[str]) -> None:
        if not isinstance(node, dict):
            return
        if node.get("type") == "url":
            records.append({"title": node.get("name", ""), "url": node.get("url", ""), "folder": folder})
            return
        children = node.get("children", [])
        if not isinstance(children, list):
            return
        name = node.get("name")
        child_folder = [*folder, str(name).strip()] if isinstance(name, str) and name.strip() else folder
        for child in children:
            walk(child, child_folder)

    roots = data.get("roots", {})
    if not isinstance(roots, dict):
        raise RuntimeError("Chromium bookmark roots are invalid")
    for root in roots.values():
        walk(root, [])
    return records


def firefox_records(database: Path) -> list[dict[str, object]]:
    uri = database.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(moz_bookmarks)")}
        if not {"parent", "type", "guid"}.issubset(columns):
            rows = connection.execute(
                "SELECT COALESCE(b.title, ''), p.url FROM moz_bookmarks b "
                "JOIN moz_places p ON p.id = b.fk WHERE p.url IS NOT NULL"
            )
            return [{"title": title, "url": url, "folder": []} for title, url in rows]
        rows = list(
            connection.execute(
                "SELECT b.id, b.parent, COALESCE(b.title, ''), b.type, b.guid, p.url "
                "FROM moz_bookmarks b LEFT JOIN moz_places p ON p.id = b.fk"
            )
        )
    nodes = {row[0]: row for row in rows}
    root_names = {
        "menu________": "Bookmarks Menu",
        "toolbar_____": "Bookmarks Toolbar",
        "unfiled_____": "Other Bookmarks",
        "mobile______": "Mobile Bookmarks",
    }

    def folder_path(parent: int) -> list[str]:
        parts: list[str] = []
        visited: set[int] = set()
        while parent in nodes and parent not in visited:
            visited.add(parent)
            _, next_parent, title, node_type, guid, _ = nodes[parent]
            if guid == "root________":
                break
            label = root_names.get(guid, title)
            if node_type == 2 and label:
                parts.append(label)
            parent = next_parent
        return list(reversed(parts))

    return [
        {"title": title, "url": url, "folder": folder_path(parent)}
        for _, parent, title, _, _, url in rows
        if url is not None
    ]


def capture_live(snapshot: ModuleType, work: Path) -> dict[str, list[dict[str, object]]]:
    support = Path.home() / "Library" / "Application Support"
    captured: dict[str, list[dict[str, object]]] = {}
    for browser, relative in CHROMIUM_PROFILES.items():
        source = support / relative / "Bookmarks"
        if not source.exists():
            captured[browser] = []
            continue
        data = snapshot.stable_json_snapshot(source, work / f"{browser}-Bookmarks")
        captured[browser] = chromium_records(data)
    profile_root = support / "Firefox"
    profiles = snapshot.firefox_profiles(profile_root)
    source = profiles["default-release"] / "places.sqlite"
    firefox_copy = work / "firefox.sqlite"
    snapshot.firefox_snapshot(source, firefox_copy)
    captured["firefox"] = firefox_records(firefox_copy)
    return captured


def write_catalog(path: Path, catalog: dict[str, object]) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".bookmarks-", dir=path.parent)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        rendered = yaml.safe_dump(catalog, sort_keys=False, allow_unicode=True, explicit_start=True)
        for line in rendered.splitlines():
            annotation = "  # noqa yaml[line-length]" if len(line) > 120 else ""
            stream.write(f"{line}{annotation}\n")
    os.chmod(temporary, 0o644)
    os.replace(temporary, path)


def fixture_check(snapshot: ModuleType, fixtures: Path) -> int:
    if snapshot.check_fixtures(fixtures) != 0:
        raise RuntimeError("snapshot fixture failed")
    counts = {}
    for browser in CHROMIUM_PROFILES:
        data = json.loads((fixtures / browser / "Default" / "Bookmarks").read_text(encoding="utf-8"))
        counts[browser] = len(chromium_records(data))
    try:
        snapshot.stable_json_snapshot(
            fixtures / "chrome" / "Default" / "Bookmarks",
            Path(tempfile.gettempdir()) / "browser-capture-unreachable",
            attempts=0,
        )
    except RuntimeError:
        pass
    else:
        raise RuntimeError("bounded snapshot failure did not fail closed")
    work = Path(tempfile.mkdtemp(prefix="browser-capture-firefox-fixture-"))
    connection = None
    try:
        database, connection = snapshot.materialize_firefox_fixture(fixtures, work)
        copied = work / "snapshot.sqlite"
        snapshot.firefox_snapshot(database, copied)
        counts["firefox"] = len(firefox_records(copied))
    finally:
        if connection is not None:
            connection.close()
        if work.exists():
            snapshot.trash(work)
    if set(counts) != set(BROWSERS) or any(count != 2 for count in counts.values()):
        raise RuntimeError("capture fixture count mismatch")
    print("browser capture: pass fixtures=5 records=10 bounded=true read-only=true")
    return 0


def live_capture(enable: bool) -> int:
    snapshot = snapshot_module
    validator = catalog_module
    work = Path(tempfile.mkdtemp(prefix="browser-capture-live-"))
    quarantine = quarantine_module.Quarantine(
        Path.home() / ".local" / "state" / "macbook-pro" / "browser-policy" / "quarantine.json"
    )
    try:
        captured = capture_live(snapshot, work)
        for browser in BROWSERS:
            path = REPO / "host_files" / "localhost" / "browsers" / browser / "bookmarks.yml"
            catalog = yaml.safe_load(path.read_text(encoding="utf-8"))
            additions, rejected = reconcile_module.reconcile(catalog, captured[browser], validator, quarantine)
            validator.validate_bookmarks(catalog, browser)
            if enable:
                write_catalog(path, catalog)
            print(
                f"browser capture: browser={browser} records={len(captured[browser])} "
                f"additions={additions} rejected={rejected} mode={'write' if enable else 'dry-run'}"
            )
        quarantined = quarantine.commit() if enable else len(quarantine.records)
        print(f"browser capture: pass browsers=5 quarantined={quarantined} output=counts-only")
        return 0
    finally:
        if work.exists():
            snapshot.trash(work)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--enable-capture", action="store_true")
    parser.add_argument("--isolated", action="store_true")
    args = parser.parse_args()
    fixture_mode = args.fixtures and args.check_only and not args.dry_run and not args.enable_capture
    live_mode = args.isolated and (args.dry_run != args.enable_capture) and not args.fixtures and not args.check_only
    if not fixture_mode and not live_mode:
        parser.error("use --fixtures PATH --check-only or one of --dry-run/--enable-capture with --isolated")
    try:
        snapshot = snapshot_module
        return fixture_check(snapshot, args.fixtures) if fixture_mode else live_capture(args.enable_capture)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, sqlite3.Error, yaml.YAMLError) as error:
        print(f"browser capture: failed ({type(error).__name__}: {error})")
        return 1


if __name__ == "__main__":
    sys.exit(main())
