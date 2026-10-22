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
                   id         INTEGER PRIMARY KEY AUTOINCREMENT,
                   title      TEXT    NOT NULL,
                   done       INTEGER NOT NULL DEFAULT 0 CHECK (done IN (0, 1)),
                   created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                   updated_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
               )"""
        )
        # A database created by an earlier version has no timestamp columns: add them (a tiny hand-made migration).
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
        for col in ("created_at", "updated_at"):
            if col not in columns:
                conn.execute(f"ALTER TABLE tasks ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
        # The done filter is the most common query, so it gets an index.
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_done ON tasks (done)")
        (count,) = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()
        if count == 0:
            conn.executemany("INSERT INTO tasks (title, done) VALUES (?, ?)", SEED)


def to_task(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "done": bool(row["done"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


SORTS = {"id": "id", "title": "title COLLATE NOCASE", "created_at": "created_at"}


def list_tasks(done: bool | None = None, search: str | None = None, sort: str = "id",
               limit: int | None = None, offset: int = 0) -> list[dict]:
    """Filtering, searching, sorting and paging all happen in SQL, not in a Python loop."""
    where, params = [], []
    if done is not None:
        where.append("done = ?")
        params.append(int(done))
    if search:
        where.append("title LIKE ?")
        params.append(f"%{search}%")
    sql = "SELECT * FROM tasks"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {SORTS[sort]}, id"  # sort comes from a fixed whitelist, never from raw user text
    sql += " LIMIT ? OFFSET ?"
    params += [limit if limit is not None else -1, offset]
    with connect() as conn:
        return [to_task(r) for r in conn.execute(sql, params)]


def get_task(task_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return to_task(row) if row else None


def create_task(title: str) -> dict:
    with connect() as conn:
        cur = conn.execute("INSERT INTO tasks (title, done) VALUES (?, ?)", (title, 0))
        new_id = cur.lastrowid
    return get_task(new_id)


def update_task(task_id: int, title: str | None, done: bool | None) -> dict | None:
    current = get_task(task_id)
    if current is None:
        return None
    new_title = title if title is not None else current["title"]
    new_done = done if done is not None else current["done"]
    with connect() as conn:
        conn.execute(
            "UPDATE tasks SET title = ?, done = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
            (new_title, int(new_done), task_id),
        )
    return get_task(task_id)


def delete_task(task_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return cur.rowcount == 1


def stats() -> dict:
    with connect() as conn:
        total, done = conn.execute("SELECT COUNT(*), COALESCE(SUM(done), 0) FROM tasks").fetchone()
    return {"total": total, "done": done, "open": total - done}


def reset() -> list[dict]:
    """Delete everything and re-seed, as one transaction (all-or-nothing)."""
    with connect() as conn:
        conn.execute("DELETE FROM tasks")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'tasks'")
        conn.executemany("INSERT INTO tasks (title, done) VALUES (?, ?)", SEED)
    return list_tasks()
