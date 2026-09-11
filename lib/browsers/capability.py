#!/usr/bin/env python3
"""Isolated browser capability smoke for B0.

This tool never discovers or opens a user's browser profile.  Browser launches
use a fresh temporary profile, and temporary state is moved to macOS Trash.
Output is deliberately limited to capability metadata and sanitized counts.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import plistlib
import pwd
import re
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from browsers import MANIFEST


@dataclass(frozen=True)
class Browser:
    name: str
    app: Path
    executable: Path
    policy_page: str
    domain: str
    bookmark_policy: str
    extension_policy: str


# Built from the manifest rather than restated. `domain` carries the policy
# domain where one is proven, and a short reason where it is not — the reports
# below print it either way.
BROWSER_APPS = tuple(
    Browser(
        name=str(entry["label"]),
        app=Path(str(entry["application"])),
        executable=Path(str(entry["application"])) / str(entry["executable"]),
        policy_page=str(entry["policy"]["page"]),
        domain=str(entry["policy"]["domain"]) or "unverified",
        bookmark_policy=str(entry["policy"]["bookmarks_key"]) or "best effort",
        extension_policy=str(entry["policy"]["extensions_key"]) or "best effort",
    )
    for entry in MANIFEST
)

# Counts came from the pre-B0 sanitized baseline in the approved playbook.
# Fake policy used only inside an isolated smoke, to prove a browser accepts a
# mandatory managed preference at all. Never real bookmark data: the URL is
# .invalid and the folder name is a fixture marker.
POLICY_PAYLOADS = {
    "com.google.Chrome": {
        "HomepageLocation": "B0-Fake-Policy",
        "ManagedBookmarks": [
            {"toplevel_name": "B0"},
            {"name": "Fake managed bookmark", "url": "https://example.invalid/managed"},
        ],
        "ExtensionSettings": {"*": {"installation_mode": "allowed"}},
    },
    "com.microsoft.Edge": {
        "HomepageLocation": "B0-Fake-Policy",
        "ManagedFavorites": [
            {"toplevel_name": "B0"},
            {"name": "Fake managed favorite", "url": "https://example.invalid/managed"},
        ],
        "ExtensionSettings": {"*": {"installation_mode": "allowed"}},
    },
    "com.brave.Browser": {
        "HomepageLocation": "B0-Fake-Policy",
        "ManagedBookmarks": [
            {"toplevel_name": "B0"},
            {"name": "Fake managed bookmark", "url": "https://example.invalid/managed"},
        ],
        "ExtensionSettings": {"*": {"installation_mode": "allowed"}},
    },
}
BASELINE = {"Chrome": (97, 0, 0), "Edge": (532, 0, 0), "Brave": (0, 0, 0), "Vivaldi": (31, 0, 0), "Firefox": (16, 0, 0)}


@dataclass
class PolicyState:
    protected_paths: dict[Path, str] = field(default_factory=dict)


class AuthorizationDenied(RuntimeError):
    pass


def _flush_preference_cache() -> None:
    """Drop cached managed preferences so a browser reads the plist on disk.

    cfprefsd keeps serving the previous value after a policy file is replaced,
    which makes a freshly installed policy look absent. The daemon restarts on
    demand, so flushing is safe to repeat.
    """
    subprocess.run(
        ["/usr/bin/killall", "cfprefsd"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
    )


PRIVILEGED_HELPER = Path("/usr/local/libexec/macbook-pro/install-managed-preference")


def _helper_paths() -> tuple[Path, Path]:
    """Ask the privileged helper where it stages from and installs to.

    Reading the paths back rather than restating them keeps one definition of
    them: the helper is rendered from the role's variables, so a change there
    cannot leave this script pointing somewhere else.
    """
    result = subprocess.run(
        ["/usr/bin/sudo", "-n", str(PRIVILEGED_HELPER), "--check"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise AuthorizationDenied(
            "privileged policy helper is unavailable; run `make browsers-authorize` once"
        )
    fields = dict(
        line.split("=", 1)
        for line in result.stdout.splitlines()
        if "=" in line and not line.startswith("managed-preference")
    )
    try:
        return Path(fields["stage"]), Path(fields["target"])
    except KeyError as error:
        raise RuntimeError("privileged policy helper did not report its paths") from error


def _helper(verb: str, domain: str) -> None:
    result = subprocess.run(
        ["/usr/bin/sudo", "-n", str(PRIVILEGED_HELPER), verb, domain],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"privileged policy helper refused {verb} ({result.returncode})")


class SystemPolicySession:
    """Temporarily swap managed policy for a fixture, then put it back exactly.

    Replaces a self-installing root helper that was launched through an
    AppleScript administrator dialog. That could not run unattended or in CI,
    and an unanswered prompt stalled the caller until something killed it. This
    drives the same managed helper the role uses for real installs: no root
    process outlives a single call, and restoring is just installing the saved
    bytes back.
    """

    def __init__(self, browsers: list[Browser]):
        # Only browsers with a proven system-policy contract are swapped;
        # Firefox uses an app-copy fixture and Vivaldi has no contract.
        self.browsers = [browser for browser in browsers if browser.domain in POLICY_PAYLOADS]
        self.stage: Path | None = None
        self.target: Path | None = None
        self.saved: dict[str, bytes | None] = {}
        self.saved_stage: dict[str, bytes | None] = {}

    def __enter__(self) -> SystemPolicySession:
        self.stage, self.target = _helper_paths()
        for browser in self.browsers:
            domain = browser.domain
            installed = self.target / f"{domain}.plist"
            staged = self.stage / f"{domain}.plist"
            # Remember both what is live and what the role had staged, so the
            # fixture leaves no trace in either place.
            self.saved[domain] = installed.read_bytes() if installed.is_file() else None
            self.saved_stage[domain] = staged.read_bytes() if staged.is_file() else None
            self._stage_and_install(domain, plistlib.dumps(POLICY_PAYLOADS[domain]))
        _flush_preference_cache()
        return self

    def __exit__(self, _error_type: object, _error: object, _traceback: object) -> None:
        failures = []
        for browser in self.browsers:
            domain = browser.domain
            try:
                self._restore(domain)
            except (OSError, RuntimeError) as error:
                failures.append(f"{domain}: {error}")
        _flush_preference_cache()
        if failures:
            raise RuntimeError(f"system policy restoration could not be proven ({'; '.join(failures)})")

    def _stage_and_install(self, domain: str, payload: bytes) -> None:
        assert self.stage is not None
        staged = self.stage / f"{domain}.plist"
        staged.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        staged.write_bytes(payload)
        staged.chmod(0o600)
        _helper("--install", domain)

    def _restore(self, domain: str) -> None:
        assert self.stage is not None and self.target is not None
        original = self.saved[domain]
        installed = self.target / f"{domain}.plist"
        if original is None:
            _helper("--remove", domain)
            if installed.exists():
                raise RuntimeError("policy was not removed")
        else:
            self._stage_and_install(domain, original)
            if not installed.is_file() or installed.read_bytes() != original:
                raise RuntimeError("policy was not restored byte-for-byte")
        # Put the role's own staged file back, so a later apply still sees the
        # state it rendered rather than a fixture.
        staged = self.stage / f"{domain}.plist"
        previous = self.saved_stage[domain]
        if previous is None:
            staged.unlink(missing_ok=True)
        else:
            staged.write_bytes(previous)
            staged.chmod(0o600)


def version(browser: Browser) -> str:
    """Read app metadata without launching a browser or touching a profile."""
    info = browser.app / "Contents" / "Info.plist"
    try:
        with info.open("rb") as stream:
            value = plistlib.load(stream).get("CFBundleShortVersionString", "unknown")
    except (OSError, plistlib.InvalidFileException):
        return "unknown"
    return str(value).strip().splitlines()[0][:80] or "unknown"


def _temporary_policy(browser: Browser, root: Path, state: PolicyState) -> None:
    """Install Firefox fixture or snapshot Chromium policy paths."""
    if browser.name == "Firefox":
        distribution = root / "Firefox.app" / "Contents" / "Resources" / "distribution"
        distribution.mkdir(parents=True, exist_ok=True)
        (distribution / "policies.json").write_text(
            json.dumps({"policies": {"Homepage": {"URL": "about:blank", "Locked": True}}}),
            encoding="utf-8",
        )
        return
    if browser.name == "Vivaldi":
        return

    # Root helper owns temporary system policy. Browser smoke only verifies those
    # exact paths remain byte-identical throughout each isolated launch.
    login = pwd.getpwuid(os.getuid()).pw_name
    candidates = (
        Path.home() / "Library" / "Managed Preferences" / f"{browser.domain}.plist",
        Path.home() / "Library" / "Managed Preferences" / login / f"{browser.domain}.plist",
        Path("/Library/Managed Preferences") / f"{browser.domain}.plist",
        Path("/Library/Managed Preferences") / login / f"{browser.domain}.plist",
    )
    state.protected_paths = {path: _path_state(path) for path in candidates}


def _restore_policy(state: PolicyState) -> None:
    for path, expected in state.protected_paths.items():
        if _path_state(path) != expected:
            raise RuntimeError("managed preference preservation check failed")


def _path_state(path: Path) -> str:
    if not path.exists():
        return "absent"
    if not path.is_file():
        raise RuntimeError("managed preference path is not a file")
    return _sha256(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _trash(path: Path, marker: str) -> None:
    """Move one temporary path to recoverable Trash and prove it left source.

    Moves the directory directly rather than shelling out to `trash`: the check
    below has to run after the move has completed, and one less thing needs to
    be on PATH in a launchd context.

    Retried because a browser that is still shutting down can recreate its
    profile directory just after the move, which failed this check
    intermittently. Each attempt keeps whatever it moved, so nothing is lost;
    at worst the Trash gains two entries for one profile.
    """
    print(f"{marker} {path.resolve()}")
    trash_dir = Path.home() / ".Trash"
    trash_dir.mkdir(mode=0o700, exist_ok=True)
    for _ in range(5):
        if not path.exists():
            return
        destination = trash_dir / f"{path.name}-{uuid.uuid4().hex}"
        try:
            shutil.move(str(path), str(destination))
        except OSError:
            time.sleep(0.2)
            continue
        if not path.exists():
            return
        time.sleep(0.2)
    raise RuntimeError("recoverable trash move could not be proven")


class DevToolsSocket:
    """Small dependency-free WebSocket client for local read-only CDP calls."""

    def __init__(self, websocket_url: str):
        parsed = urlsplit(websocket_url)
        if parsed.scheme != "ws" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise RuntimeError("unexpected DevTools endpoint")
        self.socket = socket.create_connection((parsed.hostname, parsed.port), timeout=3)
        self.socket.settimeout(3)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {parsed.path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{parsed.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.socket.sendall(request.encode("ascii"))
        response = self._receive_http_headers()
        if not response.startswith(b"HTTP/1.1 101"):
            self.socket.close()
            raise RuntimeError("DevTools WebSocket upgrade failed")
        self.next_id = 1

    def close(self) -> None:
        self.socket.close()

    def call(self, method: str, params: dict[str, object] | None = None) -> dict[str, object]:
        request_id = self.next_id
        self.next_id += 1
        payload: dict[str, object] = {"id": request_id, "method": method}
        if params:
            payload["params"] = params
        self._send_text(json.dumps(payload, separators=(",", ":")))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            message = json.loads(self._receive_text())
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError("DevTools command failed")
                result = message.get("result", {})
                return result if isinstance(result, dict) else {}
        raise TimeoutError("DevTools command timed out")

    def _receive_http_headers(self) -> bytes:
        response = bytearray()
        while b"\r\n\r\n" not in response:
            chunk = self.socket.recv(4096)
            if not chunk:
                break
            response.extend(chunk)
            if len(response) > 16384:
                raise RuntimeError("oversized DevTools handshake")
        return bytes(response)

    def _send_text(self, text: str) -> None:
        payload = text.encode("utf-8")
        mask = os.urandom(4)
        header = bytearray([0x81])
        if len(payload) < 126:
            header.append(0x80 | len(payload))
        elif len(payload) < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", len(payload)))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", len(payload)))
        header.extend(mask)
        masked = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        self.socket.sendall(bytes(header) + masked)

    def _receive_text(self) -> str:
        fragments = bytearray()
        while True:
            first, second = self._read_exact(2)
            final = bool(first & 0x80)
            opcode = first & 0x0F
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read_exact(8))[0]
            mask = self._read_exact(4) if second & 0x80 else b""
            payload = self._read_exact(length)
            if mask:
                payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
            if opcode == 0x9:
                continue
            if opcode == 0x8:
                raise RuntimeError("DevTools WebSocket closed")
            if opcode in {0x0, 0x1}:
                fragments.extend(payload)
                if final:
                    return fragments.decode("utf-8")

    def _read_exact(self, length: int) -> bytes:
        data = bytearray()
        while len(data) < length:
            chunk = self.socket.recv(length - len(data))
            if not chunk:
                raise RuntimeError("unexpected DevTools socket close")
            data.extend(chunk)
        return bytes(data)


def _devtools_target(profile: Path, process: subprocess.Popen[bytes]) -> str:
    active_port = profile / "DevToolsActivePort"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("browser exited before DevTools became ready")
        if active_port.is_file():
            lines = active_port.read_text(encoding="utf-8").splitlines()
            if lines and lines[0].isdigit():
                port = int(lines[0])
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=3) as response:
                    targets = json.load(response)
                for target in targets:
                    if target.get("type") == "page":
                        endpoint = target.get("webSocketDebuggerUrl")
                        if isinstance(endpoint, str):
                            return endpoint
        time.sleep(0.25)
    raise TimeoutError("DevTools target did not become ready")


def _inspect_chromium_policy(
    profile: Path,
    page: str,
    process: subprocess.Popen[bytes],
    expected_keys: tuple[str, str],
) -> tuple[bool, bool, bool, str, str]:
    endpoint = _devtools_target(profile, process)
    client = DevToolsSocket(endpoint)
    page_aliases = [page.rstrip("/").lower()]
    if page == "brave://policy":
        page_aliases.append("chrome://policy")
    expected_pages = json.dumps(page_aliases)
    expected_policy_keys = json.dumps(expected_keys)
    expression = f"""
        (() => {{
          const expectedPages = {expected_pages};
          const expectedKeys = {expected_policy_keys};
          const rows = [];
          const app = document.querySelector('policy-app');
          if (app && app.shadowRoot) {{
            for (const table of app.shadowRoot.querySelectorAll('policy-table')) {{
              if (table.shadowRoot) rows.push(...table.shadowRoot.querySelectorAll('policy-row'));
            }}
          }}
          const edgeTable = document.querySelector('#chrome-table');
          const headers = edgeTable ? [...edgeTable.querySelectorAll('[role="columnheader"]')]
            .map(cell => cell.textContent.trim().toLowerCase()) : [];
          const edgeRows = edgeTable ? [...edgeTable.querySelectorAll('[role="row"]')] : [];
          const edgeCell = (row, name) => {{
            const index = headers.indexOf(name);
            const cells = [...row.querySelectorAll('[role="rowheader"], [role="cell"]')];
            return index >= 0 && cells[index] ? cells[index].textContent.trim() : '';
          }};
          const matching = expectedKeys.map(name => edgeTable
            ? edgeRows.find(row => edgeCell(row, 'policy name') === name)
            : rows.find(row => row.policy && row.policy.name === name));
          const statusOf = row => {{
            if (!row) return '';
            if (edgeTable) return edgeCell(row, 'status').toLowerCase();
            const cell = row.shadowRoot &&
              row.shadowRoot.querySelector('#status, .status, [data-field="status"]');
            return String(row.policy.status || (cell && cell.textContent) || '').trim().toLowerCase();
          }};
          const statuses = matching.map(row => {{
            const status = statusOf(row);
            return ['ok', 'valid', 'success'].includes(status) ? status : (status ? 'other' : 'missing');
          }});
          const valid = matching.every(row => {{
            if (!row || !['ok', 'valid', 'success'].includes(statusOf(row))) return false;
            if (edgeTable) return true;
            return row.policy.value !== undefined && !row.policy.error && !row.policy.ignored &&
              !(Array.isArray(row.policy.errors) && row.policy.errors.length);
          }});
          const levels = [...new Set(matching.filter(Boolean).map(row => edgeTable
            ? edgeCell(row, 'level').toLowerCase() : row.policy.level || ''))];
          const currentPage = location.href.replace(/[/]$/, '').toLowerCase();
          return {{
            page: expectedPages.includes(currentPage),
            pageKind: expectedPages.indexOf(currentPage),
            keys: matching.every(Boolean),
            matched: matching.filter(Boolean).length,
            totalRows: edgeTable ? edgeRows.length : rows.length,
            status: valid,
            statuses,
            level: levels.length === 1 ? levels[0] : '',
          }};
        }})()
    """
    try:
        client.call("Runtime.enable")
        client.call("Page.enable")
        client.call("Page.navigate", {"url": page})
        deadline = time.monotonic() + 30
        last = {"page": False, "keys": False, "status": False}
        while time.monotonic() < deadline:
            response = client.call(
                "Runtime.evaluate",
                {"expression": expression, "returnByValue": True},
            )
            remote = response.get("result", {})
            if isinstance(remote, dict):
                value = remote.get("value", {})
                if isinstance(value, dict):
                    last = value
            if last.get("page") and last.get("keys") and last.get("status"):
                break
            time.sleep(0.5)
        level = last.get("level", "")
        statuses = last.get("statuses", [])
        safe_statuses = statuses if isinstance(statuses, list) else []
        diagnostic = (
            f"page-kind-{last.get('pageKind', -1)}-rows-{last.get('matched', 0)}of{len(expected_keys)}-"
            f"total-{last.get('totalRows', 0)}-"
            f"statuses-{','.join(str(value) for value in safe_statuses)}"
        )
        return (
            bool(last.get("page")),
            bool(last.get("keys")),
            bool(last.get("status")),
            level if isinstance(level, str) else "",
            diagnostic,
        )
    finally:
        client.close()


def _stop_launched_process(process: subprocess.Popen[bytes]) -> None:
    """Stop only process group created by this script, never user browser sessions."""
    if process.poll() is not None:
        return
    try:
        process.wait(timeout=1)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        process_group = os.getpgid(process.pid)
    except ProcessLookupError:
        process.wait(timeout=1)
        return
    if process_group != process.pid:
        raise RuntimeError("launched browser process-group identity changed")
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def isolated_smoke(browser: Browser) -> tuple[str, str, str]:
    temp_dir = Path(tempfile.mkdtemp(prefix=f"browser-capability-{browser.name.lower()}-"))
    print(f"TEMP_PROFILE {temp_dir}")
    state = PolicyState()
    process: subprocess.Popen[bytes] | None = None
    try:
        if browser.name == "Firefox":
            app_copy = temp_dir / "Firefox.app"
            # Strip extended attributes: a freshly installed bundle carries
            # provenance metadata that makes macOS kill a copy of it outright.
            subprocess.run(
                ["ditto", "--noextattr", "--norsrc", str(browser.app), str(app_copy)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            executable = app_copy / "Contents" / "MacOS" / "firefox"
        else:
            executable = browser.executable
        _temporary_policy(browser, temp_dir, state)
        if browser.name == "Firefox":
            page_screenshot = temp_dir / "policy.png"
            command = [
                str(executable),
                "-headless",
                "-no-remote",
                "-profile",
                str(temp_dir / "profile"),
                "-screenshot",
                str(page_screenshot),
                browser.policy_page,
            ]
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and not page_screenshot.is_file():
                if process.poll() is not None:
                    break
                time.sleep(0.25)
            page_seen = page_screenshot.is_file()
            key_seen = False
            if page_seen:
                ocr = subprocess.run(
                    ["tesseract", str(page_screenshot), "stdout"],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                key_seen = "homepage" in ocr.stdout.lower()
            return (
                "observed" if page_seen else "not-observed",
                "pass" if page_seen and key_seen else "failed",
                "temp-app-copy-key-observed" if key_seen else "temp-app-copy-key-missing",
            )

        profile = temp_dir / "profile"
        cfhome = temp_dir / "cfhome"
        cfhome.mkdir(parents=True, exist_ok=True)
        command = [
            str(executable),
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
            "--lang=en-US",
            f"--user-data-dir={profile}",
            browser.policy_page,
        ]
        environment = os.environ.copy()
        environment["HOME"] = str(cfhome)
        environment["CFFIXED_USER_HOME"] = str(cfhome)
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=environment,
        )
        if browser.name == "Vivaldi":
            try:
                _devtools_target(profile, process)
                return ("observed", "pass", "unsupported-audit-launch-observed")
            except (OSError, RuntimeError, TimeoutError, ValueError):
                return ("not-observed", "pass", "unsupported-audit-launch-unavailable")
        page_seen, key_seen, status_ok, level, diagnostic = _inspect_chromium_policy(
            profile,
            browser.policy_page,
            process,
            (browser.bookmark_policy, browser.extension_policy),
        )
        accepted = page_seen and key_seen and status_ok and level in {"mandatory", "recommended"}
        return (
            "observed" if page_seen else "not-observed",
            "pass" if accepted else "failed",
            f"required-keys-status-ok-{level}" if accepted else diagnostic,
        )
    except (
        OSError,
        RuntimeError,
        TimeoutError,
        ValueError,
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
    ) as error:
        safe_errors = {
            "browser exited before DevTools became ready": "browser-exited-before-devtools",
            "DevTools target did not become ready": "devtools-target-missing",
            "DevTools WebSocket upgrade failed": "devtools-websocket-unavailable",
            "DevTools command failed": "devtools-command-failed",
            "DevTools command timed out": "devtools-command-timeout",
            "DevTools WebSocket closed": "devtools-websocket-closed",
            "unexpected DevTools socket close": "devtools-socket-closed",
            "timed out": "timeout",
        }
        return ("not-observed", "failed", safe_errors.get(str(error), "launch-or-inspection-error"))
    finally:
        if process is not None:
            _stop_launched_process(process)
        _restore_policy(state)
        # Print path before removal, then use recoverable Trash. Never use rm.
        if temp_dir.exists():
            _trash(temp_dir, "TRASH_PROFILE")


def _local_verdict(browser: Browser, evidence: str) -> str:
    """Summarise whether local policy acceptance was proven for one browser."""
    if evidence.startswith("required-keys-status-ok-") or evidence == "temp-app-copy-key-observed":
        return "accepted"
    return "unsupported" if browser.name == "Vivaldi" else "not-proven"


def discover() -> int:
    installed = [browser for browser in BROWSER_APPS if browser.app.is_dir()]
    if not installed:
        print("browser-capability: no supported installed browsers")
        return 0
    privileged = [browser for browser in installed if browser.name in {"Chrome", "Edge", "Brave"}]
    unprivileged = [browser for browser in installed if browser not in privileged]
    failures = 0

    def run(browser: Browser) -> None:
        nonlocal failures
        smoke, result, evidence = isolated_smoke(browser)
        if result != "pass" and browser.name != "Vivaldi":
            failures += 1
        bookmarks, enabled, components = BASELINE[browser.name]
        print(
            f"{browser.name}: version={version(browser)} policy_page={smoke} smoke={result} evidence={evidence} "
            f"local={_local_verdict(browser, evidence)} "
            f"bookmark_policy={browser.bookmark_policy} "
            f"extension_policy={browser.extension_policy} baseline_bookmarks={bookmarks} baseline_enabled={enabled} "
            f"baseline_components={components} baseline_user_candidates=0 snapshot_hash=not-collected"
        )

    try:
        with SystemPolicySession(privileged):
            for browser in privileged:
                run(browser)
    except AuthorizationDenied:
        print("system-policy: authorization=denied-or-timeout state=unchanged-or-helper-restored")
        return 2
    except RuntimeError:
        print("system-policy: restoration=unproven recovery=preserved")
        return 3
    for browser in unprivileged:
        run(browser)
    return 1 if failures else 0


def check_report(path: Path) -> int:
    if not path.is_file():
        print(f"report check failed: missing report {path}")
        return 1
    text = path.read_text(encoding="utf-8")
    required = (
        "# Browser capability spike",
        "## Capability matrix",
        "## Sanitized inventory",
        "## Duplicate experiment",
    )
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
