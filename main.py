from fastapi import FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

import db

app = FastAPI(
    title="Task API",
    version="1.0",
    description="A small to-do API: full CRUD on an SQLite database (FlyRank Backend track, A2).",
)

db.init_db()

ERROR = {"content": {"application/json": {"example": {"error": "Task 99 not found"}}}}

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be empty")
        return v.strip()


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    done: bool | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("title must not be empty")
        return v.strip() if v else v


def bad_request(message: str) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": message})


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    # FastAPI answers 422 by default; this API's contract is 400 + {"error": ...}.
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"] if p != "body") or "body"
    return JSONResponse(status_code=400, content={"error": f"{field}: {first['msg']}"})


def not_found(task_id: int) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": f"Task {task_id} not found"})


@app.get("/", tags=["meta"], summary="Describe this API")
def root():
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health", tags=["meta"], summary="Liveness check")
def health():
    return {"status": "ok"}


@app.get("/tasks", tags=["tasks"], summary="List tasks (optional filter, search and pagination)")
def list_tasks(
    done: bool | None = Query(default=None, description="Only finished (true) or open (false) tasks"),
    search: str | None = Query(default=None, description="Case-insensitive text search in the title"),
    limit: int | None = Query(default=None, ge=1, le=100, description="Page size"),
    offset: int = Query(default=0, ge=0, description="How many tasks to skip"),
):
    result = db.list_tasks()
    if done is not None:
        result = [t for t in result if t["done"] == done]
    if search:
        result = [t for t in result if search.lower() in t["title"].lower()]
    result = result[offset:]
    return result[:limit] if limit else result


@app.get("/stats", tags=["extras"], summary="Counts of all, finished and open tasks")
def stats():
    return db.stats()


@app.post("/reset", tags=["extras"], summary="Restore the three example tasks")
def reset():
    return db.reset()


@app.get("/tasks/{task_id}", tags=["tasks"], summary="Get one task", responses={404: {"description": "Unknown id", **ERROR}})
def get_task(task_id: int):
    task = db.get_task(task_id)
    return task if task else not_found(task_id)


@app.post("/tasks", status_code=201, tags=["tasks"], summary="Create a task", responses={400: {"description": "Missing or empty title"}})
def create_task(body: TaskCreate):
    return db.create_task(body.title)


@app.put("/tasks/{task_id}", tags=["tasks"], summary="Update a task's title and/or done flag", responses={400: {"description": "Empty or invalid body"}, 404: {"description": "Unknown id", **ERROR}})
def update_task(task_id: int, body: TaskUpdate):
    if body.title is None and body.done is None:
        return bad_request("body must contain 'title' and/or 'done'")
    task = db.update_task(task_id, body.title, body.done)
    return task if task else not_found(task_id)


@app.delete("/tasks/{task_id}", status_code=204, tags=["tasks"], summary="Delete a task", responses={404: {"description": "Unknown id", **ERROR}})
def delete_task(task_id: int):
    if not db.delete_task(task_id):
        return not_found(task_id)
    return Response(status_code=204)
