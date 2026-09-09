#!/usr/bin/env python3
"""Validate browser-owned catalogs without printing sensitive values."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yaml

BROWSERS = ("chrome", "edge", "brave", "firefox", "vivaldi")
KINDS = ("bookmarks", "extensions", "policies")
CREDENTIAL_KEYS = re.compile(r"(?:access|auth|refresh|session|api)[_-]?(?:key|token)|password|passwd|secret", re.I)
SECRET_VALUE = re.compile(r"(?:bearer\s+\S+|gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})", re.I)
OAUTH_MARKER = re.compile(r"(?:oauth|callback|redirect_uri|code_verifier|id_token)", re.I)


class CatalogError(ValueError):
    pass


def normalized_url(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogError("URL must be a non-empty string")
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise CatalogError("URL must use https without user information")
    if OAUTH_MARKER.search(parsed.path) or OAUTH_MARKER.search(parsed.fragment):
        raise CatalogError("URL contains an OAuth marker")
    query = parse_qsl(parsed.query, keep_blank_values=True)
    if any(CREDENTIAL_KEYS.search(key) or OAUTH_MARKER.search(key) for key, _ in query):
        raise CatalogError("URL contains a credential-shaped query key")
    if (
        any(SECRET_VALUE.search(item) for pair in query for item in pair)
        or SECRET_VALUE.search(parsed.path)
        or SECRET_VALUE.search(parsed.fragment)
    ):
        raise CatalogError("URL contains a secret-shaped value")
    host = parsed.hostname.lower()
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or "/"
    return urlunsplit(("https", host + port, path, urlencode(sorted(query)), parsed.fragment))


def fingerprint(browser: str, title: str, url: str, folder: list[str]) -> str:
    normalized = {
        "browser": browser.lower(),
        "folder": [part.strip() for part in folder],
        "title": title.strip(),
        "url": normalized_url(url),
    }
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def require_keys(record: dict[str, object], keys: set[str], label: str) -> None:
    missing = keys - record.keys()
    extra = record.keys() - keys
    if missing or extra:
        raise CatalogError(f"{label} has missing or unexpected fields")


def validate_bookmarks(data: dict[str, object], browser: str) -> int:
    require_keys(data, {"version", "browser", "mode", "managed_folder", "bookmarks"}, "bookmark catalog")
    if (
        data["mode"] != "additions_only"
        or not isinstance(data["managed_folder"], str)
        or not data["managed_folder"].strip()
    ):
        raise CatalogError("bookmark catalog must be additions-only with a managed folder")
    records = data["bookmarks"]
    if not isinstance(records, list):
        raise CatalogError("bookmarks must be a list")
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise CatalogError("bookmark must be a mapping")
        require_keys(record, {"browser", "title", "url", "folder", "fingerprint"}, "bookmark")
        if record["browser"] != browser or not isinstance(record["title"], str):
            raise CatalogError("bookmark browser or title is invalid")
        folder = record["folder"]
        if not isinstance(folder, list) or not all(isinstance(part, str) and part.strip() for part in folder):
            raise CatalogError("bookmark folder must be a list of non-empty strings")
        normalized = normalized_url(record["url"])
        try:
            record["title"].encode("utf-8")
            for part in folder:
                part.encode("utf-8")
        except UnicodeEncodeError as error:
            raise CatalogError("bookmark text is not valid UTF-8") from error
        if record["title"] != record["title"].strip() or folder != [part.strip() for part in folder]:
            raise CatalogError("bookmark text fields are not normalized")
        if record["url"] != normalized:
            raise CatalogError("bookmark URL is not normalized")
        expected = fingerprint(browser, record["title"], normalized, folder)
        if record["fingerprint"] != expected or expected in seen:
            raise CatalogError("bookmark fingerprint is invalid or duplicated")
        seen.add(expected)
    return len(records)


def validate_extensions(data: dict[str, object], browser: str) -> int:
    require_keys(
        data,
        {"version", "browser", "enforcement", "system_components", "user_candidates", "required"},
        "extension catalog",
    )
    if data["enforcement"] not in {"report_only", "allowlist"}:
        raise CatalogError("extension enforcement is invalid")
    total = 0
    expected_presence = {
        "system_components": "observed",
        "user_candidates": "candidate",
        "required": "required",
    }
    identifiers: set[str] = set()
    for group in ("system_components", "user_candidates", "required"):
        records = data[group]
        if not isinstance(records, list):
            raise CatalogError("extension groups must be lists")
        for record in records:
            if not isinstance(record, dict):
                raise CatalogError("extension must be a mapping")
            require_keys(record, {"name", "id", "source", "update_url", "presence"}, "extension")
            if record["presence"] != expected_presence[group]:
                raise CatalogError("extension presence is invalid")
            if record["source"] != normalized_url(record["source"]):
                raise CatalogError("extension source URL is not normalized")
            if record["update_url"] != normalized_url(record["update_url"]):
                raise CatalogError("extension update URL is not normalized")
            if not all(isinstance(record[key], str) and record[key].strip() for key in ("name", "id")):
                raise CatalogError("extension name and id are required")
            if record["id"] in identifiers:
                raise CatalogError("extension id is duplicated")
            identifiers.add(record["id"])
            total += 1
    return total


def validate_policies(data: dict[str, object], _browser: str) -> int:
    require_keys(data, {"version", "browser", "policies"}, "policy catalog")
    records = data["policies"]
    if not isinstance(records, list):
        raise CatalogError("policies must be a list")
    names: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise CatalogError("policy must be a mapping")
        require_keys(record, {"name", "scope", "value"}, "policy")
        if record["scope"] not in {"mandatory", "recommended"} or not isinstance(record["name"], str):
            raise CatalogError("policy name or scope is invalid")
        if not record["name"].strip() or record["name"] in names:
            raise CatalogError("policy name is empty or duplicated")
        names.add(record["name"])
        if SECRET_VALUE.search(json.dumps(record["value"], sort_keys=True)):
            raise CatalogError("policy contains a secret-shaped value")
        validate_policy_strings(record["value"])
    return len(records)


def validate_policy_strings(value: object) -> None:
    if isinstance(value, dict):
        for child in value.values():
            validate_policy_strings(child)
    elif isinstance(value, list):
        for child in value:
            validate_policy_strings(child)
    elif isinstance(value, str) and (
        "://" in value or value.lower().startswith(("javascript:", "data:", "file:"))
    ):
        normalized_url(value)


VALIDATORS = {"bookmarks": validate_bookmarks, "extensions": validate_extensions, "policies": validate_policies}


def validate_file(path: Path, browser: str, kind: str) -> int:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1 or data.get("browser") != browser:
        raise CatalogError("catalog version or browser ownership is invalid")
    return VALIDATORS[kind](data, browser)


def validate_vivaldi_contract(root: Path) -> None:
    policies = yaml.safe_load((root / "vivaldi" / "policies.yml").read_text(encoding="utf-8"))
    extensions = yaml.safe_load((root / "vivaldi" / "extensions.yml").read_text(encoding="utf-8"))
    if policies.get("policies") or extensions.get("enforcement") != "report_only":
        raise CatalogError("Vivaldi must remain best-effort and report-only")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--browser", choices=BROWSERS)
    parser.add_argument("--root", type=Path, default=Path("host_files/localhost/browsers"))
    args = parser.parse_args()
    if not args.all and not args.browser:
        parser.error("pass --all or --browser")
    browsers = (args.browser,) if args.browser else BROWSERS
    counts = {kind: 0 for kind in KINDS}
    try:
        for browser in browsers:
            for kind in KINDS:
                counts[kind] += validate_file(args.root / browser / f"{kind}.yml", browser, kind)
        if "vivaldi" in browsers:
            validate_vivaldi_contract(args.root)
    except (OSError, yaml.YAMLError, CatalogError, ValueError) as error:
        print(f"browser catalog: failed ({type(error).__name__}: {error})")
        return 1
    print(
        "browser catalog: pass "
        f"browsers={len(browsers)} bookmarks={counts['bookmarks']} "
        f"extensions={counts['extensions']} policies={counts['policies']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
