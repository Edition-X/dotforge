#!/usr/bin/env python3
"""Store rejected browser records locally without printing their contents."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


class Quarantine:
    def __init__(self, path: Path):
        self.path = path
        self.records: list[dict[str, object]] = []

    def add(self, browser: str, reason: str, record: object) -> None:
        self.records.append({"browser": browser, "reason": reason, "record": record})

    def commit(self) -> int:
        if not self.records:
            return 0
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        existing: list[object] = []
        if self.path.exists():
            if self.path.is_symlink() or not self.path.is_file():
                raise RuntimeError("browser quarantine path is unsafe")
            existing = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                raise RuntimeError("browser quarantine is invalid")
        seen = {json.dumps(record, sort_keys=True, separators=(",", ":")) for record in existing}
        additions = []
        for record in self.records:
            fingerprint = json.dumps(record, sort_keys=True, separators=(",", ":"))
            if fingerprint not in seen:
                seen.add(fingerprint)
                additions.append(record)
        if not additions:
            return 0
        descriptor, temporary = tempfile.mkstemp(prefix=".quarantine-", dir=self.path.parent)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump([*existing, *additions], stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.path)
        if self.path.stat().st_mode & 0o777 != 0o600:
            raise RuntimeError("browser quarantine mode is unsafe")
        return len(additions)
