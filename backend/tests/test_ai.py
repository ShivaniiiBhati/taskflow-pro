from tests.helpers import create_task
from app.services import dependency_ai


def test_suggestion_endpoint_runs_in_mock_mode_without_api_key(client):
    create_task(client, "Database Schema", description="Design tables for tasks and dependencies.")
    create_task(client, "Marketing Plan", description="Draft the go-to-market messaging.")

    resp = client.post("/ai/suggest-dependencies", json={
        "title": "Backend API integration tests",
        "description": "Tests require the database schema to already exist.",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "mock"
    # The lexically closest existing task shares "database"/"schema".
    if body["suggestions"]:
        assert body["suggestions"][0]["title"] == "Database Schema"


def test_ai_suggestions_never_persist_a_dependency(client):
    create_task(client, "Database Schema", description="Design tables.")
    client.post("/ai/suggest-dependencies", json={
        "title": "Integration Tests",
        "description": "Needs the database schema.",
    })
    assert client.get("/dependencies").json() == []


def test_ai_suggestion_requires_existing_task_or_title(client):
    resp = client.post("/ai/suggest-dependencies", json={})
    assert resp.status_code == 400


def test_unknown_task_id_in_model_response_is_discarded():
    """
    Unit-tests the hallucination guard directly: even if a (simulated)
    model response references a task id that was never in the
    candidate set we sent it, it must be dropped, not surfaced.
    """
    raw_response = '{"suggestions": [{"task_id": 9999, "reason": "fabricated"}]}'
    valid = dependency_ai._parse_and_validate(raw_response, valid_ids={1, 2, 3})
    assert valid == []


def test_malformed_json_response_is_discarded():
    valid = dependency_ai._parse_and_validate("not json at all", valid_ids={1, 2, 3})
    assert valid == []


def test_valid_suggestion_within_candidate_set_is_kept():
    raw_response = '{"suggestions": [{"task_id": 2, "reason": "Needs the schema first."}]}'
    valid = dependency_ai._parse_and_validate(raw_response, valid_ids={1, 2, 3})
    assert valid == [{"task_id": 2, "reason": "Needs the schema first."}]
