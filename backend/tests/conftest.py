import os
import tempfile

# Must happen before any `app.*` import, since app.config reads env vars
# at import time. Each test run gets its own throwaway SQLite file, and
# AI calls are forced into mock mode so tests never depend on network
# access or a real API key.
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["API_TOKEN"] = "test-token"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    """Fresh schema before every single test -- tests never see each
    other's tasks/edges, which keeps DAG assertions unambiguous."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    """A TestClient pre-authenticated with the shared bearer token, so
    every existing test keeps working without repeating auth
    boilerplate. test_auth.py uses a plain, unauthenticated TestClient
    directly to test the 401 paths."""
    c = TestClient(app)
    c.headers.update({"Authorization": "Bearer test-token"})
    return c
