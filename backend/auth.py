import hashlib
import secrets
from datetime import UTC, datetime

import db

SESSION_COOKIE_NAME = "pm_session"
SESSION_DURATION_DAYS = 7


def hash_password(password: str) -> str:
  salt = secrets.token_hex(16)
  hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
  return f"{salt}:{hashed}"


def verify_password(password: str, stored: str) -> bool:
  try:
    salt, hashed = stored.split(":", 1)
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return secrets.compare_digest(check, hashed)
  except Exception:
    return False


def get_session_user(session_token: str | None) -> dict[str, str | int] | None:
  if not session_token:
    return None

  now_iso = datetime.now(UTC).isoformat()
  with db.get_db() as conn:
    row = conn.execute(
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
      conn.execute("DELETE FROM sessions WHERE token = ?", (session_token,))
      return None

    return {"id": row["id"], "username": row["username"]}


def require_auth(pm_session: str | None) -> dict[str, str | int]:
  from fastapi import HTTPException, status
  user = get_session_user(pm_session)
  if not user:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
  return user


def cleanup_expired_sessions() -> None:
  with db.get_db() as conn:
    conn.execute(
      "DELETE FROM sessions WHERE expires_at < ?",
      (datetime.now(UTC).isoformat(),),
    )


def initialize_database() -> None:
  cleanup_expired_sessions()
  with db.get_db() as conn:
    conn.execute(
      """
      INSERT INTO users (username, password)
      VALUES (?, ?)
      ON CONFLICT(username) DO NOTHING
      """,
      ("user", hash_password("password")),
    )
