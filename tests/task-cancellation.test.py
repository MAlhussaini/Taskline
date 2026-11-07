"""Persistent cancelled completion, using real HTTP and a temporary database."""
import runpy
import unittest
from pathlib import Path

helpers = runpy.run_path(str(Path(__file__).with_name('star-rules.test.py')))
app, base = helpers['app'], helpers['StarRules']


class TaskCancellation(unittest.TestCase):
    setUp = base.setUp
    tearDown = base.tearDown
    request = base.request
    create = base.create
    update = base.update
    tasks = base.tasks

    def test_existing_database_migration_preserves_all_old_task_fields(self):
        parent = self.create()
        self.create(parent_id=parent)
        self.update(parent, completed=True)
        with app.connect() as db:
            # Reconstruct the previous schema in this test's temporary DB only.
            db.execute('ALTER TABLE tasks DROP COLUMN cancelled')
            columns = [row[1] for row in db.execute('PRAGMA table_info(tasks)')]
            projection = ', '.join(columns)
            before = [tuple(row) for row in db.execute(f'SELECT {projection} FROM tasks ORDER BY id')]
        app.initialize_database()
        with app.connect() as db:
            after = [tuple(row) for row in db.execute(f'SELECT {projection} FROM tasks ORDER BY id')]
            self.assertEqual(after, before)
            self.assertTrue(all(row[0] == 0 for row in db.execute('SELECT cancelled FROM tasks')))

    def test_persistent_completion_reopen_star_capacity_and_archive(self):
        for space in ('personal', 'work'):
            task = self.create(workspace=space)
            self.update(task, starred=2, label='Keep me', workspace=space)
            cancelled = self.update(task, cancelled=True, workspace=space)
            self.assertEqual((cancelled['completed'], cancelled['cancelled'], cancelled['starred']), (1, 1, 1))
            self.assertIsNotNone(cancelled['completed_at'])
            self.assertEqual(self.tasks(workspace=space)[0], cancelled)
            self.assertEqual(self.update(task, cancelled=True, workspace=space), cancelled)
            self.assertFalse(self.request('GET', '/api/tasks/overdue?before=2026-09-24', workspace=space))
            self.assertEqual(self.update(task, title='Edited cancelled task', workspace=space)['cancelled'], 1)
            self.request('POST', f'/api/tasks/{task}/archive', {'timezone': 'Asia/Riyadh'}, space)
            with app.connect() as db:
                row = db.execute('SELECT * FROM tasks WHERE id = ?', (task,)).fetchone()
                self.assertEqual(row['cancelled'], 1)
                self.assertEqual(row['label'], 'Keep me')
            self.update(task, task_date='2026-09-23', workspace=space)
            for _ in range(3):
                self.update(self.create(workspace=space), starred=1, workspace=space)
            reopened = self.update(task, completed=False, workspace=space)
            self.assertEqual((reopened['completed'], reopened['cancelled'], reopened['starred'], reopened['completed_at']), (0, 0, 0, None))
            normal = self.update(task, completed=True, workspace=space)
            self.assertEqual((normal['completed'], normal['cancelled']), (1, 0))

    def test_cancel_parent_keeps_already_completed_children_and_reopens_family(self):
        parent = self.create()
        done, pending = self.create(parent_id=parent), self.create(parent_id=parent)
        done_before = self.update(done, completed=True)
        self.update(parent, cancelled=True)
        rows = {row['id']: row for row in self.tasks()}
        self.assertEqual([rows[key]['cancelled'] for key in (parent, done, pending)], [1, 0, 1])
        self.assertTrue(all(row['completed'] for row in rows.values()))
        self.assertEqual(rows[done]['completed_at'], done_before['completed_at'])
        app.initialize_database()
        self.assertEqual({row['id']: row for row in self.tasks()}, rows)
        self.update(parent, completed=False)
        self.assertTrue(all(not row['completed'] and not row['cancelled'] for row in self.tasks()))
        self.update(parent, cancelled=True)
        self.create(parent_id=parent)
        root = next(row for row in self.tasks() if row['id'] == parent)
        self.assertEqual((root['completed'], root['cancelled']), (0, 0))

    def test_child_completion_syncs_parent_and_cancel_is_not_delete(self):
        parent = self.create()
        first, second = self.create(parent_id=parent), self.create(parent_id=parent)
        self.update(first, cancelled=True)
        self.assertFalse(next(row for row in self.tasks() if row['id'] == parent)['completed'])
        self.update(second, cancelled=True)
        self.assertTrue(all(row['cancelled'] and row['completed'] for row in self.tasks()))
        self.update(first, completed=False)
        self.update(first, completed=True)
        rows = {row['id']: row for row in self.tasks()}
        self.assertEqual((rows[parent]['completed'], rows[parent]['cancelled']), (1, 0))
        self.assertEqual(rows[second]['cancelled'], 1)
        app.initialize_database()
        self.assertEqual({row['id']: row for row in self.tasks()}, rows)
        self.request('DELETE', f'/api/tasks/{parent}')
        remaining = self.tasks()
        self.assertEqual({row['id'] for row in remaining}, {first, second})
        self.assertTrue(all(row['parent_id'] is None for row in remaining))

    def test_validation_and_workspace_isolation(self):
        task = self.create()
        self.update(task, cancelled=True, workspace='work', expected=404)
        for payload in ({'cancelled': 1}, {'cancelled': 'true'}, {'cancelled': True, 'completed': False}, {'cancelled': False}):
            self.update(task, **payload, expected=400)
        self.assertFalse(self.tasks()[0]['completed'])
        self.assertFalse(self.tasks()[0]['cancelled'])

    def test_direct_conversion_to_normal_completion_preserves_time_and_position(self):
        for space in ('personal', 'work'):
            parent = self.create(workspace=space)
            child = self.create(parent_id=parent, workspace=space)
            self.update(parent, starred=2, workspace=space)
            self.update(parent, cancelled=True, workspace=space)
            before = {row['id']: row for row in self.tasks(workspace=space)}
            result = self.update(parent, completed=True, cancelled=False, workspace=space)
            self.assertEqual((result['completed'], result['cancelled']), (1, 0))
            after = {row['id']: row for row in self.tasks(workspace=space)}
            for task_id in (parent, child):
                self.assertEqual(after[task_id], {**before[task_id], 'cancelled': 0})
            self.assertEqual(self.update(parent, completed=True, cancelled=False, workspace=space), result)
            app.initialize_database()
            self.assertEqual({row['id']: row for row in self.tasks(workspace=space)}, after)

    def test_routine_cancellation_only_closes_one_occurrence(self):
        day = app.date.today().isoformat()
        self.request('POST', '/api/routines', {'title': 'Recurring', 'frequency': 'daily', 'start_date': day, 'steps': ['Step']}, expected=201)
        root = next(row for row in self.tasks(date=day) if not row['parent_id'])
        self.update(root['id'], cancelled=True)
        self.assertTrue(all(row['completed'] and row['cancelled'] for row in self.tasks(date=day)))
        summary = next(row for row in self.request('GET', f'/api/task-days?through={day}') if row['task_date'] == day)
        self.assertEqual(summary['incomplete_count'], 0)
        tomorrow = (app.date.today() + app.timedelta(days=1)).isoformat()
        self.assertTrue(all(not row['completed'] and not row['cancelled'] for row in self.tasks(date=tomorrow)))


del base, helpers
if __name__ == '__main__':
    unittest.main()
