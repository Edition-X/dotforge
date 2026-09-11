#!/usr/bin/env python3
"""Take validated read-only browser snapshots and report counts only."""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import uuid
from pathlib import Path

CHROMIUM = ("chrome", "edge", "brave", "vivaldi")
FIREFOX_PROFILE_NAMES = ("default-release", "default")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            value.update(chunk)
    return value.hexdigest()


def stable_json_snapshot(source: Path, destination: Path, attempts: int = 3) -> dict[str, object]:
    if source.is_symlink() or not source.is_file():
        raise RuntimeError("Chromium snapshot source is not a regular file")
    for _ in range(attempts):
        before = source.stat()
        before_hash = digest(source)
        shutil.copyfile(source, destination)
        os.chmod(destination, 0o600)
        after = source.stat()
        if (before.st_size, before.st_mtime_ns, before_hash) != (
            after.st_size,
            after.st_mtime_ns,
            digest(source),
        ):
            time.sleep(0.05)
            continue
        with destination.open(encoding="utf-8") as stream:
            data = json.load(stream)
        if digest(destination) != before_hash or not isinstance(data, dict):
            raise RuntimeError("Chromium snapshot validation failed")
        return data
    raise RuntimeError("Chromium source changed during bounded snapshot retries")


def firefox_snapshot(source: Path, destination: Path, attempts: int = 5) -> int:
    if source.is_symlink() or not source.is_file():
        raise RuntimeError("Firefox snapshot source is not a regular file")
    copied_source: Path | None = None
    for _ in range(attempts):
        try:
            before = firefox_source_state(source)
            staging = Path(tempfile.mkdtemp(prefix="firefox-source-", dir=destination.parent))
            for suffix, _, _, _ in before:
                candidate = Path(str(source) + suffix)
                target = staging / f"{source.name}{suffix}"
                shutil.copyfile(candidate, target)
                os.chmod(target, 0o600)
            after = firefox_source_state(source)
        except FileNotFoundError:
            time.sleep(0.05)
            continue
        if after == before:
            copied_source = staging / source.name
            break
        time.sleep(0.05)
    if copied_source is None:
        raise RuntimeError("Firefox source changed during bounded snapshot retries")

    with sqlite3.connect(copied_source) as stable, sqlite3.connect(destination) as snapshot:
        if stable.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise RuntimeError("Firefox staged source integrity check failed")
        stable.backup(snapshot)
    os.chmod(destination, 0o600)
    with sqlite3.connect(destination.resolve().as_uri() + "?mode=ro", uri=True) as snapshot:
        if snapshot.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise RuntimeError("Firefox snapshot integrity check failed")
        return int(
            snapshot.execute(
                "SELECT count(*) FROM moz_bookmarks b JOIN moz_places p ON p.id = b.fk WHERE p.url IS NOT NULL"
            ).fetchone()[0]
        )


def firefox_source_state(source: Path) -> tuple[tuple[str, int, int, str], ...]:
    state = []
    for suffix in ("", "-wal"):
        candidate = Path(str(source) + suffix)
        if not candidate.exists():
            continue
        if candidate.is_symlink() or not candidate.is_file():
            raise RuntimeError("Firefox bookmark source is not a regular file")
        metadata = candidate.stat()
        state.append((suffix, metadata.st_size, metadata.st_mtime_ns, digest(candidate)))
    return tuple(state)


def firefox_profiles(profile_root: Path) -> dict[str, Path]:
    configuration_path = profile_root / "profiles.ini"
    if configuration_path.is_symlink() or not configuration_path.is_file():
        raise RuntimeError("Firefox profiles configuration is unavailable")
    configuration = configparser.ConfigParser(interpolation=None)
    configuration.read(configuration_path, encoding="utf-8")
    selected: dict[str, Path] = {}
    root = profile_root.resolve()
    for section in configuration.sections():
        if not section.startswith("Profile"):
            continue
        name = configuration.get(section, "Name", fallback="")
        if name not in FIREFOX_PROFILE_NAMES:
            continue
        if name in selected:
            raise RuntimeError("Firefox profile name is duplicated")
        raw_path = configuration.get(section, "Path", fallback="")
        if not raw_path or not configuration.getboolean(section, "IsRelative", fallback=True):
            raise RuntimeError("Firefox managed snapshot profile path is unsupported")
        profile = profile_root / raw_path
        if profile.is_symlink() or not profile.is_dir() or not profile.resolve().is_relative_to(root):
            raise RuntimeError("Firefox managed snapshot profile is unsafe")
        selected[name] = profile
    if set(selected) != set(FIREFOX_PROFILE_NAMES):
        raise RuntimeError("Firefox expected profiles are unavailable")
    return selected


def snapshot_firefox_profiles(profile_root: Path, work: Path) -> tuple[int, int]:
    work.mkdir(mode=0o700)
    profiles = firefox_profiles(profile_root)
    total = 0
    for name in FIREFOX_PROFILE_NAMES:
        source = profiles[name] / "places.sqlite"
        if not source.exists():
            if name != "default":
                raise RuntimeError("Firefox active profile bookmark database is unavailable")
            continue
        count = firefox_snapshot(source, work / f"{name}.sqlite")
        if name == "default" and count != 0:
            raise RuntimeError("Firefox default profile is not empty")
        total += count
    return len(profiles), total


def chromium_count(node: object) -> int:
    if isinstance(node, dict):
        return (1 if node.get("type") == "url" else 0) + sum(chromium_count(value) for value in node.values())
    if isinstance(node, list):
        return sum(chromium_count(value) for value in node)
    return 0


def materialize_firefox_fixture(fixtures: Path, work: Path) -> tuple[Path, sqlite3.Connection]:
    database = work / "places.sqlite"
    connection = sqlite3.connect(database)
    connection.executescript((fixtures / "firefox" / "places.sql").read_text(encoding="utf-8"))
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("INSERT INTO moz_places(url) VALUES (?)", ("https://fixture.example.invalid/wal",))
    place = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.execute("INSERT INTO moz_bookmarks(fk, title) VALUES (?, ?)", (place, "WAL fixture"))
    connection.commit()
    return database, connection


def trash(path: Path) -> None:
    """Move a temporary snapshot to recoverable Trash and prove it left source.

    Moves the directory directly rather than shelling out to `trash`: the
    external tool is absent on a CI runner, and the check below needs the move
    to have completed when it runs. Retried because a process still exiting can
    recreate the directory just after the move.
    """
    print(f"TRASH_SNAPSHOT {path.resolve()}")
    trash_dir = Path.home() / ".Trash"
    trash_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
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
    raise RuntimeError("snapshot cleanup could not be proven")


def check_fixtures(fixtures: Path) -> int:
    work = Path(tempfile.mkdtemp(prefix="browser-snapshot-fixtures-"))
    counts: dict[str, int] = {}
    firefox_connection: sqlite3.Connection | None = None
    try:
        for browser in CHROMIUM:
            source = fixtures / browser / "Default" / "Bookmarks"
            data = stable_json_snapshot(source, work / f"{browser}-Bookmarks")
            counts[browser] = chromium_count(data.get("roots", {}))
        firefox_database, firefox_connection = materialize_firefox_fixture(fixtures, work)
        counts["firefox"] = firefox_snapshot(firefox_database, work / "firefox-snapshot.sqlite")
        if any(count != 2 for count in counts.values()):
            raise RuntimeError("fixture snapshot count mismatch")
        print("browser snapshot: pass browsers=5 records=10 wal=verified stable-hash=verified")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error, RuntimeError) as error:
        print(f"browser snapshot: failed ({type(error).__name__}: {error})")
        return 1
    finally:
        if firefox_connection is not None:
            firefox_connection.close()
        if work.exists():
            trash(work)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if not args.fixtures or not args.check_only:
        parser.error("snapshot command requires --fixtures PATH --check-only")
    return check_fixtures(args.fixtures)


if __name__ == "__main__":
    sys.exit(main())
