#!/usr/bin/env python3
"""Run browser fixture checks and installed-browser isolated policy smoke."""

from __future__ import annotations

import argparse
import copy
import json
import os
import plistlib
import pwd
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import ModuleType

from browsers import REPO, managed
from browsers import capability as capability_module
from browsers import catalog as catalog_module
from browsers import snapshot as snapshot_module

# Catalog name -> (label, bookmark pages to accept), from the manifest.
CHROMIUM_BROWSERS = {
    str(entry["catalog"]): (str(entry["label"]), tuple(entry["policy"]["bookmarks_pages"]))
    for entry in managed("chromium")
}


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
    capability = capability_module
    browser_name, bookmarks_pages = CHROMIUM_BROWSERS[browser_catalog]
    bookmarks_page = bookmarks_pages[0]
    browser = next(browser for browser in capability.BROWSER_APPS if browser.name == browser_name)
    policy_page, result, evidence = capability.isolated_smoke(browser)
    if policy_page != "observed" or result != "pass" or not evidence.startswith("required-keys-status-ok-"):
        raise RuntimeError(f"{browser_name} policy page did not accept required policies")

    login = pwd.getpwuid(os.getuid()).pw_name
    policy_path = Path("/Library/Managed Preferences") / login / f"{browser.domain}.plist"
    production_policy_hash = capability._sha256(policy_path)
    with policy_path.open("rb") as stream:
        policy = plistlib.load(stream)
    # The catalog records bookmarks; it is never pushed back as policy. A
    # bookmark key here would put a read-only managed folder on the bar again.
    if browser.bookmark_policy in policy:
        raise RuntimeError(f"{browser_name} policy carries a managed bookmark folder")

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
    print(
        f"browser {browser_name} smoke: pass policy=mandatory bookmark-policy=absent "
        "fixture-channel=visible profile=isolated"
    )


class MarionetteSession:
    """Minimal Marionette client.

    Firefox refuses script evaluation on privileged pages, so policy evidence
    comes from the policy engine itself in chrome context rather than from a
    rendered page: no screenshots, no OCR, no theme sensitivity.
    """

    def __init__(self, port: int):
        self.port = port
        self.socket: socket.socket | None = None
        self.counter = 0

    def connect(self, deadline: float) -> None:
        while time.monotonic() < deadline and self.socket is None:
            try:
                self.socket = socket.create_connection(("127.0.0.1", self.port), timeout=5)
            except OSError:
                time.sleep(0.5)
        if self.socket is None:
            raise RuntimeError("Marionette did not accept a connection")
        self._read()

    def _read(self) -> object:
        assert self.socket is not None
        buffer = b""
        while b":" not in buffer:
            chunk = self.socket.recv(1)
            if not chunk:
                raise RuntimeError("Marionette closed the connection")
            buffer += chunk
        length, _, body = buffer.partition(b":")
        while len(body) < int(length):
            body += self.socket.recv(int(length) - len(body))
        return json.loads(body)

    def call(self, name: str, parameters: dict[str, object]) -> object:
        assert self.socket is not None
        self.counter += 1
        payload = json.dumps([0, self.counter, name, parameters])
        self.socket.sendall(f"{len(payload)}:{payload}".encode())
        message = self._read()
        if not isinstance(message, list) or len(message) < 4 or message[2] is not None:
            raise RuntimeError(f"Marionette rejected {name}")
        return message[3]

    def close(self) -> None:
        if self.socket is not None:
            self.socket.close()
            self.socket = None


def firefox_active_policies(app: Path, profile: Path, port: int = 2830) -> dict[str, object]:
    """Ask the running Firefox which policies its engine actually activated."""
    profile.mkdir(parents=True, exist_ok=True)
    (profile / "user.js").write_text(f'user_pref("marionette.port", {port});\n', encoding="utf-8")
    command = [
        str(app / "Contents" / "MacOS" / "firefox"),
        "-headless",
        "-no-remote",
        "-profile",
        str(profile),
        "-marionette",
        "-remote-allow-system-access",
        "about:blank",
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    session = MarionetteSession(port)
    try:
        session.connect(time.monotonic() + 90)
        session.call("WebDriver:NewSession", {})
        session.call("Marionette:SetContext", {"value": "chrome"})
        response = session.call(
            "WebDriver:ExecuteScript",
            {
                "script": (
                    "const policies = Services.policies;"
                    "const active = policies.getActivePolicies() || {};"
                    "const bookmarks = active.ManagedBookmarks || [];"
                    "const settings = active.ExtensionSettings || {};"
                    "return JSON.stringify({"
                    "  status: policies.status,"
                    "  names: Object.keys(active),"
                    "  toplevel: (bookmarks[0] || {}).toplevel_name || '',"
                    "  bookmarks: bookmarks.length,"
                    "  wildcard: (settings['*'] || {}).installation_mode || '',"
                    "  forced: Object.keys(settings).filter("
                    "    key => key !== '*' && settings[key].installation_mode === 'force_installed'"
                    "  ),"
                    "});"
                ),
                "args": [],
            },
        )
        value = response.get("value") if isinstance(response, dict) else None
        if not isinstance(value, str):
            raise RuntimeError("Firefox policy engine returned no state")
        return json.loads(value)
    finally:
        session.close()
        capability = capability_module
        capability._stop_launched_process(process)


def firefox_policy_smoke(validator: ModuleType, snapshot: ModuleType) -> None:
    capability = capability_module
    firefox = next(browser for browser in capability.BROWSER_APPS if browser.name == "Firefox")
    extensions_catalog = extension_catalog("firefox", validator)

    # Policy lives in a managed preference. A file inside Firefox.app would break
    # the bundle signature, which macOS enforces on a freshly installed bundle.
    bundle_policy = firefox.app / "Contents" / "Resources" / "distribution"
    if bundle_policy.exists():
        raise RuntimeError("Firefox.app carries a distribution directory")
    signature = subprocess.run(
        ["codesign", "--verify", "--strict", str(firefox.app)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if signature.returncode != 0:
        raise RuntimeError("Firefox application signature does not verify")

    login = pwd.getpwuid(os.getuid()).pw_name
    policy_path = Path("/Library/Managed Preferences") / login / "org.mozilla.firefox.plist"
    policy_hash = capability._sha256(policy_path)
    with policy_path.open("rb") as stream:
        policy = plistlib.load(stream)
    if policy.get("EnterprisePoliciesEnabled") is not True:
        raise RuntimeError("Firefox enterprise policies are not enabled")
    if "ManagedBookmarks" in policy:
        raise RuntimeError("Firefox policy carries a managed bookmark folder")
    settings = policy.get("ExtensionSettings", {})
    if settings.get("*", {}).get("installation_mode") != "allowed":
        raise RuntimeError("Firefox extension policy is missing")
    if extensions_catalog["enforcement"] != "report_only":
        raise RuntimeError("Firefox extension enforcement is not report-only")
    for record in extensions_catalog["required"]:
        entry = settings.get(record["id"], {})
        if entry.get("installation_mode") != "force_installed" or entry.get("install_url") != record["update_url"]:
            raise RuntimeError("Firefox required extension is not force-installed")

    root = Path(tempfile.mkdtemp(prefix="browser-firefox-policy-"))
    try:
        profile_root = Path.home() / "Library" / "Application Support" / "Firefox"
        profile_count, bookmark_count = snapshot.snapshot_firefox_profiles(profile_root, root / "snapshots")
        active = firefox_active_policies(firefox.app, root / "profile")
        if active.get("status") != 1:
            raise RuntimeError("Firefox policy engine is not active")
        names = set(active.get("names", []))
        if "ExtensionSettings" not in names:
            raise RuntimeError("Firefox did not activate the required policies")
        if "ManagedBookmarks" in names or active.get("bookmarks"):
            raise RuntimeError("Firefox activated a managed bookmark folder")
        if active.get("wildcard") != "allowed":
            raise RuntimeError("Firefox active policy values do not match the catalog")
        required_ids = {str(record["id"]) for record in extensions_catalog["required"]}
        if required_ids - set(active.get("forced", [])):
            raise RuntimeError("Firefox active policy is missing a required extension")
    finally:
        if root.exists():
            capability._trash(root, "TRASH_PROFILE")
    if capability._sha256(policy_path) != policy_hash:
        raise RuntimeError("Firefox managed policy changed during smoke")
    print(
        "browser Firefox smoke: pass policy=active source=managed-preference bundle=unmodified "
        f"signature=valid profile=isolated profiles={profile_count} bookmarks={bookmark_count} "
        f"managed-bookmarks={active.get('bookmarks')} forced-extensions={len(active.get('forced', []))} wal=verified"
    )


def vivaldi_policy_smoke() -> None:
    capability = capability_module
    vivaldi = next(browser for browser in capability.BROWSER_APPS if browser.name == "Vivaldi")
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


def extension_catalog(browser_catalog: str, validator: ModuleType) -> dict[str, object]:
    path = REPO / "host_files" / "localhost" / "browsers" / browser_catalog / "extensions.yml"
    return validator.yaml.safe_load(path.read_text(encoding="utf-8"))


def chromium_extension_smoke(validator: ModuleType, browser_catalog: str) -> None:
    """Prove managed presence entries reached the live policy, read-only."""
    capability = capability_module
    browser_name, _ = CHROMIUM_BROWSERS[browser_catalog]
    browser = next(browser for browser in capability.BROWSER_APPS if browser.name == browser_name)
    catalog = extension_catalog(browser_catalog, validator)
    if catalog["enforcement"] != "report_only":
        raise RuntimeError(f"{browser_name} extension enforcement is not report-only")

    policy_page, result, evidence = capability.isolated_smoke(browser)
    if policy_page != "observed" or result != "pass" or not evidence.startswith("required-keys-status-ok-"):
        raise RuntimeError(f"{browser_name} did not accept the extension policy live")

    login = pwd.getpwuid(os.getuid()).pw_name
    policy_path = Path("/Library/Managed Preferences") / login / f"{browser.domain}.plist"
    with policy_path.open("rb") as stream:
        policy = plistlib.load(stream)
    settings = policy.get("ExtensionSettings", {})
    forcelist = policy.get("ExtensionInstallForcelist", [])
    if settings.get("*", {}).get("installation_mode") != "allowed":
        raise RuntimeError(f"{browser_name} unlisted extensions are not still allowed")
    for record in catalog["required"]:
        entry = settings.get(record["id"], {})
        if entry.get("installation_mode") != "force_installed" or entry.get("update_url") != record["update_url"]:
            raise RuntimeError(f"{browser_name} required extension is not force-installed")
        if f"{record['id']};{record['update_url']}" not in forcelist:
            raise RuntimeError(f"{browser_name} required extension is missing from the forcelist")
    print(
        f"browser {browser_name} extensions: pass required={len(catalog['required'])} "
        "policy=force-installed unlisted=allowed enforcement=report-only profile=isolated"
    )


def extension_report_smoke() -> None:
    """Sanitized live presence evidence: counts only, no sign-in, no IDs printed."""
    report = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "browser-extension-report.py"),
            "--all",
            "--sanitized",
            "--isolated",
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if report.returncode != 0 or "://" in report.stdout:
        print(report.stdout, end="")
        raise RuntimeError("browser extension report failed or produced unsafe output")
    absent = [line for line in report.stdout.splitlines() if "lastpass=absent" in line]
    if absent:
        raise RuntimeError("a managed browser is missing its LastPass presence")
    print(report.stdout, end="")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", action="store_true")
    parser.add_argument("--all-installed", action="store_true")
    parser.add_argument("--isolated", action="store_true")
    parser.add_argument("--browser", choices=(*CHROMIUM_BROWSERS, "firefox", "vivaldi"))
    parser.add_argument("--policy", action="store_true")
    parser.add_argument("--capture-read-only", action="store_true")
    parser.add_argument("--automation", action="store_true")
    parser.add_argument("--extensions", action="store_true")
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
        and (args.policy or args.capture_read_only or args.extensions)
        and not args.fixtures
        and not args.browser
    )
    if not fixture_mode and not browser_mode and not all_mode and not automation_mode:
        parser.error(
            "use --fixtures --isolated, --all-installed --isolated --policy, "
            "--automation --isolated --fake-github, "
            "--all-installed --isolated --extensions --policy, "
            "or --browser <chrome|edge|brave|firefox|vivaldi> --isolated --policy"
        )
    if automation_mode:
        return automation_smoke()
    fixtures = REPO / "tests" / "fixtures" / "browsers"
    try:
        validator = catalog_module
        snapshot = snapshot_module
        if fixture_mode:
            validate_url_cases(validator, fixtures)
            validate_schema_contract(validator)
            validate_duplicate_contract(validator, fixtures)
            if snapshot.check_fixtures(fixtures) != 0:
                raise RuntimeError("fixture snapshot smoke failed")
            live_policy_smoke()
        elif all_mode:
            capability = capability_module
            installed = {browser.name for browser in capability.BROWSER_APPS if browser.app.is_dir()}
            if args.policy:
                for catalog, (name, _) in CHROMIUM_BROWSERS.items():
                    if name in installed:
                        chromium_policy_smoke(validator, catalog)
                if "Firefox" in installed:
                    firefox_policy_smoke(validator, snapshot)
                if "Vivaldi" in installed:
                    vivaldi_policy_smoke()
                print(f"browser policy matrix: pass installed={len(installed)} isolated=true")
            if args.extensions:
                for catalog, (name, _) in CHROMIUM_BROWSERS.items():
                    if name in installed:
                        chromium_extension_smoke(validator, catalog)
                if "Firefox" in installed and not args.policy:
                    firefox_policy_smoke(validator, snapshot)
                extension_report_smoke()
                print(f"browser extension matrix: pass installed={len(installed)} isolated=true sign-in=manual")
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
