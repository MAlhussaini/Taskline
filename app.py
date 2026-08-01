from __future__ import annotations

import json
import mimetypes
import sqlite3
import base64
import re
import uuid
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "tasks.db"
STATIC_DIR = ROOT / "static"
UPLOAD_DIR = ROOT / "uploads"


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def initialize_database() -> None:
    UPLOAD_DIR.mkdir(exist_ok=True)
    with connect() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 280),
                position INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columns = {row[1] for row in db.execute("PRAGMA table_info(tasks)").fetchall()}
        if "completed" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN completed INTEGER NOT NULL DEFAULT 0")
        if "task_date" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN task_date TEXT")
            db.execute("UPDATE tasks SET task_date = ? WHERE task_date IS NULL", (date.today().isoformat(),))
        if "location" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN location TEXT NOT NULL DEFAULT 'day'")
        if "label" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN label TEXT")
        if "label_color" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN label_color TEXT")
        if "starred" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN starred INTEGER NOT NULL DEFAULT 0")
        if "parent_id" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN parent_id INTEGER")
        if "planning_kind" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN planning_kind TEXT NOT NULL DEFAULT 'none'")
        if "planning_value" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN planning_value TEXT")
        db.execute(
            """CREATE TABLE IF NOT EXISTS dreams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                expected_year INTEGER,
                description TEXT,
                image_path TEXT,
                archived INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS dream_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dream_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                position INTEGER NOT NULL,
                FOREIGN KEY(dream_id) REFERENCES dreams(id)
            )"""
        )


def valid_date(value: object) -> str:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as error:
        raise ValueError("Invalid task date") from error


class TodoHandler(BaseHTTPRequestHandler):
    def send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 6_000_000:
            raise ValueError("Request is too large")
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path.startswith("/uploads/"):
            file_path = (UPLOAD_DIR / path.removeprefix("/uploads/")).resolve()
            if UPLOAD_DIR not in file_path.parents or not file_path.is_file():
                self.send_error(404)
                return
            data = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(file_path)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/api/dreams":
            archived = 1 if query.get("archived", ["0"])[0] == "1" else 0
            with connect() as db:
                dreams = [dict(row) for row in db.execute(
                    "SELECT id, title, expected_year, description, image_path, archived, created_at FROM dreams WHERE archived = ? ORDER BY id DESC",
                    (archived,),
                ).fetchall()]
                for dream in dreams:
                    dream["items"] = [dict(row) for row in db.execute(
                        "SELECT id, dream_id, title, completed, position FROM dream_items WHERE dream_id = ? ORDER BY position, id",
                        (dream["id"],),
                    ).fetchall()]
            self.send_json(dreams)
            return
        if path in {"/api/history", "/api/planned"}:
            period = query.get("period", ["month"])[0]
            current = date.today()
            if period == "week":
                start, end = current - timedelta(days=current.weekday()), current + timedelta(days=6-current.weekday())
            elif period == "quarter":
                start = date(current.year, ((current.month - 1)//3)*3 + 1, 1)
                next_month = start.month + 3
                next_start = date(start.year + (next_month > 12), ((next_month-1)%12)+1, 1)
                end = next_start - timedelta(days=1)
            elif period == "tertial":
                start = date(current.year, ((current.month - 1)//4)*4 + 1, 1)
                next_month = start.month + 4
                next_start = date(start.year + (next_month > 12), ((next_month-1)%12)+1, 1)
                end = next_start - timedelta(days=1)
            elif period == "year":
                start, end = date(current.year, 1, 1), date(current.year, 12, 31)
            else:
                start = date(current.year, current.month, 1)
                next_start = date(current.year + (current.month == 12), current.month % 12 + 1, 1)
                end = next_start - timedelta(days=1)
            with connect() as db:
                rows = [dict(row) for row in db.execute(
                    "SELECT id, title, completed, task_date, location, label, label_color, starred, parent_id, planning_kind, planning_value FROM tasks WHERE location = 'day' AND task_date BETWEEN ? AND ? ORDER BY task_date, position, id",
                    (start.isoformat(), end.isoformat()),
                ).fetchall()]
                inbox_rows = [dict(row) for row in db.execute(
                    "SELECT id, title, completed, task_date, location, label, label_color, starred, parent_id, planning_kind, planning_value FROM tasks WHERE location = 'inbox' AND planning_kind != 'none' ORDER BY position, id"
                ).fetchall()]
            month_numbers = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,"Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
            for task in inbox_rows:
                value = task.get("planning_value") or ""
                match = re.fullmatch(r"(\d{4})(?:-Q([1-4]))?(?:-([A-Z][a-z]{2}))?", value)
                if not match:
                    try:
                        exact = date.fromisoformat(value)
                        item_start = item_end = exact
                        if item_start <= end and item_end >= start:
                            rows.append(task)
                    except ValueError:
                        pass
                    continue
                year = int(match.group(1))
                quarter = int(match.group(2)) if match.group(2) else None
                month = month_numbers.get(match.group(3)) if match.group(3) else None
                if month:
                    item_start = date(year, month, 1)
                    next_month = date(year + (month == 12), month % 12 + 1, 1)
                    item_end = next_month - timedelta(days=1)
                elif quarter:
                    item_start = date(year, (quarter - 1) * 3 + 1, 1)
                    next_month = item_start.month + 3
                    next_start = date(item_start.year + (next_month > 12), ((next_month-1)%12)+1, 1)
                    item_end = next_start - timedelta(days=1)
                else:
                    item_start, item_end = date(year, 1, 1), date(year, 12, 31)
                if item_start <= end and item_end >= start:
                    rows.append(task)
            rows.sort(key=lambda item: (item.get("planning_value") or item.get("task_date") or "", item["id"]))
            self.send_json({"period": period, "start": start.isoformat(), "end": end.isoformat(), "tasks": rows})
            return
        if path == "/api/task-days":
            with connect() as db:
                rows = db.execute(
                    "SELECT task_date, COUNT(*) AS task_count FROM tasks WHERE location = 'day' GROUP BY task_date ORDER BY task_date"
                ).fetchall()
            self.send_json([dict(row) for row in rows])
            return
        if path == "/api/tasks/overdue":
            before = valid_date(query.get("before", [date.today().isoformat()])[0])
            with connect() as db:
                rows = db.execute(
                    "SELECT id, title, position, completed, task_date, location, label, label_color, starred, parent_id, planning_kind, planning_value, created_at FROM tasks WHERE location = 'day' AND task_date < ? AND completed = 0 ORDER BY task_date DESC, position, id",
                    (before,),
                ).fetchall()
            self.send_json([dict(row) for row in rows])
            return
        if path == "/api/tasks":
            location = query.get("location", ["day"])[0]
            if location not in {"day", "inbox"}:
                self.send_json({"error": "Invalid task location"}, 400)
                return
            task_date = valid_date(query.get("date", [date.today().isoformat()])[0])
            with connect() as db:
                if location == "inbox":
                    rows = db.execute(
                        "SELECT id, title, position, completed, task_date, location, label, label_color, starred, parent_id, planning_kind, planning_value, created_at FROM tasks WHERE location = 'inbox' ORDER BY position, id"
                    ).fetchall()
                else:
                    rows = db.execute(
                        "SELECT id, title, position, completed, task_date, location, label, label_color, starred, parent_id, planning_kind, planning_value, created_at FROM tasks WHERE location = 'day' AND task_date = ? ORDER BY position, id",
                        (task_date,),
                    ).fetchall()
            self.send_json([dict(row) for row in rows])
            return

        if path == "/":
            path = "/index.html"
        file_path = (STATIC_DIR / path.lstrip("/")).resolve()
        if STATIC_DIR not in file_path.parents or not file_path.is_file():
            self.send_error(404)
            return
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(file_path)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/dreams":
            try:
                payload = self.read_json()
                title = str(payload.get("title", "")).strip()
                if not title or len(title) > 280:
                    raise ValueError("Invalid dream title")
                year = payload.get("expected_year")
                if year not in (None, ""):
                    year = int(year)
                    if year < date.today().year or year > date.today().year + 100:
                        raise ValueError("Invalid expected year")
                else:
                    year = None
                with connect() as db:
                    cursor = db.execute("INSERT INTO dreams (title, expected_year) VALUES (?, ?)", (title, year))
                self.send_json({"id": cursor.lastrowid, "title": title, "expected_year": year, "description": None, "image_path": None, "archived": 0, "items": []}, 201)
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            return
        dream_item_match = re.fullmatch(r"/api/dreams/(\d+)/items", path)
        if dream_item_match:
            try:
                dream_id = int(dream_item_match.group(1))
                title = str(self.read_json().get("title", "")).strip()
                if not title or len(title) > 280:
                    raise ValueError("Invalid inner task")
                with connect() as db:
                    position = db.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM dream_items WHERE dream_id = ?", (dream_id,)).fetchone()[0]
                    cursor = db.execute("INSERT INTO dream_items (dream_id, title, position) VALUES (?, ?, ?)", (dream_id, title, position))
                self.send_json({"id": cursor.lastrowid, "dream_id": dream_id, "title": title, "completed": 0, "position": position}, 201)
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            return
        archive_match = re.fullmatch(r"/api/dreams/(\d+)/archive-to-inbox", path)
        if archive_match:
            dream_id = int(archive_match.group(1))
            with connect() as db:
                dream = db.execute("SELECT title FROM dreams WHERE id = ?", (dream_id,)).fetchone()
                if dream is None:
                    self.send_json({"error": "Dream not found"}, 404)
                    return
                position = db.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM tasks WHERE location = 'inbox'").fetchone()[0]
                cursor = db.execute("INSERT INTO tasks (title, position, task_date, location, label, label_color) VALUES (?, ?, ?, 'inbox', 'Dream', 'purple')", (dream[0], position, date.today().isoformat()))
                parent_id = cursor.lastrowid
                items = db.execute("SELECT title, completed FROM dream_items WHERE dream_id = ? ORDER BY position, id", (dream_id,)).fetchall()
                for offset, item in enumerate(items, 1):
                    db.execute("INSERT INTO tasks (title, position, task_date, location, completed, parent_id, label, label_color) VALUES (?, ?, ?, 'inbox', ?, ?, 'Dream', 'purple')", (item[0], position + offset, date.today().isoformat(), item[1], parent_id))
                db.execute("UPDATE dreams SET archived = 1 WHERE id = ?", (dream_id,))
            self.send_json({"ok": True, "task_id": parent_id})
            return
        if path != "/api/tasks":
            self.send_error(404)
            return
        try:
            payload = self.read_json()
            title = str(payload.get("title", "")).strip()
            task_date = valid_date(payload.get("task_date", date.today().isoformat()))
            location = payload.get("location", "day")
            if location not in {"day", "inbox"}:
                raise ValueError("Invalid task location")
            planning_kind = payload.get("planning_kind", "none")
            if planning_kind not in {"none", "date", "month", "quarter", "year"}:
                raise ValueError("Invalid planning type")
            planning_value = str(payload.get("planning_value", "")).strip() or None
            if not title or len(title) > 280:
                raise ValueError("Enter a task between 1 and 280 characters")
            with connect() as db:
                position = db.execute(
                    "SELECT COALESCE(MAX(position), -1) + 1 FROM tasks WHERE location = ? AND (? = 'inbox' OR task_date = ?)",
                    (location, location, task_date),
                ).fetchone()[0]
                cursor = db.execute(
                    "INSERT INTO tasks (title, position, task_date, location, planning_kind, planning_value) VALUES (?, ?, ?, ?, ?, ?)",
                    (title, position, task_date, location, planning_kind, planning_value),
                )
                row = db.execute(
                    "SELECT id, title, position, completed, task_date, location, label, label_color, starred, parent_id, planning_kind, planning_value, created_at FROM tasks WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
            self.send_json(dict(row), 201)
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        dream_match = re.fullmatch(r"/api/dreams/(\d+)", path)
        if dream_match:
            try:
                dream_id = int(dream_match.group(1))
                payload = self.read_json()
                updates, values = [], []
                if "description" in payload:
                    updates.append("description = ?")
                    values.append(str(payload["description"]).strip() or None)
                if "expected_year" in payload:
                    year = payload["expected_year"]
                    year = int(year) if year not in (None, "") else None
                    updates.append("expected_year = ?")
                    values.append(year)
                if "title" in payload:
                    title = str(payload["title"]).strip()
                    if not title:
                        raise ValueError("Invalid dream title")
                    updates.append("title = ?")
                    values.append(title)
                if "image_data" in payload:
                    match = re.fullmatch(r"data:image/(png|jpeg|webp);base64,(.+)", payload["image_data"], re.DOTALL)
                    if not match:
                        raise ValueError("Use a PNG, JPEG, or WebP image")
                    image_bytes = base64.b64decode(match.group(2), validate=True)
                    if len(image_bytes) > 4_000_000:
                        raise ValueError("Image is too large")
                    extension = "jpg" if match.group(1) == "jpeg" else match.group(1)
                    filename = f"dream-{dream_id}-{uuid.uuid4().hex}.{extension}"
                    (UPLOAD_DIR / filename).write_bytes(image_bytes)
                    updates.append("image_path = ?")
                    values.append(f"/uploads/{filename}")
                if not updates:
                    raise ValueError("Nothing to update")
                values.append(dream_id)
                with connect() as db:
                    cursor = db.execute(f"UPDATE dreams SET {', '.join(updates)} WHERE id = ?", values)
                    if cursor.rowcount == 0:
                        self.send_json({"error": "Dream not found"}, 404)
                        return
                    row = db.execute("SELECT id, title, expected_year, description, image_path, archived, created_at FROM dreams WHERE id = ?", (dream_id,)).fetchone()
                self.send_json(dict(row))
            except (ValueError, json.JSONDecodeError, base64.binascii.Error) as error:
                self.send_json({"error": str(error)}, 400)
            return
        item_match = re.fullmatch(r"/api/dream-items/(\d+)", path)
        if item_match:
            try:
                item_id = int(item_match.group(1))
                payload = self.read_json()
                if "completed" not in payload or not isinstance(payload["completed"], bool):
                    raise ValueError("Invalid completion status")
                with connect() as db:
                    cursor = db.execute("UPDATE dream_items SET completed = ? WHERE id = ?", (int(payload["completed"]), item_id))
                if cursor.rowcount == 0:
                    self.send_json({"error": "Inner task not found"}, 404)
                else:
                    self.send_json({"ok": True})
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            return
        if path.startswith("/api/tasks/") and path != "/api/tasks/reorder":
            try:
                task_id = int(path.rsplit("/", 1)[-1])
                payload = self.read_json()
                updates = []
                values = []
                if "completed" in payload:
                    if not isinstance(payload["completed"], bool):
                        raise ValueError("Invalid completion status")
                    updates.append("completed = ?")
                    values.append(int(payload["completed"]))
                if "title" in payload:
                    title = str(payload["title"]).strip()
                    if not title or len(title) > 280:
                        raise ValueError("Enter a task between 1 and 280 characters")
                    updates.append("title = ?")
                    values.append(title)
                if "task_date" in payload:
                    updates.append("task_date = ?")
                    values.append(valid_date(payload["task_date"]))
                if "location" in payload:
                    if payload["location"] not in {"day", "inbox"}:
                        raise ValueError("Invalid task location")
                    updates.append("location = ?")
                    values.append(payload["location"])
                if "label" in payload:
                    label = str(payload["label"]).strip()
                    if len(label) > 40:
                        raise ValueError("Label is too long")
                    updates.append("label = ?")
                    values.append(label or None)
                if "label_color" in payload:
                    color = payload["label_color"]
                    allowed_colors = {"green", "blue", "orange", "purple", "red", "gray", None, ""}
                    if color not in allowed_colors:
                        raise ValueError("Invalid label color")
                    updates.append("label_color = ?")
                    values.append(color or None)
                if "parent_id" in payload:
                    parent_id = payload["parent_id"]
                    if parent_id is not None:
                        if not isinstance(parent_id, int) or parent_id == task_id:
                            raise ValueError("Invalid parent task")
                        with connect() as check_db:
                            parent = check_db.execute(
                                "SELECT id, location, task_date FROM tasks WHERE id = ?", (parent_id,)
                            ).fetchone()
                            child = check_db.execute(
                                "SELECT location, task_date FROM tasks WHERE id = ?", (task_id,)
                            ).fetchone()
                        if parent is None or child is None or parent[1] != child[0] or (child[0] == "day" and parent[2] != child[1]):
                            raise ValueError("Parent task must be in the same list")
                    updates.append("parent_id = ?")
                    values.append(parent_id)
                if "starred" in payload:
                    if not isinstance(payload["starred"], bool):
                        raise ValueError("Invalid starred status")
                    if payload["starred"]:
                        with connect() as check_db:
                            scope = check_db.execute(
                                "SELECT location, task_date FROM tasks WHERE id = ?", (task_id,)
                            ).fetchone()
                            if scope is None:
                                raise ValueError("Task not found")
                            starred_count = check_db.execute(
                                "SELECT COUNT(*) FROM tasks WHERE starred = 1 AND id != ? AND location = ? AND (? = 'inbox' OR task_date = ?)",
                                (task_id, scope[0], scope[0], scope[1]),
                            ).fetchone()[0]
                        if starred_count >= 3:
                            raise ValueError("Only three tasks can be starred in this list")
                    updates.append("starred = ?")
                    values.append(int(payload["starred"]))
                if "planning_kind" in payload:
                    if payload["planning_kind"] not in {"none", "date", "month", "quarter", "year"}:
                        raise ValueError("Invalid planning type")
                    updates.append("planning_kind = ?")
                    values.append(payload["planning_kind"])
                if "planning_value" in payload:
                    updates.append("planning_value = ?")
                    values.append(str(payload["planning_value"]).strip() or None)
                if not updates:
                    raise ValueError("Nothing to update")
                values.append(task_id)
                with connect() as db:
                    cursor = db.execute(
                        f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?",
                        values,
                    )
                    if cursor.rowcount == 0:
                        self.send_json({"error": "Task not found"}, 404)
                        return
                    row = db.execute(
                        "SELECT id, title, position, completed, task_date, location, label, label_color, starred, parent_id, planning_kind, planning_value, created_at FROM tasks WHERE id = ?",
                        (task_id,),
                    ).fetchone()
                self.send_json(dict(row))
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            return

        if path != "/api/tasks/reorder":
            self.send_error(404)
            return
        try:
            payload = self.read_json()
            ids = payload.get("ids")
            location = payload.get("location", "day")
            if location not in {"day", "inbox"}:
                raise ValueError("Invalid task location")
            task_date = valid_date(payload.get("task_date", date.today().isoformat()))
            if not isinstance(ids, list) or any(not isinstance(item, int) for item in ids):
                raise ValueError("Invalid task order")
            with connect() as db:
                existing = [row[0] for row in db.execute(
                    "SELECT id FROM tasks WHERE location = ? AND (? = 'inbox' OR task_date = ?)",
                    (location, location, task_date),
                ).fetchall()]
                if len(ids) != len(existing) or set(ids) != set(existing):
                    raise ValueError("Task list changed; refresh and try again")
                db.executemany(
                    "UPDATE tasks SET position = ? WHERE id = ?",
                    [(position, task_id) for position, task_id in enumerate(ids)],
                )
            self.send_json({"ok": True})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        if not path.startswith("/api/tasks/"):
            self.send_error(404)
            return
        try:
            task_id = int(path.rsplit("/", 1)[-1])
            with connect() as db:
                task_row = db.execute("SELECT task_date, location FROM tasks WHERE id = ?", (task_id,)).fetchone()
                if task_row is None:
                    self.send_json({"error": "Task not found"}, 404)
                    return
                cursor = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                db.execute("UPDATE tasks SET parent_id = NULL WHERE parent_id = ?", (task_id,))
                rows = db.execute(
                    "SELECT id FROM tasks WHERE location = ? AND (? = 'inbox' OR task_date = ?) ORDER BY position, id",
                    (task_row[1], task_row[1], task_row[0]),
                ).fetchall()
                db.executemany(
                    "UPDATE tasks SET position = ? WHERE id = ?",
                    [(position, row[0]) for position, row in enumerate(rows)],
                )
            self.send_json({"ok": True})
        except ValueError:
            self.send_json({"error": "Invalid task id"}, 400)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


if __name__ == "__main__":
    initialize_database()
    server = ThreadingHTTPServer(("0.0.0.0", 8000), TodoHandler)
    print("Taskline is running at http://localhost:8000")
    print("Press Ctrl+C to stop it.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTaskline stopped.")
    finally:
        server.server_close()
