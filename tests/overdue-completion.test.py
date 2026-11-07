"""Retrospective completion API tests, using only temporary SQLite databases."""
import concurrent.futures
import runpy
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

helpers = runpy.run_path(str(Path(__file__).with_name('star-rules.test.py')))
app = helpers['app']
base = helpers['StarRules']


class OverdueCompletion(unittest.TestCase):
    setUp = base.setUp
    tearDown = base.tearDown
    request = base.request
    create = base.create
    update = base.update
    tasks = base.tasks

    def complete(self, task_id, workspace='personal', expected=200, **payload):
        return self.request('POST', f'/api/tasks/{task_id}/overdue-action',
                            {'action': 'complete', 'timezone': 'Asia/Riyadh', **payload}, workspace, expected)

    def test_family_completion_preserves_dates_positions_metadata_and_done_children(self):
        parent = self.create(label='Home', label_color='green')
        first, second = self.create(parent_id=parent), self.create(parent_id=parent)
        self.update(first, completed=True)
        self.update(parent, starred=2)
        before = {task['id']: task for task in self.tasks()}
        result = self.complete(parent, original_date='2026-09-23')
        self.assertEqual(result['task_date'], '2026-09-23')
        after = {task['id']: task for task in self.tasks()}
        for task_id in (parent, first, second):
            self.assertTrue(after[task_id]['completed'])
            for field in ('task_date', 'location', 'position', 'label', 'label_color', 'parent_id', 'planning_kind', 'planning_value'):
                self.assertEqual(after[task_id][field], before[task_id][field])
        self.assertEqual(after[first]['completed_at'], before[first]['completed_at'])
        self.assertEqual(after[parent]['completed_at'], '2026-09-23 00:00:00')
        self.assertEqual(after[second]['completed_at'], after[parent]['completed_at'])
        self.assertEqual(after[parent]['starred'], 1)
        self.assertFalse(self.request('GET', '/api/tasks/overdue?before=2026-09-24'))
        status = self.request('GET', '/api/task-days?through=2026-09-24')[0]
        self.assertEqual(status['incomplete_count'], 0)
        self.request('POST', f'/api/tasks/{parent}/archive', {'timezone': 'Asia/Riyadh'})
        self.assertEqual({task['id']: task for task in self.tasks()}, after)
        # Completing in the past frees a priority slot; reopening uses the usual limits.
        for _ in range(3):
            self.update(self.create(), starred=1)
        self.assertEqual(self.update(parent, completed=False)['starred'], 0)

    def test_custom_boundaries_workspaces_and_retries(self):
        self.request('PUT', '/api/settings', {'dayStart': {'personal': 270, 'work': 0}})
        for workspace, expected_stamp in [('personal', '2026-09-23 01:30:00'), ('work', '2026-09-22 21:00:00')]:
            task = self.create(workspace=workspace)
            self.complete(task, workspace)
            row = self.tasks(workspace=workspace)[0]
            self.assertEqual(row['completed_at'], expected_stamp)
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                list(pool.map(lambda _: self.complete(task, workspace), range(3)))
            self.assertEqual(self.tasks(workspace=workspace)[0], row)
            archived = self.request('POST', f'/api/tasks/{task}/archive', {'timezone': 'Asia/Riyadh'}, workspace)
            self.assertEqual(archived['task_date'], '2026-09-23')

    def test_invalid_and_stale_requests_do_not_change_tasks(self):
        past = self.create()
        inbox = self.create(location='inbox')
        today = app.completion_day(datetime.now(timezone.utc).isoformat(), 'personal', 'Asia/Riyadh')
        current = self.create(task_date=today)
        self.complete(past, workspace='work', expected=404)
        self.complete(past, timezone='Not/AZone', expected=400)
        self.complete(past, original_date='2026-09-22', expected=400)
        self.complete(inbox, expected=400)
        self.complete(current, target_date='2999-01-01', expected=400)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM tasks WHERE completed = 1').fetchone()[0], 0)
        self.request('POST', f'/api/tasks/{past}/overdue-action', {'action': 'today', 'target_date': today})
        self.complete(past, original_date='2026-09-23', expected=400)

    def test_carried_task_stays_in_the_date_displayed_in_overdue(self):
        task = self.create(task_date='2026-09-20')
        self.request('POST', f'/api/tasks/{task}/overdue-action', {'action': 'today', 'target_date': '2026-09-23'})
        self.complete(task, original_date='2026-09-23')
        row = self.tasks()[0]
        self.assertEqual(row['carried_from_date'], '2026-09-20')
        self.assertEqual(row['task_date'], '2026-09-23')
        self.assertEqual(app.completion_day(row['completed_at'], 'personal', 'Asia/Riyadh'), '2026-09-23')

    def test_routine_completes_only_one_occurrence_and_updates_original_day_statistics(self):
        old_day = (app.date.today() - timedelta(days=2)).isoformat()
        routine = self.request('POST', '/api/routines', {'title': 'Follow-up routine', 'start_date': old_day,
                               'frequency': 'daily', 'follow_until_complete': True, 'steps': ['Step']}, expected=201)
        rows = self.tasks(date=old_day)
        parent = next(row for row in rows if not row['parent_id'])
        self.assertTrue(parent['routine_missed'] and parent['cancelled'])
        self.update(parent['id'], completed=True, cancelled=False)
        self.assertTrue(all(row['completed'] for row in self.tasks(date=old_day)))
        self.assertTrue(all(not row['completed'] for row in self.tasks(date=app.date.today().isoformat())))
        points = self.request('GET', f"/api/routines/stats?days=7&routine_id={routine['id']}")['points']
        point = next(point for point in points if point['date'] == old_day)
        self.assertEqual((point['scheduled'], point['completed'], point['percentage']), (1, 1, 100))

    def test_date_anchor_roundtrips_in_time_zones_and_custom_boundaries(self):
        for zone in ('Asia/Riyadh', 'America/New_York', 'Pacific/Auckland'):
            for day in ('2026-03-08', '2026-11-01', '2026-09-23'):
                for boundary in (0, 150, 180, 1439):
                    stamp = app.completion_stamp_for_day(day, zone, boundary)
                    self.assertEqual(app.completion_day(stamp, 'personal', zone, boundary), day)


del base, helpers
if __name__ == '__main__':
    unittest.main()
