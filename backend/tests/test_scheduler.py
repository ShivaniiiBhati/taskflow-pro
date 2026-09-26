from datetime import date, timedelta
from tests.helpers import create_task, link, get_task


def _patch_duration(client, task_id, new_duration):
    resp = client.patch(f"/tasks/{task_id}", json={"duration_days": new_duration})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_diamond_dependency_does_not_compound(client):
    """
    A -> B -> D
    A -> C -> D
    Extending A by 3 days must move D by exactly 3 days, not 6.
    """
    today = date.today()
    a = create_task(client, "A", duration_days=2, start_date=today)          # ends day+2
    b = create_task(client, "B", duration_days=1, start_date=today + timedelta(days=2))  # ends day+3
    c = create_task(client, "C", duration_days=1, start_date=today + timedelta(days=2))  # ends day+3
    d = create_task(client, "D", duration_days=1, start_date=today + timedelta(days=3))  # ends day+4

    link(client, a["id"], b["id"])
    link(client, a["id"], c["id"])
    link(client, b["id"], d["id"])
    link(client, c["id"], d["id"])

    d_before = get_task(client, d["id"])
    original_d_end = date.fromisoformat(d_before["end_date"])

    # Extend A by 3 days: 2 -> 5.
    _patch_duration(client, a["id"], 5)

    d_after = get_task(client, d["id"])
    new_d_end = date.fromisoformat(d_after["end_date"])

    assert (new_d_end - original_d_end).days == 3, (
        f"Expected D to move by exactly 3 days, moved by "
        f"{(new_d_end - original_d_end).days} instead (compounding bug)."
    )


def test_multiple_paths_same_upstream_change_produce_same_intermediate_dates(client):
    """Both B and C, fed by the same upstream A, should land on the
    exact same finish date after A's change -- if they diverged, D's
    max-of-predecessors calculation could accidentally mask a bug."""
    today = date.today()
    a = create_task(client, "A", duration_days=2, start_date=today)
    b = create_task(client, "B", duration_days=1, start_date=today + timedelta(days=2))
    c = create_task(client, "C", duration_days=1, start_date=today + timedelta(days=2))
    link(client, a["id"], b["id"])
    link(client, a["id"], c["id"])

    _patch_duration(client, a["id"], 6)  # +4 days

    b_after = get_task(client, b["id"])
    c_after = get_task(client, c["id"])
    assert b_after["end_date"] == c_after["end_date"]


def test_independent_upstream_changes_are_combined_correctly(client):
    """
    D depends on both B (fed by A) and E (independent). A delay on A
    should move D; a LATER, larger, independent delay on E should
    move D again to reflect E's date, not simply add on top of the
    earlier A-driven shift, and not get ignored either.
    """
    today = date.today()
    a = create_task(client, "A", duration_days=2, start_date=today)                       # ends +2
    b = create_task(client, "B", duration_days=1, start_date=today + timedelta(days=2))   # ends +3
    e = create_task(client, "E", duration_days=1, start_date=today)                       # ends +1
    d = create_task(client, "D", duration_days=1, start_date=today + timedelta(days=3))   # ends +4

    link(client, a["id"], b["id"])
    link(client, b["id"], d["id"])
    link(client, e["id"], d["id"])

    # Step 1: delay A by 3 days (2 -> 5). B moves to end +6. D should
    # follow B since B's new end (+6) is later than E's end (+1).
    _patch_duration(client, a["id"], 5)
    d_after_step1 = get_task(client, d["id"])
    assert d_after_step1["end_date"] == (today + timedelta(days=7)).isoformat()  # start=6,duration=1,end=7

    # Step 2: independently delay E by a lot -- E's new end (+15) is
    # now later than B's end (+6), so D must follow E this time.
    _patch_duration(client, e["id"], 15)
    d_after_step2 = get_task(client, d["id"])
    assert d_after_step2["end_date"] == (today + timedelta(days=16)).isoformat()  # start=15,duration=1,end=16


def test_unaffected_downstream_task_does_not_move(client):
    """If a predecessor's change doesn't actually push past a
    dependent's current start date, the dependent must not move."""
    today = date.today()
    a = create_task(client, "A", duration_days=2, start_date=today)  # ends +2
    # B starts well after A's current end, with slack built in.
    b = create_task(client, "B", duration_days=1, start_date=today + timedelta(days=10))
    link(client, a["id"], b["id"])

    original_b_start = get_task(client, b["id"])["start_date"]

    _patch_duration(client, a["id"], 3)  # A now ends +3, still well before B's start (+10)

    b_after = get_task(client, b["id"])
    assert b_after["start_date"] == original_b_start
