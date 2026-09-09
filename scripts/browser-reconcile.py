#!/usr/bin/env python3
"""Append browser-owned bookmark additions without inferring deletions."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType

import yaml

REPO = Path(__file__).resolve().parent.parent


def load_script(name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError("browser reconcile module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def clean_text(value: object) -> str:
    return str(value).strip().encode("utf-8", errors="replace").decode("utf-8")


def reconcile(catalog: dict[str, object], records: list[dict[str, object]], validator: ModuleType, quarantine: object) -> tuple[int, int]:
    browser = str(catalog["browser"])
    existing = {str(record["fingerprint"]) for record in catalog["bookmarks"]}
    additions: list[dict[str, object]] = []
    rejected = 0
    for raw in records:
        try:
            title = clean_text(raw["title"])
            folder = [clean_text(part) for part in raw["folder"]]
            if not title or any(not part for part in folder):
                raise validator.CatalogError("bookmark text is empty")
            url = validator.normalized_url(raw["url"])
            fingerprint = validator.fingerprint(browser, title, url, folder)
            record = {"browser": browser, "title": title, "url": url, "folder": folder, "fingerprint": fingerprint}
            if fingerprint not in existing:
                existing.add(fingerprint)
                additions.append(record)
        except (KeyError, TypeError, ValueError, validator.CatalogError):
            quarantine.add(browser, "invalid-or-suspicious-record", raw)
            rejected += 1
    additions.sort(key=lambda record: (record["folder"], record["title"], record["url"]))
    catalog["bookmarks"].extend(additions)
    return len(additions), rejected


def check_fixtures(fixtures: Path) -> int:
    validator = load_script("browser_catalog_validator", "validate-browser-catalog.py")
    quarantine_module = load_script("browser_quarantine", "browser-quarantine.py")
    source = {
        "version": 1,
        "browser": "chrome",
        "mode": "additions_only",
        "managed_folder": "Managed",
        "bookmarks": [],
    }
    cases = json.loads((fixtures / "capability" / "catalog-cases.json").read_text(encoding="utf-8"))
    valid = {"title": "Fixture", "url": cases["accepted"][0], "folder": ["Folder"]}
    moved = {"title": "Fixture", "url": cases["accepted"][0], "folder": ["Moved"]}
    suspicious = {"title": "Rejected", "url": cases["rejected"][0], "folder": []}
    root = Path(tempfile.mkdtemp(prefix="browser-reconcile-fixtures-"))
    try:
        quarantine = quarantine_module.Quarantine(root / "quarantine.json")
        added, rejected = reconcile(source, [valid, valid, suspicious], validator, quarantine)
        if (added, rejected, len(source["bookmarks"])) != (1, 1, 1):
            raise RuntimeError("addition, duplicate or suspicious fixture failed")
        added, rejected = reconcile(source, [], validator, quarantine)
        if (added, rejected, len(source["bookmarks"])) != (0, 0, 1):
            raise RuntimeError("absence inferred deletion")
        added, rejected = reconcile(source, [moved], validator, quarantine)
        if (added, rejected, len(source["bookmarks"])) != (1, 0, 2):
            raise RuntimeError("move absence removed prior record")
        if quarantine.commit() != 1 or root.joinpath("quarantine.json").stat().st_mode & 0o777 != 0o600:
            raise RuntimeError("quarantine fixture failed")
        validator.validate_bookmarks(source, "chrome")
        print("browser reconcile: pass additions=2 duplicates=1 absences=preserved moves=preserved rejected=1")
        return 0
    finally:
        snapshot = load_script("browser_snapshot_cleanup", "browser-snapshot.py")
        if root.exists():
            snapshot.trash(root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path)
    parser.add_argument("--additions-only", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if not args.fixtures or not args.additions_only or not args.check_only:
        parser.error("reconcile check requires --fixtures PATH --additions-only --check-only")
    try:
        return check_fixtures(args.fixtures)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, yaml.YAMLError) as error:
        print(f"browser reconcile: failed ({type(error).__name__}: {error})")
        return 1


if __name__ == "__main__":
    sys.exit(main())
