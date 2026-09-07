#!/usr/bin/env python3
"""Opt-in paid native scout smoke. Never run from CI or pre-commit.

One bounded discovery call per invocation. Full local records stay in a temporary
folder; stdout contains only correlated session/model evidence. This is a routing
smoke, not a paired benchmark or proof of write-denial enforcement.
"""
import argparse
import importlib.util
import hashlib
import json
import subprocess
import sqlite3
import tempfile
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
PROMPT = (
    'Read-only factual discovery, no changes or memory saves. Map how scout model and '
    'permissions flow from routing/workflow.yml and models.yml into the three native '
    'agent templates under roles/ai_agents/templates. Use configured discovery routing '
    'where useful. Limit inspection to those five files plus the scout prompt. '
    'Return file references, configured model/effort, and enforcement differences in '
    'at most 250 words. Do not run deployment, tests, or external research.'
)


def snapshot():
    paths = subprocess.check_output(
        ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=REPO)
    result = {}
    for raw in paths.split(b'\0'):
        if not raw:
            continue
        path = REPO / raw.decode()
        result[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--harness', choices=('opencode', 'codex', 'claude-work'), required=True)
    parser.add_argument('--natural', action='store_true', help='Probe discretionary routing; direct reads are not scout proof')
    args = parser.parse_args()
    policy = yaml.safe_load((REPO / 'host_files/localhost/ai/routing/models.yml').read_text())
    provider = 'anthropic' if args.harness == 'claude-work' else 'openai'
    lead = policy['tiers']['lead'][provider]
    scout = policy['tiers']['worker'][provider]
    prompt = PROMPT if args.natural else ('Delegate the following bounded task to your configured scout subagent, then return its answer. ' + PROMPT)
    out = Path(tempfile.mkdtemp(prefix='scout-live-'))
    print(f'Local evidence: {out}', flush=True)
    if args.harness == 'opencode':
        command = ['opencode', 'run', '--agent', 'orchestrator', '--model', f"openai/{lead['model']}",
                   '--variant', lead['effort'], '--dir', str(REPO), '--format', 'json', prompt]
    elif args.harness == 'codex':
        command = ['codex', 'exec', '--json', '-C', str(REPO), '-s', 'read-only',
                   '-m', lead['model'], '-c', f'model_reasoning_effort="{lead["effort"]}"', prompt]
    else:
        command = ['claude-work', '-p', '--output-format', 'json', '--model', lead['model'],
                   '--effort', lead['effort'], prompt]
    spec = importlib.util.spec_from_file_location('evidence', REPO / 'scripts/scout-routing-evidence.py')
    evidence = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evidence)
    before = snapshot()
    try:
        with (out / 'stdout.jsonl').open('w') as stdout, (out / 'stderr.log').open('w') as stderr:
            result = subprocess.run(command, cwd=REPO, stdout=stdout, stderr=stderr, timeout=240)
        if snapshot() != before:
            raise ValueError('Repository contents changed during smoke')
        if result.returncode:
            raise ValueError(f'Harness exited {result.returncode}; inspect local evidence')
        rows = evidence.records(out / 'stdout.jsonl')
        if args.harness == 'opencode':
            ids = {r['sessionID'] for r in rows if r.get('sessionID')}
            if len(ids) != 1:
                raise ValueError('Missing or ambiguous root session ID')
            parent = ids.pop()
            children = evidence.opencode(parent, Path.home() / '.local/share/opencode/opencode.db', f"openai/{scout['model']}")
            if any(c['effort'] != scout['effort'] for c in children):
                raise ValueError('Scout effort mismatch')
        elif args.harness == 'codex':
            ids = {r['thread_id'] for r in rows if r.get('type') == 'thread.started'}
            if len(ids) != 1:
                raise ValueError('Missing or ambiguous root thread ID')
            parent = ids.pop()
            sessions = Path.home() / '.codex/sessions'
            paths = list(sessions.rglob(f'*{parent}*.jsonl'))
            if len(paths) != 1:
                raise ValueError('Missing or ambiguous parent rollout')
            children = evidence.codex(paths[0], sessions, scout['model'])
            if any(c['effort'] != scout['effort'] for c in children):
                raise ValueError('Scout effort mismatch')
        else:
            result_json = json.loads((out / 'stdout.jsonl').read_text())
            if result_json.get('is_error'):
                raise ValueError('Claude returned an error result')
            parent = result_json['session_id']
            sessions = Path.home() / '.claude-work/projects'
            paths = list(sessions.rglob(f'{parent}.jsonl'))
            if len(paths) != 1:
                raise ValueError('Missing or ambiguous parent transcript')
            children = evidence.claude(paths[0], paths[0].parent / parent / 'subagents', scout['model'])
        summary = {'harness': args.harness, 'parent': parent, 'children': children}
        (out / 'evidence.json').write_text(json.dumps(summary, indent=2) + '\n')
        print(json.dumps(summary, indent=2))
    except (ValueError, KeyError, OSError, sqlite3.Error, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f'FAIL: {exc}; records: {out}\n')


if __name__ == '__main__':
    main()
