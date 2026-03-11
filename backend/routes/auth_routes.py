import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, HTTPException, Response, status

import auth
import db
from models import LoginRequest, LoginResponse, LogoutResponse, SessionResponse

router = APIRouter()


@router.get("/api/auth/session")
def auth_session(pm_session: str | None = Cookie(default=None)) -> SessionResponse:
  user = auth.get_session_user(pm_session)
  if not user:
    return SessionResponse(authenticated=False)
  return SessionResponse(authenticated=True, username=str(user["username"]))


@router.post("/api/auth/login")
def auth_login(payload: LoginRequest, response: Response) -> LoginResponse:
  with db.get_db() as conn:
    row = conn.execute(
      "SELECT id, username, password FROM users WHERE username = ?",
      (payload.username,),
    ).fetchone()

    if not row or not auth.verify_password(payload.password, row["password"]):
      raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
      )

    token = secrets.token_urlsafe(32)
    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(days=auth.SESSION_DURATION_DAYS)
    conn.execute(
      """
      INSERT INTO sessions (token, user_id, created_at, expires_at)
      VALUES (?, ?, ?, ?)
      """,
      (token, row["id"], created_at.isoformat(), expires_at.isoformat()),
    )

  response.set_cookie(
    key=auth.SESSION_COOKIE_NAME,
    value=token,
    httponly=True,
    samesite="lax",
    secure=False,
    max_age=auth.SESSION_DURATION_DAYS * 24 * 60 * 60,
  )
  return LoginResponse(authenticated=True, username=row["username"])


@router.post("/api/auth/logout")
def auth_logout(response: Response, pm_session: str | None = Cookie(default=None)) -> LogoutResponse:
  if pm_session:
    with db.get_db() as conn:
      conn.execute("DELETE FROM sessions WHERE token = ?", (pm_session,))
  response.delete_cookie(auth.SESSION_COOKIE_NAME)
  return LogoutResponse(ok=True)
