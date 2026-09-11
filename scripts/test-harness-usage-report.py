#!/usr/bin/env python3
"""Offline coverage for harness-usage-report.py against tiny fixture stores."""
from __future__ import annotations

import datetime as dt
import importlib.machinery
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("harness-usage-report.py")
spec = importlib.util.spec_from_loader("report", importlib.machinery.SourceFileLoader("report", str(SCRIPT)))
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)

SINCE = dt.date(2026, 9, 6)
OLD_MS = 1_000
NEW_MS = int(dt.datetime(2026, 9, 10, tzinfo=dt.UTC).timestamp() * 1000)


def make_opencode_db(path: Path) -> None:
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE session (id TEXT, parent_id TEXT, agent TEXT, model TEXT, title TEXT, "
        "directory TEXT, time_created INTEGER, tokens_output INTEGER)"
    )
    db.execute("CREATE TABLE message (id TEXT, session_id TEXT, data TEXT)")
    db.execute("CREATE TABLE part (id TEXT, session_id TEXT, message_id TEXT, data TEXT)")
    sol = json.dumps({"id": "sol", "providerID": "openai", "variant": "high"})
    luna = json.dumps({"id": "luna", "providerID": "openai", "variant": "medium"})
    rows = [
        ("root", None, "orchestrator", sol, "New session", "/repo", NEW_MS, 10),
        ("bridged", None, "worker", luna, "ticket-1", "/repo", NEW_MS, 10),
        ("w1", "root", "worker", luna, "Implement X", "/repo", NEW_MS, 5),
        ("w2", "root", "worker", luna, "Correct X", "/repo", NEW_MS, 5),
        ("w3", "root", "worker", luna, "Correct X", "/repo", NEW_MS, 5),
        ("v1", "root", "verifier", luna, "Verify X", "/repo", NEW_MS, 5),
        ("old", None, "orchestrator", sol, "old", "/repo", OLD_MS, 5),
    ]
    db.executemany("INSERT INTO session VALUES (?,?,?,?,?,?,?,?)", rows)
    db.executemany("INSERT INTO message VALUES (?,?,?)", [
        ("m1", "root", json.dumps({"role": "assistant", "agent": "compaction"})),
        ("m2", "root", json.dumps({"role": "assistant", "agent": "orchestrator"})),
    ])
    db.executemany("INSERT INTO part VALUES (?,?,?,?)", [
        ("p1", "w1", "mw1", json.dumps({"type": "text", "text": "deviations: Maximum steps reached before commit"})),
        ("p2", "w2", "mw2", json.dumps({"type": "text", "text": "status: COMPLETE"})),
    ])
    db.commit()
    db.close()


def make_t3_db(path: Path) -> None:
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE projection_threads (thread_id TEXT, created_at TEXT, interaction_mode TEXT, "
        "model_selection_json TEXT)"
    )
    db.execute("CREATE TABLE projection_thread_sessions (thread_id TEXT, provider_name TEXT)")
    db.execute("CREATE TABLE projection_thread_proposed_plans (plan_id TEXT, created_at TEXT)")
    sel = json.dumps({"model": "claude-opus-5", "options": [{"id": "effort", "value": "medium"}]})
    db.executemany("INSERT INTO projection_threads VALUES (?,?,?,?)", [
        ("t1", "2026-09-08T10:00:00Z", "default", sel),
        ("t2", "2026-09-09T10:00:00Z", "plan", sel),
        ("t0", "2026-08-01T10:00:00Z", "default", sel),
    ])
    db.executemany(
        "INSERT INTO projection_thread_sessions VALUES (?,?)",
        [("t1", "claudeAgent"), ("t2", "codex"), ("t0", "claudeAgent")],
    )
    db.execute("INSERT INTO projection_thread_proposed_plans VALUES ('p1', '2026-09-09T11:00:00Z')")
    db.commit()
    db.close()


def make_claude_dir(root: Path) -> None:
    project = root / "-Users-x-Projects-repo"
    project.mkdir(parents=True)
    def asst(tool: dict | None, tokens: int) -> str:
        content = [tool] if tool else [{"type": "text", "text": "hi"}]
        message = {"usage": {"output_tokens": tokens}, "content": content}
        return json.dumps({"type": "assistant", "timestamp": "2026-09-09T10:00:00Z", "message": message})
    (project / "a.jsonl").write_text("\n".join([
        json.dumps({"type": "user", "timestamp": "2026-09-09T09:00:00Z"}),
        asst({"type": "tool_use", "name": "Agent", "input": {"subagent_type": "general-purpose"}}, 100),
        asst({"type": "tool_use", "name": "EnterPlanMode", "input": {}}, 50),
    ]) + "\n")
    old_user = json.dumps({"type": "user", "timestamp": "2026-08-01T09:00:00Z"})
    (project / "old.jsonl").write_text(old_user + "\n" + asst(None, 999) + "\n")
    side_user = json.dumps({"type": "user", "timestamp": "2026-09-09T09:00:00Z", "isSidechain": True})
    (project / "side.jsonl").write_text(side_user + "\n")


class ReportTests(unittest.TestCase):
    def test_report_counts_only_the_window_and_the_right_things(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_opencode_db(root / "oc.db")
            make_t3_db(root / "t3.db")
            make_claude_dir(root / "claude")
            out = report.build_report(SINCE, root / "oc.db", root / "t3.db", {"claude-work": root / "claude"})
        oc = out["opencode"]
        self.assertEqual(oc["root_sessions"], 2)
        self.assertEqual(oc["bridged_root_sessions"], 1)
        self.assertEqual(oc["root_models"], {"sol:high": 1, "luna:medium": 1})
        self.assertEqual(oc["child_dispatches_by_agent"], {"worker": 3, "verifier": 1})
        self.assertEqual(oc["repeated_corrections"], {"Correct X": 2})
        self.assertEqual(oc["step_cap_handoffs"], 1)
        self.assertEqual(oc["compactions"], 1)
        t3 = out["t3"]
        self.assertEqual(t3["threads"], 2)
        self.assertEqual(t3["threads_by_provider"], {"claudeAgent": 1, "codex": 1})
        self.assertEqual(t3["thread_models"], {"claude-opus-5:medium": 2})
        self.assertEqual(t3["plan_mode_threads"], 1)
        self.assertEqual(t3["proposed_plans"], 1)
        cw = out["claude-work"]
        self.assertEqual(cw["sessions"], 1)
        self.assertEqual(cw["agent_dispatches"], {"general-purpose": 1})
        self.assertEqual(cw["enter_plan_mode"], 1)
        self.assertEqual(cw["largest_sessions"][0]["output_tokens"], 150)

    def test_missing_stores_are_reported_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = report.build_report(SINCE, root / "no.db", root / "no.db", {"claude-work": root / "nope"})
        self.assertFalse(out["opencode"]["available"])
        self.assertFalse(out["t3"]["available"])
        self.assertFalse(out["claude-work"]["available"])
        self.assertIn("not available", report.render(out))


if __name__ == "__main__":
    unittest.main()
