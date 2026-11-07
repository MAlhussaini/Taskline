"""Shared settings API regressions; temporary SQLite only."""
import concurrent.futures
import runpy
import unittest
from pathlib import Path

helpers = runpy.run_path(str(Path(__file__).with_name('star-rules.test.py')))
app = helpers['app']
base = helpers['StarRules']


class SettingsTests(unittest.TestCase):
    setUp = base.setUp
    tearDown = base.tearDown
    request = base.request

    def test_defaults_catalog_and_persistence_across_devices(self):
        result = self.request('GET', '/api/settings')
        self.assertEqual(len(result['catalog']), 24)
        self.assertTrue(all(result['settings']['features'].values()))
        self.assertEqual(result['settings']['dayStart'], {'personal': 180, 'work': 0})
        changed = self.request('PUT', '/api/settings', {'features': {'stars': False}, 'dayStart': {'work': 90}})
        self.assertFalse(changed['settings']['features']['stars'])
        self.assertTrue(changed['settings']['features']['taskOfDay'])
        app.initialize_database()
        self.assertEqual(self.request('GET', '/api/settings', workspace='work'), changed)

    def test_invalid_changes_are_atomic(self):
        before = self.request('GET', '/api/settings')
        for patch in [[], {'unknown': True}, {'features': {'stars': 0}},
                      {'features': {'gamification': True}}, {'features': []},
                      {'dayStart': {'work': -1}}, {'dayStart': {'work': 1440}},
                      {'dayStart': {'work': True}}, {'dayStart': {'personal': '03:00'}},
                      {'footer': ['day', 'inbox', 'settings', 'routines', 'lists']},
                      {'footer': ['none', 'day', 'day', 'none', 'none']},
                      {'footer': ['settings', 'settings', 'day', 'none', 'none']},
                      {'features': {'stars': False}, 'footer': ['day']},
                      {'footer': ['settings', {}, 'day', 'none', 'none']}]:
            self.request('PUT', '/api/settings', patch, expected=400)
            self.assertEqual(self.request('GET', '/api/settings'), before)
        result = self.request('PUT', '/api/settings', {'footer': ['none', 'none', 'day', 'none', 'none']})
        self.assertEqual(result['settings']['footer'][2], 'day')

    def test_concurrent_partial_saves_preserve_unrelated_preferences(self):
        with concurrent.futures.ThreadPoolExecutor() as pool:
            list(pool.map(lambda key: self.request('PUT', '/api/settings', {'features': {key: False}}), ['stars', 'labels', 'lists', 'routines']))
        features = self.request('GET', '/api/settings')['settings']['features']
        for key in ['stars', 'labels', 'lists', 'routines']:
            self.assertFalse(features[key])
        self.assertTrue(features['subtasks'])

    def test_disabling_features_never_mutates_existing_data(self):
        parent = self.request('POST', '/api/tasks', {'title': 'Parent', 'task_date': '2026-10-11'}, expected=201)
        self.request('POST', '/api/tasks', {'title': 'Child', 'parent_id': parent['id'], 'task_date': '2026-10-11'}, expected=201)
        with app.connect() as db:
            before = [tuple(row) for row in db.execute('SELECT * FROM tasks ORDER BY id')]
        self.request('PUT', '/api/settings', {'features': {key: False for key in app.default_settings()['features']}})
        with app.connect() as db:
            self.assertEqual([tuple(row) for row in db.execute('SELECT * FROM tasks ORDER BY id')], before)

    def test_archive_uses_configured_boundary_to_the_minute(self):
        self.request('PUT', '/api/settings', {'dayStart': {'personal': 270, 'work': 60}})
        for workspace, completed, expected_day in [
            ('personal', '2026-10-11 01:29:00', '2026-10-10'),
            ('personal', '2026-10-11 01:30:00', '2026-10-11'),
            ('work', '2026-10-10 21:59:00', '2026-10-10'),
            ('work', '2026-10-10 22:00:00', '2026-10-11')]:
            task = self.request('POST', '/api/tasks', {'title': 'Archive me', 'location': 'inbox'}, workspace=workspace, expected=201)
            with app.connect() as db:
                db.execute('UPDATE tasks SET completed = 1, completed_at = ? WHERE id = ?', (completed, task['id']))
            self.request('POST', f"/api/tasks/{task['id']}/archive", {'timezone': 'Asia/Riyadh'}, workspace=workspace)
            with app.connect() as db:
                row = db.execute('SELECT task_date, completed_at FROM tasks WHERE id = ?', (task['id'],)).fetchone()
                self.assertEqual(tuple(row), (expected_day, completed))


del base, helpers  # Do not rediscover the imported star suite a second time.

if __name__ == '__main__':
    unittest.main()
