"""Calendar count regressions using an isolated SQLite database and real HTTP."""
import runpy
import unittest
from datetime import timedelta
from pathlib import Path

helpers = runpy.run_path(str(Path(__file__).with_name('star-rules.test.py')))
app, base = helpers['app'], helpers['StarRules']


class CalendarRoutines(unittest.TestCase):
    setUp = base.setUp
    tearDown = base.tearDown
    request = base.request
    create = base.create
    update = base.update
    tasks = base.tasks

    def test_routine_counts_and_manual_children_in_both_workspaces(self):
        today = app.date.today()
        days = [(today + timedelta(days=offset)).isoformat() for offset in (-1, 0, 1)]
        for workspace in ('personal', 'work'):
            self.request('POST', '/api/routines', {
                'title': 'Calendar routine', 'start_date': days[0],
                'frequency': 'daily', 'steps': ['Generated step'],
            }, workspace, 201)
            for day in days:
                rows = self.tasks(date=day, workspace=workspace)
                parent = next(row for row in rows if row['parent_id'] is None)
                self.create(parent_id=parent['id'], task_date=day, workspace=workspace)
            summaries = self.request('GET', f'/api/task-days?through={days[-1]}', workspace=workspace)
            for day in days:
                summary = next(row for row in summaries if row['task_date'] == day)
                self.assertEqual((summary['task_count'], summary['incomplete_count'], summary['ordinary_incomplete_count']), (3, 0 if day < days[1] else 3, 0))
                self.assertEqual(summary['missed_count'], 3 if day < days[1] else 0)
                self.assertEqual(summary['ordinary_task_count'], 0)

            normal = self.create(task_date=days[0], workspace=workspace)
            self.create(parent_id=normal, task_date=days[0], workspace=workspace)
            self.create(task_date=days[0], location='inbox', workspace=workspace)
            def summary():
                return next(row for row in self.request('GET', f'/api/task-days?through={days[-1]}', workspace=workspace) if row['task_date'] == days[0])
            self.assertEqual(summary()['ordinary_incomplete_count'], 2)
            self.assertEqual(summary()['ordinary_task_count'], 2)
            self.update(normal, completed=True, workspace=workspace)
            self.assertEqual(summary()['ordinary_incomplete_count'], 0)
            self.assertEqual(summary()['incomplete_count'], 0)
            self.assertEqual(summary()['missed_count'], 3)
            root = next(row for row in self.tasks(date=days[0], workspace=workspace) if row['routine_occurrence_id'] and not row['parent_id'])
            self.update(root['id'], completed=True, workspace=workspace)
            self.assertEqual(summary()['incomplete_count'], 0)
            self.assertEqual(summary()['task_count'], 5)

    def test_workspace_isolation_and_empty_dates(self):
        self.create(task_date='2026-10-01')
        self.assertEqual(self.request('GET', '/api/task-days?through=2026-10-02', workspace='work'), [])
        self.assertEqual(self.request('GET', '/api/task-days?through=2026-10-02'), [
            {'task_date': '2026-10-01', 'task_count': 1, 'incomplete_count': 1, 'ordinary_incomplete_count': 1, 'ordinary_task_count': 1, 'missed_count': 0},
        ])


del base, helpers
if __name__ == '__main__':
    unittest.main()
