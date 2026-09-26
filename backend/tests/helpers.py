from datetime import date


def create_task(client, title, duration_days=1, start_date=None, description=""):
    resp = client.post("/tasks", json={
        "title": title,
        "description": description,
        "start_date": (start_date or date.today()).isoformat(),
        "duration_days": duration_days,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def link(client, predecessor_id, successor_id):
    return client.post("/dependencies", json={
        "predecessor_id": predecessor_id,
        "successor_id": successor_id,
    })


def set_status(client, task_id, status):
    resp = client.patch(f"/tasks/{task_id}", json={"status": status})
    assert resp.status_code == 200, resp.text
    return resp.json()


def get_task(client, task_id):
    resp = client.get(f"/tasks/{task_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()
