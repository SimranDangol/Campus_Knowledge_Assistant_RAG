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


def test_student_cannot_access_faculty_doc():
    """Student asking about faculty grading moderation must receive found=False."""
    token_resp = client.post(
        "/token",
        data={"username": "alice", "password": "studentpass"},
    )
    token = token_resp.json()["access_token"]

    response = client.post(
        "/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "How are faculty grades moderated?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "student"
    assert data["found"] is False


def test_professor_can_access_faculty_doc():
    """Professor asking about faculty grading moderation gets found=True and citations."""
    token_resp = client.post(
        "/token",
        data={"username": "bob", "password": "profpass"},
    )
    token = token_resp.json()["access_token"]

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
