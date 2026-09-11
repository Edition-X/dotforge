#!/usr/bin/env python3
"""Read-only usage report across the AI harnesses on this Mac.

Prints the numbers the lead-worker routing policy and the Claude-plans /
OpenCode-builds bridge are judged by, so the same questions can be asked again
after a week instead of re-deriving ad hoc SQL:

- OpenCode: root sessions, child dispatches by agent, model/variant actually
  used versus the managed one, step-cap handoffs, repeated corrections,
  compactions.
- T3 Code: threads by provider, per-thread model selection, plan-mode use.
- Claude Code (personal and work): sessions, Agent dispatches by subagent
  type, EnterPlanMode use, the largest sessions by output tokens.

It only reads the local databases and transcripts; nothing is written and no
message body is printed. Cost columns are not reported because subscription
auth stores 0.

    harness-usage-report.py --since 2026-09-06 [--json]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_OPENCODE_DB = Path.home() / ".local/share/opencode/opencode.db"
DEFAULT_T3_DB = Path.home() / ".t3/userdata/state.sqlite"
DEFAULT_CLAUDE_DIRS = {
    "claude-personal": Path.home() / ".claude/projects",
    "claude-work": Path.home() / ".claude-work/projects",
}
STEP_CAP_MARKER = "maximum steps"


def ro_connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def parse_model(value: str | None) -> str:
    try:
        data = json.loads(value or "{}")
    except json.JSONDecodeError:
        return "?"
    if not isinstance(data, dict):
        return "?"
    return f"{data.get('id') or data.get('model') or '?'}:{data.get('variant') or '-'}"


def opencode_report(db: Path, since_ms: int) -> dict[str, Any]:
    if not db.is_file():
        return {"available": False}
    conn = ro_connect(db)
    roots = conn.execute(
        "SELECT id, agent, model, tokens_output, directory FROM session "
        "WHERE parent_id IS NULL AND time_created >= ? ORDER BY time_created", (since_ms,),
    ).fetchall()
    children = conn.execute(
        "SELECT agent, model, title FROM session WHERE parent_id IS NOT NULL AND time_created >= ?",
        (since_ms,),
    ).fetchall()
    root_models = Counter(parse_model(r["model"]) for r in roots)
    child_agents = Counter(r["agent"] or "?" for r in children)
    child_models = Counter(parse_model(r["model"]) for r in children)
    correction_titles = Counter(r["title"] for r in children if (r["title"] or "").lower().startswith("correct"))
    repeated_corrections = {title: n for title, n in correction_titles.items() if n > 1}
    root_ids = [r["id"] for r in roots]
    compactions = 0
    step_cap_handoffs = 0
    if root_ids:
        placeholders = ",".join("?" for _ in root_ids)
        compactions = conn.execute(
            f"SELECT COUNT(*) FROM message WHERE session_id IN ({placeholders}) "
            "AND json_extract(data, '$.agent') = 'compaction'", root_ids,
        ).fetchone()[0]
        step_cap_handoffs = conn.execute(
            "SELECT COUNT(*) FROM part p JOIN session s ON s.id = p.session_id "
            "WHERE s.parent_id IS NOT NULL AND s.time_created >= ? "
            "AND json_extract(p.data, '$.type') = 'text' "
            "AND lower(json_extract(p.data, '$.text')) LIKE ?",
            (since_ms, f"%{STEP_CAP_MARKER}%"),
        ).fetchone()[0]
    bridged = conn.execute(
        "SELECT COUNT(*) FROM session WHERE parent_id IS NULL AND time_created >= ? "
        "AND agent IN ('worker', 'rescue', 'verifier')", (since_ms,),
    ).fetchone()[0]
    conn.close()
    return {
        "available": True,
        "root_sessions": len(roots),
        "bridged_root_sessions": bridged,
        "root_models": dict(root_models),
        "child_dispatches_by_agent": dict(child_agents),
        "child_models": dict(child_models),
        "repeated_corrections": repeated_corrections,
        "step_cap_handoffs": step_cap_handoffs,
        "compactions": compactions,
    }


def t3_report(db: Path, since_iso: str) -> dict[str, Any]:
    if not db.is_file():
        return {"available": False}
    conn = ro_connect(db)
    rows = conn.execute(
        "SELECT t.interaction_mode, t.model_selection_json, s.provider_name "
        "FROM projection_threads t LEFT JOIN projection_thread_sessions s ON s.thread_id = t.thread_id "
        "WHERE t.created_at >= ?", (since_iso,),
    ).fetchall()
    plans = conn.execute(
        "SELECT COUNT(*) FROM projection_thread_proposed_plans WHERE created_at >= ?", (since_iso,),
    ).fetchone()[0]
    conn.close()
    providers = Counter(r["provider_name"] or "?" for r in rows)
    models: Counter = Counter()
    for r in rows:
        try:
            sel = json.loads(r["model_selection_json"] or "{}")
        except json.JSONDecodeError:
            sel = {}
        options = sel.get("options", [])
        effort = next((o.get("value") for o in options if o.get("id") in ("effort", "reasoningEffort")), "-")
        models[f"{sel.get('model', '?')}:{effort}"] += 1
    return {
        "available": True,
        "threads": len(rows),
        "threads_by_provider": dict(providers),
        "thread_models": dict(models),
        "plan_mode_threads": sum(1 for r in rows if r["interaction_mode"] == "plan"),
        "proposed_plans": plans,
    }


def claude_report(projects_dir: Path, since_iso: str, top: int = 3) -> dict[str, Any]:
    if not projects_dir.is_dir():
        return {"available": False}
    sessions = 0
    dispatches: Counter = Counter()
    plan_mode = 0
    largest: list[tuple[int, int, str]] = []
    for path in projects_dir.glob("*/*.jsonl"):
        first_ts = None
        output_tokens = 0
        turns = 0
        sidechain = False
        local: Counter = Counter()
        local_plan = 0
        with path.open() as fh:
            for line in fh:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("isSidechain") or record.get("agentId"):
                    sidechain = True
                    break
                ts = record.get("timestamp")
                if ts and first_ts is None:
                    first_ts = ts
                if record.get("type") != "assistant":
                    continue
                turns += 1
                message = record.get("message") or {}
                output_tokens += (message.get("usage") or {}).get("output_tokens", 0)
                for block in message.get("content") or []:
                    if block.get("type") != "tool_use":
                        continue
                    name = block.get("name")
                    if name in ("Task", "Agent"):
                        local[(block.get("input") or {}).get("subagent_type", "?")] += 1
                    elif name == "EnterPlanMode":
                        local_plan += 1
        if sidechain or not first_ts or first_ts < since_iso:
            continue
        sessions += 1
        dispatches.update(local)
        plan_mode += local_plan
        largest.append((output_tokens, turns, path.parent.name[-30:]))
    largest.sort(reverse=True)
    return {
        "available": True,
        "sessions": sessions,
        "agent_dispatches": dict(dispatches),
        "enter_plan_mode": plan_mode,
        "largest_sessions": [
            {"output_tokens": o, "assistant_turns": t, "project": p} for o, t, p in largest[:top]
        ],
    }


def build_report(since: dt.date, opencode_db: Path, t3_db: Path, claude_dirs: dict[str, Path]) -> dict[str, Any]:
    since_iso = since.isoformat()
    since_ms = int(dt.datetime(since.year, since.month, since.day, tzinfo=dt.UTC).timestamp() * 1000)
    report: dict[str, Any] = {
        "since": since_iso,
        "opencode": opencode_report(opencode_db, since_ms),
        "t3": t3_report(t3_db, since_iso),
    }
    for name, path in claude_dirs.items():
        report[name] = claude_report(path, since_iso)
    return report


def render(report: dict[str, Any]) -> str:
    lines = [f"Harness usage since {report['since']}"]
    for name, section in report.items():
        if name == "since":
            continue
        lines.append(f"\n[{name}]")
        if not section.get("available"):
            lines.append("  not available")
            continue
        for key, value in section.items():
            if key == "available":
                continue
            lines.append(f"  {key}: {json.dumps(value, sort_keys=True)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--since", type=dt.date.fromisoformat, default=dt.date.today() - dt.timedelta(days=7))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--opencode-db", type=Path, default=DEFAULT_OPENCODE_DB)
    parser.add_argument("--t3-db", type=Path, default=DEFAULT_T3_DB)
    args = parser.parse_args(argv)
    report = build_report(args.since, args.opencode_db, args.t3_db, DEFAULT_CLAUDE_DIRS)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
