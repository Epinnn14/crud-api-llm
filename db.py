"""SQLite storage for the Task API. The database file is created on first use."""
import os
import sqlite3

DB_PATH = os.environ.get("TASKS_DB", "tasks.db")

SEED = [
    ("Read the A1 brief", 1),
    ("Build the CRUD API", 0),
    ("Publish to GitHub", 0),
]


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the table if it is missing and seed 3 tasks only when the table is empty."""
    with connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS tasks (
                   id    INTEGER PRIMARY KEY AUTOINCREMENT,
                   title TEXT    NOT NULL,
                   done  INTEGER NOT NULL DEFAULT 0 CHECK (done IN (0, 1))
               )"""
        )
        (count,) = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()
        if count == 0:
            conn.executemany("INSERT INTO tasks (title, done) VALUES (?, ?)", SEED)


def to_task(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "title": row["title"], "done": bool(row["done"])}


def list_tasks() -> list[dict]:
    with connect() as conn:
        return [to_task(r) for r in conn.execute("SELECT * FROM tasks ORDER BY id")]


def get_task(task_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return to_task(row) if row else None


def create_task(title: str) -> dict:
    with connect() as conn:
        cur = conn.execute("INSERT INTO tasks (title, done) VALUES (?, ?)", (title, 0))
        new_id = cur.lastrowid
    return get_task(new_id)
