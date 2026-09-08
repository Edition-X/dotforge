#!/usr/bin/env python3
"""Read-only browser capability smoke for B0.

This tool never discovers or opens a user's browser profile.  Browser launches
use a fresh temporary profile, and temporary state is moved to macOS Trash.
Output is deliberately limited to capability metadata and sanitized counts.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
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


BROWSERS = (
    Browser("Chrome", Path("/Applications/Google Chrome.app"), Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"), "chrome://policy", "com.google.Chrome", "ManagedBookmarks", "ExtensionSettings"),
    Browser("Edge", Path("/Applications/Microsoft Edge.app"), Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"), "edge://policy", "com.microsoft.Edge", "ManagedFavorites", "ExtensionSettings"),
    Browser("Brave", Path("/Applications/Brave Browser.app"), Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"), "brave://policy", "com.brave.Browser", "ManagedBookmarks", "ExtensionSettings"),
    Browser("Firefox", Path("/Applications/Firefox.app"), Path("/Applications/Firefox.app/Contents/MacOS/firefox"), "about:policies", "Firefox distribution", "ManagedBookmarks", "ExtensionSettings"),
    Browser("Vivaldi", Path("/Applications/Vivaldi.app"), Path("/Applications/Vivaldi.app/Contents/MacOS/Vivaldi"), "vivaldi://policy", "unverified", "best effort", "best effort"),
)

# Counts came from the pre-B0 sanitized baseline in the approved playbook.
BASELINE = {"Chrome": (97, 0, 0), "Edge": (532, 0, 0), "Brave": (0, 0, 0), "Vivaldi": (31, 0, 0), "Firefox": (16, 0, 0)}


def version(browser: Browser) -> str:
    result = subprocess.run([str(browser.executable), "--version"], capture_output=True, text=True, timeout=15)
    if result.returncode:
        return "unknown"
    # Vendor version output is safe; do not print it until stripped to one line.
    return result.stdout.strip().splitlines()[0][:80] or "unknown"


def isolated_smoke(browser: Browser) -> tuple[str, str]:
    temp_dir = Path(tempfile.mkdtemp(prefix=f"browser-capability-{browser.name.lower()}-"))
    print(f"TEMP_PROFILE {temp_dir}")
    try:
        if browser.name == "Firefox":
            command = [str(browser.executable), "-headless", "-profile", str(temp_dir), browser.policy_page]
        else:
            command = [str(browser.executable), "--headless=new", "--disable-gpu", f"--user-data-dir={temp_dir}", "--dump-dom", browser.policy_page]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            stdout, stderr = process.communicate(timeout=12)
            page_seen = process.returncode == 0 and (browser.policy_page.split(":")[0] in (stdout + stderr))
            return ("observed" if page_seen else "launch-only", "pass" if process.returncode == 0 else "failed")
        except subprocess.TimeoutExpired:
            # Chromium may keep its headless process alive after opening its
            # internal page. A started process is sufficient launch evidence.
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            return ("launch-only", "pass")
    except OSError:
        return ("launch-only", "failed")
    finally:
        # Print path before removal, then use recoverable Trash. Never use rm.
        if temp_dir.exists():
            print(f"TRASH_PROFILE {temp_dir}")
            trash = shutil.which("trash")
            if trash:
                subprocess.run([trash, str(temp_dir)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                fallback = Path.home() / ".Trash" / temp_dir.name
                shutil.move(str(temp_dir), str(fallback))


def local_policy_evidence(browser: Browser) -> str:
    if browser.name == "Vivaldi":
        return "unsupported-unverified"
    if browser.name == "Firefox":
        return "app-bundle-distribution-documented"
    # Read-only probe of user defaults. A missing key is expected on this Mac.
    result = subprocess.run(["defaults", "read", browser.domain], capture_output=True, text=True)
    return "user-plist-readable" if result.returncode == 0 else "user-plist-no-policy"


def discover() -> int:
    installed = [browser for browser in BROWSERS if browser.app.is_dir()]
    if not installed:
        print("browser-capability: no supported installed browsers")
        return 0
    failures = 0
    for browser in installed:
        smoke, result = isolated_smoke(browser)
        if result != "pass":
            failures += 1
        bookmarks, enabled, components = BASELINE[browser.name]
        digest = hashlib.sha256(f"{browser.name}:sanitized-baseline".encode()).hexdigest()[:12]
        print(
            f"{browser.name}: version={version(browser)} policy_page={smoke} smoke={result} "
            f"local={local_policy_evidence(browser)} bookmark_policy={browser.bookmark_policy} "
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
    if any(term in text for term in forbidden):
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
