import secrets
import sqlite3
import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from pydantic import BaseModel, model_validator
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi import Cookie, HTTPException, Response, status

app = FastAPI(title="Project Management MVP API")
STATIC_DIR = Path(__file__).resolve().parent / "static"
DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "app.db"
ALEMBIC_INI_PATH = Path(__file__).resolve().parent / "alembic.ini"
ALEMBIC_SCRIPT_PATH = Path(__file__).resolve().parent / "alembic"
SESSION_COOKIE_NAME = "pm_session"
SESSION_DURATION_DAYS = 7
OPENROUTER_MODEL = "openai/gpt-oss-120b"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


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

  @model_validator(mode="after")
  def validate_integrity(self) -> "BoardModel":
    column_ids = [column.id for column in self.columns]
    if len(column_ids) != len(set(column_ids)):
      raise ValueError("Column ids must be unique")

    referenced_card_ids: list[str] = []
    for column in self.columns:
      referenced_card_ids.extend(column.cardIds)

    if len(referenced_card_ids) != len(set(referenced_card_ids)):
      raise ValueError("Card ids must not appear in more than one column")

    cards_by_key = set(self.cards.keys())
    for card_key, card in self.cards.items():
      if card.id != card_key:
        raise ValueError("Card id must match its dictionary key")

    referenced_set = set(referenced_card_ids)
    missing_cards = referenced_set - cards_by_key
    if missing_cards:
      raise ValueError("All referenced card ids must exist in cards")

    orphan_cards = cards_by_key - referenced_set
    if orphan_cards:
      raise ValueError("All cards must be referenced by a column")

    return self


class DiagnosticAIRequest(BaseModel):
  prompt: str = "What is 2+2? Answer with just the number."


class ChatMessage(BaseModel):
  role: Literal["user", "assistant"]
  content: str


class AIChatRequest(BaseModel):
  message: str
  history: list[ChatMessage] = []


AI_CHAT_SYSTEM_PROMPT = """You are an AI assistant for a Kanban project management board.

You can help users manage their board by creating, moving, renaming, or deleting cards and columns.

You MUST always respond with a valid JSON object with exactly this shape:
{{
  "assistant_text": "<your response to the user>",
  "board_update": <full board payload object, or null>
}}

Rules:
- assistant_text is required and must be a non-empty string.
- Set board_update to null when making no board changes.
- When making board changes, board_update must be the COMPLETE board (all columns and all cards). Never partial.
- Board shape: {{"columns": [{{"id":"...","title":"...","cardIds":["..."]}}], "cards":{{"id":{{"id":"...","title":"...","details":"..."}}}}}}
- All cardIds referenced in columns must exist in cards.
- All cards must be placed in exactly one column.
- Column ids must be unique. Card dict keys must match each card's id field.

Current board state:
{board_json}"""


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


def run_migrations() -> None:
  DATA_DIR.mkdir(parents=True, exist_ok=True)
  config = Config(str(ALEMBIC_INI_PATH))
  config.set_main_option("script_location", str(ALEMBIC_SCRIPT_PATH))
  config.set_main_option("sqlalchemy.url", f"sqlite:///{DB_PATH}")

  with sqlite3.connect(DB_PATH) as db:
    table_names = {
      row[0]
      for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }

    has_alembic_version = "alembic_version" in table_names
    alembic_version_rows = (
      db.execute("SELECT version_num FROM alembic_version").fetchall()
      if has_alembic_version
      else []
    )

  has_any_legacy_table = bool({"users", "sessions", "boards"}.intersection(table_names))
  has_empty_alembic_version = has_alembic_version and not alembic_version_rows

  if has_any_legacy_table and (not has_alembic_version or has_empty_alembic_version):
    command.stamp(config, "head")

    with sqlite3.connect(DB_PATH) as db:
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
    return

  command.upgrade(config, "head")


def initialize_database() -> None:
  with get_db() as db:
    # For MVP UX, start each server launch at the login screen.
    db.execute("DELETE FROM sessions")
    db.execute(
      """
      INSERT INTO users (username, password)
      VALUES (?, ?)
      ON CONFLICT(username) DO NOTHING
      """,
      ("user", "password"),
    )
@app.on_event("startup")
def on_startup() -> None:
  run_migrations()
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


def get_openrouter_api_key() -> str:
  api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
  if not api_key:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="OPENROUTER_API_KEY is not configured",
    )
  return api_key


def call_openrouter_messages(messages: list[dict]) -> str:
  api_key = get_openrouter_api_key()
  request_body = {
    "model": OPENROUTER_MODEL,
    "messages": messages,
  }

  encoded_body = json.dumps(request_body).encode("utf-8")
  request = urllib.request.Request(
    OPENROUTER_API_URL,
    data=encoded_body,
    headers={
      "Authorization": f"Bearer {api_key}",
      "Content-Type": "application/json",
    },
    method="POST",
  )

  try:
    with urllib.request.urlopen(request, timeout=30) as response:
      payload = json.loads(response.read().decode("utf-8"))
  except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8", errors="replace")
    raise HTTPException(
      status_code=status.HTTP_502_BAD_GATEWAY,
      detail=f"OpenRouter error ({exc.code}): {body}",
    ) from exc
  except urllib.error.URLError as exc:
    raise HTTPException(
      status_code=status.HTTP_502_BAD_GATEWAY,
      detail=f"OpenRouter connection failed: {exc.reason}",
    ) from exc

  try:
    output = payload["choices"][0]["message"]["content"]
  except (KeyError, IndexError, TypeError) as exc:
    raise HTTPException(
      status_code=status.HTTP_502_BAD_GATEWAY,
      detail="OpenRouter returned an unexpected response shape",
    ) from exc

  if not isinstance(output, str) or not output.strip():
    raise HTTPException(
      status_code=status.HTTP_502_BAD_GATEWAY,
      detail="OpenRouter returned empty output",
    )

  return output


def call_openrouter(prompt: str) -> str:
  return call_openrouter_messages([{"role": "user", "content": prompt}])


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
def board_get(pm_session: str | None = Cookie(default=None)) -> dict[str, object]:
  user = get_session_user(pm_session)
  if not user:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

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
def board_put(board: BoardModel, pm_session: str | None = Cookie(default=None)) -> dict[str, bool]:
  user = get_session_user(pm_session)
  if not user:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

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


@app.post("/api/ai/diagnostic")
def ai_diagnostic(
  payload: DiagnosticAIRequest,
  pm_session: str | None = Cookie(default=None),
) -> dict[str, str]:
  user = get_session_user(pm_session)
  if not user:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

  output = call_openrouter(payload.prompt)
  return {"model": OPENROUTER_MODEL, "output": output}


@app.post("/api/ai/chat")
def ai_chat(
  payload: AIChatRequest,
  pm_session: str | None = Cookie(default=None),
) -> dict[str, object]:
  user = get_session_user(pm_session)
  if not user:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

  with get_db() as db:
    row = db.execute(
      "SELECT payload FROM boards WHERE user_id = ?",
      (user["id"],),
    ).fetchone()
  current_board = json.loads(row["payload"]) if row else DEFAULT_BOARD

  system_content = AI_CHAT_SYSTEM_PROMPT.format(board_json=json.dumps(current_board))
  messages: list[dict] = [{"role": "system", "content": system_content}]
  for msg in payload.history:
    messages.append({"role": msg.role, "content": msg.content})
  messages.append({"role": "user", "content": payload.message})

  raw_output = call_openrouter_messages(messages)

  try:
    ai_response = json.loads(raw_output)
  except json.JSONDecodeError:
    return {"assistant_text": "The AI returned an unreadable response. Please try again.", "board_updated": False}

  assistant_text = ai_response.get("assistant_text", "")
  if not isinstance(assistant_text, str) or not assistant_text.strip():
    return {"assistant_text": "The AI returned an invalid response. Please try again.", "board_updated": False}

  board_update_data = ai_response.get("board_update")
  if board_update_data is None:
    return {"assistant_text": assistant_text, "board_updated": False}

  try:
    validated_board = BoardModel.model_validate(board_update_data)
  except Exception:
    return {"assistant_text": assistant_text, "board_updated": False}

  with get_db() as db:
    db.execute(
      """
      INSERT INTO boards (user_id, payload, updated_at)
      VALUES (?, ?, ?)
      ON CONFLICT(user_id) DO UPDATE SET
        payload = excluded.payload,
        updated_at = excluded.updated_at
      """,
      (user["id"], json.dumps(validated_board.model_dump()), datetime.now(UTC).isoformat()),
    )

  return {"assistant_text": assistant_text, "board_updated": True}


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
