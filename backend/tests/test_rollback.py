from tests.helpers import create_task, link, set_status, get_task


def test_rollback_blocks_downstream_chain(client):
    """
    A -> B -> C. Mark A and B Done (C becomes Ready). Move A back to
    In Progress: B and C must both become Blocked, even though C's
    direct predecessor (B) never left the Done column -- only B's
    readiness flag changed, which is what C actually checks.
    """
    a = create_task(client, "A")
    b = create_task(client, "B")
    c = create_task(client, "C")
    link(client, a["id"], b["id"])
    link(client, b["id"], c["id"])

    set_status(client, a["id"], "DONE")
    set_status(client, b["id"], "DONE")

    assert get_task(client, c["id"])["readiness"] == "READY"

    # Regression: A goes back to In Progress.
    result = set_status(client, a["id"], "IN_PROGRESS")

    b_after = get_task(client, b["id"])
    c_after = get_task(client, c["id"])

    assert b_after["readiness"] == "BLOCKED"
    assert c_after["readiness"] == "BLOCKED"
    # B's board column is untouched -- only its readiness flag moved.
    assert b_after["status"] == "DONE"
    assert set(result["affected_task_ids"]) == {b["id"], c["id"]}


def test_recovery_restores_readiness(client):
    """Putting A back to Done should un-block B and C again."""
    a = create_task(client, "A")
    b = create_task(client, "B")
    c = create_task(client, "C")
    link(client, a["id"], b["id"])
    link(client, b["id"], c["id"])

    set_status(client, a["id"], "DONE")
    set_status(client, b["id"], "DONE")
    set_status(client, a["id"], "IN_PROGRESS")  # regress

    assert get_task(client, b["id"])["readiness"] == "BLOCKED"
    assert get_task(client, c["id"])["readiness"] == "BLOCKED"

    set_status(client, a["id"], "DONE")  # recover

    assert get_task(client, b["id"])["readiness"] == "READY"
    assert get_task(client, c["id"])["readiness"] == "READY"


def test_multiple_unsatisfied_prerequisites_stay_blocked_until_all_done(client):
    a = create_task(client, "A")
    b = create_task(client, "B")
    target = create_task(client, "Target")
    link(client, a["id"], target["id"])
    link(client, b["id"], target["id"])

    assert get_task(client, target["id"])["readiness"] == "BLOCKED"

    set_status(client, a["id"], "DONE")
    assert get_task(client, target["id"])["readiness"] == "BLOCKED"  # B still not done

    set_status(client, b["id"], "DONE")
    assert get_task(client, target["id"])["readiness"] == "READY"
