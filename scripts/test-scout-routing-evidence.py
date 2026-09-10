#!/usr/bin/env python3
"""Reject narrative claims, unrelated children and incorrect runtime models."""
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('evidence', Path(__file__).with_name('scout-routing-evidence.py'))
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


def write(path, rows):
    path.write_text(''.join(json.dumps(r) + '\n' for r in rows))


class EvidenceTests(unittest.TestCase):
    def test_codex_correlation_and_runtime_model(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            parent = home / 'parent.jsonl'
            child = home / 'rollout-child.jsonl'
            call = {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'spawn_agent',
                    'call_id': 'call1', 'arguments': json.dumps({'agent_type': 'scout'})}}
            activity = {'type': 'event_msg', 'payload': {'type': 'item_completed', 'item': {
                'type': 'SubAgentActivity', 'id': 'call1', 'kind': 'started', 'agent_thread_id': 'child'}}}
            write(parent, [call, activity])
            write(child, [{'type': 'session_meta', 'payload': {'id': 'child'}},
                          {'type': 'turn_context', 'payload': {'turn_id': 'parent-turn', 'model': 'expensive'}},
                          {'type': 'turn_context',
                           'payload': {'turn_id': 'child-turn', 'model': 'cheap',
                                       'sandbox_policy': {'type': 'read-only'}}},
                          {'type': 'token_usage_record', 'payload': {'thread_id': 'child', 'turn_id': 'child-turn'}}])
            self.assertEqual(evidence.codex(parent, home, 'cheap')[0]['child_id'], 'child')
            with self.assertRaises(ValueError):
                evidence.codex(parent, home, 'expensive')
            activity['payload']['item']['id'] = 'unrelated'
            write(parent, [call, activity])
            with self.assertRaises(ValueError):
                evidence.codex(parent, home, 'cheap')

    def test_opencode_exact_parent_and_model(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sessions.db'
            db = sqlite3.connect(path)
            db.execute('CREATE TABLE session (id TEXT, parent_id TEXT, agent TEXT, model TEXT)')
            model = json.dumps({'providerID': 'openai', 'id': 'cheap', 'variant': 'medium'})
            db.executemany('INSERT INTO session VALUES (?,?,?,?)', [
                ('child', 'root', 'scout', model), ('unrelated', 'other', 'scout', model),
                ('worker', 'root', 'worker', model)])
            db.commit()
            db.close()
            result = evidence.opencode('root', path, 'openai/cheap')
            self.assertEqual([r['child_id'] for r in result], ['child'])
            self.assertEqual(result[0]['effort'], 'medium')
            with self.assertRaises(ValueError):
                evidence.opencode('root', path, 'openai/expensive')
            with self.assertRaises(ValueError):
                evidence.opencode('missing', path, 'openai/cheap')

    def test_claude_correlated_agent_result(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            parent = home / 'parent.jsonl'
            write(parent, [
                {'message': {'content': [{'type': 'tool_use', 'id': 'tool1', 'name': 'Agent',
                                          'input': {'subagent_type': 'scout'}}]}},
                {'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'tool1'}]},
                 'toolUseResult': {'agentId': 'child'}}])
            child = home / 'agent-child.jsonl'
            write(child, [{'type': 'assistant', 'agentId': 'child', 'message': {'model': 'cheap'}}])
            self.assertEqual(evidence.claude(parent, home, 'cheap')[0]['model'], 'cheap')
            write(child, [{'type': 'assistant', 'agentId': 'other', 'message': {'model': 'cheap'}}])
            with self.assertRaises(ValueError):
                evidence.claude(parent, home, 'cheap')
            write(parent, [{'message': {'content': 'I delegated to scout using cheap model'}}])
            with self.assertRaises(ValueError):
                evidence.claude(parent, home, 'cheap')


if __name__ == '__main__':
    unittest.main()
