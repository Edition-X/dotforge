#!/usr/bin/env python3
"""Validate native scout dispatch using correlated harness records, never prose.

Offline only. Callers supply the exact parent session, expected child model, and
record location. Missing evidence raises an error; this does not prove answer
quality, billing savings, or that a runtime respected every configured permission.
"""
import argparse
import json
import sqlite3
from pathlib import Path


def records(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def codex(parent, sessions, expected):
    calls = set()
    children = set()
    for row in records(parent):
        payload = row.get('payload', {})
        if row.get('type') == 'response_item' and payload.get('type') == 'function_call':
            if payload.get('name', '').split('.')[-1] != 'spawn_agent':
                continue
            args = json.loads(payload.get('arguments', '{}'))
            if args.get('agent_type') == 'scout':
                calls.add(payload['call_id'])
        if row.get('type') == 'event_msg':
            item = payload.get('item', {})
            if (item.get('type') == 'SubAgentActivity' and item.get('kind') == 'started'
                    and item.get('id') in calls):
                children.add(item['agent_thread_id'])
    evidence = []
    for child in sorted(children):
        paths = list(Path(sessions).rglob(f'*{child}*.jsonl'))
        if len(paths) != 1:
            raise ValueError(f'Expected exactly one child rollout for {child}')
        rows = records(paths[0])
        metas = [r['payload'] for r in rows if r.get('type') == 'session_meta']
        if not any(m.get('id', m.get('session_id')) == child for m in metas):
            raise ValueError('Child session identity mismatch')
        # Forked transcripts include parent turn_context records. Attribute only
        # turns with harness token records naming this child thread.
        own_turns = {r['payload'].get('turn_id') for r in rows
                     if r.get('type') == 'token_usage_record'
                     and r['payload'].get('thread_id') == child}
        turns = [r['payload'] for r in rows if r.get('type') == 'turn_context'
                 and r['payload'].get('turn_id') in own_turns]
        if not turns or any(t.get('model') != expected for t in turns):
            raise ValueError('Child effective model missing or mismatched')
        evidence.append({'child_id': child, 'model': expected,
                         'sandbox_policy': turns[-1].get('sandbox_policy'),
                         'effort': turns[-1].get('effort')})
    if not evidence:
        raise ValueError('No correlated scout dispatch and child runtime evidence')
    return evidence


def claude(parent, sessions, expected):
    calls = set()
    children = set()
    for row in records(parent):
        content = row.get('message', {}).get('content', [])
        if not isinstance(content, list):
            continue
        for item in content:
            if (item.get('type') == 'tool_use' and item.get('name') in {'Agent', 'Task'}
                    and item.get('input', {}).get('subagent_type') == 'scout'):
                calls.add(item['id'])
            if item.get('type') == 'tool_result' and item.get('tool_use_id') in calls:
                result = row.get('toolUseResult', {})
                if isinstance(result, dict) and result.get('agentId'):
                    children.add(result['agentId'])
    evidence = []
    for child in sorted(children):
        paths = list(Path(sessions).rglob(f'agent-{child}.jsonl'))
        if len(paths) != 1:
            raise ValueError(f'Expected exactly one child transcript for {child}')
        rows = records(paths[0])
        messages = [r for r in rows if r.get('type') == 'assistant']
        models = {r.get('message', {}).get('model') for r in messages}
        if not messages or models != {expected}:
            raise ValueError('Child effective model missing or mismatched')
        if any(r.get('agentId') != child for r in messages):
            raise ValueError('Child agent identity mismatch')
        evidence.append({'child_id': child, 'model': expected})
    if not evidence:
        raise ValueError('No correlated scout dispatch and child runtime evidence')
    return evidence


def opencode(parent, database, expected):
    connection = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        rows = connection.execute(
            'SELECT id, model FROM session WHERE parent_id = ? AND agent = ?',
            (parent, 'scout')).fetchall()
    finally:
        connection.close()
    evidence = []
    for child, raw in rows:
        model = json.loads(raw or '{}')
        observed = f"{model.get('providerID')}/{model.get('id')}"
        if observed != expected:
            raise ValueError(f'Child model mismatch: {observed}')
        evidence.append({'child_id': child, 'model': observed, 'effort': model.get('variant')})
    if not evidence:
        raise ValueError('No scout child attached to supplied parent session')
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--harness', choices=('codex', 'claude', 'opencode'), required=True)
    parser.add_argument('--parent', required=True, help='Parent transcript path, or OpenCode session ID')
    parser.add_argument('--records', type=Path, required=True, help='Child transcript directory, or OpenCode DB')
    parser.add_argument('--expected-model', required=True)
    args = parser.parse_args()
    try:
        result = globals()[args.harness](args.parent, args.records, args.expected_model)
    except (ValueError, KeyError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f'FAIL: {exc}\n')
    print(json.dumps({'harness': args.harness, 'children': result}, indent=2))


if __name__ == '__main__':
    main()
