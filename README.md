# Task API on Postgres + Docker (FlyRank Backend track, A3: Containerize your stack)

This is the A1/A2 to-do API, now backed by **Postgres running in Docker**. The app and the database start together with
**one command**, and the data lives in a Docker **volume**, so it survives app and container restarts. This repo continues
A2: A1's commits come first, then A2's, then A3's.

## Run the whole stack

Needs Docker Desktop.

```powershell
copy .env.example .env          # macOS/Linux: cp .env.example .env   (then change the password)
docker compose up --build       # → API on http://localhost:8000 · Swagger /docs · Postgres on localhost:5432
```

- On a brand-new volume, Postgres runs `sql/001_create_tasks.sql`. The app runs the same file on every start, and the
  file is idempotent (`CREATE TABLE IF NOT EXISTS`). Then the app seeds 3 tasks, but only if the table is empty.
- To stop the stack: `docker compose down`. That keeps the data.
- To wipe the data too: `docker compose down -v`.

To run the API on your machine instead of in Docker, while still using the Postgres container:

```powershell
docker compose up -d db
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt
uvicorn main:app --reload       # DATABASE_URL from .env points at localhost:5432
```

## The architecture proving itself

```
routes (main.py)  ──calls──▶  db.py (facade)  ──▶  TaskRepository interface (storage/base.py)
                                                     ├── SqliteTaskRepository   (A2, file tasks.db)
                                                     └── PostgresTaskRepository (A3, Docker)
```

- **Service and routes unchanged:** `git diff a2-sqlite -- main.py` is empty. Switching storage meant adding
  `storage/postgres_repo.py` and having `db.py` pick a backend from `DATABASE_URL`. If `DATABASE_URL` isn't set, the A2
  SQLite file is used.
- **Same tests, both backends:** the 15 tests (12 from A1 and 3 from A2) pass unchanged against both:

  ```text
  $ pytest -q                                                    → 15 passed   (SQLite)
  $ DATABASE_URL=postgresql://…/tasks_test pytest -q             → 15 passed   (Postgres 16)
  ```

- **Every query is parameterized** (`%s` placeholders). The `ORDER BY` column comes from a fixed whitelist, never from
  user input.

## Configuration and secrets

- **The connection string** comes from `.env`, which is git-ignored. `.env.example` is committed with placeholder values.
- **Inside compose,** the app reaches the database at host `db` (the service name), not `localhost`.

## Persistence proof

The app was run against a real Postgres 16 server:

1. Create a task.
2. Stop the app **and restart the Postgres server**.
3. Start the app again.

```text
{"id":4,"title":"Survive a Postgres restart","done":false,"created_at":"2026-10-22T06:07:22Z", ...}
after app + Postgres restart:
HTTP/1.1 200 OK
{"id":4,"title":"Survive a Postgres restart","done":false,"created_at":"2026-10-22T06:07:22Z", ...}
{"total":4,"done":1,"open":3}        ← 4 tasks, so the seed did not run a second time
```

**The same check with Docker:**

```powershell
curl.exe -X POST http://localhost:8000/tasks -H "Content-Type: application/json" -d '{\"title\":\"Survive a restart\"}'
docker compose restart          # restarts BOTH the app and the db containers
curl.exe http://localhost:8000/tasks
```

The task is still there, because it's stored in the `pgdata` volume and not inside the container.

## Stretch: index + EXPLAIN ANALYZE

`idx_tasks_done` on `done`. On 200,000 rows, `WHERE done = true` went from a **10.1 ms** sequential scan to a
**1.3 ms** index scan. The full output is in [docs/explain-analyze.md](docs/explain-analyze.md).

## Limitations

- `docker-compose.yml` wasn't run in the build environment, because Docker wasn't available there. The Postgres code
  path was tested against a local Postgres 16 server. The compose stack itself still needs to be checked on a machine
  with Docker (see *Run the whole stack* above).
- The schema is created by an idempotent SQL file, not a migration tool. That's fine for one table, but a real project
  would use Alembic.

## How AI was used

Built **with an AI assistant (Claude)**, and stated openly here. Verified by running it:

- 15 tests on SQLite and 15 on Postgres
- the restart transcript
- the EXPLAIN output
