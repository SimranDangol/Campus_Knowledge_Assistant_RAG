from fastapi.testclient import TestClient

from src import main


client = TestClient(main.app)


def test_ask_rejects_invalid_role(monkeypatch):
    def unexpected_ask(*args, **kwargs):
        raise AssertionError("RAG pipeline should not run for an invalid role")

    monkeypatch.setattr(main, "ask", unexpected_ask)

    response = client.post(
        "/ask",
        json={"question": "What is the minimum attendance?", "role": "visitor"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Invalid role: visitor. Use student, professor, or admin."
    }
