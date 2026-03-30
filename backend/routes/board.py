import json
import sqlite3
from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends

import auth
import db
from models import BoardModel, BoardResponse, BoardUpdateResponse

router = APIRouter()


@router.get("/api/board")
def board_get(
  conn: sqlite3.Connection = Depends(db.get_request_db),
  pm_session: str | None = Cookie(default=None),
) -> BoardResponse:
  user = auth.require_auth(pm_session, conn)
  row = conn.execute(
    "SELECT payload FROM boards WHERE user_id = ?",
    (user["id"],),
  ).fetchone()
  if row:
    board_data = json.loads(row["payload"])
  else:
    from seed import DEFAULT_BOARD
    board_data = dict(DEFAULT_BOARD)
    conn.execute(
      "INSERT INTO boards (user_id, payload, updated_at) VALUES (?, ?, ?)",
      (user["id"], json.dumps(DEFAULT_BOARD), datetime.now(UTC).isoformat()),
    )
  return BoardResponse(board=BoardModel.model_validate(board_data))


@router.put("/api/board")
def board_put(
  board: BoardModel,
  conn: sqlite3.Connection = Depends(db.get_request_db),
  pm_session: str | None = Cookie(default=None),
) -> BoardUpdateResponse:
  user = auth.require_auth(pm_session, conn)

  conn.execute(
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

  return BoardUpdateResponse(ok=True)
