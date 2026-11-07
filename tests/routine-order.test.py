"""Routine order persists per workspace and rejects stale or invalid lists."""
import runpy
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

helpers = runpy.run_path(str(Path(__file__).with_name('star-rules.test.py')))
app, base = helpers['app'], helpers['StarRules']


class RoutineOrderTests(unittest.TestCase):
    setUp = base.setUp
    tearDown = base.tearDown
    request = base.request

    def test_order_persists_and_is_scoped(self):
        payload = {'title': 'Routine', 'start_date': '2030-01-01', 'frequency': 'daily'}
        ids = [self.request('POST', '/api/routines', payload, expected=201)['id'] for _ in range(3)]
        other = self.request('POST', '/api/routines', payload, workspace='work', expected=201)['id']
        ordered = [ids[0], ids[2], ids[1]]
        self.request('PUT', '/api/routines/reorder', {'ids': ordered})
        app.initialize_database()
        self.assertEqual([row['id'] for row in self.request('GET', '/api/routines')], ordered)
        self.assertEqual([row['id'] for row in self.request('GET', '/api/routines', workspace='work')], [other])
        for invalid in (ordered[:-1], [ids[0], ids[0], ids[1]], [ids[0], ids[1], other], [True], 'bad'):
            self.request('PUT', '/api/routines/reorder', {'ids': invalid}, expected=400)
            self.assertEqual([row['id'] for row in self.request('GET', '/api/routines')], ordered)

    def test_added_day_tasks_go_before_routines_and_children_stay_attached(self):
        for space in ('personal', 'work'):
            self.request('POST', '/api/routines', {'title': 'Routine', 'start_date': '2030-01-01', 'frequency': 'daily', 'steps': ['Step']}, workspace=space, expected=201)
            query = '/api/tasks?date=2030-01-01&location=day'
            routine_tasks = self.request('GET', query, workspace=space)
            root = next(task for task in routine_tasks if task['parent_id'] is None)
            for title in ('New first', 'New second'):
                self.request('POST', '/api/tasks', {'title': title, 'task_date': '2030-01-01'}, workspace=space, expected=201)
            tasks = self.request('GET', query, workspace=space)
            self.assertEqual([task['title'] for task in tasks], ['New first', 'New second', 'Routine', 'Step'])
            self.request('POST', '/api/tasks', {'title': 'New step', 'parent_id': root['id']}, workspace=space, expected=201)
            tasks = self.request('GET', query, workspace=space)
            self.assertEqual([task['title'] for task in tasks], ['New first', 'New second', 'Routine', 'Step', 'New step'])
            self.assertEqual(tasks[-1]['parent_id'], root['id'])
            self.assertEqual(len({task['position'] for task in tasks}), len(tasks))

    def test_future_occurrences_follow_order_without_rearranging_other_tasks(self):
        for space in ('personal', 'work'):
            with app.connect() as db:
                start = date.fromisoformat(app.completion_day(datetime.now(timezone.utc).isoformat(), space, 'Asia/Riyadh', app.read_settings(db)['dayStart'][space]))
            tomorrow = (start + timedelta(days=1)).isoformat()
            later = (start + timedelta(days=2)).isoformat()
            ids = []
            for name in ('First', 'Second', 'Third'):
                routine = self.request('POST', '/api/routines', {'title': name, 'start_date': start.isoformat(), 'frequency': 'daily', 'steps': [name + ' step']}, workspace=space, expected=201)
                ids.append(routine['id'])
            query = f'/api/tasks?date={tomorrow}&location=day'
            self.request('GET', query, workspace=space)
            ordinary = self.request('POST', '/api/tasks', {'title': 'Ordinary', 'task_date': tomorrow}, workspace=space, expected=201)
            rows = self.request('GET', query, workspace=space)
            root_ids = [row['id'] for row in rows if row['parent_id'] is None and row['id'] != ordinary['id']]
            child_ids = [row['id'] for row in rows if row['parent_id'] is not None]
            self.request('PUT', '/api/tasks/reorder', {'ids': [root_ids[0], child_ids[0], ordinary['id'], *root_ids[1:], *child_ids[1:]], 'task_date': tomorrow, 'location': 'day'}, workspace=space)
            with app.connect() as db:
                today_before = [tuple(row) for row in db.execute('SELECT id, position FROM tasks WHERE workspace = ? AND task_date = ? ORDER BY id', (space, start.isoformat()))]
                ordinary_position = db.execute('SELECT position FROM tasks WHERE id = ?', (ordinary['id'],)).fetchone()[0]
                children_before = [tuple(row) for row in db.execute('SELECT id, parent_id, position FROM tasks WHERE workspace = ? AND task_date = ? AND parent_id IS NOT NULL ORDER BY id', (space, tomorrow))]
            self.request('PUT', '/api/routines/reorder', {'ids': ids}, workspace=space)
            for day in (tomorrow, later):
                tasks = self.request('GET', f'/api/tasks?date={day}&location=day', workspace=space)
                self.assertEqual([task['title'] for task in tasks if task['parent_id'] is None and task['routine_occurrence_id']], ['First', 'Second', 'Third'])
            with app.connect() as db:
                self.assertEqual([tuple(row) for row in db.execute('SELECT id, position FROM tasks WHERE workspace = ? AND task_date = ? ORDER BY id', (space, start.isoformat()))], today_before)
                self.assertEqual(db.execute('SELECT position FROM tasks WHERE id = ?', (ordinary['id'],)).fetchone()[0], ordinary_position)
                self.assertEqual([tuple(row) for row in db.execute('SELECT id, parent_id, position FROM tasks WHERE workspace = ? AND task_date = ? AND parent_id IS NOT NULL ORDER BY id', (space, tomorrow))], children_before)
            self.request('PUT', '/api/routines/reorder', {'ids': ids[::-1]}, workspace=space)
            tasks = self.request('GET', query, workspace=space)
            self.assertEqual([task['title'] for task in tasks if task['parent_id'] is None and task['routine_occurrence_id']], ['Third', 'Second', 'First'])
            self.request('POST', '/api/routines', {'title': 'New', 'start_date': tomorrow, 'frequency': 'daily'}, workspace=space, expected=201)
            tasks = self.request('GET', query, workspace=space)
            self.assertEqual([task['title'] for task in tasks if task['parent_id'] is None and task['routine_occurrence_id']], ['Third', 'Second', 'First', 'New'])


del base, helpers
if __name__ == '__main__':
    unittest.main()
