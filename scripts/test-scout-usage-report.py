#!/usr/bin/env python3
"""Offline coverage for recursive accounting, cohort isolation and opaque costs."""
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('usage', Path(__file__).with_name('scout-usage-report.py'))
usage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usage)


class UsageTests(unittest.TestCase):
    def test_recursive_filtered_accounting(self):
        with tempfile.TemporaryDirectory() as home:
            path = Path(home) / 'usage.db'
            db = sqlite3.connect(path)
            db.execute(
                'CREATE TABLE session ('
                'id TEXT, '
                'parent_id TEXT, '
                'agent TEXT, '
                'model TEXT, '
                'directory TEXT, '
                'time_created INTEGER, '
                'cost REAL, '
                'tokens_input INTEGER, '
                'tokens_output INTEGER, '
                'tokens_reasoning INTEGER, '
                'tokens_cache_read INTEGER, '
                'tokens_cache_write INTEGER'
                ')'
            )
            model = json.dumps({'providerID': 'openai', 'id': 'cheap', 'variant': 'medium'})
            rows = [('root', None, 'orchestrator', model, '/repo', 20),
                    ('child', 'root', 'scout', model, '/repo', 21),
                    ('grandchild', 'child', 'worker', '[]', '/elsewhere', 22),
                    ('old', None, 'orchestrator', model, '/repo', 1),
                    ('other', None, 'orchestrator', model, '/other', 30)]
            db.executemany('INSERT INTO session VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                           [(*r, 0, 10, 2, 1, 100, 3) for r in rows])
            db.commit()
            db.close()
            before = path.read_bytes()
            report = usage.usage_report(path, 20, '/repo', 10)
            self.assertEqual(report['totals']['session_count'], 3)
            self.assertEqual(report['totals']['tokens_input'], 30)
            self.assertEqual(report['totals']['tokens_cache_read'], 300)
            self.assertEqual(report['model_totals']['unknown/unknown/unknown']['tokens_input'], 10)
            self.assertEqual(report['attribution']['discovery_sessions'], 1)
            self.assertTrue(report['cost_status'].startswith('unavailable'))
            empty = usage.usage_report(path, 20, '/missing')
            self.assertEqual(set(empty), set(report))
            self.assertEqual(empty['totals']['session_count'], 0)
            self.assertEqual(before, path.read_bytes())

    def test_model_invalid_json(self):
        for raw in ('[]', 'null', '42', '{broken'):
            self.assertIsNone(usage.parse_model(raw)['id'])


if __name__ == '__main__':
    unittest.main()
