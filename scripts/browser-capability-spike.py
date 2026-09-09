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
import shlex
import signal
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


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
ROOT_POLICY_HELPER = r'''#!/usr/bin/python3
import hashlib
import json
import os
import plistlib
import pwd
import signal
import stat
import sys
import tempfile
import time
from pathlib import Path

ALLOWED_DOMAINS = ("com.google.Chrome", "com.microsoft.Edge", "com.brave.Browser")
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


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            value.update(chunk)
    return value.hexdigest()


def atomic_policy(path, payload):
    descriptor, temporary_name = tempfile.mkstemp(prefix=".b0-policy-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            plistlib.dump(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.chown(temporary, 0, 0)
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            os.replace(temporary, recovery / (temporary.name + ".unused"))


def write_marker(path, value, uid, gid):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w", encoding="ascii") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())
    os.chown(path, uid, gid)


def move_created(path, destination):
    if path.is_symlink() or not path.exists():
        raise RuntimeError("created-path-state-unexpected")
    os.replace(path, destination)
    if path.exists():
        raise RuntimeError("created-path-removal-unproven")


def copy_exact(source, destination, mode=0o600):
    with source.open("rb") as input_stream, destination.open("xb") as output_stream:
        while True:
            chunk = input_stream.read(65536)
            if not chunk:
                break
            output_stream.write(chunk)
        output_stream.flush()
        os.fsync(output_stream.fileno())
    os.chown(destination, 0, 0)
    os.chmod(destination, mode)


def restore_entry(entry):
    path = Path(entry["path"])
    if not entry["existed"]:
        if path.exists() or path.is_symlink():
            move_created(path, recovery / (str(entry["index"]) + ".created-policy"))
        return
    backup = Path(entry["backup"])
    descriptor, temporary_name = tempfile.mkstemp(prefix=".browser-policy-restore-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output_stream, backup.open("rb") as input_stream:
            while True:
                chunk = input_stream.read(65536)
                if not chunk:
                    break
                output_stream.write(chunk)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        os.chown(temporary, entry["uid"], entry["gid"])
        os.chmod(temporary, entry["mode"])
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            os.replace(temporary, recovery / (temporary.name + ".failed-restore"))
    metadata = path.stat()
    if digest(path) != entry["hash"]:
        raise RuntimeError("restore-hash-mismatch")
    if (metadata.st_uid, metadata.st_gid, stat.S_IMODE(metadata.st_mode)) != (
        entry["uid"], entry["gid"], entry["mode"]
    ):
        raise RuntimeError("restore-metadata-mismatch")


def stop(_signum, _frame):
    raise KeyboardInterrupt


request_arg = Path(sys.argv[1])
request_fd = os.open(request_arg, os.O_RDONLY | os.O_NOFOLLOW)
request_metadata = os.fstat(request_fd)
with os.fdopen(request_fd, "r", encoding="utf-8") as request_stream:
    request = json.load(request_stream)
uid = int(request["uid"])
gid = int(request["gid"])
account = pwd.getpwuid(uid)
if request_metadata.st_uid != uid or stat.S_IMODE(request_metadata.st_mode) != 0o400:
    raise SystemExit(20)
if account.pw_name != request["login"] or account.pw_gid != gid:
    raise SystemExit(21)
request_path = request_arg.resolve()
work = Path(request["work"]).resolve()
started = work / "started"
ready = work / "ready"
release = work / "release"
result = work / "result.json"
recovery = Path(request["recovery"]).resolve()
managed = Path("/Library/Managed Preferences")
user_managed = managed / request["login"]
paths = [
    user_managed / (domain + ".plist")
    for domain in request["domains"]
]
work_metadata = work.lstat()
trash = Path(account.pw_dir) / ".Trash"
if os.geteuid() != 0 or request_path.parent != work or work.is_symlink():
    raise SystemExit(22)
if work_metadata.st_uid != uid or stat.S_IMODE(work_metadata.st_mode) != 0o700:
    raise SystemExit(23)
requested_domains = tuple(request["domains"])
if not requested_domains or requested_domains != tuple(
    domain for domain in ALLOWED_DOMAINS if domain in requested_domains
):
    raise SystemExit(24)
if managed != Path(request["managed"]) or user_managed != Path(request["user_managed"]):
    raise SystemExit(25)
if trash.is_symlink() or not trash.is_dir() or trash.stat().st_uid != uid:
    raise SystemExit(26)
if recovery.parent != trash or not recovery.name.startswith("browser-policy-b0-recovery-"):
    raise SystemExit(27)
for candidate in (managed, user_managed):
    if candidate.is_symlink() or (candidate.exists() and (not candidate.is_dir() or candidate.stat().st_uid != 0)):
        raise SystemExit(28)
for candidate in paths:
    if candidate.is_symlink() or (candidate.exists() and (not candidate.is_file() or candidate.stat().st_uid != 0)):
        raise SystemExit(29)
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
recovery.mkdir(mode=0o700)
os.chown(recovery, 0, 0)
write_marker(started, "started", uid, gid)
entries = []
managed_created = False
user_managed_created = False
try:
    if not managed.exists():
        managed.mkdir(mode=0o755)
        managed_created = True
    if not user_managed.exists():
        user_managed.mkdir(mode=0o755)
        user_managed_created = True
    for index, (domain, path) in enumerate(zip(requested_domains, paths)):
        entry = {"index": index, "path": str(path), "existed": path.exists()}
        if entry["existed"]:
            metadata = path.stat()
            backup = recovery / (str(index) + ".original")
            entry.update(
                uid=metadata.st_uid,
                gid=metadata.st_gid,
                mode=stat.S_IMODE(metadata.st_mode),
                hash=digest(path),
                backup=str(backup),
            )
            copy_exact(path, backup)
            if digest(backup) != entry["hash"]:
                raise RuntimeError("backup-hash-mismatch")
        entries.append(entry)
        atomic_policy(path, POLICY_PAYLOADS[domain])
    write_marker(ready, "ready", uid, gid)
    deadline = time.monotonic() + 180
    while not release.exists() and time.monotonic() < deadline:
        time.sleep(0.2)
    if not release.exists():
        raise RuntimeError("release-timeout")
finally:
    restore_error = None
    for entry in reversed(entries):
        try:
            restore_entry(entry)
        except Exception as error:
            restore_error = type(error).__name__
    try:
        if user_managed_created and user_managed.exists():
            if next(user_managed.iterdir(), None) is not None:
                raise RuntimeError("managed-user-directory-not-empty")
            move_created(user_managed, recovery / "created-managed-user-directory")
        if managed_created and managed.exists():
            if next(managed.iterdir(), None) is not None:
                raise RuntimeError("managed-directory-not-empty")
            move_created(managed, recovery / "created-managed-directory")
    except Exception as error:
        restore_error = type(error).__name__
    payload = {"status": "restored" if restore_error is None else "restore-failed"}
    write_marker(result, json.dumps(payload), uid, gid)
    if restore_error is not None:
        raise SystemExit(30)
'''


@dataclass
class PolicyState:
    protected_paths: dict[Path, str] = field(default_factory=dict)


class AuthorizationDenied(RuntimeError):
    pass


def _apple_script_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


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


class SystemPolicySession:
    """One-dialog root helper with byte-exact restore for allowlisted policy files."""

    def __init__(self, browsers: list[Browser]):
        self.browsers = browsers
        self.work: Path | None = None
        self.release: Path | None = None
        self.result: Path | None = None
        self.recovery: Path | None = None
        self.process: subprocess.Popen[str] | None = None
        self.started: Path | None = None

    def __enter__(self) -> SystemPolicySession:
        login = pwd.getpwuid(os.getuid()).pw_name
        trash = Path.home() / ".Trash"
        if not trash.is_dir():
            raise RuntimeError("user Trash directory unavailable")
        self.work = Path(tempfile.mkdtemp(prefix="browser-system-policy-helper-"))
        self.release = self.work / "release"
        self.result = self.work / "result.json"
        self.started = self.work / "started"
        self.recovery = trash / f"browser-policy-b0-recovery-{uuid.uuid4().hex}"
        helper = self.work / "root-policy-helper.py"
        request = self.work / "request.json"
        helper.write_text(textwrap.dedent(ROOT_POLICY_HELPER), encoding="utf-8")
        helper.chmod(0o500)
        request.write_text(
            json.dumps(
                {
                    "work": str(self.work.resolve()),
                    "recovery": str(self.recovery.resolve()),
                    "managed": "/Library/Managed Preferences",
                    "user_managed": f"/Library/Managed Preferences/{login}",
                    "login": login,
                    "domains": [browser.domain for browser in self.browsers],
                    "uid": os.getuid(),
                    "gid": os.getgid(),
                },
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        request.chmod(0o400)
        helper_hash = _sha256(helper)
        bootstrap = (
            "import hashlib,os,stat,sys;"
            "p=sys.argv[1];fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW);s=os.fstat(fd);"
            "b=b'';"
            "\nwhile True:\n c=os.read(fd,65536)\n if not c: break\n b+=c\n"
            "os.close(fd);"
            "assert s.st_uid==int(sys.argv[4]) and stat.S_IMODE(s.st_mode)==0o500;"
            "assert hashlib.sha256(b).hexdigest()==sys.argv[3];"
            "sys.argv=[p,sys.argv[2]];exec(compile(b,p,'exec'))"
        )
        command = " ".join(
            (
                shlex.quote("/usr/bin/python3"),
                "-c",
                shlex.quote(bootstrap),
                shlex.quote(str(helper.resolve())),
                shlex.quote(str(request.resolve())),
                shlex.quote(helper_hash),
                shlex.quote(str(os.getuid())),
            )
        )
        apple_script = f"do shell script {_apple_script_string(command)} with administrator privileges"
        self.process = subprocess.Popen(
            ["/usr/bin/osascript", "-e", apple_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        ready = self.work / "ready"
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if ready.is_file():
                _flush_preference_cache()
                return self
            if self.process.poll() is not None:
                if self.started.is_file():
                    self._require_restored()
                    raise AuthorizationDenied("system policy helper declined before install")
                self._cleanup_work()
                raise AuthorizationDenied("administrator authorization denied")
            time.sleep(0.25)
        # Release may be created before authorization. If approval arrives later,
        # helper installs then immediately restores without waiting for this process.
        self.release.touch(mode=0o600)
        if self.started.is_file():
            self._wait_for_restoration(timeout=210)
        raise AuthorizationDenied("administrator authorization timed out")

    def __exit__(self, _error_type: object, _error: object, _traceback: object) -> None:
        if self.release is None or self.result is None or self.process is None:
            raise RuntimeError("system policy helper state incomplete")
        self.release.touch(mode=0o600)
        self._wait_for_restoration(timeout=210)
        _flush_preference_cache()

    def _wait_for_restoration(self, timeout: int) -> None:
        if self.process is None:
            raise RuntimeError("system policy helper process missing")
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("system policy helper restoration timed out") from error
        self._require_restored()

    def _require_restored(self) -> None:
        if self.result is None or self.process is None:
            raise RuntimeError("system policy helper result missing")
        restored = False
        if self.result.is_file():
            payload = json.loads(self.result.read_text(encoding="ascii"))
            restored = payload.get("status") == "restored"
        recovery = self.recovery
        if recovery is not None:
            print(f"SYSTEM_POLICY_RECOVERY {recovery.resolve()}")
        if self.process.returncode != 0 or not restored:
            raise RuntimeError("system policy restoration could not be proven")
        self._cleanup_work()

    def _cleanup_work(self) -> None:
        if self.work is not None and self.work.exists():
            _trash(self.work, "TRASH_POLICY_HELPER")


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
    """Move one temporary path to recoverable Trash and prove it left source."""
    print(f"{marker} {path.resolve()}")
    trash = shutil.which("trash")
    if trash:
        subprocess.run(
            [trash, str(path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        trash_dir = Path.home() / ".Trash"
        trash_dir.mkdir(mode=0o700, exist_ok=True)
        destination = trash_dir / f"{path.name}-{uuid.uuid4().hex}"
        shutil.move(str(path), str(destination))
    if path.exists():
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
    except (OSError, RuntimeError, TimeoutError, ValueError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as error:
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


def discover() -> int:
    installed = [browser for browser in BROWSERS if browser.app.is_dir()]
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
            f"local={'accepted' if evidence.startswith('required-keys-status-ok-') or evidence == 'temp-app-copy-key-observed' else ('unsupported' if browser.name == 'Vivaldi' else 'not-proven')} "
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
