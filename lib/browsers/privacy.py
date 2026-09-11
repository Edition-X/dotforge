#!/usr/bin/env python3
"""Enforce the browser privacy contract on repository content and tool output.

Two rules the browser work depends on, which were previously only checked
inside a path-filtered GitHub workflow — so a change to the Makefile or the
cleanup role could break them without any check running:

1. Bookmark URLs live only in the five per-browser bookmark catalogs. Every
   other managed file, and every line the browser tools print, is counts-only.
2. No browser state that carries credentials or sessions is ever tracked —
   Login Data, key4.db, logins.json, Cookies, a preference store, and so on.

Vendored trees are skipped, matching the lint exclusions. Findings name the
file and the reason, never the offending value.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from browsers import BROWSERS, REPO

BOOKMARK_CATALOGS = {f"host_files/localhost/browsers/{name}/bookmarks.yml" for name in BROWSERS}

# Browser state that carries credentials, sessions or a preference store.
FORBIDDEN_STATE = re.compile(
    r"(?:^|/)(?:Login Data|Login Data For Account|key[34]\.db|cert[89]\.db|logins\.json"
    r"|Cookies|Secure Preferences|signons\.sqlite|Local Storage|Session Storage)(?:$|/)",
    re.IGNORECASE,
)

URL = re.compile(r"https?://[^\s\"'<>)\\]+")

# Hosts that legitimately appear in managed source: vendor documentation, the
# extension stores the catalogs reference, fixtures, and localhost.
ALLOWED_HOSTS = {
    "127.0.0.1",
    "localhost",
    "addons.mozilla.org",
    "chromeenterprise.google",
    "chromewebstore.google.com",
    "claude.com",
    "clients2.google.com",
    "cli.github.com",
    "docs.brew.sh",
    "docs.github.com",
    "edge.microsoft.com",
    "gist.github.com",
    "github.com",
    "ipapi.co",
    "help.vivaldi.com",
    "img.shields.io",
    "lastpass.com",
    "learn.microsoft.com",
    "microsoftedge.microsoft.com",
    "mozilla.github.io",
    "opencode.ai",
    "playwright.dev",
    "pre-commit.com",
    "raw.githubusercontent.com",
    "support.brave.com",
    "support.google.com",
    "www.apple.com",
    "www.ansible.com",
    "www.python.org",
}

SKIP_PREFIXES = (
    "collections/",
    "node_modules/",
    "venv/",
    "docs/",
    "host_files/localhost/nvim/",
    "host_files/localhost/ai/skills/",
)


def tracked() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], capture_output=True, text=True, check=True, cwd=REPO
    )
    return [path for path in result.stdout.split("\0") if path]


def check_forbidden_state(paths: list[str]) -> list[str]:
    return [f"{path}: tracked browser state that may carry credentials or sessions"
            for path in paths if FORBIDDEN_STATE.search(path)]


def check_url_confinement(paths: list[str]) -> list[str]:
    findings = []
    for path in paths:
        if path in BOOKMARK_CATALOGS or path.startswith(SKIP_PREFIXES):
            continue
        full = REPO / path
        if not full.is_file():
            continue
        try:
            content = full.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        unexpected = {
            host
            for match in URL.findall(content)
            # A templated URL names no host until it is rendered.
            if "{{" not in match
            and (host := (urlsplit(match).hostname or "").lower())
            and host not in ALLOWED_HOSTS
            and not host.endswith(".invalid")
            and not host.endswith(".example.com")
        }
        if unexpected:
            findings.append(f"{path}: {len(unexpected)} unexpected host(s) outside the bookmark catalogs")
    return findings


def check_tool_output() -> list[str]:
    """The browser tools report counts. A URL or secret in their output is a leak."""
    unsafe = re.compile(r"://|bearer |gh[pousr]_[A-Za-z0-9]{20,}", re.IGNORECASE)
    findings = []
    commands = (
        [sys.executable, "scripts/validate-browser-catalog.py", "--all"],
        [sys.executable, "scripts/browser-git-automation.py", "--check",
         "--isolated-root", str(Path.home() / ".local" / "state")],
    )
    for command in commands:
        result = subprocess.run(command, capture_output=True, text=True, cwd=REPO, timeout=300)
        if result.returncode != 0:
            findings.append(f"{Path(command[1]).name}: exited {result.returncode}")
            continue
        if unsafe.search(result.stdout):
            findings.append(f"{Path(command[1]).name}: printed a URL or secret-shaped value")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="check tracked content and tool output")
    parser.parse_args()

    paths = tracked()
    findings = check_forbidden_state(paths) + check_url_confinement(paths) + check_tool_output()
    for finding in findings:
        print(f"❌ {finding}")
    if findings:
        return 1
    print(
        f"✅ browser privacy: tracked={len(paths)} catalogs={len(BOOKMARK_CATALOGS)} "
        "urls-confined=true forbidden-state=absent output=counts-only"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
