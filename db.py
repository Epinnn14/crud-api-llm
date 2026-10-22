"""Storage facade used by the routes. It picks ONE backend at startup:

- DATABASE_URL=postgresql://...  → Postgres (A3, via Docker)
- otherwise                      → SQLite file TASKS_DB (default tasks.db, the A2 behaviour)

Routes keep calling db.list_tasks(), db.create_task(), ... exactly as in A2.
Switching storage changed this file and added storage/postgres_repo.py; main.py did not change.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

from storage.base import TaskRepository

load_dotenv()


def create_repository() -> TaskRepository:
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith(("postgresql://", "postgres://")):
        from storage.postgres_repo import PostgresTaskRepository
        return PostgresTaskRepository(url)
    from storage.sqlite_repo import SqliteTaskRepository
    return SqliteTaskRepository(os.environ.get("TASKS_DB", "tasks.db"))


repo: TaskRepository = create_repository()


def backend_name() -> str:
    return type(repo).__name__


def init_db() -> None:
    repo.init()


def list_tasks(done=None, search=None, sort="id", limit=None, offset=0):
    return repo.list_tasks(done=done, search=search, sort=sort, limit=limit, offset=offset)


def get_task(task_id):
    return repo.get_task(task_id)


def create_task(title):
    return repo.create_task(title)


def update_task(task_id, title, done):
    return repo.update_task(task_id, title, done)


def delete_task(task_id):
    return repo.delete_task(task_id)


def stats():
    return repo.stats()


def reset():
    return repo.reset()
