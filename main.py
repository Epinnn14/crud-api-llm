from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Task API", version="1.0")

# In-memory "database": gone when the server stops (that's the lesson of A1).
tasks: list[dict] = [
    {"id": 1, "title": "Read the A1 brief", "done": True},
    {"id": 2, "title": "Build the CRUD API", "done": False},
    {"id": 3, "title": "Publish to GitHub", "done": False},
]


def not_found(task_id: int) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": f"Task {task_id} not found"})


@app.get("/")
def root():
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tasks")
def list_tasks():
    return tasks


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    for task in tasks:
        if task["id"] == task_id:
            return task
    return not_found(task_id)
