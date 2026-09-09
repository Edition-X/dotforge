#!/usr/bin/env python3
"""Take validated read-only browser snapshots and report counts only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

CHROMIUM = ("chrome", "edge", "brave", "vivaldi")


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


def firefox_snapshot(source: Path, destination: Path) -> int:
    if source.is_symlink() or not source.is_file():
        raise RuntimeError("Firefox snapshot source is not a regular file")
    source_uri = source.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as live, sqlite3.connect(destination) as snapshot:
        live.backup(snapshot)
    os.chmod(destination, 0o600)
    with sqlite3.connect(destination.resolve().as_uri() + "?mode=ro", uri=True) as snapshot:
        if snapshot.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise RuntimeError("Firefox snapshot integrity check failed")
        return int(
            snapshot.execute(
                "SELECT count(*) FROM moz_bookmarks b JOIN moz_places p ON p.id = b.fk WHERE p.url IS NOT NULL"
            ).fetchone()[0]
        )


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
    print(f"TRASH_SNAPSHOT {path.resolve()}")
    command = shutil.which("trash")
    if command:
        subprocess.run([command, str(path)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        destination = Path.home() / ".Trash" / f"{path.name}-{uuid.uuid4().hex}"
        shutil.move(str(path), str(destination))
    if path.exists():
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
