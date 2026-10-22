"""Checkpoint tests for A1: the same checks as the curl commands in the README."""
import pytest
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def fresh_data():
    client.post("/reset")


def test_root_and_health():
    assert client.get("/").json()["endpoints"] == ["/tasks"]
    assert client.get("/health").json() == {"status": "ok"}


def test_read_list_and_one():
    assert len(client.get("/tasks").json()) == 3
    r = client.get("/tasks/1")
    assert r.status_code == 200 and r.json()["id"] == 1


def test_unknown_id_is_404_with_error():
    r = client.get("/tasks/99")
    assert r.status_code == 404 and r.json() == {"error": "Task 99 not found"}


def test_create_201_and_listed():
    r = client.post("/tasks", json={"title": "Buy milk"})
    assert r.status_code == 201
    assert r.json() == {"id": 4, "title": "Buy milk", "done": False}
    assert any(t["title"] == "Buy milk" for t in client.get("/tasks").json())


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "   "}, {"title": 5}])
def test_create_rejects_bad_title_with_400(body):
    r = client.post("/tasks", json=body)
    assert r.status_code == 400 and "error" in r.json()


def test_update_and_empty_body():
    r = client.put("/tasks/2", json={"done": True})
    assert r.status_code == 200 and r.json()["done"] is True
    assert client.put("/tasks/2", json={}).status_code == 400
    assert client.put("/tasks/2", json={"title": ""}).status_code == 400
    assert client.put("/tasks/99", json={"done": True}).status_code == 404


def test_delete_204_then_404():
    r = client.delete("/tasks/3")
    assert r.status_code == 204 and r.content == b""
    assert client.delete("/tasks/3").status_code == 404
    assert client.get("/tasks/3").status_code == 404


def test_ids_are_not_reused_after_delete():
    client.delete("/tasks/3")
    assert client.post("/tasks", json={"title": "new"}).json()["id"] == 4


def test_extras_filter_search_stats_pagination():
    client.put("/tasks/2", json={"done": True})
    assert [t["id"] for t in client.get("/tasks?done=true").json()] == [1, 2]
    assert [t["id"] for t in client.get("/tasks?search=github").json()] == [3]
    assert client.get("/stats").json() == {"total": 3, "done": 2, "open": 1}
    assert [t["id"] for t in client.get("/tasks?limit=2&offset=1").json()] == [2, 3]
