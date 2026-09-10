#!/usr/bin/env python3
"""Report sanitized browser extension state and verify managed presence entries."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from types import ModuleType

import yaml

REPO = Path(__file__).resolve().parent.parent
BROWSERS = ("chrome", "edge", "brave", "firefox", "vivaldi")
CHROMIUM_PROFILES = {
    "chrome": "Google/Chrome/Default",
    "edge": "Microsoft Edge/Default",
    "brave": "BraveSoftware/Brave-Browser/Default",
    "vivaldi": "Vivaldi/Default",
}
# Chromium install locations that belong to the browser itself rather than the
# user: 5 is a bundled component, 10 an external component.
COMPONENT_LOCATIONS = {5, 10}
FIREFOX_USER_LOCATION = "app-profile"
# Store update endpoints proven against vendor evidence in this ticket:
# Chrome Web Store (also used by Brave), Microsoft Edge Add-ons, and
# addons.mozilla.org. Any other update URL fails the catalog check.
VERIFIED_UPDATE_URLS = {
    "https://clients2.google.com/service/update2/crx",
    "https://edge.microsoft.com/extensionwebstorebase/v1/crx",
    "https://addons.mozilla.org/firefox/downloads/latest/lastpass-password-manager/latest.xpi",
}
REPORT_PATH = Path.home() / ".local" / "state" / "macbook-pro" / "browser-policy" / "extension-report.json"


def load_script(name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError("browser extension report module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def catalog(browser: str) -> dict[str, object]:
    path = REPO / "host_files" / "localhost" / "browsers" / browser / "extensions.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def check_catalog(data: dict[str, object], validator: ModuleType, browser: str) -> int:
    """Presence entries must carry a vendor-verified id and store update URL."""
    validator.validate_extensions(data, browser)
    if data["enforcement"] != "report_only":
        raise RuntimeError("blocking enforcement needs an explicit migration review")
    for record in data["required"]:
        if record["update_url"] not in VERIFIED_UPDATE_URLS:
            raise RuntimeError("required extension update URL is not vendor-verified")
    return len(data["required"])


def stable_json_read(path: Path, attempts: int = 5) -> dict[str, object]:
    """Read a live preference file in memory only.

    Extension state lives in the browser's preference store, which is never
    copied or written: the file is read in place, twice, and only accepted when
    metadata and content hash agree. Copying it anywhere would put a preference
    database outside the profile that owns it.
    """
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("browser preference source is unsafe")
    for _ in range(attempts):
        before = path.stat()
        payload = path.read_bytes()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns) and hashlib.sha256(
            payload
        ).digest() == hashlib.sha256(path.read_bytes()).digest():
            value = json.loads(payload)
            if not isinstance(value, dict):
                raise RuntimeError("browser preference content is invalid")
            return value
        time.sleep(0.1)
    raise RuntimeError("browser preference source stayed inconsistent")


def chromium_enabled(record: dict[str, object]) -> bool:
    """Current Chromium builds drop `state` and record disable reasons instead."""
    state = record.get("state")
    if state is not None:
        return state == 1
    reasons = record.get("disable_reasons")
    if isinstance(reasons, list):
        return not reasons
    return reasons in (None, 0)


def chromium_state(browser: str) -> dict[str, object]:
    profile = Path.home() / "Library" / "Application Support" / CHROMIUM_PROFILES[browser]
    settings: object = {}
    if not profile.is_dir():
        return {"system": [], "user": [], "profile": "absent"}
    # Chromium keeps extension records in the protected store, falling back to
    # the plain one on older profiles.
    for name in ("Secure Preferences", "Preferences"):
        source = profile / name
        if not source.is_file():
            continue
        candidate = stable_json_read(source).get("extensions", {})
        if isinstance(candidate, dict) and candidate.get("settings"):
            settings = candidate["settings"]
            break
    if not isinstance(settings, dict):
        raise RuntimeError("Chromium extension settings are invalid")
    system: list[dict[str, object]] = []
    user: list[dict[str, object]] = []
    for identifier, record in settings.items():
        if not isinstance(record, dict):
            continue
        manifest = record.get("manifest") if isinstance(record.get("manifest"), dict) else {}
        entry = {
            "id": identifier,
            "name": str(manifest.get("name", "")),
            "enabled": chromium_enabled(record),
            "update_url": str(manifest.get("update_url", "")),
        }
        component = record.get("location") in COMPONENT_LOCATIONS or record.get("was_installed_by_default") is True
        (system if component else user).append(entry)
    return {"system": system, "user": user, "profile": "present"}


def firefox_state(snapshot: ModuleType) -> dict[str, object]:
    profiles = snapshot.firefox_profiles(Path.home() / "Library" / "Application Support" / "Firefox")
    source = profiles["default-release"] / "extensions.json"
    if not source.is_file():
        return {"system": [], "user": [], "profile": "absent"}
    addons = stable_json_read(source).get("addons", [])
    if not isinstance(addons, list):
        raise RuntimeError("Firefox add-on state is invalid")
    system: list[dict[str, object]] = []
    user: list[dict[str, object]] = []
    for addon in addons:
        if not isinstance(addon, dict):
            continue
        entry = {
            "id": str(addon.get("id", "")),
            "name": str((addon.get("defaultLocale") or {}).get("name", "")),
            "enabled": addon.get("active") is True,
            "update_url": "",
        }
        (user if addon.get("location") == FIREFOX_USER_LOCATION else system).append(entry)
    return {"system": system, "user": user, "profile": "present"}


def vivaldi_state() -> dict[str, object]:
    """Vivaldi has no proven policy contract, so presence is observed only."""
    directory = Path.home() / "Library" / "Application Support" / "Vivaldi" / "Default" / "Extensions"
    if not directory.is_dir():
        return {"system": [], "user": [], "profile": "absent"}
    identifiers = sorted(entry.name for entry in directory.iterdir() if entry.is_dir())
    return {
        "system": [],
        "user": [{"id": identifier, "name": "", "enabled": True, "update_url": ""} for identifier in identifiers],
        "profile": "present",
    }


def presence(state: dict[str, object], data: dict[str, object]) -> str:
    required = {str(record["id"]) for record in data["required"]}
    if not required:
        return "not-managed"
    installed = {str(entry["id"]) for entry in [*state["system"], *state["user"]]}
    enabled = {str(entry["id"]) for entry in [*state["system"], *state["user"]] if entry["enabled"]}
    if required <= enabled:
        return "present"
    if required <= installed:
        return "installed-disabled"
    return "absent"


def write_report(report: dict[str, object]) -> None:
    """Keep candidate identifiers in local mode-0600 state, never in the repository."""
    REPORT_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".extension-report-", dir=REPORT_PATH.parent)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    os.chmod(temporary, 0o600)
    os.replace(temporary, REPORT_PATH)
    if REPORT_PATH.stat().st_mode & 0o777 != 0o600:
        raise RuntimeError("extension report mode is unsafe")


def build(browsers: tuple[str, ...]) -> int:
    snapshot = load_script("browser_snapshot", "browser-snapshot.py")
    validator = load_script("browser_catalog_validator", "validate-browser-catalog.py")
    work = Path(tempfile.mkdtemp(prefix="browser-extension-report-"))
    report: dict[str, object] = {
        "version": 1,
        "generated": datetime.datetime.now(tz=datetime.UTC).replace(microsecond=0).isoformat(),
        "review": "pending",
        "enforcement": "report_only",
        "browsers": {},
    }
    try:
        for browser in browsers:
            data = catalog(browser)
            required = check_catalog(data, validator, browser)
            if browser == "firefox":
                state = firefox_state(snapshot)
            elif browser == "vivaldi":
                state = vivaldi_state()
            else:
                state = chromium_state(browser)
            report["browsers"][browser] = state
            enabled = sum(1 for entry in [*state["system"], *state["user"]] if entry["enabled"])
            print(
                f"browser extensions: browser={browser} profile={state['profile']} "
                f"components={len(state['system'])} user-candidates={len(state['user'])} "
                f"enabled={enabled} required={required} lastpass={presence(state, data)} "
                "catalog=verified"
            )
        write_report(report)
    finally:
        if work.exists():
            snapshot.trash(work)
    print(
        f"browser extensions: pass browsers={len(browsers)} report=local-0600 "
        "enforcement=report-only review=pending output=counts-only"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--browser", choices=BROWSERS)
    parser.add_argument("--sanitized", action="store_true")
    parser.add_argument("--isolated", action="store_true")
    args = parser.parse_args()
    if not args.sanitized or not args.isolated or (args.all == bool(args.browser)):
        parser.error("use --sanitized --isolated with either --all or --browser <name>")
    browsers = BROWSERS if args.all else (args.browser,)
    try:
        return build(browsers)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, yaml.YAMLError) as error:
        print(f"browser extensions: failed ({type(error).__name__}: {error})")
        return 1


if __name__ == "__main__":
    sys.exit(main())
