import json
from datetime import UTC, datetime

from fastapi import APIRouter, Cookie

import auth
import db
from models import BoardModel, BoardResponse, BoardUpdateResponse

router = APIRouter()


@router.get("/api/board")
def board_get(pm_session: str | None = Cookie(default=None)) -> BoardResponse:
  user = auth.require_auth(pm_session)
  board_data = db.get_or_create_board(user["id"])
  return BoardResponse(board=BoardModel.model_validate(board_data))


@router.put("/api/board")
def board_put(board: BoardModel, pm_session: str | None = Cookie(default=None)) -> BoardUpdateResponse:
  user = auth.require_auth(pm_session)

  with db.get_db() as conn:
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
