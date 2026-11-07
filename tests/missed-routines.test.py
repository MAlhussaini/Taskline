"""Auto-close missed routines without changing normal tasks or successful history."""
import runpy
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

helpers = runpy.run_path(str(Path(__file__).with_name('star-rules.test.py')))
app, base = helpers['app'], helpers['StarRules']


class MissedRoutines(unittest.TestCase):
    setUp = base.setUp
    tearDown = base.tearDown
    request = base.request
    create = base.create
    update = base.update
    tasks = base.tasks

    def routine(self, workspace='personal', follow=False):
        day = (app.date.today() - timedelta(days=2)).isoformat()
        routine = self.request('POST', '/api/routines', {
            'title': 'Missed routine', 'start_date': day, 'frequency': 'daily',
            'steps': ['First', 'Second'], 'follow_until_complete': follow,
        }, workspace, 201)
        return day, routine

    def test_catchup_flags_family_excludes_overdue_and_preserves_today_future(self):
        for space in ('personal', 'work'):
            for follow in (False, True):
                day, routine = self.routine(space, follow)
                rows = self.tasks(date=day, workspace=space)
                self.assertTrue(all(row['completed'] == row['cancelled'] == row['routine_missed'] == 1 for row in rows))
                for row in rows:
                    self.assertEqual(app.completion_day(row['completed_at'], space, 'Asia/Riyadh'), day)
                self.assertEqual(self.tasks(date=day, workspace=space), rows)
                for target in (app.date.today(), app.date.today() + timedelta(days=3)):
                    self.assertTrue(all(not row['completed'] and not row['routine_missed'] for row in self.tasks(date=target.isoformat(), workspace=space)))
                self.assertFalse(self.request('GET', f'/api/tasks/overdue?before={app.date.today().isoformat()}', workspace=space))

    def test_direct_success_clears_badge_and_corrects_statistics_not_schedule(self):
        day, routine = self.routine()
        rows = self.tasks(date=day)
        root = next(row for row in rows if not row['parent_id'])
        def point():
            return next(row for row in self.request('GET', f"/api/routines/stats?days=7&routine_id={routine['id']}")['points'] if row['date'] == day)
        self.assertEqual(point()['completed'], 0)
        self.update(root['id'], completed=True, cancelled=False)
        after = self.tasks(date=day)
        for before, updated in zip(rows, after):
            self.assertEqual(updated, {**before, 'cancelled': 0, 'routine_missed': 0})
        self.assertEqual(point()['percentage'], 100)
        app.initialize_database()
        self.assertEqual(self.tasks(date=day), after)
        self.request('POST', f"/api/tasks/{root['id']}/archive", {'timezone': 'Asia/Riyadh'})
        self.assertEqual(self.tasks(date=day), after)

    def test_boundary_uses_workspace_settings_timezone_and_clock_not_viewed_date(self):
        # Future fixtures avoid reconciliation against the real clock.
        day = '2035-01-01'
        for space in ('personal', 'work'):
            self.request('POST', '/api/routines', {'title': 'Boundary', 'frequency': 'daily', 'start_date': day}, space, 201)
            self.tasks(date='2035-01-10', workspace=space)
        with app.connect() as db:
            app.close_missed_routines(db, now=datetime(2035, 1, 1, 23, 59, tzinfo=timezone.utc))  # 02:59 Riyadh
            personal = db.execute('SELECT completed FROM tasks WHERE workspace = ? AND task_date = ?', ('personal', day)).fetchone()[0]
            work = db.execute('SELECT completed FROM tasks WHERE workspace = ? AND task_date = ?', ('work', day)).fetchone()[0]
            self.assertEqual((personal, work), (0, 1))
            app.close_missed_routines(db, now=datetime(2035, 1, 2, 0, 0, tzinfo=timezone.utc))
            self.assertEqual(db.execute('SELECT completed FROM tasks WHERE workspace = ? AND task_date = ?', ('personal', day)).fetchone()[0], 1)
            self.assertFalse(db.execute("SELECT COUNT(*) FROM tasks WHERE task_date >= '2035-01-02' AND completed = 1").fetchone()[0])
        self.request('PUT', '/api/settings', {'dayStart': {'personal': 360}})
        with app.connect() as db:
            app.close_missed_routines(db, 'personal', 'America/New_York', datetime(2035, 1, 3, 10, 59, tzinfo=timezone.utc))
            self.assertEqual(db.execute("SELECT completed FROM tasks WHERE workspace='personal' AND task_date='2035-01-02'").fetchone()[0], 0)
            app.close_missed_routines(db, 'personal', 'America/New_York', datetime(2035, 1, 3, 11, 0, tzinfo=timezone.utc))
            self.assertEqual(db.execute("SELECT completed FROM tasks WHERE workspace='personal' AND task_date='2035-01-02'").fetchone()[0], 1)

    def test_successful_steps_normal_tasks_and_manual_children(self):
        day = '2035-02-01'
        self.request('POST', '/api/routines', {'title': 'Family', 'frequency': 'daily', 'start_date': day, 'steps': ['Done step']}, expected=201)
        rows = self.tasks(date=day)
        root = next(row for row in rows if not row['parent_id'])
        manual = self.create(parent_id=root['id'], task_date=day)
        done = next(row for row in rows if row['parent_id'])
        self.update(done['id'], completed=True)
        normal = self.create(task_date=day)
        self.update(root['id'], starred=2)
        before = {row['id']: row for row in self.tasks(date=day)}
        with app.connect() as db:
            app.close_missed_routines(db, now=datetime(2035, 2, 2, 12, tzinfo=timezone.utc))
        after = {row['id']: row for row in self.tasks(date=day)}
        self.assertEqual(after[normal], before[normal])
        self.assertEqual(after[done['id']], before[done['id']])
        self.assertEqual(after[root['id']]['starred'], 1)
        self.assertTrue(after[root['id']]['routine_missed'] and after[manual]['routine_missed'])
        # Correcting the last missed child also restores the auto-missed parent.
        self.update(manual, completed=True, cancelled=False)
        updated = {row['id']: row for row in self.tasks(date=day)}
        self.assertEqual((updated[root['id']]['completed'], updated[root['id']]['cancelled'], updated[root['id']]['routine_missed']), (1, 0, 0))

    def test_invalid_timezone_is_rejected_before_reconciliation(self):
        self.request('GET', '/api/tasks?date=2026-01-01&timezone=Not/AZone', expected=400)

    def test_reopen_recloses_missed_and_legacy_completion_corrects_it(self):
        day, _ = self.routine()
        root = next(row for row in self.tasks(date=day) if not row['parent_id'])
        self.update(root['id'], completed=False)
        rows = self.tasks(date=day)
        self.assertTrue(all(row['completed'] and row['cancelled'] and row['routine_missed'] for row in rows))
        self.request('POST', f"/api/tasks/{root['id']}/overdue-action", {
            'action': 'complete', 'original_date': day, 'timezone': 'Asia/Riyadh',
        })
        self.assertTrue(all(row['completed'] and not row['cancelled'] and not row['routine_missed'] for row in self.tasks(date=day)))

    def test_missed_marker_survives_move_and_pause_but_not_success(self):
        day, routine = self.routine()
        root = next(row for row in self.tasks(date=day) if not row['parent_id'])
        today = app.date.today().isoformat()
        self.update(root['id'], task_date=today)
        moved = next(row for row in self.tasks(date=today) if row['id'] == root['id'])
        self.assertTrue(moved['routine_missed'] and moved['cancelled'])
        self.update(root['id'], completed=True, cancelled=False)
        self.assertFalse(next(row for row in self.tasks(date=today) if row['id'] == root['id'])['routine_missed'])
        self.request('PUT', f"/api/routines/{routine['id']}", {'active': False})
        self.assertTrue(all(row['routine_missed'] for row in self.tasks(date=(app.date.today() - timedelta(days=1)).isoformat())))


del base, helpers
if __name__ == '__main__':
    unittest.main()
