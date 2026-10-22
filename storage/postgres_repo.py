"""Postgres implementation of TaskRepository (A3). Same interface, same behaviour as SQLite."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .base import SEED

SCHEMA = Path(__file__).resolve().parent.parent / "sql" / "001_create_tasks.sql"
_SORT_SQL = {"id": "id", "title": "lower(title)", "created_at": "created_at"}


def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class PostgresTaskRepository:
    def __init__(self, url: str):
        self.url = url

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.url, row_factory=dict_row)

    def init(self) -> None:
        with self._connect() as conn:  # `with` = one transaction, committed on success
            conn.execute(SCHEMA.read_text())
            if conn.execute("SELECT COUNT(*) AS n FROM tasks").fetchone()["n"] == 0:
                with conn.cursor() as cur:
                    cur.executemany("INSERT INTO tasks (title, done) VALUES (%s, %s)", SEED)

    @staticmethod
    def _to_task(row: dict) -> dict:
        return {"id": row["id"], "title": row["title"], "done": row["done"],
                "created_at": _iso(row["created_at"]), "updated_at": _iso(row["updated_at"])}

    def list_tasks(self, done=None, search=None, sort="id", limit=None, offset=0) -> list[dict]:
        where, params = [], []
        if done is not None:
            where.append("done = %s")
            params.append(done)
        if search:
            where.append("title ILIKE %s")  # case-insensitive, like SQLite's LIKE
            params.append(f"%{search}%")
        sql = "SELECT * FROM tasks" + (" WHERE " + " AND ".join(where) if where else "")
        sql += f" ORDER BY {_SORT_SQL[sort]}, id LIMIT %s OFFSET %s"
        params += [limit, offset]  # LIMIT NULL = no limit in Postgres
        with self._connect() as conn:
            return [self._to_task(r) for r in conn.execute(sql, params)]

    def get_task(self, task_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = %s", (task_id,)).fetchone()
        return self._to_task(row) if row else None

    def create_task(self, title: str) -> dict:
        with self._connect() as conn:
            row = conn.execute("INSERT INTO tasks (title) VALUES (%s) RETURNING *", (title,)).fetchone()
        return self._to_task(row)

    def update_task(self, task_id: int, title: str | None, done: bool | None) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """UPDATE tasks
                      SET title = COALESCE(%s, title), done = COALESCE(%s, done), updated_at = now()
                    WHERE id = %s RETURNING *""",
                (title, done, task_id),
            ).fetchone()
        return self._to_task(row) if row else None

    def delete_task(self, task_id: int) -> bool:
        with self._connect() as conn:
            return conn.execute("DELETE FROM tasks WHERE id = %s", (task_id,)).rowcount == 1

    def stats(self) -> dict:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE done) AS done FROM tasks").fetchone()
        return {"total": row["total"], "done": row["done"], "open": row["total"] - row["done"]}

    def reset(self) -> list[dict]:
        with self._connect() as conn:  # one transaction
            conn.execute("TRUNCATE tasks RESTART IDENTITY")
            with conn.cursor() as cur:
                cur.executemany("INSERT INTO tasks (title, done) VALUES (%s, %s)", SEED)
        return self.list_tasks()
