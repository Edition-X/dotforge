#!/usr/bin/env python3
"""Read-only, bounded usage evidence for Scout routing evaluation.

OpenCode stores a row for every root and delegated child session.  This tool
groups each recent managed root with its entire descendant tree and aggregates
the stored counters without treating cache reads as normal input or inventing
provider prices.  It never reads message bodies or writes either database.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_DB = Path.home() / ".local/share/opencode/opencode.db"
DEFAULT_T3_DB = Path.home() / ".t3/userdata/state.sqlite"
TOKEN_COLUMNS = ("tokens_input", "tokens_output", "tokens_reasoning", "tokens_cache_read", "tokens_cache_write")


def parse_model(value: str | None) -> dict[str, str | None]:
    try:
        data = json.loads(value or "{}")
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return {key: data.get(field) if isinstance(data.get(field), str) else None
            for key, field in (("id", "id"), ("provider", "providerID"), ("variant", "variant"))}


def usage_report(db_path: Path, limit: int, directory: str | None, since_ms: int | None = None) -> dict[str, Any]:
    if not db_path.is_file():
        raise ValueError(f"OpenCode database not found: {db_path}")
    connection = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    where = "parent_id IS NULL AND agent IS NOT NULL"
    values: list[Any] = []
    if directory:
        where += " AND directory = ?"
        values.append(directory)
    if since_ms is not None:
        where += " AND time_created >= ?"
        values.append(since_ms)
    roots = connection.execute(
        f"SELECT id FROM session WHERE {where} ORDER BY time_created DESC LIMIT ?", [*values, limit]
    ).fetchall()
    root_ids = [row["id"] for row in roots]
    if not root_ids:
        connection.close()
        return {"source": "opencode", "limit": limit, "directory": directory,
                "since_ms": since_ms, "root_sessions": [], "totals": empty_totals(),
                "model_totals": {}, "attribution": {"discovery_sessions": 0, "implementation_sessions": 0},
                "cost_status": "unavailable: no positive provider-exported session cost"}
    placeholders = ",".join("?" for _ in root_ids)
    rows = connection.execute(
        f"""WITH RECURSIVE tree(root_id, id) AS (
              SELECT id, id FROM session WHERE id IN ({placeholders})
              UNION ALL
              SELECT tree.root_id, child.id FROM session child JOIN tree ON child.parent_id = tree.id
            )
            SELECT tree.root_id, s.id, s.parent_id, s.agent, s.model, s.directory, s.time_created,
                   s.cost, s.tokens_input, s.tokens_output, s.tokens_reasoning,
                   s.tokens_cache_read, s.tokens_cache_write
            FROM tree JOIN session s ON s.id = tree.id
            ORDER BY tree.root_id, s.time_created""",
        root_ids,
    ).fetchall()
    connection.close()
    by_root: dict[str, list[sqlite3.Row]] = {root_id: [] for root_id in root_ids}
    for row in rows:
        by_root[row["root_id"]].append(row)
    sessions = [summarize_root(root_id, by_root[root_id]) for root_id in root_ids]
    totals = empty_totals()
    by_model: dict[str, dict[str, float | int]] = {}
    for item in sessions:
        add_totals(totals, item["totals"])
        for model, model_totals in item["model_totals"].items():
            target = by_model.setdefault(model, empty_totals())
            add_totals(target, model_totals)
    attribution = {"discovery_sessions": 0, "implementation_sessions": 0}
    for session in sessions:
        for key in attribution:
            attribution[key] += session["attribution"][key]
    return {
        "source": "opencode",
        "limit": limit,
        "directory": directory,
        "since_ms": since_ms,
        "root_sessions": sessions,
        "totals": totals,
        "model_totals": by_model,
        "attribution": attribution,
        "cost_status": (
            "unavailable: no positive provider-exported session cost"
            if totals["cost"] == 0
            else "provider-recorded only: billing coverage unverified; not a savings estimate"
        ),
    }


def empty_totals() -> dict[str, float | int]:
    return {**{column: 0 for column in TOKEN_COLUMNS}, "cost": 0.0, "session_count": 0}


def add_totals(target: dict[str, float | int], source: dict[str, float | int]) -> None:
    for key in (*TOKEN_COLUMNS, "cost", "session_count"):
        target[key] += source[key]


def summarize_root(root_id: str, rows: list[sqlite3.Row]) -> dict[str, Any]:
    totals = empty_totals()
    models: Counter[str] = Counter()
    model_totals: dict[str, dict[str, float | int]] = {}
    roles: Counter[str] = Counter()
    for row in rows:
        totals["session_count"] += 1
        totals["cost"] += float(row["cost"] or 0)
        for column in TOKEN_COLUMNS:
            totals[column] += int(row[column] or 0)
        model = parse_model(row["model"])
        key = "/".join(value or "unknown" for value in (model["provider"], model["id"], model["variant"]))
        models[key] += 1
        target = model_totals.setdefault(key, empty_totals())
        target["session_count"] += 1
        target["cost"] += float(row["cost"] or 0)
        for column in TOKEN_COLUMNS:
            target[column] += int(row[column] or 0)
        roles[row["agent"] or "unassigned"] += 1
    attribution = {
        "discovery_sessions": sum(
            count
            for role, count in roles.items()
            if role in {"scout", "explorer", "documentation", "worker-fast"}
        ),
        "implementation_sessions": sum(
            count for role, count in roles.items() if role in {"implementer", "worker", "build"}
        ),
    }
    return {
        "root_session_id": root_id,
        "totals": totals,
        "roles": dict(roles),
        "models": dict(models),
        "model_totals": model_totals,
        "attribution": attribution,
    }


def t3_evidence(db_path: Path, limit: int, excluded_threads: set[str], project_id: str | None = None) -> dict[str, Any]:
    """Read actual T3 root selections from state.sqlite, never message bodies."""
    if not db_path.is_file():
        return {"source": "t3", "root_selection_evidence": "unavailable", "storage_present": False}
    connection = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    clause = "WHERE deleted_at IS NULL" + (" AND project_id = ?" if project_id else "")
    rows = connection.execute(
        """SELECT thread_id, project_id, created_at, model_selection_json
           FROM projection_threads """
        + clause
        + " ORDER BY updated_at DESC LIMIT ?",
        ((project_id, limit) if project_id else (limit,)),
    ).fetchall()
    connection.close()
    selections: Counter[str] = Counter()
    providers: Counter[str] = Counter()
    excluded = 0
    for thread_id, _project_id, _created_at, raw in rows:
        if thread_id in excluded_threads:
            excluded += 1
            continue
        try:
            selection = json.loads(raw or "{}")
        except json.JSONDecodeError:
            continue
        if not isinstance(selection, dict):
            continue
        model = selection.get("model")
        instance = selection.get("instanceId")
        if isinstance(model, str):
            selections[f"{instance or 'unknown'}/{model}"] += 1
            if model.startswith("claude-"):
                providers["anthropic"] += 1
            elif model.startswith("gpt-"):
                providers["openai"] += 1
            else:
                providers["unknown"] += 1
    return {
        "source": "t3",
        "storage_present": True,
        "root_selection_evidence": "projection_threads.model_selection_json",
        "thread_limit": limit,
        "excluded_threads": excluded,
        "root_selections": dict(selections),
        "providers": dict(providers),
        "token_usage_evidence": "unavailable: T3 state.sqlite has no provider token accounting",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Scout routing usage report")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--directory")
    parser.add_argument("--since-ms", type=int, help="post-policy OpenCode cohort lower bound, Unix milliseconds")
    parser.add_argument("--t3-db", type=Path, default=DEFAULT_T3_DB)
    parser.add_argument("--no-t3", action="store_true")
    parser.add_argument(
        "--exclude-t3-thread",
        action="append",
        default=[],
        help="thread ID excluded from T3 baseline (repeatable)",
    )
    parser.add_argument("--t3-project-id", help="filter T3 root selections to one project UUID")
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 100:
        parser.error("--limit must be between 1 and 100")
    try:
        report = usage_report(args.db, args.limit, args.directory, args.since_ms)
        if not args.no_t3:
            report["t3"] = t3_evidence(args.t3_db, args.limit, set(args.exclude_t3_thread), args.t3_project_id)
    except (sqlite3.Error, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
