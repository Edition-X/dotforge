#!/usr/bin/env python3
"""Offline coverage for the claude-edit-guard PreToolUse hook. No model calls."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parent.parent / "host_files/localhost/bin/claude-edit-guard"


def run_hook(state: Path, cwd: str, tool: str, path: str, session: str = "s1") -> dict | None:
    payload = {"session_id": session, "cwd": cwd, "tool_name": tool, "tool_input": {"file_path": path}}
    env = {**os.environ, "CLAUDE_EDIT_GUARD_STATE": str(state)}
    out = subprocess.run([str(GUARD)], input=json.dumps(payload), capture_output=True, text=True, env=env, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout) if out.stdout.strip() else None


def run_cli(state: Path, cwd: str, command: str) -> str:
    env = {**os.environ, "CLAUDE_EDIT_GUARD_STATE": str(state)}
    out = subprocess.run([str(GUARD), command], capture_output=True, text=True, env=env, cwd=cwd, check=False)
    assert out.returncode == 0, out.stderr
    return out.stdout


class EditGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "state"
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def src(self, name: str) -> str:
        return str(self.repo / "src" / name)

    def test_docs_and_scratch_are_always_free(self):
        for path in (str(self.repo / "README.md"), str(self.repo / "docs/plan.html"), "/private/tmp/claude-1/x.py"):
            self.assertIsNone(run_hook(self.state, str(self.repo), "Edit", path))

    def test_budget_allows_three_files_then_denies_a_fourth(self):
        for name in ("a.py", "b.py", "c.py"):
            self.assertIsNone(run_hook(self.state, str(self.repo), "Write", self.src(name)))
        # Re-editing a counted file stays free.
        self.assertIsNone(run_hook(self.state, str(self.repo), "Edit", self.src("a.py")))
        decision = run_hook(self.state, str(self.repo), "Edit", self.src("d.py"))
        self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("build", decision["hookSpecificOutput"]["permissionDecisionReason"])

    def test_budget_is_per_session(self):
        for name in ("a.py", "b.py", "c.py"):
            run_hook(self.state, str(self.repo), "Write", self.src(name), session="one")
        self.assertIsNone(run_hook(self.state, str(self.repo), "Write", self.src("d.py"), session="two"))

    def test_direct_mode_lifts_the_guard_for_that_repo_only(self):
        for name in ("a.py", "b.py", "c.py"):
            run_hook(self.state, str(self.repo), "Write", self.src(name))
        self.assertIn("OFF", run_cli(self.state, str(self.repo), "off"))
        self.assertIsNone(run_hook(self.state, str(self.repo), "Edit", self.src("d.py")))
        other = Path(self.tmp.name) / "other"
        other.mkdir()
        for name in ("a.py", "b.py", "c.py"):
            run_hook(self.state, str(other), "Write", str(other / name), session="o")
        self.assertIsNotNone(run_hook(self.state, str(other), "Write", str(other / "d.py"), session="o"))
        self.assertIn("ON", run_cli(self.state, str(self.repo), "on"))
        self.assertIsNotNone(run_hook(self.state, str(self.repo), "Edit", self.src("e.py")))

    def test_unguarded_tools_and_bad_input_fail_open(self):
        self.assertIsNone(run_hook(self.state, str(self.repo), "Bash", self.src("a.py")))
        env = {**os.environ, "CLAUDE_EDIT_GUARD_STATE": str(self.state)}
        out = subprocess.run([str(GUARD)], input="not json", capture_output=True, text=True, env=env, check=False)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout, "")


if __name__ == "__main__":
    unittest.main()
