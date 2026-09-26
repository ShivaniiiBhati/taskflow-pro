from datetime import date, timedelta
from tests.helpers import create_task, link


def test_create_dependency_success(client):
    a = create_task(client, "A")
    b = create_task(client, "B")

    resp = link(client, a["id"], b["id"])
    assert resp.status_code == 201
    body = resp.json()
    assert body["predecessor_id"] == a["id"]
    assert body["successor_id"] == b["id"]

    resp = client.get("/dependencies")
    assert len(resp.json()) == 1


def test_dependency_with_missing_task_404s(client):
    a = create_task(client, "A")
    resp = link(client, a["id"], 99999)
    assert resp.status_code == 404


def test_duplicate_dependency_rejected(client):
    a = create_task(client, "A")
    b = create_task(client, "B")
    link(client, a["id"], b["id"])

    resp = link(client, a["id"], b["id"])
    assert resp.status_code == 409


def test_self_dependency_rejected(client):
    a = create_task(client, "A")
    resp = link(client, a["id"], a["id"])
    assert resp.status_code == 409


def test_new_task_becomes_blocked_when_predecessor_not_done(client):
    a = create_task(client, "A")
    b = create_task(client, "B")
    link(client, a["id"], b["id"])

    b_reloaded = client.get(f"/tasks/{b['id']}").json()
    assert b_reloaded["readiness"] == "BLOCKED"


def test_deleting_dependency_recomputes_readiness(client):
    a = create_task(client, "A")
    b = create_task(client, "B")
    dep = link(client, a["id"], b["id"]).json()

    assert client.get(f"/tasks/{b['id']}").json()["readiness"] == "BLOCKED"

    resp = client.delete(f"/dependencies/{dep['id']}")
    assert resp.status_code == 204

    # B has no predecessors left, so it should be Ready again.
    assert client.get(f"/tasks/{b['id']}").json()["readiness"] == "READY"

def test_adding_dependency_reconciles_successor_schedule(client):
    """
    If a dependency is added after tasks already have schedules,
    the successor must be pushed later when its prerequisite finishes
    after its current start date.
    """
    today = date.today()

    # A finishes on day +5.
    a = create_task(
        client,
        "A",
        duration_days=5,
        start_date=today,
    )

    # B currently starts on day +2, before A finishes.
    b = create_task(
        client,
        "B",
        duration_days=2,
        start_date=today + timedelta(days=2),
    )

    # Before the dependency exists, B keeps its original schedule.
    assert client.get(f"/tasks/{b['id']}").json()["start_date"] == (
        today + timedelta(days=2)
    ).isoformat()

    # Adding A -> B should force B to start when A finishes.
    resp = link(client, a["id"], b["id"])
    assert resp.status_code == 201, resp.text

    b_after = client.get(f"/tasks/{b['id']}").json()

    assert b_after["start_date"] == (
        today + timedelta(days=5)
    ).isoformat()

    assert b_after["end_date"] == (
        today + timedelta(days=7)
    ).isoformat()
