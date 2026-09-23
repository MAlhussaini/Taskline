"""Real HTTP regressions for stars, completion and archiving; temporary SQLite only."""
import concurrent.futures
import importlib.util
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("taskline_stars", ROOT / "app.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class StarRules(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="taskline-stars-")
        app.DB_PATH = Path(self.temporary.name) / "test.db"
        app.UPLOAD_DIR = Path(self.temporary.name) / "uploads"
        app.initialize_database()

        class QuietHandler(app.TodoHandler):
            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def request(self, method, path, payload=None, workspace="personal", expected=200):
        separator = "&" if "?" in path else "?"
        req = urllib.request.Request(
            f"{self.origin}{path}{separator}workspace={workspace}",
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Content-Type": "application/json"}, method=method,
        )
        try:
            response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            data = json.load(response)
            if expected is not None:
                self.assertEqual(response.status, expected, data)
            return data if expected is not None else (response.status, data)

    def create(self, **fields):
        workspace = fields.pop("workspace", "personal")
        return self.request("POST", "/api/tasks", {"title": "Test task", "task_date": "2026-09-23", **fields}, workspace, 201)["id"]

    def update(self, task_id, expected=200, workspace="personal", **fields):
        return self.request("PUT", f"/api/tasks/{task_id}", fields, workspace, expected)

    def tasks(self, **scope):
        workspace = scope.pop("workspace", "personal")
        query = {"location": "day", "date": "2026-09-23", **scope}
        return self.request("GET", "/api/tasks?" + urllib.parse.urlencode(query), workspace=workspace)

    def test_red_counts_within_three_and_one_red_only(self):
        ids = [self.create() for _ in range(4)]
        self.update(ids[0], starred=2)
        self.update(ids[1], starred=True)  # Legacy clients remain compatible.
        self.update(ids[2], starred=1)
        self.update(ids[3], starred=1, expected=400)
        self.update(ids[1], starred=2, expected=400)
        self.assertEqual([task["starred"] for task in self.tasks()], [2, 1, 1, 0])
        self.update(ids[0], starred=0)
        self.update(ids[1], starred=2)
        self.update(ids[3], starred=1)

    def test_completion_frees_slot_and_restores_yellow(self):
        first, second = self.create(), self.create()
        self.update(first, starred=2)
        done = self.update(first, completed=True)
        self.assertEqual(done["starred"], 1)
        self.update(second, starred=2)
        restored = self.update(first, completed=False)
        self.assertEqual((restored["completed"], restored["starred"]), (0, 1))
        self.update(first, completed=True)
        self.update(first, starred=2, expected=400)

    def test_restoration_at_capacity_succeeds_without_star(self):
        first = self.create()
        self.update(first, starred=1)
        self.update(first, completed=True)
        for _ in range(3):
            self.update(self.create(), starred=1)
        restored = self.update(first, completed=False)
        self.assertEqual((restored["completed"], restored["starred"]), (0, 0))
        self.assertEqual(sum(bool(task["starred"]) for task in self.tasks()), 3)

    def test_parent_and_children_completion_obey_limits(self):
        parent = self.create()
        children = [self.create(parent_id=parent) for _ in range(2)]
        for task in [parent, *children]:
            self.update(task, starred=1)
        self.update(parent, starred=2)
        for child in children:
            self.update(child, completed=True)
        self.assertTrue(all(task["completed"] for task in self.tasks()))
        newcomer = self.create()
        self.update(newcomer, starred=2)
        self.update(parent, completed=False)
        rows = {task["id"]: task for task in self.tasks()}
        self.assertTrue(all(not task["completed"] for task in rows.values()))
        self.assertEqual(rows[newcomer]["starred"], 2)
        self.assertEqual(rows[parent]["starred"], 1)
        self.assertEqual(sum(bool(task["starred"]) for task in rows.values()), 3)

    def test_new_subtask_reopens_parent_without_exceeding_capacity(self):
        parent = self.create()
        self.update(parent, starred=2)
        self.update(parent, completed=True)
        for _ in range(3):
            self.update(self.create(), starred=1)
        child = self.create(parent_id=parent)
        rows = {task["id"]: task for task in self.tasks()}
        self.assertEqual(rows[child]["parent_id"], parent)
        self.assertEqual((rows[parent]["completed"], rows[parent]["starred"], rows[parent]["completed_at"]), (0, 0, None))

    def test_scope_is_independent_and_moving_respects_destination(self):
        for _ in range(3):
            self.update(self.create(), starred=1)
        other_day = self.create(task_date="2026-09-24")
        self.update(other_day, starred=2)
        moved = self.update(other_day, task_date="2026-09-23")
        self.assertEqual(moved["starred"], 0)
        inbox = self.create(location="inbox")
        self.update(inbox, starred=2)
        work = self.create(workspace="work")
        self.update(work, workspace="work", starred=2)
        self.assertEqual(self.tasks(workspace="work")[0]["starred"], 2)

    def test_deleting_incomplete_child_downgrades_completed_red_parent(self):
        parent = self.create()
        first, second = self.create(parent_id=parent), self.create(parent_id=parent)
        self.update(parent, starred=2)
        self.update(first, completed=True)
        self.request("DELETE", f"/api/tasks/{second}")
        parent_row = next(task for task in self.tasks() if task["id"] == parent)
        self.assertEqual((parent_row["completed"], parent_row["starred"]), (1, 1))

    def test_concurrent_requests_do_not_exceed_limits(self):
        ids = [self.create() for _ in range(4)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(lambda task: self.update(task, starred=1, expected=None)[0], ids))
        self.assertEqual(sorted(statuses), [200, 200, 200, 400])
        starred = [task["id"] for task in self.tasks() if task["starred"]]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            statuses = list(pool.map(lambda task: self.update(task, starred=2, expected=None)[0], starred))
        self.assertEqual(sorted(statuses), [200, 400, 400])

    def test_completion_day_boundaries(self):
        for stamp, workspace, expected in [
            ("2026-09-23 23:59:59", "personal", "2026-09-23"),
            ("2026-09-24 00:00:00", "personal", "2026-09-24"),
            ("2026-09-23 20:59:59", "work", "2026-09-23"),
            ("2026-09-23 21:00:00", "work", "2026-09-24"),
        ]:
            self.assertEqual(app.completion_day(stamp, workspace, "Asia/Riyadh"), expected)
        self.assertEqual(app.completion_day("2026-09-24T01:00:00+03:00", "personal", "Asia/Riyadh"), "2026-09-23")

    def test_archive_family_retains_completion_times_and_is_idempotent(self):
        parent = self.create(location="inbox", label="test")
        child = self.create(parent_id=parent)
        self.update(parent, completed=True)
        with app.connect() as db:
            db.execute("UPDATE tasks SET completed_at = '2026-09-24 00:00:00' WHERE id = ?", (parent,))
            db.execute("UPDATE tasks SET completed_at = '2026-09-23 22:00:00' WHERE id = ?", (child,))
        result = self.request("POST", f"/api/tasks/{child}/archive", {"timezone": "Asia/Riyadh"})
        self.assertEqual(result["task_date"], "2026-09-24")
        self.assertEqual(result["task_ids"], [parent, child])
        self.assertEqual(self.tasks(location="inbox"), [])
        archived = self.tasks(date="2026-09-24")
        self.assertEqual([task["completed_at"] for task in archived], ["2026-09-24 00:00:00", "2026-09-23 22:00:00"])
        self.assertEqual(archived[1]["parent_id"], parent)
        self.assertTrue(all(task["completed"] for task in archived))
        self.request("POST", f"/api/tasks/{parent}/archive", {"timezone": "Asia/Riyadh"})
        self.assertEqual(self.tasks(date="2026-09-24"), archived)

    def test_archive_rejects_incomplete_family_missing_time_and_wrong_workspace(self):
        parent = self.create(location="inbox")
        child = self.create(parent_id=parent)
        self.create(parent_id=parent)
        self.update(child, completed=True)
        self.request("POST", f"/api/tasks/{child}/archive", {}, expected=400)
        self.assertEqual(len(self.tasks(location="inbox")), 3)
        self.update(parent, completed=True)
        self.request("POST", f"/api/tasks/{parent}/archive", {}, workspace="work", expected=404)
        self.request("POST", f"/api/tasks/{parent}/archive", {"timezone": "Not/AZone"}, expected=400)
        with app.connect() as db:
            db.execute("UPDATE tasks SET completed_at = NULL WHERE id = ?", (parent,))
        self.request("POST", f"/api/tasks/{parent}/archive", {}, expected=400)

    def test_archive_work_uses_midnight_and_moves_existing_day_task(self):
        task = self.create(workspace="work", task_date="2026-09-01")
        self.update(task, workspace="work", completed=True)
        with app.connect() as db:
            db.execute("UPDATE tasks SET completed_at = '2026-09-23 22:00:00' WHERE id = ?", (task,))
        result = self.request("POST", f"/api/tasks/{task}/archive", {"timezone": "Asia/Riyadh"}, workspace="work")
        self.assertEqual(result["task_date"], "2026-09-24")
        self.assertEqual(self.tasks(workspace="work", date="2026-09-24")[0]["id"], task)
        self.assertEqual(self.tasks(workspace="work", date="2026-09-01"), [])


if __name__ == "__main__":
    unittest.main()
