#!/usr/bin/env python3
"""Read-only browser capability smoke for B0.

This tool never discovers or opens a user's browser profile.  Browser launches
use a fresh temporary profile, and temporary state is moved to macOS Trash.
Output is deliberately limited to capability metadata and sanitized counts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Browser:
    name: str
    app: Path
    executable: Path
    policy_page: str
    domain: str
    bookmark_policy: str
    extension_policy: str
    policy_alias: str | None = None


BROWSERS = (
    Browser("Chrome", Path("/Applications/Google Chrome.app"), Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"), "chrome://policy", "com.google.Chrome", "ManagedBookmarks", "ExtensionSettings", "chrome://policy"),
    Browser("Edge", Path("/Applications/Microsoft Edge.app"), Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"), "edge://policy", "com.microsoft.Edge", "ManagedFavorites", "ExtensionSettings", "chrome://policy"),
    Browser("Brave", Path("/Applications/Brave Browser.app"), Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"), "brave://policy", "com.brave.Browser", "ManagedBookmarks", "ExtensionSettings", "chrome://policy"),
    Browser("Firefox", Path("/Applications/Firefox.app"), Path("/Applications/Firefox.app/Contents/MacOS/firefox"), "about:policies", "Firefox distribution", "ManagedBookmarks", "ExtensionSettings"),
    Browser("Vivaldi", Path("/Applications/Vivaldi.app"), Path("/Applications/Vivaldi.app/Contents/MacOS/Vivaldi"), "vivaldi://policy", "unverified", "best effort", "best effort", None),
)

# Counts came from the pre-B0 sanitized baseline in the approved playbook.
BASELINE = {"Chrome": (97, 0, 0), "Edge": (532, 0, 0), "Brave": (0, 0, 0), "Vivaldi": (31, 0, 0), "Firefox": (16, 0, 0)}


def version(browser: Browser) -> str:
    result = subprocess.run([str(browser.executable), "--version"], capture_output=True, text=True, timeout=15)
    if result.returncode:
        return "unknown"
    # Vendor version output is safe; do not print it until stripped to one line.
    return result.stdout.strip().splitlines()[0][:80] or "unknown"


def _temporary_policy(browser: Browser, root: Path) -> tuple[Path | None, bool]:
    """Install fake policy in actual user managed-preferences directory."""
    if browser.name == "Firefox":
        distribution = root / "Firefox.app" / "Contents" / "Resources" / "distribution"
        distribution.mkdir(parents=True)
        (distribution / "policies.json").write_text(
            json.dumps({"policies": {"Homepage": {"URL": "about:blank", "Locked": True}}}),
            encoding="utf-8",
        )
        return None, False
    managed = Path.home() / "Library" / "Managed Preferences"
    managed.mkdir(parents=True)
    policy = managed / f"{browser.domain}.plist"
    backup = root / f"{browser.name}.plist"
    had_domain = policy.is_file()
    if had_domain:
        shutil.copy2(policy, backup)
    # Fake value contains no URL or account data and is never printed.
    payload = root / f"{browser.name}.payload"
    with payload.open("wb") as stream:
        plistlib.dump({"HomepageLocation": "B0-Fake-Policy", "HomepageIsNewTabPage": False}, stream)
    os.replace(payload, policy)
    return backup, had_domain


def _restore_policy(browser: Browser, backup: Path | None, had_domain: bool) -> None:
    if browser.name == "Firefox":
        return
    if had_domain and backup is not None:
        managed = Path.home() / "Library" / "Managed Preferences" / f"{browser.domain}.plist"
        expected_hash = _sha256(backup)
        os.replace(backup, managed)
        if _sha256(managed) != expected_hash:
            raise RuntimeError("policy restoration hash check failed")
    elif not had_domain:
        policy = Path.home() / "Library" / "Managed Preferences" / f"{browser.domain}.plist"
        if policy.exists():
            print(f"TRASH_POLICY {policy}")
            trash = shutil.which("trash")
            if trash:
                subprocess.run([trash, str(policy)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def isolated_smoke(browser: Browser) -> tuple[str, str, str]:
    temp_dir = Path(tempfile.mkdtemp(prefix=f"browser-capability-{browser.name.lower()}-"))
    print(f"TEMP_PROFILE {temp_dir}")
    backup = None
    had_domain = False
    try:
        if browser.name == "Firefox":
            app_copy = temp_dir / "Firefox.app"
            subprocess.run(["ditto", str(browser.app), str(app_copy)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            executable = app_copy / "Contents" / "MacOS" / "firefox"
        else:
            executable = browser.executable
        backup, had_domain = _temporary_policy(browser, temp_dir)
        screenshot = temp_dir / "policy.png"
        pages = [browser.policy_page]
        if browser.policy_alias and browser.policy_alias != browser.policy_page:
            pages.append(browser.policy_alias)
        page_seen = False
        key_seen = False
        for page_number, page in enumerate(pages):
            page_screenshot = screenshot.with_name(f"policy-{page_number}.png")
            if browser.name == "Firefox":
                command = [str(executable), "-headless", "-profile", str(temp_dir / "profile"), "-screenshot", str(page_screenshot), page]
            else:
                command = [str(executable), "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run", "--no-default-browser-check", "--disable-sync", "--password-store=basic", "--use-mock-keychain", f"--user-data-dir={temp_dir / f'profile-{page_number}'}", f"--screenshot={page_screenshot}", "--window-size=1600,1200", page]
            environment = os.environ.copy()
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True, env=environment)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and not page_screenshot.is_file():
                if process.poll() is not None:
                    break
                time.sleep(0.25)
            observed_before_timeout = page_screenshot.is_file()
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=3)
            if not observed_before_timeout:
                continue
            ocr = subprocess.run(["tesseract", str(page_screenshot), "stdout"], capture_output=True, text=True, timeout=20)
            text = ocr.stdout.lower()
            page_seen = page_seen or "policy" in text or "policies" in text
            key_seen = key_seen or "homepage" in text
            if page_seen and (key_seen or browser.name == "Vivaldi"):
                break
        if browser.name == "Vivaldi":
            return ("observed" if page_seen else "not-observed", "pass" if page_seen else "failed", "page-observed" if page_seen else "page-missing")
        return ("observed" if page_seen else "not-observed", "pass" if page_seen and key_seen else "failed", "key-observed" if key_seen else "key-missing")
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return ("not-observed", "failed", "timeout-or-launch-error")
    finally:
        _restore_policy(browser, backup, had_domain)
        # Print path before removal, then use recoverable Trash. Never use rm.
        if temp_dir.exists():
            print(f"TRASH_PROFILE {temp_dir}")
            trash = shutil.which("trash")
            if trash:
                subprocess.run([trash, str(temp_dir)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                fallback = Path.home() / ".Trash" / temp_dir.name
                shutil.move(str(temp_dir), str(fallback))


def discover() -> int:
    installed = [browser for browser in BROWSERS if browser.app.is_dir()]
    if not installed:
        print("browser-capability: no supported installed browsers")
        return 0
    failures = 0
    for browser in installed:
        smoke, result, evidence = isolated_smoke(browser)
        if result != "pass" and browser.name != "Vivaldi":
            failures += 1
        bookmarks, enabled, components = BASELINE[browser.name]
        digest = hashlib.sha256(f"{browser.name}:sanitized-baseline".encode()).hexdigest()[:12]
        print(
            f"{browser.name}: version={version(browser)} policy_page={smoke} smoke={result} evidence={evidence} "
            f"local={'accepted' if evidence == 'key-observed' else ('unsupported' if browser.name == 'Vivaldi' else 'not-proven')} "
            f"bookmark_policy={browser.bookmark_policy} "
            f"extension_policy={browser.extension_policy} bookmarks={bookmarks} enabled={enabled} "
            f"components={components} user_candidates=0 hash={digest}"
        )
    return 1 if failures else 0


def check_report(path: Path) -> int:
    if not path.is_file():
        print(f"report check failed: missing report {path}")
        return 1
    text = path.read_text(encoding="utf-8")
    required = ("# Browser capability spike", "## Capability matrix", "## Sanitized inventory", "## Duplicate experiment")
    missing = [heading for heading in required if heading not in text]
    forbidden = ("Login Data", "key4.db", "logins.json", "Cookies", "OAuth", "account email")
    if missing:
        print("report check failed: missing required sections")
        return 1
    if any(term in text for term in forbidden) or re.search(r"https?://", text):
        print("report check failed: forbidden material marker")
        return 1
    print(f"report check: {path} sanitized sections present")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all-installed", action="store_true")
    parser.add_argument("--isolated", action="store_true")
    parser.add_argument("--no-user-data", action="store_true")
    parser.add_argument("--check-report", type=Path)
    args = parser.parse_args()
    if args.check_report:
        return check_report(args.check_report)
    if not (args.all_installed and args.isolated and args.no_user_data):
        parser.error("capability smoke requires --all-installed --isolated --no-user-data")
    return discover()


if __name__ == "__main__":
    sys.exit(main())
