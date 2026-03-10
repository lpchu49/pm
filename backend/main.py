import secrets
import sqlite3
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi import Cookie, Response, status

app = FastAPI(title="Project Management MVP API")
STATIC_DIR = Path(__file__).resolve().parent / "static"
DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "app.db"
SESSION_COOKIE_NAME = "pm_session"
SESSION_DURATION_DAYS = 7


class LoginRequest(BaseModel):
  username: str
  password: str


class CardModel(BaseModel):
  id: str
  title: str
  details: str


class ColumnModel(BaseModel):
  id: str
  title: str
  cardIds: list[str]


class BoardModel(BaseModel):
  columns: list[ColumnModel]
  cards: dict[str, CardModel]


DEFAULT_BOARD: dict[str, object] = {
  "columns": [
    {"id": "col-backlog", "title": "Backlog", "cardIds": ["card-1", "card-2"]},
    {"id": "col-discovery", "title": "Discovery", "cardIds": ["card-3"]},
    {"id": "col-progress", "title": "In Progress", "cardIds": ["card-4", "card-5"]},
    {"id": "col-review", "title": "Review", "cardIds": ["card-6"]},
    {"id": "col-done", "title": "Done", "cardIds": ["card-7", "card-8"]},
  ],
  "cards": {
    "card-1": {
      "id": "card-1",
      "title": "Align roadmap themes",
      "details": "Draft quarterly themes with impact statements and metrics.",
    },
    "card-2": {
      "id": "card-2",
      "title": "Gather customer signals",
      "details": "Review support tags, sales notes, and churn feedback.",
    },
    "card-3": {
      "id": "card-3",
      "title": "Prototype analytics view",
      "details": "Sketch initial dashboard layout and key drill-downs.",
    },
    "card-4": {
      "id": "card-4",
      "title": "Refine status language",
      "details": "Standardize column labels and tone across the board.",
    },
    "card-5": {
      "id": "card-5",
      "title": "Design card layout",
      "details": "Add hierarchy and spacing for scanning dense lists.",
    },
    "card-6": {
      "id": "card-6",
      "title": "QA micro-interactions",
      "details": "Verify hover, focus, and loading states.",
    },
    "card-7": {
      "id": "card-7",
      "title": "Ship marketing page",
      "details": "Final copy approved and asset pack delivered.",
    },
    "card-8": {
      "id": "card-8",
      "title": "Close onboarding sprint",
      "details": "Document release notes and share internally.",
    },
  },
}


def get_db() -> sqlite3.Connection:
  DATA_DIR.mkdir(parents=True, exist_ok=True)
  connection = sqlite3.connect(DB_PATH)
  connection.row_factory = sqlite3.Row
  return connection


def initialize_database() -> None:
  with get_db() as db:
    db.execute(
      """
      CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL
      )
      """
    )
    db.execute(
      """
      CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
      )
      """
    )
    db.execute(
      """
      CREATE TABLE IF NOT EXISTS boards (
        user_id INTEGER PRIMARY KEY,
        payload TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
      )
      """
    )
    db.execute(
      """
      INSERT INTO users (username, password)
      VALUES (?, ?)
      ON CONFLICT(username) DO NOTHING
      """,
      ("user", "password"),
    )
    user_row = db.execute(
      "SELECT id FROM users WHERE username = ?",
      ("user",),
    ).fetchone()
    if user_row:
      db.execute(
        """
        INSERT INTO boards (user_id, payload, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO NOTHING
        """,
        (
          user_row["id"],
          json.dumps(DEFAULT_BOARD),
          datetime.now(UTC).isoformat(),
        ),
      )


@app.on_event("startup")
def on_startup() -> None:
  initialize_database()


def get_session_user(session_token: str | None) -> dict[str, str | int] | None:
  if not session_token:
    return None

  now_iso = datetime.now(UTC).isoformat()
  with get_db() as db:
    row = db.execute(
      """
      SELECT users.id, users.username, sessions.expires_at
      FROM sessions
      JOIN users ON users.id = sessions.user_id
      WHERE sessions.token = ?
      """,
      (session_token,),
    ).fetchone()
    if not row:
      return None

    if row["expires_at"] <= now_iso:
      db.execute("DELETE FROM sessions WHERE token = ?", (session_token,))
      return None

    return {"id": row["id"], "username": row["username"]}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "pm-backend"}


@app.get("/api/auth/session")
def auth_session(pm_session: str | None = Cookie(default=None)) -> dict[str, str | bool]:
  user = get_session_user(pm_session)
  if not user:
    return {"authenticated": False}
  return {"authenticated": True, "username": user["username"]}


@app.post("/api/auth/login")
def auth_login(payload: LoginRequest, response: Response) -> dict[str, str | bool]:
  with get_db() as db:
    row = db.execute(
      "SELECT id, username FROM users WHERE username = ? AND password = ?",
      (payload.username, payload.password),
    ).fetchone()

    if not row:
      response.status_code = status.HTTP_401_UNAUTHORIZED
      return {"authenticated": False, "message": "Invalid credentials"}

    token = secrets.token_urlsafe(32)
    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(days=SESSION_DURATION_DAYS)
    db.execute(
      """
      INSERT INTO sessions (token, user_id, created_at, expires_at)
      VALUES (?, ?, ?, ?)
      """,
      (token, row["id"], created_at.isoformat(), expires_at.isoformat()),
    )

  response.set_cookie(
    key=SESSION_COOKIE_NAME,
    value=token,
    httponly=True,
    samesite="lax",
    secure=False,
    max_age=SESSION_DURATION_DAYS * 24 * 60 * 60,
  )
  return {"authenticated": True, "username": row["username"]}


@app.post("/api/auth/logout")
def auth_logout(response: Response, pm_session: str | None = Cookie(default=None)) -> dict[str, bool]:
  if pm_session:
    with get_db() as db:
      db.execute("DELETE FROM sessions WHERE token = ?", (pm_session,))
  response.delete_cookie(SESSION_COOKIE_NAME)
  return {"ok": True}


@app.get("/api/board")
def board_get(response: Response, pm_session: str | None = Cookie(default=None)) -> dict[str, object] | dict[str, str]:
  user = get_session_user(pm_session)
  if not user:
    response.status_code = status.HTTP_401_UNAUTHORIZED
    return {"message": "Unauthorized"}

  with get_db() as db:
    row = db.execute(
      "SELECT payload FROM boards WHERE user_id = ?",
      (user["id"],),
    ).fetchone()

    if not row:
      payload = json.dumps(DEFAULT_BOARD)
      db.execute(
        """
        INSERT INTO boards (user_id, payload, updated_at)
        VALUES (?, ?, ?)
        """,
        (user["id"], payload, datetime.now(UTC).isoformat()),
      )
      return {"board": DEFAULT_BOARD}

  return {"board": json.loads(row["payload"])}


@app.put("/api/board")
def board_put(board: BoardModel, response: Response, pm_session: str | None = Cookie(default=None)) -> dict[str, bool] | dict[str, str]:
  user = get_session_user(pm_session)
  if not user:
    response.status_code = status.HTTP_401_UNAUTHORIZED
    return {"message": "Unauthorized"}

  with get_db() as db:
    db.execute(
      """
      INSERT INTO boards (user_id, payload, updated_at)
      VALUES (?, ?, ?)
      ON CONFLICT(user_id) DO UPDATE SET
        payload = excluded.payload,
        updated_at = excluded.updated_at
      """,
      (
        user["id"],
        json.dumps(board.model_dump()),
        datetime.now(UTC).isoformat(),
      ),
    )

  return {"ok": True}


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
else:
    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return """<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>PM MVP Backend</title>
    <style>
      body {
        margin: 0;
        font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif;
        background: #f7f8fb;
        color: #032147;
      }
      main {
        max-width: 760px;
        margin: 48px auto;
        padding: 24px;
      }
      .card {
        background: #ffffff;
        border: 1px solid rgba(3, 33, 71, 0.08);
        border-radius: 16px;
        padding: 20px;
      }
      h1 {
        margin-top: 0;
      }
      code {
        background: #eef2f8;
        padding: 2px 6px;
        border-radius: 6px;
      }
    </style>
  </head>
  <body>
    <main>
      <div class=\"card\">
        <h1>Frontend build not found</h1>
        <p>Build frontend assets and place them in <code>backend/static</code>.</p>
      </div>
    </main>
  </body>
</html>
"""
