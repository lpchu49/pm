from pathlib import Path
import sys
import sqlite3
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "app.db")
    monkeypatch.setattr(main, "ALEMBIC_INI_PATH", Path(main.__file__).resolve().parent / "alembic.ini")
    monkeypatch.setattr(main, "ALEMBIC_SCRIPT_PATH", Path(main.__file__).resolve().parent / "alembic")
    main.run_migrations()
    main.initialize_database()

    with TestClient(main.app) as test_client:
        yield test_client


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "pm-backend"}


def test_session_starts_unauthenticated(client: TestClient) -> None:
    response = client.get("/api/auth/session")

    assert response.status_code == 200
    assert response.json() == {"authenticated": False}


def test_login_rejects_invalid_credentials(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "bad-user", "password": "bad-pass"},
    )

    assert response.status_code == 401
    assert response.json()["authenticated"] is False


def test_login_sets_cookie_and_session(client: TestClient) -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )

    assert login_response.status_code == 200
    assert login_response.json() == {"authenticated": True, "username": "user"}
    assert main.SESSION_COOKIE_NAME in login_response.cookies

    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json() == {"authenticated": True, "username": "user"}


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
    assert session_response.json() == {"authenticated": False}


def test_board_requires_auth(client: TestClient) -> None:
    response = client.get("/api/board")

    assert response.status_code == 401
    assert response.json() == {"message": "Unauthorized"}


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
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main, "DB_PATH", db_path)
    monkeypatch.setattr(main, "ALEMBIC_INI_PATH", Path(main.__file__).resolve().parent / "alembic.ini")
    monkeypatch.setattr(main, "ALEMBIC_SCRIPT_PATH", Path(main.__file__).resolve().parent / "alembic")

    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
            """
        )

    main.run_migrations()

    with sqlite3.connect(db_path) as db:
        row = db.execute("SELECT version_num FROM alembic_version").fetchone()
        tables = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }

    assert row is not None
    assert row[0] == "20260310_0001"
    assert {"users", "sessions", "boards"}.issubset(tables)
