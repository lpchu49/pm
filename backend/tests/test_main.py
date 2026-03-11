from pathlib import Path
import sys
import sqlite3
import json
import os
import re
from datetime import UTC, datetime, timedelta
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
import db
import auth
import openrouter
from models import BoardModel
from seed import DEFAULT_BOARD


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "app.db")
    monkeypatch.setattr(db, "ALEMBIC_INI_PATH", Path(main.__file__).resolve().parent / "alembic.ini")
    monkeypatch.setattr(db, "ALEMBIC_SCRIPT_PATH", Path(main.__file__).resolve().parent / "alembic")
    db.run_migrations()
    auth.initialize_database()

    with TestClient(main.app) as test_client:
        yield test_client


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "pm-backend"}


def test_session_starts_unauthenticated(client: TestClient) -> None:
    response = client.get("/api/auth/session")

    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is False


def test_login_rejects_invalid_credentials(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "bad-user", "password": "bad-pass"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


def test_login_sets_cookie_and_session(client: TestClient) -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )

    assert login_response.status_code == 200
    data = login_response.json()
    assert data["authenticated"] is True
    assert data["username"] == "user"
    assert auth.SESSION_COOKIE_NAME in login_response.cookies

    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    session_data = session_response.json()
    assert session_data["authenticated"] is True
    assert session_data["username"] == "user"


def test_logout_clears_session(client: TestClient) -> None:
    client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )

    logout_response = client.post("/api/auth/logout")
    assert logout_response.status_code == 200
    assert logout_response.json() == {"ok": True}

    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json()["authenticated"] is False


def test_board_requires_auth(client: TestClient) -> None:
    response = client.get("/api/board")

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_board_put_requires_auth(client: TestClient) -> None:
    response = client.put("/api/board", json=DEFAULT_BOARD)

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_board_put_rejects_invalid_payload(client: TestClient) -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert login_response.status_code == 200

    invalid_board = {
        "columns": [
            {"id": "col-backlog", "title": "Backlog", "cardIds": ["card-1", "card-missing"]},
            {"id": "col-review", "title": "Review", "cardIds": []},
        ],
        "cards": {
            "card-1": {"id": "card-1", "title": "Card 1", "details": "Valid card"},
        },
    }

    response = client.put("/api/board", json=invalid_board)
    assert response.status_code == 422


def test_session_with_deleted_user_is_unauthorized(client: TestClient) -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert login_response.status_code == 200

    token = login_response.cookies[auth.SESSION_COOKIE_NAME]

    with db.get_db() as conn:
        conn.execute("DELETE FROM users WHERE username = ?", ("user",))

    client.cookies.set(auth.SESSION_COOKIE_NAME, token)

    board_response = client.get("/api/board")
    assert board_response.status_code == 401
    assert board_response.json() == {"detail": "Unauthorized"}

    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json()["authenticated"] is False


def test_ai_diagnostic_requires_auth(client: TestClient) -> None:
    response = client.post("/api/ai/diagnostic", json={"prompt": "2+2"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_ai_diagnostic_rejects_missing_api_key(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert login_response.status_code == 200

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    response = client.post("/api/ai/diagnostic", json={"prompt": "2+2"})
    assert response.status_code == 500
    assert response.json() == {"detail": "OPENROUTER_API_KEY is not configured"}


def test_ai_diagnostic_handles_openrouter_non_200(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert login_response.status_code == 200

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from fastapi import HTTPException

    def fake_call_openrouter(_prompt: str) -> str:
        raise HTTPException(status_code=502, detail="OpenRouter error (429): rate limit")

    monkeypatch.setattr(openrouter, "call_openrouter", fake_call_openrouter)

    response = client.post("/api/ai/diagnostic", json={"prompt": "2+2"})
    assert response.status_code == 502
    assert response.json() == {"detail": "OpenRouter error (429): rate limit"}


def test_ai_diagnostic_returns_model_output(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert login_response.status_code == 200

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "call_openrouter", lambda _prompt: "4")

    response = client.post("/api/ai/diagnostic", json={"prompt": "2+2"})
    assert response.status_code == 200
    assert response.json() == {"model": "openai/gpt-oss-120b", "output": "4"}


def test_ai_diagnostic_live_openrouter_network(client: TestClient) -> None:

    login_response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert login_response.status_code == 200

    response = client.post(
        "/api/ai/diagnostic",
        json={"prompt": "What is 2+2? Respond with just the number."},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["model"] == openrouter.OPENROUTER_MODEL
    assert isinstance(payload["output"], str)
    assert re.search(r"\b4\b", payload["output"]) is not None


def test_board_persists_changes_across_relogin(client: TestClient) -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert login_response.status_code == 200

    board_response = client.get("/api/board")
    assert board_response.status_code == 200
    board_payload = board_response.json()["board"]

    board_payload["columns"][0]["title"] = "Persisted Backlog"
    update_response = client.put("/api/board", json=board_payload)
    assert update_response.status_code == 200
    assert update_response.json() == {"ok": True}

    logout_response = client.post("/api/auth/logout")
    assert logout_response.status_code == 200

    relogin_response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert relogin_response.status_code == 200

    refreshed_board_response = client.get("/api/board")
    assert refreshed_board_response.status_code == 200
    assert refreshed_board_response.json()["board"]["columns"][0]["title"] == "Persisted Backlog"


def test_run_migrations_stamps_legacy_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "app.db"
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", db_path)
    monkeypatch.setattr(db, "ALEMBIC_INI_PATH", Path(main.__file__).resolve().parent / "alembic.ini")
    monkeypatch.setattr(db, "ALEMBIC_SCRIPT_PATH", Path(main.__file__).resolve().parent / "alembic")

    with sqlite3.connect(db_path) as tmp_conn:
        tmp_conn.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
            """
        )

    db.run_migrations()

    with sqlite3.connect(db_path) as tmp_conn:
        row = tmp_conn.execute("SELECT version_num FROM alembic_version").fetchone()
        tables = {
            row[0]
            for row in tmp_conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }

    assert row is not None
    assert row[0] is not None
    assert {"users", "sessions", "boards"}.issubset(tables)


# --- Part 9: AI chat contract ---

MINIMAL_BOARD = {
    "columns": [
        {"id": "col-1", "title": "Todo", "cardIds": ["card-1"]},
    ],
    "cards": {
        "card-1": {"id": "card-1", "title": "Task", "details": ""},
    },
}


def _login(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "user", "password": "password"})
    assert response.status_code == 200


def test_ai_chat_requires_auth(client: TestClient) -> None:
    response = client.post("/api/ai/chat", json={"message": "hello", "history": []})

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_ai_chat_returns_text_only_when_no_board_update(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _login(client)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    ai_output = json.dumps({"assistant_text": "Hello! How can I help?", "board_update": None})
    monkeypatch.setattr(openrouter, "call_openrouter_messages", lambda _msgs: ai_output)

    response = client.post("/api/ai/chat", json={"message": "hi", "history": []})

    assert response.status_code == 200
    data = response.json()
    assert data["assistant_text"] == "Hello! How can I help?"
    assert data["board_updated"] is False


def test_ai_chat_applies_valid_board_update(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _login(client)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    ai_output = json.dumps({"assistant_text": "Done! Added a card.", "board_update": MINIMAL_BOARD})
    monkeypatch.setattr(openrouter, "call_openrouter_messages", lambda _msgs: ai_output)

    response = client.post("/api/ai/chat", json={"message": "Add a task", "history": []})

    assert response.status_code == 200
    data = response.json()
    assert data["assistant_text"] == "Done! Added a card."
    assert data["board_updated"] is True

    board_response = client.get("/api/board")
    assert board_response.status_code == 200
    assert board_response.json()["board"] == MINIMAL_BOARD


def test_ai_chat_preserves_board_on_invalid_json(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _login(client)
    client.put("/api/board", json=MINIMAL_BOARD)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "call_openrouter_messages", lambda _msgs: "not valid json {{")

    response = client.post("/api/ai/chat", json={"message": "help", "history": []})

    assert response.status_code == 200
    assert response.json()["board_updated"] is False

    board_response = client.get("/api/board")
    assert board_response.json()["board"] == MINIMAL_BOARD


def test_ai_chat_preserves_board_on_invalid_board_schema(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _login(client)
    client.put("/api/board", json=MINIMAL_BOARD)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    invalid_board = {"columns": [{"id": "col-1", "title": "Bad", "cardIds": ["missing-card"]}], "cards": {}}
    ai_output = json.dumps({"assistant_text": "Here is your update.", "board_update": invalid_board})
    monkeypatch.setattr(openrouter, "call_openrouter_messages", lambda _msgs: ai_output)

    response = client.post("/api/ai/chat", json={"message": "update", "history": []})

    assert response.status_code == 200
    data = response.json()
    assert data["assistant_text"] == "Here is your update."
    assert data["board_updated"] is False

    board_response = client.get("/api/board")
    assert board_response.json()["board"] == MINIMAL_BOARD


def test_ai_chat_includes_history_and_board_in_messages(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _login(client)
    client.put("/api/board", json=MINIMAL_BOARD)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    captured: list[list] = []

    def capture(msgs: list) -> str:
        captured.append(msgs)
        return json.dumps({"assistant_text": "ok", "board_update": None})

    monkeypatch.setattr(openrouter, "call_openrouter_messages", capture)

    history = [
        {"role": "user", "content": "prev question"},
        {"role": "assistant", "content": "prev answer"},
    ]
    response = client.post("/api/ai/chat", json={"message": "new question", "history": history})

    assert response.status_code == 200
    assert len(captured) == 1
    msgs = captured[0]

    roles = [m["role"] for m in msgs]
    assert roles[0] == "system"
    contents = [m["content"] for m in msgs]
    # System prompt contains current board JSON
    assert "col-1" in contents[0]
    assert "prev question" in contents
    assert "prev answer" in contents
    assert "new question" in contents


# --- M7: Direct password hashing tests ---

def test_hash_password_round_trip() -> None:
    hashed = auth.hash_password("test-password")
    assert auth.verify_password("test-password", hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = auth.hash_password("correct-password")
    assert auth.verify_password("wrong-password", hashed) is False


def test_verify_password_rejects_malformed_stored_hash() -> None:
    assert auth.verify_password("anything", "no-colon-here") is False
    assert auth.verify_password("anything", "") is False


# --- M8: Expired session test ---

def test_expired_session_returns_unauthenticated(client: TestClient) -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert login_response.status_code == 200
    token = login_response.cookies[auth.SESSION_COOKIE_NAME]

    # Manually expire the session
    expired_time = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    with db.get_db() as conn:
        conn.execute(
            "UPDATE sessions SET expires_at = ? WHERE token = ?",
            (expired_time, token),
        )

    client.cookies.set(auth.SESSION_COOKIE_NAME, token)

    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json()["authenticated"] is False

    # The expired session should have been deleted
    with db.get_db() as conn:
        row = conn.execute("SELECT token FROM sessions WHERE token = ?", (token,)).fetchone()
    assert row is None
