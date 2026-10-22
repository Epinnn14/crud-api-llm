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
