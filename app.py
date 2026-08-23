from __future__ import annotations

import json
import mimetypes
import os
import sqlite3
import base64
import calendar
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
                workspace TEXT NOT NULL DEFAULT 'personal',
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
        if "routine_occurrence_id" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN routine_occurrence_id INTEGER")
        if "routine_scheduled_date" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN routine_scheduled_date TEXT")
        if "overdue_ignored" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN overdue_ignored INTEGER NOT NULL DEFAULT 0")
        if "completed_at" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN completed_at TEXT")
            db.execute("UPDATE tasks SET completed_at = created_at WHERE completed = 1")
        if "follow_until_complete" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN follow_until_complete INTEGER NOT NULL DEFAULT 1")
        if "carried_from_date" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN carried_from_date TEXT")
        if "workspace" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN workspace TEXT NOT NULL DEFAULT 'personal'")
        normalize_task_hierarchy(db)
        db.execute(
            """CREATE TABLE IF NOT EXISTS dreams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                expected_year INTEGER,
                description TEXT,
                image_path TEXT,
                archived INTEGER NOT NULL DEFAULT 0,
                workspace TEXT NOT NULL DEFAULT 'personal',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        dream_columns = {row[1] for row in db.execute("PRAGMA table_info(dreams)").fetchall()}
        if "workspace" not in dream_columns:
            db.execute("ALTER TABLE dreams ADD COLUMN workspace TEXT NOT NULL DEFAULT 'personal'")
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
        db.execute(
            """CREATE TABLE IF NOT EXISTS routines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                start_date TEXT NOT NULL,
                effective_date TEXT NOT NULL,
                frequency TEXT NOT NULL,
                interval_value INTEGER NOT NULL DEFAULT 1,
                weekdays TEXT,
                month_day INTEGER,
                year_month INTEGER,
                year_day INTEGER,
                end_mode TEXT NOT NULL DEFAULT 'never',
                end_value TEXT,
                follow_until_complete INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                archived INTEGER NOT NULL DEFAULT 0,
                workspace TEXT NOT NULL DEFAULT 'personal',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        routine_columns = {row[1] for row in db.execute("PRAGMA table_info(routines)").fetchall()}
        if "follow_until_complete" not in routine_columns:
            db.execute("ALTER TABLE routines ADD COLUMN follow_until_complete INTEGER NOT NULL DEFAULT 0")
        if "workspace" not in routine_columns:
            db.execute("ALTER TABLE routines ADD COLUMN workspace TEXT NOT NULL DEFAULT 'personal'")
        db.execute(
            """CREATE TABLE IF NOT EXISTS routine_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                routine_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                position INTEGER NOT NULL,
                FOREIGN KEY(routine_id) REFERENCES routines(id)
            )"""
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS routine_occurrences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                routine_id INTEGER NOT NULL,
                scheduled_date TEXT NOT NULL,
                task_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(routine_id, scheduled_date),
                FOREIGN KEY(routine_id) REFERENCES routines(id)
            )"""
        )
        db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_routine_occurrence ON tasks(routine_occurrence_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_routine_occurrences_date ON routine_occurrences(scheduled_date)")
        db.execute(
            """CREATE TABLE IF NOT EXISTS checklists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 280),
                workspace TEXT NOT NULL DEFAULT 'personal',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS checklist_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checklist_id INTEGER NOT NULL,
                title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 280),
                completed INTEGER NOT NULL DEFAULT 0,
                position INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(checklist_id) REFERENCES checklists(id)
            )"""
        )
        db.execute("CREATE INDEX IF NOT EXISTS idx_checklist_items_list ON checklist_items(checklist_id, position)")


def valid_date(value: object) -> str:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as error:
        raise ValueError("Invalid task date") from error


def valid_workspace(value: object) -> str:
    workspace = str(value or "personal")
    if workspace not in {"personal", "work"}:
        raise ValueError("Invalid workspace")
    return workspace


def sync_task_completion_from_children(db: sqlite3.Connection, task_id: int) -> None:
    child_counts = db.execute(
        "SELECT COUNT(*), SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) FROM tasks WHERE parent_id = ?",
        (task_id,),
    ).fetchone()
    if child_counts[0] > 0:
        completed = int(child_counts[0] == child_counts[1])
        db.execute(
            "UPDATE tasks SET completed = ?, completed_at = CASE WHEN ? = 1 THEN COALESCE(completed_at, CURRENT_TIMESTAMP) ELSE NULL END WHERE id = ?",
            (completed, completed, task_id),
        )


def sync_ancestor_completion(db: sqlite3.Connection, task_id: int) -> None:
    row = db.execute("SELECT parent_id FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is not None and row[0] is not None:
        sync_task_completion_from_children(db, row[0])


def normalize_task_hierarchy(db: sqlite3.Connection) -> None:
    """Keep task/subtask relationships to one level and repair old nested data."""
    db.execute(
        "UPDATE tasks SET parent_id = NULL WHERE parent_id IS NOT NULL AND parent_id NOT IN (SELECT id FROM tasks)"
    )
    rows = db.execute("SELECT id, parent_id FROM tasks").fetchall()
    parents = {row[0]: row[1] for row in rows}
    normalized: list[tuple[int | None, int]] = []
    for task_id, parent_id in parents.items():
        if parent_id is None:
            continue
        root_id = parent_id
        seen = {task_id}
        while root_id is not None and parents.get(root_id) is not None and root_id not in seen:
            seen.add(root_id)
            root_id = parents[root_id]
        if root_id in seen:
            root_id = None
        if root_id != parent_id:
            normalized.append((root_id, task_id))
    if normalized:
        db.executemany("UPDATE tasks SET parent_id = ? WHERE id = ?", normalized)
    for row in db.execute("SELECT DISTINCT parent_id FROM tasks WHERE parent_id IS NOT NULL").fetchall():
        sync_task_completion_from_children(db, row[0])


def parse_routine(payload: dict, existing: sqlite3.Row | None = None) -> dict:
    def current(name: str, default: object = None) -> object:
        if name in payload:
            return payload[name]
        return existing[name] if existing is not None else default

    title = str(current("title", "")).strip()
    if not title or len(title) > 280:
        raise ValueError("Enter a routine between 1 and 280 characters")
    start_date = valid_date(current("start_date", date.today().isoformat()))
    frequency = str(current("frequency", "daily"))
    if frequency not in {"daily", "weekly", "monthly", "yearly"}:
        raise ValueError("Invalid routine frequency")
    interval_value = int(current("interval_value", 1))
    if interval_value < 1 or interval_value > 99:
        raise ValueError("Invalid repeat interval")
    raw_weekdays = current("weekdays", "[]")
    if isinstance(raw_weekdays, str):
        weekdays = json.loads(raw_weekdays or "[]")
    else:
        weekdays = raw_weekdays
    if not isinstance(weekdays, list) or any(not isinstance(day, int) or day < 0 or day > 6 for day in weekdays):
        raise ValueError("Invalid weekdays")
    weekdays = sorted(set(weekdays))
    if frequency == "weekly" and not weekdays:
        weekdays = [date.fromisoformat(start_date).weekday()]
    month_day_value = current("month_day")
    month_day = int(month_day_value) if month_day_value not in (None, "") else None
    if frequency == "monthly" and month_day is None:
        month_day = date.fromisoformat(start_date).day
    if month_day is not None and month_day not in {*range(1, 32), -1}:
        raise ValueError("Invalid day of month")
    year_month_value = current("year_month")
    year_day_value = current("year_day")
    year_month = int(year_month_value) if year_month_value not in (None, "") else None
    year_day = int(year_day_value) if year_day_value not in (None, "") else None
    if frequency == "yearly" and (year_month is None or year_day is None):
        start = date.fromisoformat(start_date)
        year_month, year_day = start.month, start.day
    if year_month is not None and not 1 <= year_month <= 12:
        raise ValueError("Invalid yearly month")
    if year_day is not None and not 1 <= year_day <= 31:
        raise ValueError("Invalid yearly day")
    if frequency == "yearly":
        try:
            date(2000, year_month, year_day)
        except ValueError as error:
            raise ValueError("Invalid yearly date") from error
    end_mode = str(current("end_mode", "never"))
    if end_mode not in {"never", "date", "count"}:
        raise ValueError("Invalid routine end")
    end_value_raw = current("end_value")
    end_value = str(end_value_raw).strip() if end_value_raw not in (None, "") else None
    if end_mode == "date":
        end_value = valid_date(end_value)
        if end_value < start_date:
            raise ValueError("End date must follow the start date")
    elif end_mode == "count":
        count = int(end_value or 0)
        if count < 1 or count > 10000:
            raise ValueError("Invalid occurrence count")
        end_value = str(count)
    else:
        end_value = None
    follow_until_complete = current("follow_until_complete", 0)
    if isinstance(follow_until_complete, bool):
        follow_until_complete = int(follow_until_complete)
    elif follow_until_complete not in {0, 1}:
        raise ValueError("Invalid follow setting")
    return {
        "title": title,
        "start_date": start_date,
        "frequency": frequency,
        "interval_value": interval_value,
        "weekdays": json.dumps(weekdays),
        "month_day": month_day,
        "year_month": year_month,
        "year_day": year_day,
        "end_mode": end_mode,
        "end_value": end_value,
        "follow_until_complete": int(follow_until_complete),
    }


def routine_matches_day(routine: sqlite3.Row, candidate: date) -> bool:
    start = date.fromisoformat(max(routine["start_date"], routine["effective_date"]))
    if candidate < start:
        return False
    interval_value = routine["interval_value"]
    if routine["frequency"] == "daily":
        return (candidate - start).days % interval_value == 0
    if routine["frequency"] == "weekly":
        start_week = start - timedelta(days=start.weekday())
        week_index = (candidate - start_week).days // 7
        return week_index % interval_value == 0 and candidate.weekday() in json.loads(routine["weekdays"] or "[]")
    if routine["frequency"] == "monthly":
        month_index = (candidate.year - start.year) * 12 + candidate.month - start.month
        if month_index < 0 or month_index % interval_value:
            return False
        target_day = calendar.monthrange(candidate.year, candidate.month)[1] if routine["month_day"] == -1 else routine["month_day"]
        return candidate.day == target_day
    year_index = candidate.year - start.year
    if year_index < 0 or year_index % interval_value:
        return False
    return candidate.month == routine["year_month"] and candidate.day == routine["year_day"]


def routine_dates(routine: sqlite3.Row, through: date) -> list[date]:
    start = date.fromisoformat(max(routine["start_date"], routine["effective_date"]))
    end = through
    if routine["end_mode"] == "date":
        end = min(end, date.fromisoformat(routine["end_value"]))
    if end < start:
        return []
    limit = int(routine["end_value"]) if routine["end_mode"] == "count" else None
    matches: list[date] = []
    candidate = start
    while candidate <= end:
        if routine_matches_day(routine, candidate):
            matches.append(candidate)
            if limit is not None and len(matches) >= limit:
                break
        candidate += timedelta(days=1)
    return matches


def materialize_routines(db: sqlite3.Connection, through: date, workspace: str | None = None) -> None:
    if workspace is None:
        routines = db.execute("SELECT * FROM routines WHERE active = 1 AND archived = 0").fetchall()
    else:
        routines = db.execute(
            "SELECT * FROM routines WHERE active = 1 AND archived = 0 AND workspace = ?", (workspace,)
        ).fetchall()
    for routine in routines:
        steps = db.execute(
            "SELECT title FROM routine_steps WHERE routine_id = ? ORDER BY position, id", (routine["id"],)
        ).fetchall()
        for scheduled in routine_dates(routine, through):
            scheduled_iso = scheduled.isoformat()
            cursor = db.execute(
                "INSERT OR IGNORE INTO routine_occurrences (routine_id, scheduled_date) VALUES (?, ?)",
                (routine["id"], scheduled_iso),
            )
            if cursor.rowcount == 0:
                continue
            occurrence_id = cursor.lastrowid
            position = db.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM tasks WHERE location = 'day' AND task_date = ? AND workspace = ?",
                (scheduled_iso, routine["workspace"]),
            ).fetchone()[0]
            task_cursor = db.execute(
                "INSERT INTO tasks (title, position, task_date, location, planning_kind, planning_value, routine_occurrence_id, routine_scheduled_date, follow_until_complete, workspace) VALUES (?, ?, ?, 'day', 'date', ?, ?, ?, ?, ?)",
                (routine["title"], position, scheduled_iso, scheduled_iso, occurrence_id, scheduled_iso, routine["follow_until_complete"], routine["workspace"]),
            )
            root_task_id = task_cursor.lastrowid
            db.execute("UPDATE routine_occurrences SET task_id = ? WHERE id = ?", (root_task_id, occurrence_id))
            for offset, step in enumerate(steps, 1):
                db.execute(
                    "INSERT INTO tasks (title, position, task_date, location, parent_id, planning_kind, planning_value, routine_occurrence_id, routine_scheduled_date, follow_until_complete, workspace) VALUES (?, ?, ?, 'day', ?, 'date', ?, ?, ?, ?, ?)",
                    (step[0], position + offset, scheduled_iso, root_task_id, scheduled_iso, occurrence_id, scheduled_iso, routine["follow_until_complete"], routine["workspace"]),
                )


def remove_pending_routine_occurrences(db: sqlite3.Connection, routine_id: int, from_date: date) -> None:
    occurrences = db.execute(
        """SELECT ro.id FROM routine_occurrences ro
           JOIN tasks t ON t.id = ro.task_id
           WHERE ro.routine_id = ? AND ro.scheduled_date >= ? AND t.completed = 0""",
        (routine_id, from_date.isoformat()),
    ).fetchall()
    occurrence_ids = [row[0] for row in occurrences]
    if not occurrence_ids:
        return
    placeholders = ",".join("?" for _ in occurrence_ids)
    db.execute(f"DELETE FROM tasks WHERE routine_occurrence_id IN ({placeholders})", occurrence_ids)
    db.execute(f"DELETE FROM routine_occurrences WHERE id IN ({placeholders})", occurrence_ids)


def routine_payload(db: sqlite3.Connection, routine: sqlite3.Row) -> dict:
    result = dict(routine)
    result["weekdays"] = json.loads(result.get("weekdays") or "[]")
    result["steps"] = [row[0] for row in db.execute(
        "SELECT title FROM routine_steps WHERE routine_id = ? ORDER BY position, id", (routine["id"],)
    ).fetchall()]
    return result


def checklist_payload(db: sqlite3.Connection, checklist: sqlite3.Row) -> dict:
    result = dict(checklist)
    result["items"] = [dict(row) for row in db.execute(
        "SELECT id, checklist_id, title, completed, position, created_at FROM checklist_items WHERE checklist_id = ? ORDER BY position, id",
        (checklist["id"],),
    ).fetchall()]
    return result


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
        try:
            workspace = valid_workspace(query.get("workspace", ["personal"])[0])
        except ValueError as error:
            self.send_json({"error": str(error)}, 400)
            return
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
        if path == "/api/lists":
            with connect() as db:
                checklists = [checklist_payload(db, row) for row in db.execute(
                    "SELECT id, title, workspace, created_at FROM checklists WHERE workspace = ? ORDER BY id DESC",
                    (workspace,),
                ).fetchall()]
            self.send_json(checklists)
            return
        if path == "/api/routines":
            with connect() as db:
                materialize_routines(db, date.today(), workspace)
                routines = [routine_payload(db, row) for row in db.execute(
                    "SELECT * FROM routines WHERE archived = 0 AND workspace = ? ORDER BY active DESC, id DESC",
                    (workspace,),
                ).fetchall()]
            self.send_json(routines)
            return
        if path == "/api/routines/stats":
            try:
                days = int(query.get("days", ["30"])[0])
                if days not in {7, 30, 365}:
                    raise ValueError("Invalid statistics period")
                routine_filter = query.get("routine_id", [""])[0]
                routine_id = int(routine_filter) if routine_filter else None
                end = date.today()
                start = end - timedelta(days=days - 1)
                with connect() as db:
                    materialize_routines(db, end, workspace)
                    sql = """SELECT ro.scheduled_date, COUNT(*) AS scheduled,
                                    SUM(CASE WHEN t.completed = 1 THEN 1 ELSE 0 END) AS completed
                             FROM routine_occurrences ro
                             JOIN tasks t ON t.id = ro.task_id
                             WHERE ro.scheduled_date BETWEEN ? AND ? AND t.workspace = ?"""
                    values: list[object] = [start.isoformat(), end.isoformat(), workspace]
                    if routine_id is not None:
                        sql += " AND ro.routine_id = ?"
                        values.append(routine_id)
                    sql += " GROUP BY ro.scheduled_date ORDER BY ro.scheduled_date"
                    grouped = {row[0]: dict(row) for row in db.execute(sql, values).fetchall()}
                points = []
                current = start
                while current <= end:
                    item = grouped.get(current.isoformat(), {"scheduled": 0, "completed": 0})
                    scheduled = int(item["scheduled"] or 0)
                    completed = int(item["completed"] or 0)
                    points.append({
                        "date": current.isoformat(),
                        "scheduled": scheduled,
                        "completed": completed,
                        "percentage": round(completed * 100 / scheduled, 1) if scheduled else None,
                    })
                    current += timedelta(days=1)
                self.send_json({"start": start.isoformat(), "end": end.isoformat(), "points": points})
            except ValueError as error:
                self.send_json({"error": str(error)}, 400)
            return
        if path == "/api/labels":
            with connect() as db:
                rows = db.execute(
                    "SELECT id, label, label_color FROM tasks WHERE workspace = ? AND label IS NOT NULL AND trim(label) != '' ORDER BY id",
                    (workspace,),
                ).fetchall()
            labels: dict[str, dict] = {}
            for row in rows:
                name = row[1].strip()
                key = name.casefold()
                if key not in labels:
                    labels[key] = {"name": name, "color": row[2] or "gray", "uses": 0}
                labels[key]["uses"] += 1
            self.send_json(sorted(labels.values(), key=lambda item: (-item["uses"], item["name"].casefold())))
            return
        if path == "/api/dreams":
            archived = 1 if query.get("archived", ["0"])[0] == "1" else 0
            with connect() as db:
                dreams = [dict(row) for row in db.execute(
                    "SELECT id, title, expected_year, description, image_path, archived, workspace, created_at FROM dreams WHERE archived = ? AND workspace = ? ORDER BY id DESC",
                    (archived, workspace),
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
                materialize_routines(db, end, workspace)
                rows = [dict(row) for row in db.execute(
                    "SELECT id, title, completed, task_date, location, label, label_color, starred, parent_id, planning_kind, planning_value FROM tasks WHERE workspace = ? AND location = 'day' AND task_date BETWEEN ? AND ? ORDER BY task_date, position, id",
                    (workspace, start.isoformat(), end.isoformat()),
                ).fetchall()]
                inbox_rows = [dict(row) for row in db.execute(
                    "SELECT id, title, completed, task_date, location, label, label_color, starred, parent_id, planning_kind, planning_value FROM tasks WHERE workspace = ? AND location = 'inbox' AND planning_kind != 'none' ORDER BY position, id",
                    (workspace,),
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
                through = valid_date(query.get("through", [(date.today() + timedelta(days=14)).isoformat()])[0])
                materialize_routines(db, date.fromisoformat(through), workspace)
                rows = db.execute(
                    """SELECT task_date, COUNT(*) AS task_count,
                              SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) AS incomplete_count
                       FROM tasks
                       WHERE workspace = ? AND location = 'day'
                       GROUP BY task_date
                       ORDER BY task_date""",
                    (workspace,),
                ).fetchall()
            self.send_json([dict(row) for row in rows])
            return
        if path == "/api/tasks/overdue":
            before = valid_date(query.get("before", [date.today().isoformat()])[0])
            with connect() as db:
                materialize_routines(db, date.fromisoformat(before) - timedelta(days=1), workspace)
                rows = db.execute(
                    "SELECT id, title, position, completed, task_date, location, label, label_color, starred, parent_id, planning_kind, planning_value, routine_occurrence_id, routine_scheduled_date, overdue_ignored, completed_at, follow_until_complete, carried_from_date, workspace, created_at FROM tasks WHERE workspace = ? AND location = 'day' AND task_date < ? AND completed = 0 AND overdue_ignored = 0 AND (routine_occurrence_id IS NULL OR follow_until_complete = 1) AND parent_id IS NULL ORDER BY task_date DESC, position, id",
                    (workspace, before),
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
                        "SELECT id, title, position, completed, task_date, location, label, label_color, starred, parent_id, planning_kind, planning_value, routine_occurrence_id, routine_scheduled_date, overdue_ignored, completed_at, follow_until_complete, carried_from_date, workspace, created_at FROM tasks WHERE workspace = ? AND location = 'inbox' ORDER BY position, id",
                        (workspace,),
                    ).fetchall()
                else:
                    materialize_routines(db, date.fromisoformat(task_date), workspace)
                    rows = db.execute(
                        "SELECT id, title, position, completed, task_date, location, label, label_color, starred, parent_id, planning_kind, planning_value, routine_occurrence_id, routine_scheduled_date, overdue_ignored, completed_at, follow_until_complete, carried_from_date, workspace, created_at FROM tasks WHERE workspace = ? AND location = 'day' AND task_date = ? ORDER BY position, id",
                        (workspace, task_date),
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
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        try:
            workspace = valid_workspace(parse_qs(parsed_url.query).get("workspace", ["personal"])[0])
        except ValueError as error:
            self.send_json({"error": str(error)}, 400)
            return
        if path == "/api/lists":
            try:
                title = str(self.read_json().get("title", "")).strip()
                if not title or len(title) > 280:
                    raise ValueError("Enter a list name between 1 and 280 characters")
                with connect() as db:
                    cursor = db.execute(
                        "INSERT INTO checklists (title, workspace) VALUES (?, ?)",
                        (title, workspace),
                    )
                    row = db.execute(
                        "SELECT id, title, workspace, created_at FROM checklists WHERE id = ?",
                        (cursor.lastrowid,),
                    ).fetchone()
                    result = checklist_payload(db, row)
                self.send_json(result, 201)
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            return
        list_item_match = re.fullmatch(r"/api/lists/(\d+)/items", path)
        if list_item_match:
            try:
                checklist_id = int(list_item_match.group(1))
                title = str(self.read_json().get("title", "")).strip()
                if not title or len(title) > 280:
                    raise ValueError("Enter an item between 1 and 280 characters")
                with connect() as db:
                    if db.execute(
                        "SELECT 1 FROM checklists WHERE id = ? AND workspace = ?",
                        (checklist_id, workspace),
                    ).fetchone() is None:
                        self.send_json({"error": "List not found"}, 404)
                        return
                    position = db.execute(
                        "SELECT COALESCE(MAX(position), -1) + 1 FROM checklist_items WHERE checklist_id = ?",
                        (checklist_id,),
                    ).fetchone()[0]
                    cursor = db.execute(
                        "INSERT INTO checklist_items (checklist_id, title, position) VALUES (?, ?, ?)",
                        (checklist_id, title, position),
                    )
                    row = db.execute(
                        "SELECT id, checklist_id, title, completed, position, created_at FROM checklist_items WHERE id = ?",
                        (cursor.lastrowid,),
                    ).fetchone()
                self.send_json(dict(row), 201)
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            return
        if path == "/api/routines":
            try:
                payload = self.read_json()
                routine = parse_routine(payload)
                steps = payload.get("steps", [])
                if not isinstance(steps, list):
                    raise ValueError("Invalid routine steps")
                steps = [str(step).strip() for step in steps if str(step).strip()]
                if any(len(step) > 280 for step in steps):
                    raise ValueError("Routine step is too long")
                with connect() as db:
                    cursor = db.execute(
                        """INSERT INTO routines
                           (title, start_date, effective_date, frequency, interval_value, weekdays,
                            month_day, year_month, year_day, end_mode, end_value, follow_until_complete, workspace)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            routine["title"], routine["start_date"], routine["start_date"], routine["frequency"],
                            routine["interval_value"], routine["weekdays"], routine["month_day"],
                            routine["year_month"], routine["year_day"], routine["end_mode"],
                            routine["end_value"], routine["follow_until_complete"], workspace,
                        ),
                    )
                    routine_id = cursor.lastrowid
                    db.executemany(
                        "INSERT INTO routine_steps (routine_id, title, position) VALUES (?, ?, ?)",
                        [(routine_id, step, position) for position, step in enumerate(steps)],
                    )
                    materialize_routines(db, date.today(), workspace)
                    row = db.execute("SELECT * FROM routines WHERE id = ?", (routine_id,)).fetchone()
                    result = routine_payload(db, row)
                self.send_json(result, 201)
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            return
        overdue_match = re.fullmatch(r"/api/tasks/(\d+)/overdue-action", path)
        if overdue_match:
            try:
                task_id = int(overdue_match.group(1))
                payload = self.read_json()
                action = payload.get("action")
                if action not in {"today", "inbox", "ignore"}:
                    raise ValueError("Invalid overdue action")
                client_today = valid_date(payload.get("target_date", date.today().isoformat()))
                with connect() as db:
                    row = db.execute("SELECT id, parent_id, task_date, routine_occurrence_id FROM tasks WHERE id = ? AND workspace = ?", (task_id, workspace)).fetchone()
                    if row is None:
                        self.send_json({"error": "Task not found"}, 404)
                        return
                    if action == "inbox" and row[3] is not None:
                        raise ValueError("Routine occurrences cannot be moved to the inbox")
                    root_id = row[1] or row[0]
                    family = db.execute(
                        "SELECT id, task_date FROM tasks WHERE workspace = ? AND (id = ? OR parent_id = ?) ORDER BY CASE WHEN id = ? THEN 0 ELSE 1 END, position, id",
                        (workspace, root_id, root_id, root_id),
                    ).fetchall()
                    if action == "ignore":
                        db.execute("UPDATE tasks SET overdue_ignored = 1 WHERE id = ?", (root_id,))
                    else:
                        location = "day" if action == "today" else "inbox"
                        target_date = client_today if action == "today" else row[2]
                        next_position = db.execute(
                            "SELECT COALESCE(MAX(position), -1) + 1 FROM tasks WHERE workspace = ? AND location = ? AND (? = 'inbox' OR task_date = ?)",
                            (workspace, location, location, target_date),
                        ).fetchone()[0]
                        for offset, member in enumerate(family):
                            if action == "today":
                                db.execute(
                                    """UPDATE tasks SET location = 'day', carried_from_date = COALESCE(carried_from_date, task_date),
                                       task_date = ?, position = ?, overdue_ignored = 0 WHERE id = ?""",
                                    (target_date, next_position + offset, member[0]),
                                )
                            else:
                                db.execute(
                                    """UPDATE tasks SET location = 'inbox', position = ?, planning_kind = 'none',
                                       planning_value = NULL, overdue_ignored = 0 WHERE id = ?""",
                                    (next_position + offset, member[0]),
                                )
                self.send_json({"ok": True, "action": action})
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            return
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
                    cursor = db.execute("INSERT INTO dreams (title, expected_year, workspace) VALUES (?, ?, ?)", (title, year, workspace))
                self.send_json({"id": cursor.lastrowid, "title": title, "expected_year": year, "description": None, "image_path": None, "archived": 0, "workspace": workspace, "items": []}, 201)
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
                    if db.execute("SELECT 1 FROM dreams WHERE id = ? AND workspace = ?", (dream_id, workspace)).fetchone() is None:
                        self.send_json({"error": "Dream not found"}, 404)
                        return
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
                dream = db.execute("SELECT title FROM dreams WHERE id = ? AND workspace = ?", (dream_id, workspace)).fetchone()
                if dream is None:
                    self.send_json({"error": "Dream not found"}, 404)
                    return
                position = db.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM tasks WHERE workspace = ? AND location = 'inbox'", (workspace,)).fetchone()[0]
                cursor = db.execute("INSERT INTO tasks (title, position, task_date, location, label, label_color, workspace) VALUES (?, ?, ?, 'inbox', 'Dream', 'purple', ?)", (dream[0], position, date.today().isoformat(), workspace))
                parent_id = cursor.lastrowid
                items = db.execute("SELECT title, completed FROM dream_items WHERE dream_id = ? ORDER BY position, id", (dream_id,)).fetchall()
                for offset, item in enumerate(items, 1):
                    db.execute("INSERT INTO tasks (title, position, task_date, location, completed, parent_id, label, label_color, workspace) VALUES (?, ?, ?, 'inbox', ?, ?, 'Dream', 'purple', ?)", (item[0], position + offset, date.today().isoformat(), item[1], parent_id, workspace))
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
            parent_id = payload.get("parent_id")
            if parent_id is not None and not isinstance(parent_id, int):
                raise ValueError("Invalid parent task")
            if not title or len(title) > 280:
                raise ValueError("Enter a task between 1 and 280 characters")
            with connect() as db:
                if parent_id is not None:
                    parent = db.execute(
                        "SELECT id, position, task_date, location, planning_kind, planning_value, parent_id FROM tasks WHERE id = ? AND workspace = ?",
                        (parent_id, workspace),
                    ).fetchone()
                    if parent is None:
                        raise ValueError("Parent task not found")
                    if parent[6] is not None:
                        parent_id = parent[6]
                        parent = db.execute(
                            "SELECT id, position, task_date, location, planning_kind, planning_value, parent_id FROM tasks WHERE id = ? AND workspace = ?",
                            (parent_id, workspace),
                        ).fetchone()
                        if parent is None:
                            raise ValueError("Parent task not found")
                    task_date, location, planning_kind, planning_value = parent[2], parent[3], parent[4], parent[5]
                    last_child_position = db.execute(
                        "SELECT COALESCE(MAX(position), ?) FROM tasks WHERE parent_id = ?",
                        (parent[1], parent_id),
                    ).fetchone()[0]
                    position = last_child_position + 1
                    db.execute(
                        "UPDATE tasks SET position = position + 1 WHERE workspace = ? AND location = ? AND (? = 'inbox' OR task_date = ?) AND position >= ?",
                        (workspace, location, location, task_date, position),
                    )
                else:
                    position = db.execute(
                        "SELECT COALESCE(MAX(position), -1) + 1 FROM tasks WHERE workspace = ? AND location = ? AND (? = 'inbox' OR task_date = ?)",
                        (workspace, location, location, task_date),
                    ).fetchone()[0]
                cursor = db.execute(
                    "INSERT INTO tasks (title, position, task_date, location, planning_kind, planning_value, parent_id, workspace) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (title, position, task_date, location, planning_kind, planning_value, parent_id, workspace),
                )
                if parent_id is not None:
                    db.execute("UPDATE tasks SET completed = 0 WHERE id = ?", (parent_id,))
                row = db.execute(
                    "SELECT id, title, position, completed, task_date, location, label, label_color, starred, parent_id, planning_kind, planning_value, routine_occurrence_id, routine_scheduled_date, overdue_ignored, completed_at, follow_until_complete, carried_from_date, workspace, created_at FROM tasks WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
            self.send_json(dict(row), 201)
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)

    def do_PUT(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        try:
            workspace = valid_workspace(parse_qs(parsed_url.query).get("workspace", ["personal"])[0])
        except ValueError as error:
            self.send_json({"error": str(error)}, 400)
            return
        checklist_match = re.fullmatch(r"/api/lists/(\d+)", path)
        if checklist_match:
            try:
                checklist_id = int(checklist_match.group(1))
                title = str(self.read_json().get("title", "")).strip()
                if not title or len(title) > 280:
                    raise ValueError("Enter a list name between 1 and 280 characters")
                with connect() as db:
                    cursor = db.execute(
                        "UPDATE checklists SET title = ? WHERE id = ? AND workspace = ?",
                        (title, checklist_id, workspace),
                    )
                if cursor.rowcount == 0:
                    self.send_json({"error": "List not found"}, 404)
                else:
                    self.send_json({"id": checklist_id, "title": title})
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            return
        checklist_item_match = re.fullmatch(r"/api/list-items/(\d+)", path)
        if checklist_item_match:
            try:
                item_id = int(checklist_item_match.group(1))
                payload = self.read_json()
                updates, values = [], []
                if "completed" in payload:
                    if not isinstance(payload["completed"], bool):
                        raise ValueError("Invalid completion status")
                    updates.append("completed = ?")
                    values.append(int(payload["completed"]))
                if "title" in payload:
                    title = str(payload["title"]).strip()
                    if not title or len(title) > 280:
                        raise ValueError("Enter an item between 1 and 280 characters")
                    updates.append("title = ?")
                    values.append(title)
                if not updates:
                    raise ValueError("Nothing to update")
                values.extend((item_id, workspace))
                with connect() as db:
                    cursor = db.execute(
                        f"UPDATE checklist_items SET {', '.join(updates)} WHERE id = ? AND checklist_id IN (SELECT id FROM checklists WHERE workspace = ?)",
                        values,
                    )
                    row = db.execute(
                        "SELECT id, checklist_id, title, completed, position, created_at FROM checklist_items WHERE id = ?",
                        (item_id,),
                    ).fetchone() if cursor.rowcount else None
                if row is None:
                    self.send_json({"error": "List item not found"}, 404)
                else:
                    self.send_json(dict(row))
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            return
        routine_match = re.fullmatch(r"/api/routines/(\d+)", path)
        if routine_match:
            try:
                routine_id = int(routine_match.group(1))
                payload = self.read_json()
                with connect() as db:
                    existing = db.execute("SELECT * FROM routines WHERE id = ? AND archived = 0 AND workspace = ?", (routine_id, workspace)).fetchone()
                    if existing is None:
                        self.send_json({"error": "Routine not found"}, 404)
                        return
                    materialize_routines(db, date.today() - timedelta(days=1), workspace)
                    schedule_keys = {
                        "title", "start_date", "frequency", "interval_value", "weekdays", "month_day",
                        "year_month", "year_day", "end_mode", "end_value", "follow_until_complete", "steps",
                    }
                    schedule_changed = any(key in payload for key in schedule_keys)
                    if schedule_changed:
                        parsed = parse_routine(payload, existing)
                        remove_pending_routine_occurrences(db, routine_id, date.today())
                        db.execute(
                            """UPDATE routines SET title = ?, start_date = ?, effective_date = ?, frequency = ?,
                               interval_value = ?, weekdays = ?, month_day = ?, year_month = ?, year_day = ?,
                               end_mode = ?, end_value = ?, follow_until_complete = ? WHERE id = ?""",
                            (
                                parsed["title"], parsed["start_date"], max(parsed["start_date"], date.today().isoformat()),
                                parsed["frequency"], parsed["interval_value"], parsed["weekdays"], parsed["month_day"],
                                parsed["year_month"], parsed["year_day"], parsed["end_mode"], parsed["end_value"],
                                parsed["follow_until_complete"], routine_id,
                            ),
                        )
                        if "steps" in payload:
                            steps = payload["steps"]
                            if not isinstance(steps, list):
                                raise ValueError("Invalid routine steps")
                            steps = [str(step).strip() for step in steps if str(step).strip()]
                            if any(len(step) > 280 for step in steps):
                                raise ValueError("Routine step is too long")
                            db.execute("DELETE FROM routine_steps WHERE routine_id = ?", (routine_id,))
                            db.executemany(
                                "INSERT INTO routine_steps (routine_id, title, position) VALUES (?, ?, ?)",
                                [(routine_id, step, position) for position, step in enumerate(steps)],
                            )
                    if "active" in payload:
                        if not isinstance(payload["active"], bool):
                            raise ValueError("Invalid routine status")
                        active = int(payload["active"])
                        if not active:
                            remove_pending_routine_occurrences(db, routine_id, date.today())
                        elif not existing["active"]:
                            db.execute("UPDATE routines SET effective_date = ? WHERE id = ?", (date.today().isoformat(), routine_id))
                        db.execute("UPDATE routines SET active = ? WHERE id = ?", (active, routine_id))
                    row = db.execute("SELECT * FROM routines WHERE id = ?", (routine_id,)).fetchone()
                    if row["active"]:
                        materialize_routines(db, date.today(), workspace)
                    result = routine_payload(db, row)
                self.send_json(result)
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            return
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
                values.extend((dream_id, workspace))
                with connect() as db:
                    cursor = db.execute(f"UPDATE dreams SET {', '.join(updates)} WHERE id = ? AND workspace = ?", values)
                    if cursor.rowcount == 0:
                        self.send_json({"error": "Dream not found"}, 404)
                        return
                    row = db.execute("SELECT id, title, expected_year, description, image_path, archived, workspace, created_at FROM dreams WHERE id = ? AND workspace = ?", (dream_id, workspace)).fetchone()
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
                    cursor = db.execute(
                        "UPDATE dream_items SET completed = ? WHERE id = ? AND dream_id IN (SELECT id FROM dreams WHERE workspace = ?)",
                        (int(payload["completed"]), item_id, workspace),
                    )
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
                canonical_label_color = None
                if "completed" in payload:
                    if not isinstance(payload["completed"], bool):
                        raise ValueError("Invalid completion status")
                    updates.append("completed = ?")
                    values.append(int(payload["completed"]))
                    updates.append("completed_at = CASE WHEN ? = 1 THEN COALESCE(completed_at, CURRENT_TIMESTAMP) ELSE NULL END")
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
                    if label:
                        with connect() as label_db:
                            existing_labels = label_db.execute(
                                "SELECT label, label_color FROM tasks WHERE workspace = ? AND id != ? AND label IS NOT NULL AND trim(label) != '' ORDER BY id",
                                (workspace, task_id),
                            ).fetchall()
                        canonical = next(
                            ((row[0].strip(), row[1] or "gray") for row in existing_labels if row[0].strip().casefold() == label.casefold()),
                            None,
                        )
                        if canonical is not None:
                            label, canonical_label_color = canonical
                    updates.append("label = ?")
                    values.append(label or None)
                if "label_color" in payload:
                    color = canonical_label_color or payload["label_color"]
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
                                "SELECT id, location, task_date, parent_id FROM tasks WHERE id = ? AND workspace = ?", (parent_id, workspace)
                            ).fetchone()
                            child = check_db.execute(
                                "SELECT location, task_date FROM tasks WHERE id = ? AND workspace = ?", (task_id, workspace)
                            ).fetchone()
                        if parent is None or child is None or parent[1] != child[0] or (child[0] == "day" and parent[2] != child[1]):
                            raise ValueError("Parent task must be in the same list")
                        if parent[3] is not None:
                            parent_id = parent[3]
                        if parent_id == task_id:
                            raise ValueError("Invalid parent task")
                    updates.append("parent_id = ?")
                    values.append(parent_id)
                if "starred" in payload:
                    if not isinstance(payload["starred"], bool):
                        raise ValueError("Invalid starred status")
                    if payload["starred"]:
                        with connect() as check_db:
                            scope = check_db.execute(
                                "SELECT location, task_date FROM tasks WHERE id = ? AND workspace = ?", (task_id, workspace)
                            ).fetchone()
                            if scope is None:
                                raise ValueError("Task not found")
                            starred_count = check_db.execute(
                                "SELECT COUNT(*) FROM tasks WHERE workspace = ? AND starred = 1 AND id != ? AND location = ? AND (? = 'inbox' OR task_date = ?)",
                                (workspace, task_id, scope[0], scope[0], scope[1]),
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
                values.extend((task_id, workspace))
                with connect() as db:
                    previous_parent = db.execute("SELECT parent_id FROM tasks WHERE id = ? AND workspace = ?", (task_id, workspace)).fetchone()
                    cursor = db.execute(
                        f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND workspace = ?",
                        values,
                    )
                    if cursor.rowcount == 0:
                        self.send_json({"error": "Task not found"}, 404)
                        return
                    if "completed" in payload:
                        children = db.execute("SELECT id FROM tasks WHERE parent_id = ?", (task_id,)).fetchall()
                        if children:
                            db.executemany(
                                "UPDATE tasks SET completed = ?, completed_at = CASE WHEN ? = 1 THEN COALESCE(completed_at, CURRENT_TIMESTAMP) ELSE NULL END WHERE id = ?",
                                [(int(payload["completed"]), int(payload["completed"]), child[0]) for child in children],
                            )
                        sync_ancestor_completion(db, task_id)
                    family_updates = []
                    family_values: list[object] = []
                    if "task_date" in payload:
                        family_updates.append("task_date = ?")
                        family_values.append(valid_date(payload["task_date"]))
                    if "location" in payload:
                        family_updates.append("location = ?")
                        family_values.append(payload["location"])
                    if family_updates:
                        db.execute(
                            f"UPDATE tasks SET {', '.join(family_updates)} WHERE parent_id = ?",
                            [*family_values, task_id],
                        )
                    if "parent_id" in payload:
                        old_parent_id = previous_parent[0] if previous_parent is not None else None
                        if old_parent_id is not None and old_parent_id != parent_id:
                            sync_task_completion_from_children(db, old_parent_id)
                        if parent_id is not None:
                            sync_task_completion_from_children(db, parent_id)
                    row = db.execute(
                        "SELECT id, title, position, completed, task_date, location, label, label_color, starred, parent_id, planning_kind, planning_value, routine_occurrence_id, routine_scheduled_date, overdue_ignored, completed_at, follow_until_complete, carried_from_date, workspace, created_at FROM tasks WHERE id = ?",
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
                    "SELECT id FROM tasks WHERE workspace = ? AND location = ? AND (? = 'inbox' OR task_date = ?)",
                    (workspace, location, location, task_date),
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
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        try:
            workspace = valid_workspace(parse_qs(parsed_url.query).get("workspace", ["personal"])[0])
        except ValueError as error:
            self.send_json({"error": str(error)}, 400)
            return
        checklist_match = re.fullmatch(r"/api/lists/(\d+)", path)
        if checklist_match:
            checklist_id = int(checklist_match.group(1))
            with connect() as db:
                existing = db.execute(
                    "SELECT 1 FROM checklists WHERE id = ? AND workspace = ?",
                    (checklist_id, workspace),
                ).fetchone()
                if existing is None:
                    self.send_json({"error": "List not found"}, 404)
                    return
                db.execute("DELETE FROM checklist_items WHERE checklist_id = ?", (checklist_id,))
                db.execute("DELETE FROM checklists WHERE id = ?", (checklist_id,))
            self.send_json({"ok": True})
            return
        checklist_item_match = re.fullmatch(r"/api/list-items/(\d+)", path)
        if checklist_item_match:
            item_id = int(checklist_item_match.group(1))
            with connect() as db:
                row = db.execute(
                    "SELECT checklist_id, position FROM checklist_items WHERE id = ? AND checklist_id IN (SELECT id FROM checklists WHERE workspace = ?)",
                    (item_id, workspace),
                ).fetchone()
                if row is None:
                    self.send_json({"error": "List item not found"}, 404)
                    return
                db.execute("DELETE FROM checklist_items WHERE id = ?", (item_id,))
                db.execute(
                    "UPDATE checklist_items SET position = position - 1 WHERE checklist_id = ? AND position > ?",
                    (row[0], row[1]),
                )
            self.send_json({"ok": True})
            return
        routine_match = re.fullmatch(r"/api/routines/(\d+)", path)
        if routine_match:
            routine_id = int(routine_match.group(1))
            with connect() as db:
                existing = db.execute("SELECT id FROM routines WHERE id = ? AND archived = 0 AND workspace = ?", (routine_id, workspace)).fetchone()
                if existing is None:
                    self.send_json({"error": "Routine not found"}, 404)
                    return
                materialize_routines(db, date.today() - timedelta(days=1), workspace)
                remove_pending_routine_occurrences(db, routine_id, date.today())
                db.execute("UPDATE routines SET active = 0, archived = 1 WHERE id = ?", (routine_id,))
            self.send_json({"ok": True})
            return
        if not path.startswith("/api/tasks/"):
            self.send_error(404)
            return
        try:
            task_id = int(path.rsplit("/", 1)[-1])
            with connect() as db:
                task_row = db.execute("SELECT task_date, location, parent_id, routine_occurrence_id FROM tasks WHERE id = ? AND workspace = ?", (task_id, workspace)).fetchone()
                if task_row is None:
                    self.send_json({"error": "Task not found"}, 404)
                    return
                if task_row[3] is not None and task_row[2] is None:
                    cursor = db.execute("DELETE FROM tasks WHERE routine_occurrence_id = ?", (task_row[3],))
                    db.execute("UPDATE routine_occurrences SET task_id = NULL WHERE id = ?", (task_row[3],))
                else:
                    cursor = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                    db.execute("UPDATE tasks SET parent_id = NULL WHERE parent_id = ?", (task_id,))
                if task_row[2] is not None:
                    parent_id = task_row[2]
                    child_counts = db.execute(
                        "SELECT COUNT(*), SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) FROM tasks WHERE parent_id = ?",
                        (parent_id,),
                    ).fetchone()
                    if child_counts[0] > 0:
                        db.execute("UPDATE tasks SET completed = ? WHERE id = ?", (int(child_counts[0] == child_counts[1]), parent_id))
                    sync_ancestor_completion(db, parent_id)
                rows = db.execute(
                    "SELECT id FROM tasks WHERE workspace = ? AND location = ? AND (? = 'inbox' OR task_date = ?) ORDER BY position, id",
                    (workspace, task_row[1], task_row[1], task_row[0]),
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
    host = os.environ.get("TASKLINE_HOST", "0.0.0.0")
    port = int(os.environ.get("TASKLINE_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), TodoHandler)
    print(f"Taskline is running at http://{host}:{port}")
    print("Press Ctrl+C to stop it.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTaskline stopped.")
    finally:
        server.server_close()
