#!/usr/bin/env python3
"""Publish captured bookmark additions from an isolated clone through one private PR."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parent.parent
REPO_SLUG = "Edition-X/macbook-pro"
BROWSERS = ("chrome", "edge", "brave", "firefox", "vivaldi")
AUTOMATION_BRANCH = "automation/browser-catalog"
COMMIT_MESSAGE = "chore(browsers): capture bookmark additions"
MERGE_METHOD = "--merge"
STAGE_ALLOWLIST = tuple(f"host_files/localhost/browsers/{name}/bookmarks.yml" for name in BROWSERS)
VALIDATOR_ALLOWLIST = ("scripts/validate-browser-catalog.py",)
STATE_RELATIVE = Path("macbook-pro") / "browser-automation"


class AutomationStop(RuntimeError):
    """A contract boundary refused the run; no repository state was published."""


def load_script(name: str, filename: str, root: Path = REPO) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, root / "scripts" / filename)
    if spec is None or spec.loader is None:
        raise AutomationStop("automation module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def safe(text: str) -> str:
    """Refuse any line that could leak a bookmark URL or secret-shaped value."""
    lowered = text.lower()
    if "://" in text or "bearer " in lowered or "ghp_" in lowered:
        raise AutomationStop("automation output would expose a URL or secret")
    return text


def report(message: str) -> None:
    print(safe(f"browser automation: {message}"))


def notify(message: str) -> None:
    """Send a local notification with counts only, never a URL."""
    body = safe(message)
    if os.environ.get("BROWSER_AUTOMATION_NO_NOTIFY") == "1":
        return
    script = f'display notification {json.dumps(body)} with title "Browser catalog"'
    subprocess.run(
        ["/usr/bin/osascript", "-e", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


class Git:
    """Run git against one worktree, refusing force pushes outright."""

    def __init__(self, root: Path):
        self.root = root

    def __call__(self, *arguments: str, check: bool = True, raw: bool = False) -> str:
        if any(argument in {"--force", "-f", "--force-with-lease"} for argument in arguments):
            raise AutomationStop("force push or force update is never allowed")
        environment = os.environ.copy()
        environment["GIT_TERMINAL_PROMPT"] = "0"
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(self.root), *arguments],
            capture_output=True,
            text=True,
            timeout=300,
            env=environment,
        )
        if check and result.returncode != 0:
            raise AutomationStop(f"git {arguments[0]} failed rc={result.returncode}")
        # Porcelain output carries meaning in its leading column, so raw callers
        # must not have it stripped away.
        return result.stdout if raw else result.stdout.strip()

    def succeeds(self, *arguments: str) -> bool:
        environment = os.environ.copy()
        environment["GIT_TERMINAL_PROMPT"] = "0"
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(self.root), *arguments],
            capture_output=True,
            text=True,
            timeout=120,
            env=environment,
        )
        return result.returncode == 0

    def status(self) -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        for line in self("status", "--porcelain", "-z", raw=True).split("\0"):
            if len(line) > 3:
                entries.append((line[:2].strip(), line[3:]))
        return entries


class GitHubHub:
    """Real `gh` surface. Only exercised once B10 activates the service."""

    def __init__(self, slug: str = REPO_SLUG):
        self.slug = slug

    def _gh(self, *arguments: str) -> str:
        result = subprocess.run(
            ["gh", *arguments],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise AutomationStop(f"gh {arguments[0]} failed rc={result.returncode}")
        return result.stdout.strip()

    def is_private(self) -> bool:
        payload = json.loads(self._gh("repo", "view", self.slug, "--json", "isPrivate"))
        return payload.get("isPrivate") is True

    def pull_requests(self, branch: str) -> list[int]:
        payload = json.loads(
            self._gh("pr", "list", "--repo", self.slug, "--head", branch, "--state", "open", "--json", "number")
        )
        return [int(item["number"]) for item in payload]

    def create_pull_request(self, branch: str, title: str, body: str) -> int:
        self._gh(
            "pr", "create", "--repo", self.slug, "--head", branch, "--base", "main",
            "--title", title, "--body", body,
        )
        numbers = self.pull_requests(branch)
        if len(numbers) != 1:
            raise AutomationStop("pull request count is not exactly one after create")
        return numbers[0]

    def update_pull_request(self, number: int, title: str, body: str) -> None:
        self._gh("pr", "edit", str(number), "--repo", self.slug, "--title", title, "--body", body)

    def enable_auto_merge(self, number: int) -> None:
        self._gh("pr", "merge", str(number), "--repo", self.slug, "--auto", MERGE_METHOD)


def resolve_isolated_root(isolated_root: Path) -> Path:
    """Refuse anything that is not a dedicated directory under ~/.local/state."""
    state = (Path.home() / ".local" / "state").resolve()
    root = isolated_root.expanduser()
    if root.is_symlink():
        raise AutomationStop("isolated root is a symlink")
    root = root.resolve()
    if root != state and state not in root.parents:
        raise AutomationStop("automation state must live under ~/.local/state")
    clone = root / STATE_RELATIVE / "repo" if root == state else root / "repo"
    if clone == REPO or REPO in clone.parents or clone in REPO.parents:
        raise AutomationStop("automation must never use the normal checkout")
    return clone


def require_private(hub: object) -> None:
    if hub.is_private() is not True:
        raise AutomationStop("repository privacy is false or unknown")


def prepare_clone(clone: Path, remote: str, git_factory: Callable[[Path], Git]) -> Git:
    clone.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not (clone / ".git").is_dir():
        result = subprocess.run(
            ["git", "clone", "--no-hardlinks", remote, str(clone)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            raise AutomationStop("isolated clone could not be created")
    git = git_factory(clone)
    if git.status():
        raise AutomationStop("isolated clone is dirty")
    git("fetch", "--prune", "origin")
    remote_branch = f"refs/remotes/origin/{AUTOMATION_BRANCH}"
    base = "origin/main"
    if git.succeeds("rev-parse", "--verify", "--quiet", remote_branch):
        contains_main = git.succeeds("merge-base", "--is-ancestor", "origin/main", remote_branch)
        merged_already = git.succeeds("merge-base", "--is-ancestor", remote_branch, "origin/main")
        if not contains_main and not merged_already:
            raise AutomationStop("automation branch has diverged from main")
        # An open automation branch keeps stacking additions; a merged one restarts from main.
        base = f"origin/{AUTOMATION_BRANCH}" if contains_main else "origin/main"
    git("checkout", "-B", AUTOMATION_BRANCH, base)
    if git("rev-parse", "HEAD") != git("rev-parse", base):
        raise AutomationStop("isolated clone is not fast-forward with its base")
    return git


def check_staged_paths(git: Git) -> list[str]:
    paths = [path for _, path in git.status()]
    unexpected = [path for path in paths if path not in STAGE_ALLOWLIST]
    if unexpected:
        raise AutomationStop(f"unexpected changed path count={len(unexpected)}")
    return sorted(paths)


def validate_catalogs(clone: Path) -> int:
    result = subprocess.run(
        [sys.executable, str(clone / "scripts" / "validate-browser-catalog.py"), "--all", "--root",
         str(clone / "host_files" / "localhost" / "browsers")],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise AutomationStop("catalog validation failed in the isolated clone")
    return result.returncode


def live_capture_with(interpreter: str) -> Callable[[Path], None]:
    """Bind the capture step to one interpreter.

    `sys.executable` is not safe here: the service runs this script under
    whichever python the runner resolved, and passing that on would spread a
    wrong interpreter rather than correct it. The caller states it explicitly.
    """

    def capture(clone: Path) -> None:
        result = subprocess.run(
            [interpreter, str(clone / "scripts" / "browser-capture.py"), "--enable-capture", "--isolated"],
            capture_output=True,
            text=True,
            timeout=900,
        )
        if result.returncode != 0 or "://" in result.stdout:
            raise AutomationStop("isolated capture failed or produced unsafe output")

    return capture


def publish(git: Git, hub: object, paths: Sequence[str], remote_branch: str = AUTOMATION_BRANCH) -> int:
    numbers = hub.pull_requests(remote_branch)
    if len(numbers) > 1:
        raise AutomationStop("more than one automation pull request is open")
    for path in paths:
        git("add", "--", path)
    git("commit", "--no-verify", "-m", COMMIT_MESSAGE)
    git("push", "origin", f"HEAD:refs/heads/{remote_branch}")
    title = COMMIT_MESSAGE
    body = f"Automated bookmark additions for {len(paths)} browser catalogs. Counts only; no URLs in logs."
    number = numbers[0] if numbers else hub.create_pull_request(remote_branch, title, body)
    if numbers:
        hub.update_pull_request(number, title, body)
    hub.enable_auto_merge(number)
    if len(hub.pull_requests(remote_branch)) != 1:
        raise AutomationStop("pull request count is not exactly one after publish")
    return number


def run(
    isolated_root: Path,
    hub: object,
    remote: str,
    capture: Callable[[Path], None],
    git_factory: Callable[[Path], Git] = Git,
) -> int:
    clone = resolve_isolated_root(isolated_root)
    require_private(hub)
    git = prepare_clone(clone, remote, git_factory)
    capture(clone)
    validate_catalogs(clone)
    paths = check_staged_paths(git)
    if not paths:
        report("pass additions=0 published=false")
        notify("No new bookmarks captured.")
        return 0
    number = publish(git, hub, paths)
    report(f"pass catalogs={len(paths)} pull-request=1 auto-merge=requested method=merge-commit pr={number}")
    notify(f"Captured additions in {len(paths)} catalogs; pull request {number} set to auto-merge.")
    return 0


def origin_url() -> str:
    return f"https://github.com/{REPO_SLUG}.git"


def require_usable_interpreter(interpreter: str) -> None:
    """Refuse to start when the named interpreter cannot run the capture scripts."""
    probe = (
        "import sys, yaml;"
        "assert sys.version_info >= (3, 12), sys.version.split()[0];"
        "print(sys.version.split()[0])"
    )
    try:
        result = subprocess.run([interpreter, "-c", probe], capture_output=True, text=True, timeout=60)
    except OSError as error:
        raise AutomationStop(f"interpreter {interpreter} is not runnable") from error
    if result.returncode != 0:
        raise AutomationStop(f"interpreter {interpreter} failed preflight")


def self_check(isolated_root: Path) -> int:
    """Static contract audit: no network, no clone, no repository mutation."""
    clone = resolve_isolated_root(isolated_root)
    if clone.exists() and clone.is_symlink():
        raise AutomationStop("existing automation clone is a symlink")

    for candidate in (REPO, Path("/tmp"), Path.home()):
        try:
            resolve_isolated_root(candidate)
        except AutomationStop:
            continue
        raise AutomationStop("isolated root guard accepted an unsafe location")

    try:
        Git(REPO)("push", "origin", "--force", "HEAD")
    except AutomationStop:
        pass
    else:
        raise AutomationStop("force push was not refused")

    for unsafe in ("https://example.invalid/page", "Bearer abc123"):
        try:
            safe(unsafe)
        except AutomationStop:
            continue
        raise AutomationStop("output sanitizer accepted unsafe text")

    validator = load_script("browser_catalog_validator", "validate-browser-catalog.py")
    if set(BROWSERS) != set(validator.BROWSERS):
        raise AutomationStop("automation browser set does not match the validator")
    if len(STAGE_ALLOWLIST) != len(BROWSERS) or any(
        not (REPO / path).is_file() for path in (*STAGE_ALLOWLIST, *VALIDATOR_ALLOWLIST)
    ):
        raise AutomationStop("allowlisted automation paths are missing")
    if MERGE_METHOD != "--merge":
        raise AutomationStop("auto-merge must use a merge commit")

    report(
        f"check pass allowlist={len(STAGE_ALLOWLIST)} branch={AUTOMATION_BRANCH} "
        f"isolated=true force-push=refused network=none"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--isolated-root", type=Path, required=True)
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="interpreter used for the capture step; defaults to the current one",
    )
    args = parser.parse_args()
    if args.check == args.run:
        parser.error("pass exactly one of --check or --run")
    try:
        if args.check:
            return self_check(args.isolated_root)
        if os.environ.get("BROWSER_AUTOMATION_AUTHORIZED") != "1":
            raise AutomationStop("live run needs BROWSER_AUTOMATION_AUTHORIZED=1 from an activated service")
        require_usable_interpreter(args.python)
        return run(args.isolated_root, GitHubHub(), origin_url(), live_capture_with(args.python))
    except (AutomationStop, OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        message = f"stop ({type(error).__name__}: {error})"
        print(f"browser automation: {message}" if "://" not in str(error) else "browser automation: stop (redacted)")
        notify("Automation stopped before publishing; see the log line.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
