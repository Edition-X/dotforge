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

    IMPLEMENT = "Implement the subtract function in calc.py, add a test, and commit on a new branch."
    READ_ONLY = "Review the diff for correctness bugs and report findings with file:line. Do not edit anything."

    def test_native_implementation_roles_are_denied_whatever_the_prompt(self):
        for agent in ("worker", "rescue", "Worker "):
            result = run_hook(self.state, str(self.repo), "Agent", {"subagent_type": agent, "prompt": self.READ_ONLY})
            self.assertEqual(decision(result), "deny", agent)
            self.assertIn("build", result["hookSpecificOutput"]["permissionDecisionReason"])

    def test_general_purpose_is_judged_by_its_prompt(self):
        implement = {"subagent_type": "general-purpose", "prompt": self.IMPLEMENT}
        self.assertEqual(decision(run_hook(self.state, str(self.repo), "Agent", implement)), "deny")
        read_only = {"subagent_type": "General-Purpose", "prompt": self.READ_ONLY}
        self.assertIsNone(run_hook(self.state, str(self.repo), "Agent", read_only))

    def test_missing_subagent_type_is_judged_like_general_purpose(self):
        self.assertEqual(decision(run_hook(self.state, str(self.repo), "Agent", {"prompt": self.IMPLEMENT})), "deny")
        self.assertIsNone(run_hook(self.state, str(self.repo), "Agent", {"prompt": self.READ_ONLY}))

    def test_read_only_and_review_agents_pass_even_with_an_implementation_prompt(self):
        for agent in ("Explore", "Plan", "scout", "verifier", "documentation", "claude"):
            result = run_hook(self.state, str(self.repo), "Agent", {"subagent_type": agent, "prompt": self.IMPLEMENT})
            self.assertIsNone(result, agent)

    def test_cli_arguments_do_not_hang_on_stdin(self):
        out = subprocess.run([str(GUARD), "off"], capture_output=True, text=True, check=False)
        self.assertEqual(out.returncode, 2)
        self.assertIn("claude-edit-guard", out.stderr)

    def test_other_tools_are_ignored(self):
        self.assertIsNone(run_hook(self.state, str(self.repo), "Bash", {"command": "ls"}))

    def test_edit_guard_off_lifts_the_dispatch_guard_too(self):
        env = {**os.environ, "CLAUDE_EDIT_GUARD_STATE": str(self.state)}
        subprocess.run([str(EDIT_GUARD), "off"], cwd=str(self.repo), env=env, check=True, capture_output=True)
        call = {"subagent_type": "worker", "prompt": self.IMPLEMENT}
        self.assertIsNone(run_hook(self.state, str(self.repo), "Agent", call))
        subprocess.run([str(EDIT_GUARD), "on"], cwd=str(self.repo), env=env, check=True, capture_output=True)
        self.assertEqual(decision(run_hook(self.state, str(self.repo), "Agent", call)), "deny")

    def test_malformed_input_fails_open(self):
        env = {**os.environ, "CLAUDE_EDIT_GUARD_STATE": str(self.state)}
        out = subprocess.run([str(GUARD)], input="not json", capture_output=True, text=True, env=env, check=False)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
