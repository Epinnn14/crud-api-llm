# Task API on SQLite (FlyRank Backend track, A2: Connecting your CRUD to the database)

This is the A1 to-do API, with the same five endpoints, the same requests and the same responses. The tasks now live in
**SQLite** (`tasks.db`) instead of a Python list, so **the data survives a restart**. This repo continues A1: the first
8 commits are A1, and the A2 stages follow.

## Run it

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload        # → http://localhost:8000  ·  docs: /docs
```

That one command is the whole setup. On the first start, `tasks.db` is **created automatically** next to `main.py`,
along with the `tasks` table and the 3 example tasks. The seed runs **only when the table is empty**, so restarting
never duplicates it. `tasks.db` is git-ignored, so every clone starts fresh. To start over, delete `tasks.db` (or call
`POST /reset`).

Tests: `pip install -r requirements-dev.txt` then `pytest -q`. All **15 pass**, and that includes all 12 A1 tests, unchanged.

## Why SQLite

- **One file, zero setup.** There's no database server to install, and `sqlite3` ships with Python.
- **The data survives restarts.** It's on disk, not in the process's memory.
- **It's a real SQL database,** so the same queries will carry over to Postgres in A3.

## What changed (and what didn't)

| Layer | A1 | A2 |
|---|---|---|
| Routes / API contract | 5 task endpoints, 200/201/204/400/404 | **unchanged** |
| Storage | a list in `main.py` | `db.py`: parameterized SQL against `tasks.db` |

The routes call `db.list_tasks()`, `db.create_task()` and so on, and only `db.py` knows SQL exists.

**Proof the API didn't change:** the 12 A1 tests run against the SQLite version and still pass. That's what "storage is
just an implementation detail" means: if every observable behaviour is identical, the client can't tell where the data lives.

**Every query is parameterized** (`WHERE id = ?`). User input is never glued into SQL text. A test sends
`search=x' OR '1'='1` and gets an empty list back, not every row.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/tasks` | `?done=true` · `?search=milk` (SQL `LIKE`) · `?sort=id\|title\|created_at` · `?limit=&offset=` |
| GET | `/tasks/{id}` | 200, or 404 `{"error":"Task 999 not found"}` |
| POST | `/tasks` | `{"title":"..."}` returns **201** with the id the database assigned. A missing or empty title returns 400 |
| PUT | `/tasks/{id}` | `title` and/or `done` return 200. An empty body returns 400, an unknown id returns 404. `updated_at` is refreshed |
| DELETE | `/tasks/{id}` | **204** with an empty body, or 404 |
| GET | `/stats` | `SELECT COUNT(*), SUM(done)` computed in SQL |
| POST | `/reset` | Re-seeds the 3 tasks in **one transaction** (all or nothing) |

## Persistence proof (real run)

The server was started, a task was created, the server was stopped, and this was repeated 3 times:

```text
start 1: {"total":4,"done":1,"open":3}     ← "Buy milk" created on this run
start 2: {"total":4,"done":1,"open":3}     ← still 4 after a restart, seed did not run again
start 3: {"total":4,"done":1,"open":3}

$ curl -i http://localhost:8000/tasks/4
HTTP/1.1 200 OK
{"id":4,"title":"Buy milk","done":false,"created_at":"2026-10-22T06:05:14Z","updated_at":"2026-10-22T06:05:14Z"}

$ curl -i http://localhost:8000/tasks/999
HTTP/1.1 404 Not Found
{"error":"Task 999 not found"}
```

## SQL by hand (Stage 4)

The full transcript is in [docs/sql-by-hand.md](docs/sql-by-hand.md). One query from it:

```sql
SELECT * FROM tasks WHERE done = 1;   -- returned 1 row: "Read the A1 brief"
```

After `UPDATE tasks SET done = 1;` was run straight on the file, `GET /tasks` immediately showed every task as done,
with no restart. The API and the SQL session read the **same file**, so there's one source of truth.

<!-- TODO before submitting: open tasks.db in DB Browser for SQLite, take a screenshot, save it as docs/db-browser.png, then replace this comment with: ![tasks.db in DB Browser for SQLite](docs/db-browser.png) -->

## Extras and stretch

- **Search, filter, sort and paging in SQL:** `LIKE`, `WHERE done = ?`, `ORDER BY` (from a fixed whitelist) and `LIMIT/OFFSET`.
- **Timestamps:** `created_at` and `updated_at`.
  - Changing the table's shape meant an old `tasks.db` was missing those columns. `init_db()` now checks
    `PRAGMA table_info` and adds them with `ALTER TABLE`.
  - Doing that by hand for every schema change would get messy fast, and that is exactly why migration tools exist.
- **Index:** `idx_tasks_done` on `done`. An index is a sorted lookup structure, so `WHERE done = 1` doesn't have to scan
  every row.
- **Transaction:** the reset/seed runs inside one transaction, so a crash halfway can't leave a half-seeded table.

## How AI was used

This project was built **with an AI assistant (Claude)**. The brief asks for the stages to be done by hand, and this
version wasn't, so it's stated here openly. Everything above was verified by running it:

- the 15 tests
- the restart transcript
- the SQL session

The optional "AI vs me" stage is not included, because there is no hand-built version to compare against.
