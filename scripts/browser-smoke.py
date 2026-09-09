#!/usr/bin/env python3
"""Run B1 fixture checks and installed-browser isolated policy smoke."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parent.parent


def load_script(name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError("browser test module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def validate_url_cases(validator: ModuleType, fixtures: Path) -> None:
    cases = json.loads((fixtures / "capability" / "catalog-cases.json").read_text(encoding="utf-8"))
    for value in cases["accepted"]:
        validator.normalized_url(value)
    rejected = 0
    for value in cases["rejected"]:
        try:
            validator.normalized_url(value)
        except validator.CatalogError:
            rejected += 1
    if rejected != len(cases["rejected"]):
        raise RuntimeError("unsafe URL fixture was accepted")


def validate_duplicate_contract(validator: ModuleType, fixtures: Path) -> None:
    data = json.loads((fixtures / "capability" / "duplicate-records.json").read_text(encoding="utf-8"))
    records = data["records"]
    urls = {validator.normalized_url(record["url"]) for record in records}
    fingerprints = {
        validator.fingerprint(record["browser"], record["title"], record["url"], record["folder"])
        for record in records
    }
    if len(urls) != 1 or len(fingerprints) != 2:
        raise RuntimeError("managed-folder duplicate contract failed")
    if data["expected"]["mode"] != "additions_only":
        raise RuntimeError("duplicate experiment is not additions-only")
    if data["expected"]["duplicate_decision"] != "keep-managed-and-ordinary-copies":
        raise RuntimeError("managed-folder duplicate decision is missing")


def validate_schema_contract(validator: ModuleType) -> None:
    url = "https://fixture.example.invalid/path"
    record = {
        "browser": "chrome",
        "title": "Fixture",
        "url": url,
        "folder": ["Managed"],
        "fingerprint": validator.fingerprint("chrome", "Fixture", url, ["Managed"]),
    }
    catalog = {
        "version": 1,
        "browser": "chrome",
        "mode": "additions_only",
        "managed_folder": "Managed",
        "bookmarks": [record],
    }
    if validator.validate_bookmarks(catalog, "chrome") != 1:
        raise RuntimeError("valid bookmark schema failed")
    invalid = copy.deepcopy(catalog)
    invalid["bookmarks"][0]["browser"] = "edge"
    try:
        validator.validate_bookmarks(invalid, "chrome")
    except validator.CatalogError:
        pass
    else:
        raise RuntimeError("cross-browser bookmark ownership was accepted")


def live_policy_smoke() -> None:
    command = [
        sys.executable,
        str(REPO / "scripts" / "browser-capability-spike.py"),
        "--all-installed",
        "--isolated",
        "--no-user-data",
    ]
    result = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=420)
    lines = result.stdout.splitlines()
    expected = {"Chrome", "Edge", "Brave", "Firefox", "Vivaldi"}
    passed = {
        line.split(":", 1)[0]
        for line in lines
        if ": version=" in line and " smoke=pass " in line
    }
    if result.returncode != 0 or not expected.issubset(passed):
        safe_lines = [line for line in lines if " version=" in line or line.startswith("system-policy:")]
        print("\n".join(safe_lines))
        raise RuntimeError("installed-browser isolated policy smoke failed")
    print("browser live smoke: pass installed=5 isolated=true user-data=unopened")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", action="store_true")
    parser.add_argument("--isolated", action="store_true")
    args = parser.parse_args()
    if not args.fixtures or not args.isolated:
        parser.error("browser smoke requires --fixtures --isolated")
    fixtures = REPO / "tests" / "fixtures" / "browsers"
    try:
        validator = load_script("browser_catalog_validator", "validate-browser-catalog.py")
        snapshot = load_script("browser_snapshot", "browser-snapshot.py")
        validate_url_cases(validator, fixtures)
        validate_schema_contract(validator)
        validate_duplicate_contract(validator, fixtures)
        if snapshot.check_fixtures(fixtures) != 0:
            raise RuntimeError("fixture snapshot smoke failed")
        live_policy_smoke()
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"browser smoke: failed ({type(error).__name__}: {error})")
        return 1
    print("browser smoke: pass fixtures=true duplicate=coexist additions-only=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
