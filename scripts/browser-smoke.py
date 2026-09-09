#!/usr/bin/env python3
"""Run browser fixture checks and installed-browser isolated policy smoke."""

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
CHROMIUM_BROWSERS = {
    "chrome": ("Chrome", ("chrome://bookmarks",)),
    "edge": ("Edge", ("edge://favorites",)),
    "brave": ("Brave", ("brave://bookmarks", "chrome://bookmarks")),
}


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


def chromium_policy_smoke(validator: ModuleType, browser_catalog: str) -> None:
    capability = load_script("browser_capability", "browser-capability-spike.py")
    browser_name, bookmarks_pages = CHROMIUM_BROWSERS[browser_catalog]
    bookmarks_page = bookmarks_pages[0]
    browser = next(browser for browser in capability.BROWSERS if browser.name == browser_name)
    policy_page, result, evidence = capability.isolated_smoke(browser)
    if policy_page != "observed" or result != "pass" or not evidence.startswith("required-keys-status-ok-"):
        raise RuntimeError(f"{browser_name} policy page did not accept required policies")

    catalog_path = REPO / "host_files" / "localhost" / "browsers" / browser_catalog / "bookmarks.yml"
    catalog = validator.yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    managed_folder = catalog["managed_folder"]
    login = pwd.getpwuid(os.getuid()).pw_name
    policy_path = Path("/Library/Managed Preferences") / login / f"{browser.domain}.plist"
    production_policy_hash = capability._sha256(policy_path)
    with policy_path.open("rb") as stream:
        policy = plistlib.load(stream)
    bookmarks = policy.get(browser.bookmark_policy, [])
    if not bookmarks or bookmarks[0].get("toplevel_name") != managed_folder:
        raise RuntimeError(f"{browser_name} managed-folder policy is missing")

    root = Path(tempfile.mkdtemp(prefix=f"browser-{browser_catalog}-managed-folder-"))
    profile = root / "profile"
    cfhome = root / "cfhome"
    cfhome.mkdir()
    command = [
        str(browser.executable),
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
        bookmarks_page,
    ]
    environment = os.environ.copy()
    environment["HOME"] = str(cfhome)
    environment["CFFIXED_USER_HOME"] = str(cfhome)
    with capability.SystemPolicySession([browser]):
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
                client.call("Page.navigate", {"url": bookmarks_page})
                fixture_managed_folder = "B0"
                expression = f"""
                  (() => {{
                    const expected = {json.dumps(fixture_managed_folder)};
                    const expectedPages = {json.dumps(bookmarks_pages)};
                    const collect = root => {{
                      let value = root.textContent || '';
                      for (const node of root.querySelectorAll('*')) {{
                        if (node.shadowRoot) value += ' ' + collect(node.shadowRoot);
                      }}
                      return value;
                    }};
                    return expectedPages.some(page => location.href.startsWith(page))
                      && collect(document).includes(expected);
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
                raise RuntimeError(f"{browser_name} managed folder was not visible")
        finally:
            capability._stop_launched_process(process)
            if root.exists():
                capability._trash(root, "TRASH_PROFILE")
    if capability._sha256(policy_path) != production_policy_hash:
        raise RuntimeError(f"{browser_name} production policy was not restored byte-for-byte")
    print(f"browser {browser_name} smoke: pass policy=mandatory managed-folder=visible profile=isolated")


def firefox_policy_smoke(validator: ModuleType, snapshot: ModuleType) -> None:
    capability = load_script("browser_capability", "browser-capability-spike.py")
    firefox = next(browser for browser in capability.BROWSERS if browser.name == "Firefox")
    catalog_path = REPO / "host_files" / "localhost" / "browsers" / "firefox" / "bookmarks.yml"
    catalog = validator.yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    policy_path = firefox.app / "Contents" / "Resources" / "distribution" / "policies.json"
    policy_hash = capability._sha256(policy_path)
    policy = json.loads(policy_path.read_text(encoding="utf-8"))["policies"]
    bookmarks = policy.get("ManagedBookmarks", [])
    if not bookmarks or bookmarks[0].get("toplevel_name") != catalog["managed_folder"]:
        raise RuntimeError("Firefox managed bookmark policy is missing")
    if policy.get("ExtensionSettings", {}).get("*", {}).get("installation_mode") != "allowed":
        raise RuntimeError("Firefox extension policy is missing")

    root = Path(tempfile.mkdtemp(prefix="browser-firefox-policy-"))
    process: subprocess.Popen[bytes] | None = None
    try:
        profile_root = Path.home() / "Library" / "Application Support" / "Firefox"
        profile_count, bookmark_count = snapshot.snapshot_firefox_profiles(profile_root, root / "snapshots")
        app_copy = root / "Firefox.app"
        subprocess.run(["ditto", str(firefox.app), str(app_copy)], check=True, timeout=180)
        copied_policy = app_copy / "Contents" / "Resources" / "distribution" / "policies.json"
        if capability._sha256(copied_policy) != policy_hash:
            raise RuntimeError("Firefox isolated app policy differs from production")
        screenshot = root / "policy.png"
        # The managed-bookmark policy value is long enough to push later
        # policies past a default viewport, so capture a tall window and read
        # the whole active table rather than only its first screen.
        command = [
            str(app_copy / "Contents" / "MacOS" / "firefox"),
            "-headless",
            "-no-remote",
            "-profile",
            str(root / "profile"),
            "--window-size=1400,20000",
            "-screenshot",
            str(screenshot),
            "about:policies#active",
        ]
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not screenshot.is_file():
            if process.poll() is not None:
                break
            time.sleep(0.25)
        if not screenshot.is_file():
            raise RuntimeError("Firefox policy page was not observed")
        ocr = subprocess.run(
            ["tesseract", str(screenshot), "stdout"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        observed = "managedbookmarks" in ocr.stdout.lower() and "extensionsettings" in ocr.stdout.lower()
        if not observed:
            raise RuntimeError("Firefox policy page did not show required policy names")
    finally:
        if process is not None:
            capability._stop_launched_process(process)
        if root.exists():
            capability._trash(root, "TRASH_PROFILE")
    if capability._sha256(policy_path) != policy_hash:
        raise RuntimeError("Firefox production policy changed during smoke")
    print(
        "browser Firefox smoke: pass policy=active profile=isolated "
        f"profiles={profile_count} bookmarks={bookmark_count} wal=verified"
    )


def vivaldi_policy_smoke() -> None:
    capability = load_script("browser_capability", "browser-capability-spike.py")
    vivaldi = next(browser for browser in capability.BROWSERS if browser.name == "Vivaldi")
    policy_page, result, evidence = capability.isolated_smoke(vivaldi)
    if result != "pass" or not evidence.startswith("unsupported-audit-launch-"):
        raise RuntimeError("Vivaldi best-effort policy probe failed")
    audit = Path.home() / ".local" / "state" / "macbook-pro" / "browser-policy" / "vivaldi-audit.sh"
    report = subprocess.run([str(audit), "--check"], capture_output=True, text=True, timeout=20)
    if report.returncode != 0 or "best-effort audit/export" not in report.stdout or "://" in report.stdout:
        raise RuntimeError("Vivaldi audit/export smoke failed")
    print(
        "browser Vivaldi smoke: pass support=best-effort audit/export=pass "
        f"policy-page={policy_page} profile=read-only"
    )


def automation_smoke() -> int:
    """Fake-GitHub automation smoke: stop conditions only, no network and no push."""
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "browser-automation-smoke.py"), "--fake", "--no-network"],
        capture_output=True,
        text=True,
        timeout=600,
    )
    print(result.stdout, end="")
    if result.returncode != 0 or "://" in result.stdout:
        print(result.stderr, end="")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", action="store_true")
    parser.add_argument("--all-installed", action="store_true")
    parser.add_argument("--isolated", action="store_true")
    parser.add_argument("--browser", choices=(*CHROMIUM_BROWSERS, "firefox", "vivaldi"))
    parser.add_argument("--policy", action="store_true")
    parser.add_argument("--capture-read-only", action="store_true")
    parser.add_argument("--automation", action="store_true")
    parser.add_argument("--fake-github", action="store_true")
    args = parser.parse_args()
    automation_mode = (
        args.automation
        and args.isolated
        and args.fake_github
        and not args.fixtures
        and not args.browser
        and not args.policy
        and not args.all_installed
        and not args.capture_read_only
    )
    fixture_mode = args.fixtures and args.isolated and not args.browser and not args.policy and not args.all_installed
    browser_mode = (
        args.browser is not None
        and args.isolated
        and args.policy
        and not args.fixtures
        and not args.all_installed
        and not args.capture_read_only
    )
    all_mode = (
        args.all_installed
        and args.isolated
        and (args.policy or args.capture_read_only)
        and not args.fixtures
        and not args.browser
    )
    if not fixture_mode and not browser_mode and not all_mode and not automation_mode:
        parser.error(
            "use --fixtures --isolated, --all-installed --isolated --policy, "
            "--automation --isolated --fake-github, "
            "or --browser <chrome|edge|brave|firefox|vivaldi> --isolated --policy"
        )
    if automation_mode:
        return automation_smoke()
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
        elif all_mode:
            capability = load_script("browser_capability_inventory", "browser-capability-spike.py")
            installed = {browser.name for browser in capability.BROWSERS if browser.app.is_dir()}
            if args.policy:
                for catalog, (name, _) in CHROMIUM_BROWSERS.items():
                    if name in installed:
                        chromium_policy_smoke(validator, catalog)
                if "Firefox" in installed:
                    firefox_policy_smoke(validator, snapshot)
                if "Vivaldi" in installed:
                    vivaldi_policy_smoke()
                print(f"browser policy matrix: pass installed={len(installed)} isolated=true")
            if args.capture_read_only:
                capture = subprocess.run(
                    [sys.executable, str(REPO / "scripts" / "browser-capture.py"), "--dry-run", "--isolated"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if capture.returncode != 0 or "://" in capture.stdout:
                    raise RuntimeError("browser read-only capture smoke failed")
                print(capture.stdout, end="")
                print(f"browser capture matrix: pass installed={len(installed)} isolated=true")
        elif args.browser == "firefox":
            firefox_policy_smoke(validator, snapshot)
        elif args.browser == "vivaldi":
            vivaldi_policy_smoke()
        else:
            chromium_policy_smoke(validator, args.browser)
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"browser smoke: failed ({type(error).__name__}: {error})")
        return 1
    if fixture_mode:
        print("browser smoke: pass fixtures=true duplicate=coexist additions-only=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
