# Stage 4: SQL by hand

The queries from the brief, run directly against `tasks.db` while the API was running. Between queries, the API reads the same file, so every change shows up through `GET /tasks` right away, with no restart and no syncing.

To see it visually, open `tasks.db` in **DB Browser for SQLite** (Browse Data → `tasks`, Execute SQL tab). The screenshot for the README is `docs/db-browser.png`.

```text
sqlite> SELECT * FROM tasks;
id | title | done
1 | Read the A1 brief | 1
2 | Build the CRUD API | 0
3 | Publish to GitHub | 0
4 | Buy milk | 0

sqlite> SELECT * FROM tasks WHERE done = 1;
id | title | done
1 | Read the A1 brief | 1

sqlite> SELECT COUNT(*) FROM tasks;
COUNT(*)
4

sqlite> UPDATE tasks SET done = 1;
-- 4 row(s) changed

$ curl -s http://localhost:8000/tasks   # API sees the change immediately, no restart
[{"id":1,"title":"Read the A1 brief","done":true},{"id":2,"title":"Build the CRUD API","done":true},{"id":3,"title":"Publish to GitHub","done":true},{"id":4,"title":"Buy milk","done":true}]

sqlite> DELETE FROM tasks WHERE done = 1;
-- 4 row(s) changed

$ curl -s http://localhost:8000/tasks
[]
```
