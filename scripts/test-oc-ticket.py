#!/usr/bin/env python3
"""Offline coverage for the oc-ticket bridge against a fake `opencode`. No model calls."""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

BRIDGE = Path(__file__).resolve().parent.parent / "host_files/localhost/bin/oc-ticket"
spec = importlib.util.spec_from_loader("oc_ticket", importlib.machinery.SourceFileLoader("oc_ticket", str(BRIDGE)))
oc_ticket = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oc_ticket)

HANDOFF = """Done.

status: COMPLETE
ticket: SPIKE-1
branch: spike-1-subtract
commit: 88e8516
files: calc.py, test_calc.py
checks: python3 -m pytest -q exit 0
failure_fingerprint: none
deviations: none
last_safe_state: committed on ticket branch
recommended_next: lead reviews diff
unresolved_risks: none
"""

FAKE_OPENCODE = r'''#!/usr/bin/env python3
import json, os, sys
argv = sys.argv[1:]
log = os.environ["FAKE_LOG"]
with open(log, "a") as fh:
    fh.write(json.dumps(argv) + "\n")
if argv[0] == "run":
    # The real CLI blocks on an open non-TTY stdin; the bridge must hand it /dev/null.
    assert sys.stdin.read() == ""
    if os.environ.get("FAKE_HANG"):
        import time
        time.sleep(30)
    sid = "ses_fake"
    for i in range(2):
        print(json.dumps({"type": "step_start", "sessionID": sid, "part": {"sessionID": sid}}))
        print(json.dumps({"type": "tool_use", "sessionID": sid, "part": {"tool": "bash", "sessionID": sid}}))
        print(json.dumps({"type": "step_finish", "sessionID": sid, "part": {}}))
    if os.environ.get("FAKE_DENY"):
        sys.stderr.write("\x1b[93m! \x1b[0m permission requested: external_directory (/x/*); auto-rejecting\n")
    sys.exit(0)
if argv[0] == "export":
    text = os.environ.get("FAKE_FINAL", "")
    parts = [{"type": "text", "text": text}] if text else [{"type": "tool", "tool": "bash"}]
    print(json.dumps({"info": {"id": argv[1]}, "messages": [
        {"info": {"role": "user"}, "parts": [{"type": "text", "text": "ticket"}]},
        {"info": {"role": "assistant"}, "parts": parts},
    ]}))
    sys.exit(0)
sys.exit(3)
'''


class ParseTests(unittest.TestCase):
    def test_parses_all_eleven_fields_and_status(self):
        fields = oc_ticket.parse_handoff(HANDOFF)
        self.assertEqual(fields["status"], "COMPLETE")
        self.assertEqual(sorted(fields), sorted(oc_ticket.EVIDENCE_FIELDS))
        self.assertEqual(fields["commit"], "88e8516")

    def test_tolerates_markdown_decoration_and_continuations(self):
        text = "- **status**: `HANDOFF_REQUIRED`\n- checks: pytest failed\n  verbatim line two\n\nticket: X\n"
        text = text.replace("**status**", "status")
        fields = oc_ticket.parse_handoff(text)
        self.assertEqual(fields["status"], "HANDOFF_REQUIRED")
        self.assertEqual(fields["checks"], "pytest failed verbatim line two")
        self.assertEqual(fields["ticket"], "X")

    def test_unknown_status_is_dropped(self):
        self.assertNotIn("status", oc_ticket.parse_handoff("status: maybe done\nticket: X"))


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.fake = root / "opencode"
        self.fake.write_text(FAKE_OPENCODE)
        self.fake.chmod(self.fake.stat().st_mode | stat.S_IEXEC)
        self.log = root / "calls.log"
        self.ticket = root / "ticket-1.md"
        self.ticket.write_text("# ticket\n")
        self.repo = root / "repo"
        self.repo.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_bridge(self, *args: str, final: str = HANDOFF, deny: bool = False, hang: bool = False):
        env = {**os.environ, "OC_TICKET_OPENCODE": str(self.fake), "FAKE_LOG": str(self.log), "FAKE_FINAL": final}
        if deny:
            env["FAKE_DENY"] = "1"
        if hang:
            env["FAKE_HANG"] = "1"
        command = [str(BRIDGE), *args, "--dir", str(self.repo)]
        out = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        return out, calls

    def test_complete_ticket_exits_zero_with_parsed_handoff(self):
        out, calls = self.run_bridge("--role", "worker", "--ticket", str(self.ticket))
        self.assertEqual(out.returncode, 0, out.stderr)
        result = json.loads(out.stdout)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["session_id"], "ses_fake")
        self.assertEqual(result["missing_fields"], [])
        self.assertEqual(result["tools"], {"bash": 2})
        run_call = calls[0]
        self.assertEqual(run_call[:1], ["run"])
        self.assertIn("--agent", run_call)
        self.assertEqual(run_call[run_call.index("--agent") + 1], "worker")
        self.assertEqual(run_call[run_call.index("-f") + 1], str(self.ticket.resolve()))
        self.assertEqual(calls[1], ["export", "ses_fake"])

    def test_resume_passes_session_and_agent(self):
        out, calls = self.run_bridge("--role", "worker", "--resume", "ses_old", "--message", "Correction 1 of 1")
        self.assertEqual(out.returncode, 0, out.stderr)
        run_call = calls[0]
        self.assertEqual(run_call[run_call.index("-s") + 1], "ses_old")
        self.assertEqual(run_call[run_call.index("--agent") + 1], "worker")
        self.assertEqual(run_call[1], "Correction 1 of 1")
        self.assertTrue(json.loads(out.stdout)["resumed"])

    def test_non_complete_status_exits_one(self):
        final = HANDOFF.replace("COMPLETE", "HANDOFF_REQUIRED")
        out, _ = self.run_bridge("--role", "worker", "--ticket", str(self.ticket), final=final)
        self.assertEqual(out.returncode, 1)
        self.assertEqual(json.loads(out.stdout)["status"], "HANDOFF_REQUIRED")

    def test_missing_handoff_after_permission_denial_is_blocked_authority(self):
        out, _ = self.run_bridge("--role", "worker", "--ticket", str(self.ticket), final="", deny=True)
        self.assertEqual(out.returncode, 1)
        result = json.loads(out.stdout)
        self.assertEqual(result["status"], "BLOCKED_AUTHORITY")
        self.assertEqual(result["permission_denials"], ["external_directory (/x/*)"])
        self.assertIn("status", result["handoff"])

    def test_missing_handoff_without_denial_is_no_handoff(self):
        final = "all good, nothing structured"
        out, _ = self.run_bridge("--role", "verifier", "--ticket", str(self.ticket), final=final)
        self.assertEqual(out.returncode, 1)
        result = json.loads(out.stdout)
        self.assertEqual(result["status"], "NO_HANDOFF")
        self.assertIn("ticket", result["missing_fields"])

    def test_silent_hang_is_killed_at_the_timeout(self):
        out, _ = self.run_bridge("--role", "worker", "--ticket", str(self.ticket), "--timeout", "1", hang=True)
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertEqual(json.loads(out.stdout)["status"], "TRANSPORT_FAILED")

    def test_resume_requires_message_and_ticket_must_exist(self):
        out, _ = self.run_bridge("--role", "worker", "--resume", "ses_old")
        self.assertEqual(out.returncode, 2)
        out, _ = self.run_bridge("--role", "worker", "--ticket", str(self.repo / "missing.md"))
        self.assertEqual(out.returncode, 2)


if __name__ == "__main__":
    unittest.main()
