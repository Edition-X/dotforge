#!/usr/bin/env python3
"""Run B1 fixture checks and installed-browser isolated policy smoke."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import plistlib
import pwd
import subprocess
import sys
import tempfile
import time
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


def chrome_policy_smoke(validator: ModuleType) -> None:
    capability = load_script("browser_capability", "browser-capability-spike.py")
    chrome = next(browser for browser in capability.BROWSERS if browser.name == "Chrome")
    policy_page, result, evidence = capability.isolated_smoke(chrome)
    if policy_page != "observed" or result != "pass" or not evidence.startswith("required-keys-status-ok-"):
        raise RuntimeError("Chrome policy page did not accept required policies")

    catalog_path = REPO / "host_files" / "localhost" / "browsers" / "chrome" / "bookmarks.yml"
    catalog = validator.yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    managed_folder = catalog["managed_folder"]
    login = pwd.getpwuid(os.getuid()).pw_name
    policy_path = Path("/Library/Managed Preferences") / login / "com.google.Chrome.plist"
    production_policy_hash = capability._sha256(policy_path)
    with policy_path.open("rb") as stream:
        policy = plistlib.load(stream)
    bookmarks = policy.get("ManagedBookmarks", [])
    if not bookmarks or bookmarks[0].get("toplevel_name") != managed_folder:
        raise RuntimeError("Chrome managed-folder policy is missing")

    root = Path(tempfile.mkdtemp(prefix="browser-chrome-managed-folder-"))
    profile = root / "profile"
    cfhome = root / "cfhome"
    cfhome.mkdir()
    command = [
        str(chrome.executable),
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
        "--password-store=basic",
        "--use-mock-keychain",
        "--remote-debugging-address=127.0.0.1",
        "--remote-debugging-port=0",
        "--remote-allow-origins=*",
        f"--user-data-dir={profile}",
        "chrome://bookmarks",
    ]
    environment = os.environ.copy()
    environment["HOME"] = str(cfhome)
    environment["CFFIXED_USER_HOME"] = str(cfhome)
    with capability.SystemPolicySession([chrome]):
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=environment,
        )
        try:
            client = capability.DevToolsSocket(capability._devtools_target(profile, process))
            try:
                client.call("Runtime.enable")
                client.call("Page.enable")
                client.call("Page.navigate", {"url": "chrome://bookmarks"})
                fixture_managed_folder = "B0"
                expression = f"""
                  (() => {{
                    const expected = {json.dumps(fixture_managed_folder)};
                    const collect = root => {{
                      let value = root.textContent || '';
                      for (const node of root.querySelectorAll('*')) {{
                        if (node.shadowRoot) value += ' ' + collect(node.shadowRoot);
                      }}
                      return value;
                    }};
                    return location.href.startsWith('chrome://bookmarks') && collect(document).includes(expected);
                  }})()
                """
                visible = False
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline and not visible:
                    response = client.call(
                        "Runtime.evaluate", {"expression": expression, "returnByValue": True}
                    )
                    visible = response.get("result", {}).get("value") is True
                    if not visible:
                        time.sleep(0.5)
            finally:
                client.close()
            if not visible:
                raise RuntimeError("Chrome managed folder was not visible")
        finally:
            capability._stop_launched_process(process)
            if root.exists():
                capability._trash(root, "TRASH_PROFILE")
    if capability._sha256(policy_path) != production_policy_hash:
        raise RuntimeError("Chrome production policy was not restored byte-for-byte")
    print("browser Chrome smoke: pass policy=mandatory managed-folder=visible profile=isolated")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", action="store_true")
    parser.add_argument("--isolated", action="store_true")
    parser.add_argument("--browser", choices=("chrome",))
    parser.add_argument("--policy", action="store_true")
    args = parser.parse_args()
    fixture_mode = args.fixtures and args.isolated and not args.browser and not args.policy
    chrome_mode = args.browser == "chrome" and args.isolated and args.policy and not args.fixtures
    if not fixture_mode and not chrome_mode:
        parser.error("use --fixtures --isolated or --browser chrome --isolated --policy")
    fixtures = REPO / "tests" / "fixtures" / "browsers"
    try:
        validator = load_script("browser_catalog_validator", "validate-browser-catalog.py")
        snapshot = load_script("browser_snapshot", "browser-snapshot.py")
        if fixture_mode:
            validate_url_cases(validator, fixtures)
            validate_schema_contract(validator)
            validate_duplicate_contract(validator, fixtures)
            if snapshot.check_fixtures(fixtures) != 0:
                raise RuntimeError("fixture snapshot smoke failed")
            live_policy_smoke()
        else:
            chrome_policy_smoke(validator)
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"browser smoke: failed ({type(error).__name__}: {error})")
        return 1
    if fixture_mode:
        print("browser smoke: pass fixtures=true duplicate=coexist additions-only=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
