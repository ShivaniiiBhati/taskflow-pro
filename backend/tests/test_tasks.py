from datetime import date
from tests.helpers import create_task, get_task, set_status


def test_create_task(client):
    task = create_task(client, "Design schema", duration_days=3)
    assert task["title"] == "Design schema"
    assert task["status"] == "BACKLOG"
    assert task["readiness"] == "READY"  # no predecessors yet
    assert task["dependency_count"] == 0


def test_update_task_fields(client):
    task = create_task(client, "Write docs")
    resp = client.patch(f"/tasks/{task['id']}", json={"title": "Write docs v2"})
    assert resp.status_code == 200
    assert resp.json()["task"]["title"] == "Write docs v2"


def test_move_task_persists_status(client):
    """Simulates a drag-and-drop card move."""
    task = create_task(client, "Build API")
    set_status(client, task["id"], "IN_PROGRESS")

    reloaded = get_task(client, task["id"])
    assert reloaded["status"] == "IN_PROGRESS"


def test_persistence_across_simulated_refresh(client):
    """
    A 'refresh' in a stateless REST API is just a fresh GET -- this
    confirms nothing about task state depends on in-memory request
    state, only on what's actually committed to the DB.
    """
    task = create_task(client, "Persisted task", duration_days=2)
    set_status(client, task["id"], "REVIEW")

    fetched_again = get_task(client, task["id"])
    assert fetched_again["status"] == "REVIEW"
    assert fetched_again["duration_days"] == 2


def test_list_tasks_returns_all(client):
    create_task(client, "Task A")
    create_task(client, "Task B")
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_delete_task_removes_it(client):
    task = create_task(client, "Temp task")
    resp = client.delete(f"/tasks/{task['id']}")
    assert resp.status_code == 204
    assert client.get(f"/tasks/{task['id']}").status_code == 404


def test_invalid_status_rejected(client):
    task = create_task(client, "Bad status test")
    resp = client.patch(f"/tasks/{task['id']}", json={"status": "NOT_A_REAL_STATUS"})
    assert resp.status_code == 400
