"""SQLite implementation of TaskRepository (the A2 storage, unchanged behaviour)."""
from __future__ import annotations

import sqlite3

from .base import SEED

_SORT_SQL = {"id": "id", "title": "title COLLATE NOCASE", "created_at": "created_at"}


class SqliteTaskRepository:
    def __init__(self, path: str):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        """Create the table if missing and seed 3 tasks only when the table is empty."""
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS tasks (
                       id         INTEGER PRIMARY KEY AUTOINCREMENT,
                       title      TEXT    NOT NULL,
                       done       INTEGER NOT NULL DEFAULT 0 CHECK (done IN (0, 1)),
                       created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                       updated_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                   )"""
            )
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
            for col in ("created_at", "updated_at"):
                if col not in columns:
                    conn.execute(f"ALTER TABLE tasks ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_done ON tasks (done)")
            (count,) = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()
            if count == 0:
                conn.executemany("INSERT INTO tasks (title, done) VALUES (?, ?)", [(t, int(d)) for t, d in SEED])

    @staticmethod
    def _to_task(row: sqlite3.Row) -> dict:
        return {"id": row["id"], "title": row["title"], "done": bool(row["done"]),
                "created_at": row["created_at"], "updated_at": row["updated_at"]}

    def list_tasks(self, done=None, search=None, sort="id", limit=None, offset=0) -> list[dict]:
        where, params = [], []
        if done is not None:
            where.append("done = ?")
            params.append(int(done))
        if search:
            where.append("title LIKE ?")
            params.append(f"%{search}%")
        sql = "SELECT * FROM tasks" + (" WHERE " + " AND ".join(where) if where else "")
        sql += f" ORDER BY {_SORT_SQL[sort]}, id LIMIT ? OFFSET ?"
        params += [limit if limit is not None else -1, offset]
        with self._connect() as conn:
            return [self._to_task(r) for r in conn.execute(sql, params)]

    def get_task(self, task_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._to_task(row) if row else None

    def create_task(self, title: str) -> dict:
        with self._connect() as conn:
            new_id = conn.execute("INSERT INTO tasks (title, done) VALUES (?, 0)", (title,)).lastrowid
        return self.get_task(new_id)

    def update_task(self, task_id: int, title: str | None, done: bool | None) -> dict | None:
        current = self.get_task(task_id)
        if current is None:
            return None
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET title = ?, done = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
                (title if title is not None else current["title"],
                 int(done if done is not None else current["done"]), task_id),
            )
        return self.get_task(task_id)

    def delete_task(self, task_id: int) -> bool:
        with self._connect() as conn:
            return conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,)).rowcount == 1

    def stats(self) -> dict:
        with self._connect() as conn:
            total, done = conn.execute("SELECT COUNT(*), COALESCE(SUM(done), 0) FROM tasks").fetchone()
        return {"total": total, "done": done, "open": total - done}

    def reset(self) -> list[dict]:
        with self._connect() as conn:  # one transaction: all or nothing
            conn.execute("DELETE FROM tasks")
            conn.execute("DELETE FROM sqlite_sequence WHERE name = 'tasks'")
            conn.executemany("INSERT INTO tasks (title, done) VALUES (?, ?)", [(t, int(d)) for t, d in SEED])
        return self.list_tasks()
