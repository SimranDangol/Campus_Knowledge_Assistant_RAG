"""
test_api.py - Integration and unit tests for FastAPI endpoints with JWT Authentication.

Tests cover:
1. Unauthenticated requests to /ask return 401 Unauthorized.
2. Invalid JWT tokens return 401 Unauthorized.
3. OAuth2 login returns valid JWT access token.
4. Bad credentials return 401 Unauthorized.
5. User profile /me returns authenticated user and role.
6. Role-based access control (RBAC):
   - Student cannot access faculty documents (found=False).
   - Professor can access faculty documents (found=True).
"""

from fastapi.testclient import TestClient
from src.chain import CampusAnswer, Citation
from src import main
from src.main import app

client = TestClient(app)


def test_frontend_served():
    """GET /app must return HTML with 200 OK."""
    response = client.get("/app")
    assert response.status_code == 200
    assert "Campus Knowledge Assistant" in response.text
    assert "text/html" in response.headers["content-type"]


def test_unauthenticated_request_rejected():
    """Accessing /ask without a token must return 401."""
    response = client.post(
        "/ask",
        json={"question": "What is the minimum attendance?"},
    )
    assert response.status_code == 401
    assert "detail" in response.json()


def test_invalid_token_rejected():
    """Accessing /ask with an invalid token must return 401."""
    response = client.post(
        "/ask",
        headers={"Authorization": "Bearer not-a-valid-jwt-token"},
        json={"question": "What is the minimum attendance?"},
    )
    assert response.status_code == 401


def test_login_success():
    """Valid credentials exchange for a JWT access token."""
    response = client.post(
        "/token",
        data={"username": "alice", "password": "studentpass"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_credentials():
    """Invalid credentials return 401."""
    response = client.post(
        "/token",
        data={"username": "alice", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_user_me_profile():
    """Authenticated user can inspect their username and role."""
    token_resp = client.post(
        "/token",
        data={"username": "bob", "password": "profpass"},
    )
    token = token_resp.json()["access_token"]

    response = client.get(
        "/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "bob"
    assert data["role"] == "professor"


def test_student_role_is_used_for_ask(monkeypatch):
    """Student JWT role is passed to RAG without requiring external services."""
    token_resp = client.post(
        "/token",
        data={"username": "alice", "password": "studentpass"},
    )
    token = token_resp.json()["access_token"]
    calls = []

    def fake_ask(question, role, config=None):
        calls.append((question, role, config))
        return CampusAnswer(
            found=False,
            answer="I don't have information on that.",
            citations=[],
        ), []

    monkeypatch.setattr(main, "ask", fake_ask)

    response = client.post(
        "/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "How are faculty grades moderated?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "student"
    assert data["found"] is False
    assert len(calls) == 1
    assert calls[0][0] == "How are faculty grades moderated?"
    assert calls[0][1] == "student"


def test_professor_role_is_used_for_ask(monkeypatch):
    """Professor JWT role is passed to RAG and its citation is returned."""
    token_resp = client.post(
        "/token",
        data={"username": "bob", "password": "profpass"},
    )
    token = token_resp.json()["access_token"]
    calls = []

    def fake_ask(question, role, config=None):
        calls.append((question, role, config))
        return CampusAnswer(
            found=True,
            answer="A second marker reviews significant grade changes.",
            citations=[Citation(document="Grading Guidelines for Faculty", page=2)],
        ), []

    monkeypatch.setattr(main, "ask", fake_ask)

    response = client.post(
        "/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "How are faculty grades moderated?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "professor"
    assert data["found"] is True
    assert len(data["citations"]) > 0
    assert any(c["document"] == "Grading Guidelines for Faculty" for c in data["citations"])
    assert len(calls) == 1
    assert calls[0][0] == "How are faculty grades moderated?"
    assert calls[0][1] == "professor"


def test_empty_question_is_rejected():
    token_resp = client.post(
        "/token",
        data={"username": "alice", "password": "studentpass"},
    )
    response = client.post(
        "/ask",
        headers={"Authorization": f"Bearer {token_resp.json()['access_token']}"},
        json={"question": "  "},
    )
    assert response.status_code == 422


def test_ask_graph_endpoint(monkeypatch):
    """Calling /ask/graph routes through LangGraph and marks pipeline as langgraph."""
    token_resp = client.post(
        "/token",
        data={"username": "alice", "password": "studentpass"},
    )
    token = token_resp.json()["access_token"]
    graph_called = False

    def fake_ask_graph(question, role, config=None):
        nonlocal graph_called
        graph_called = True
        return CampusAnswer(
            found=True,
            answer="Answered via LangGraph state machine.",
            citations=[Citation(document="Student Handbook", page=1)],
        ), [object()]

    monkeypatch.setattr(main, "ask_graph", fake_ask_graph)

    # Test /ask/graph endpoint
    resp = client.post(
        "/ask/graph",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "What is the policy?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pipeline"] == "langgraph"
    assert data["answer"] == "Answered via LangGraph state machine."
    assert graph_called is True

    # Test /ask with use_graph=True
    graph_called = False
    resp2 = client.post(
        "/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "What is the policy?", "use_graph": True},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["pipeline"] == "langgraph"
    assert graph_called is True
