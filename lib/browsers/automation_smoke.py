#!/usr/bin/env python3
"""Exercise browser automation stop conditions against fake state, without network."""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from browsers import REPO
from browsers import automation as automation_module
from browsers import catalog as catalog_module
from browsers import snapshot as snapshot_module

LAUNCHD_LABEL = "com.dkelly.browser-capture"
LAUNCHD_PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"
EXPECTED_INTERVAL = 900


AUTOMATION = automation_module
VALIDATOR = catalog_module


def git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if result.returncode != 0:
        raise RuntimeError(f"fixture git {arguments[0]} failed: {result.stderr.strip()}")
    return result.stdout.strip()


class FakeHub:
    """Stand-in for `gh`; records calls instead of reaching GitHub."""

    def __init__(self, private: bool = True, open_pulls: list[int] | None = None):
        self.private = private
        self.open_pulls = list(open_pulls or [])
        self.created = 0
        self.updated: list[int] = []
        self.auto_merged: list[tuple[int, str]] = []
        self.bodies: list[str] = []

    def is_private(self) -> bool:
        return self.private

    def pull_requests(self, branch: str) -> list[int]:
        return list(self.open_pulls)

    def create_pull_request(self, branch: str, title: str, body: str) -> int:
        self.created += 1
        self.bodies.append(body)
        self.open_pulls = [4242]
        return 4242

    def update_pull_request(self, number: int, title: str, body: str) -> None:
        self.updated.append(number)
        self.bodies.append(body)

    def enable_auto_merge(self, number: int) -> None:
        self.auto_merged.append((number, AUTOMATION.MERGE_METHOD))


def catalog_documents(browser: str) -> dict[str, dict[str, object]]:
    return {
        "bookmarks": {
            "version": 1,
            "browser": browser,
            "mode": "additions_only",
            "managed_folder": "Managed",
            "bookmarks": [],
        },
        "extensions": {
            "version": 1,
            "browser": browser,
            "enforcement": "report_only",
            "system_components": [],
            "user_candidates": [],
            "required": [],
        },
        "policies": {"version": 1, "browser": browser, "policies": []},
    }


def seed_source(root: Path) -> Path:
    """Build a fake repository with synthetic catalogs only — never real bookmark data."""
    source = root / "upstream"
    catalogs = source / "host_files" / "localhost" / "browsers"
    (source / "scripts").mkdir(parents=True)
    for browser in AUTOMATION.BROWSERS:
        (catalogs / browser).mkdir(parents=True)
        for kind, document in catalog_documents(browser).items():
            (catalogs / browser / f"{kind}.yml").write_text(
                yaml.safe_dump(document, sort_keys=False, explicit_start=True), encoding="utf-8"
            )
    for helper in ("validate-browser-catalog.py", "check-unencrypted-secrets.py"):
        (source / "scripts" / helper).write_text(
            (REPO / "scripts" / helper).read_text(encoding="utf-8"), encoding="utf-8"
        )
    # The entry points import the package next to them, so a clone that is meant
    # to run its own code needs the package too.
    shutil.copytree(REPO / "lib" / "browsers", source / "lib" / "browsers")
    # The catalogs are synthetic but the fleet description is the real one, so
    # the fixture exercises the same manifest the validator checks against.
    (catalogs / "manifest.yml").write_text(
        (REPO / "host_files" / "localhost" / "browsers" / "manifest.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (source / "Brewfile").write_text('cask "fixture-browser"\n', encoding="utf-8")
    (source / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
    git(source.parent, "init", "--quiet", "--initial-branch=main", str(source))
    git(source, "config", "user.email", "fixture@example.invalid")
    git(source, "config", "user.name", "Fixture")
    git(source, "add", "--", "scripts", "lib", "host_files", "Brewfile", ".gitignore")
    git(source, "commit", "--quiet", "--no-verify", "-m", "fixture: seed catalogs")
    return source


def fresh_remote(root: Path, source: Path, name: str) -> Path:
    """Give every case its own bare remote so pushes never cross-contaminate."""
    remote = root / f"{name}.git"
    subprocess.run(
        ["git", "clone", "--quiet", "--bare", str(source), str(remote)],
        check=True,
        capture_output=True,
        timeout=120,
    )
    return remote


def write_addition(clone: Path, url: str, browser: str = "chrome") -> None:
    path = clone / "host_files" / "localhost" / "browsers" / browser / "bookmarks.yml"
    catalog = yaml.safe_load(path.read_text(encoding="utf-8"))
    record = {
        "browser": browser,
        "title": "Fixture",
        "url": url,
        "folder": ["Folder"],
        "fingerprint": "0" * 64,
    }
    try:
        normalized = VALIDATOR.normalized_url(url)
        record["url"] = normalized
        record["fingerprint"] = VALIDATOR.fingerprint(browser, "Fixture", normalized, ["Folder"])
    except VALIDATOR.CatalogError:
        pass
    catalog["bookmarks"].append(record)
    path.write_text(yaml.safe_dump(catalog, sort_keys=False, explicit_start=True), encoding="utf-8")


def configure_clone(clone: Path) -> None:
    git(clone, "config", "user.email", "fixture@example.invalid")
    git(clone, "config", "user.name", "Fixture")


def expect_stop(case: str, function, *arguments, **keywords) -> None:
    try:
        function(*arguments, **keywords)
    except AUTOMATION.AutomationStop:
        return
    raise RuntimeError(f"{case} did not stop the run")


def case_happy(state: Path, remote: Path) -> None:
    hub = FakeHub()

    def capture(clone: Path) -> None:
        configure_clone(clone)
        write_addition(clone, "https://fixture.example.invalid/one")

    if AUTOMATION.run(state, hub, str(remote), capture) != 0:
        raise RuntimeError("happy path did not publish")
    if hub.created != 1 or hub.auto_merged != [(4242, "--merge")] or hub.updated:
        raise RuntimeError("happy path did not request exactly one auto-merge pull request")
    if any("://" in body for body in hub.bodies):
        raise RuntimeError("pull request body exposed a URL")
    branches = git(remote, "branch", "--list", AUTOMATION.AUTOMATION_BRANCH)
    if AUTOMATION.AUTOMATION_BRANCH not in branches:
        raise RuntimeError("automation branch was not pushed")

    def recapture(clone: Path) -> None:
        configure_clone(clone)
        write_addition(clone, "https://fixture.example.invalid/two")

    if AUTOMATION.run(state, hub, str(remote), recapture) != 0:
        raise RuntimeError("second run did not publish")
    if hub.created != 1 or hub.updated != [4242] or len(hub.auto_merged) != 2:
        raise RuntimeError("second run did not reuse the single pull request")


def case_secret_gate(state: Path, remote: Path) -> None:
    """The secret gate must refuse a staged credential.

    Aimed at the gate directly rather than through run(): the catalog schema
    rejects an unexpected key before publish() is ever reached, so a case that
    merely planted one in a catalog would have proved nothing about the gate.
    """
    clone = AUTOMATION.resolve_isolated_root(state)
    clone.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(remote), str(clone)],
        check=True, capture_output=True, timeout=120,
    )
    configure_clone(clone)

    # A clean clone passes.
    AUTOMATION.scan_staged_for_secrets(clone, sys.executable)

    planted = clone / "host_vars" / "localhost" / "planted.yml"
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_text("db_password: hunter2\n", encoding="utf-8")
    git(clone, "add", "--", "host_vars/localhost/planted.yml")
    expect_stop("secret gate", AUTOMATION.scan_staged_for_secrets, clone, sys.executable)

    # And it refuses to run at all when the gate itself is missing, rather than
    # silently treating an absent check as a pass.
    (clone / "scripts" / "check-unencrypted-secrets.py").unlink()
    expect_stop("missing secret gate", AUTOMATION.scan_staged_for_secrets, clone, sys.executable)


def case_no_additions(state: Path, remote: Path) -> None:
    hub = FakeHub()
    if AUTOMATION.run(state, hub, str(remote), configure_clone) != 0:
        raise RuntimeError("empty capture did not pass")
    if hub.created or hub.auto_merged:
        raise RuntimeError("empty capture opened a pull request")


def case_public(state: Path, remote: Path) -> None:
    expect_stop("public repository", AUTOMATION.run, state, FakeHub(private=False), str(remote), configure_clone)


def case_dirty(state: Path, remote: Path) -> None:
    clone = AUTOMATION.resolve_isolated_root(state)
    clone.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(remote), str(clone)],
        check=True,
        capture_output=True,
        timeout=120,
    )
    (clone / "unexpected-local-file").write_text("dirty\n", encoding="utf-8")
    expect_stop("dirty isolated clone", AUTOMATION.run, state, FakeHub(), str(remote), configure_clone)


def case_unexpected_path(state: Path, remote: Path) -> None:
    def capture(clone: Path) -> None:
        configure_clone(clone)
        write_addition(clone, "https://fixture.example.invalid/three")
        (clone / "Brewfile").write_text('cask "fixture-browser"\ncask "sneaky"\n', encoding="utf-8")

    expect_stop("unexpected path", AUTOMATION.run, state, FakeHub(), str(remote), capture)


def case_suspicious_url(state: Path, remote: Path) -> None:
    def capture(clone: Path) -> None:
        configure_clone(clone)
        write_addition(clone, "http://fixture.example.invalid/insecure?access_token=abc")

    expect_stop("suspicious URL", AUTOMATION.run, state, FakeHub(), str(remote), capture)


def case_non_fast_forward(state: Path, remote: Path) -> None:
    class MovedRemoteGit(AUTOMATION.Git):
        def __call__(self, *arguments: str, check: bool = True, raw: bool = False) -> str:
            if arguments[:2] == ("rev-parse", "origin/main"):
                return "1" * 40
            return super().__call__(*arguments, check=check, raw=raw)

    expect_stop(
        "non-fast-forward",
        AUTOMATION.run,
        state,
        FakeHub(),
        str(remote),
        configure_clone,
        git_factory=MovedRemoteGit,
    )


def case_push_conflict(state: Path, remote: Path, root: Path) -> None:
    diverged = Path(tempfile.mkdtemp(prefix="diverged-", dir=root)) / "clone"
    subprocess.run(
        ["git", "clone", "--quiet", str(remote), str(diverged)],
        check=True,
        capture_output=True,
        timeout=120,
    )
    configure_clone(diverged)
    git(diverged, "checkout", "--quiet", "-B", AUTOMATION.AUTOMATION_BRANCH, "origin/main")
    write_addition(diverged, "https://fixture.example.invalid/conflict")
    git(diverged, "add", "--", "host_files/localhost/browsers/chrome/bookmarks.yml")
    git(diverged, "commit", "--quiet", "--no-verify", "-m", "fixture: divergent automation branch")
    git(diverged, "push", "--quiet", "origin", f"HEAD:refs/heads/{AUTOMATION.AUTOMATION_BRANCH}")
    # Move main on after the branch so neither ref contains the other.
    git(diverged, "checkout", "--quiet", "main")
    (diverged / "Brewfile").write_text('cask "fixture-browser"\ncask "later"\n', encoding="utf-8")
    git(diverged, "add", "--", "Brewfile")
    git(diverged, "commit", "--quiet", "--no-verify", "-m", "fixture: advance main")
    git(diverged, "push", "--quiet", "origin", "HEAD:refs/heads/main")

    def capture(clone: Path) -> None:
        configure_clone(clone)
        write_addition(clone, "https://fixture.example.invalid/four")

    expect_stop("push conflict", AUTOMATION.run, state, FakeHub(), str(remote), capture)


def case_two_pull_requests(state: Path, remote: Path) -> None:
    def capture(clone: Path) -> None:
        configure_clone(clone)
        write_addition(clone, "https://fixture.example.invalid/five")

    expect_stop(
        "two open pull requests",
        AUTOMATION.run,
        state,
        FakeHub(open_pulls=[1, 2]),
        str(remote),
        capture,
    )


def case_normal_checkout_guard() -> None:
    for candidate in (REPO, REPO / ".git", Path("/tmp"), Path.home()):
        expect_stop(f"isolated guard {candidate.name or 'root'}", AUTOMATION.resolve_isolated_root, candidate)


def case_launchd_state() -> str:
    """Read-only launchd evidence: installed disabled, interval-polled, never WatchPaths."""
    if not LAUNCHD_PLIST.is_file():
        return "absent"
    with LAUNCHD_PLIST.open("rb") as stream:
        plist = plistlib.load(stream)
    if plist.get("Label") != LAUNCHD_LABEL:
        raise RuntimeError("launchd label is unexpected")
    if "WatchPaths" in plist or "QueueDirectories" in plist:
        raise RuntimeError("launchd job must poll by interval, not watch paths")
    if plist.get("StartInterval") != EXPECTED_INTERVAL:
        raise RuntimeError("launchd interval is not about 15 minutes")
    if plist.get("Disabled") is not True or plist.get("RunAtLoad") is not False:
        raise RuntimeError("launchd job is not installed disabled")
    listed = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=60)
    if LAUNCHD_LABEL in listed.stdout:
        raise RuntimeError("launchd job is loaded before activation")
    return "installed-disabled"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fake", action="store_true")
    parser.add_argument("--no-network", action="store_true")
    args = parser.parse_args()
    if not args.fake or not args.no_network:
        parser.error("automation smoke runs only with --fake --no-network")
    snapshot = snapshot_module
    state_root = Path.home() / ".local" / "state" / "macbook-pro" / "browser-automation-smoke"
    state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="browser-automation-smoke-", dir=state_root))
    os.environ["BROWSER_AUTOMATION_NO_NOTIFY"] = "1"
    cases = 0
    try:
        source = seed_source(root)
        for case in (case_happy, case_no_additions, case_public, case_unexpected_path, case_suspicious_url,
                     case_non_fast_forward, case_two_pull_requests, case_dirty,
                     case_secret_gate):
            state = Path(tempfile.mkdtemp(prefix="state-", dir=root))
            case(state, fresh_remote(root, source, case.__name__))
            cases += 1
        state = Path(tempfile.mkdtemp(prefix="state-", dir=root))
        case_push_conflict(state, fresh_remote(root, source, "case_push_conflict"), root)
        cases += 1
        case_normal_checkout_guard()
        cases += 1
        launchd = case_launchd_state()
        cases += 1
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError, yaml.YAMLError,
            subprocess.SubprocessError, AUTOMATION.AutomationStop) as error:
        print(f"browser automation smoke: failed ({type(error).__name__}: {error})")
        return 1
    finally:
        if root.exists():
            snapshot.trash(root)
    print(
        f"browser automation smoke: pass cases={cases} network=none launchd={launchd} "
        "checkout=untouched pull-requests=1"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
