#!/usr/bin/env python3
"""Offline coverage for the claude-dispatch-guard PreToolUse hook. No model calls."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "host_files/localhost/bin"
GUARD = BIN / "claude-dispatch-guard"
EDIT_GUARD = BIN / "claude-edit-guard"


def run_hook(state: Path, cwd: str, tool: str, tool_input: dict) -> dict | None:
    payload = {"session_id": "s1", "cwd": cwd, "tool_name": tool, "tool_input": tool_input}
    env = {**os.environ, "CLAUDE_EDIT_GUARD_STATE": str(state)}
    out = subprocess.run([str(GUARD)], input=json.dumps(payload), capture_output=True, text=True, env=env, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout) if out.stdout.strip() else None


def decision(result: dict | None) -> str | None:
    return result["hookSpecificOutput"]["permissionDecision"] if result else None


class DispatchGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "state"
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_implementation_agents_are_denied_with_a_build_pointer(self):
        for agent in ("general-purpose", "worker", "rescue"):
            result = run_hook(self.state, str(self.repo), "Agent", {"subagent_type": agent, "prompt": "x"})
            self.assertEqual(decision(result), "deny", agent)
            self.assertIn("build", result["hookSpecificOutput"]["permissionDecisionReason"])

    def test_missing_subagent_type_is_treated_as_general_purpose(self):
        result = run_hook(self.state, str(self.repo), "Agent", {"prompt": "x"})
        self.assertEqual(decision(result), "deny")

    def test_read_only_and_review_agents_pass(self):
        for agent in ("Explore", "Plan", "scout", "verifier", "documentation", "claude"):
            self.assertIsNone(run_hook(self.state, str(self.repo), "Agent", {"subagent_type": agent}), agent)

    def test_other_tools_are_ignored(self):
        self.assertIsNone(run_hook(self.state, str(self.repo), "Bash", {"command": "ls"}))

    def test_edit_guard_off_lifts_the_dispatch_guard_too(self):
        env = {**os.environ, "CLAUDE_EDIT_GUARD_STATE": str(self.state)}
        subprocess.run([str(EDIT_GUARD), "off"], cwd=str(self.repo), env=env, check=True, capture_output=True)
        self.assertIsNone(run_hook(self.state, str(self.repo), "Agent", {"subagent_type": "general-purpose"}))
        subprocess.run([str(EDIT_GUARD), "on"], cwd=str(self.repo), env=env, check=True, capture_output=True)
        again = run_hook(self.state, str(self.repo), "Agent", {"subagent_type": "general-purpose"})
        self.assertEqual(decision(again), "deny")

    def test_malformed_input_fails_open(self):
        env = {**os.environ, "CLAUDE_EDIT_GUARD_STATE": str(self.state)}
        out = subprocess.run([str(GUARD)], input="not json", capture_output=True, text=True, env=env, check=False)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
