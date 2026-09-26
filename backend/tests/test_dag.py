from tests.helpers import create_task, link


def test_cycle_dependency_is_rejected(client):
    a = create_task(client, "A")
    b = create_task(client, "B")
    c = create_task(client, "C")

    assert link(client, a["id"], b["id"]).status_code == 201
    assert link(client, b["id"], c["id"]).status_code == 201

    # C -> A would close the loop A -> B -> C -> A.
    resp = link(client, c["id"], a["id"])
    assert resp.status_code == 409
    assert "cycle" in resp.json()["detail"].lower()


def test_existing_graph_unchanged_after_rejected_cycle(client):
    a = create_task(client, "A")
    b = create_task(client, "B")
    c = create_task(client, "C")
    link(client, a["id"], b["id"])
    link(client, b["id"], c["id"])

    before = client.get("/dependencies").json()
    link(client, c["id"], a["id"])  # rejected
    after = client.get("/dependencies").json()

    assert before == after


def test_indirect_cycle_is_rejected(client):
    """A -> B -> C -> D, then D -> A should also be rejected, not just
    the two-hop case."""
    a = create_task(client, "A")
    b = create_task(client, "B")
    c = create_task(client, "C")
    d = create_task(client, "D")
    link(client, a["id"], b["id"])
    link(client, b["id"], c["id"])
    link(client, c["id"], d["id"])

    resp = link(client, d["id"], a["id"])
    assert resp.status_code == 409


def test_direct_self_loop_rejected(client):
    a = create_task(client, "A")
    resp = link(client, a["id"], a["id"])
    assert resp.status_code == 409


def test_diamond_shape_is_a_valid_dag_not_a_cycle(client):
    """A -> B, A -> C, B -> D, C -> D is a valid DAG (reconvergence,
    not a cycle) and must be accepted."""
    a = create_task(client, "A")
    b = create_task(client, "B")
    c = create_task(client, "C")
    d = create_task(client, "D")

    assert link(client, a["id"], b["id"]).status_code == 201
    assert link(client, a["id"], c["id"]).status_code == 201
    assert link(client, b["id"], d["id"]).status_code == 201
    assert link(client, c["id"], d["id"]).status_code == 201
