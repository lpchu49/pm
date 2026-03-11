import json
from datetime import UTC, datetime

from fastapi import APIRouter, Cookie

import auth
import db
import openrouter
from models import (
  AIChatRequest,
  AIChatResponse,
  BoardModel,
  DiagnosticAIRequest,
  DiagnosticResponse,
)
from seed import AI_CHAT_SYSTEM_PROMPT

router = APIRouter()


@router.post("/api/ai/diagnostic")
def ai_diagnostic(
  payload: DiagnosticAIRequest,
  pm_session: str | None = Cookie(default=None),
) -> DiagnosticResponse:
  auth.require_auth(pm_session)
  output = openrouter.call_openrouter(payload.prompt)
  return DiagnosticResponse(model=openrouter.OPENROUTER_MODEL, output=output)


@router.post("/api/ai/chat")
def ai_chat(
  payload: AIChatRequest,
  pm_session: str | None = Cookie(default=None),
) -> AIChatResponse:
  user = auth.require_auth(pm_session)
  current_board = db.get_or_create_board(user["id"])

  system_content = AI_CHAT_SYSTEM_PROMPT + json.dumps(current_board)
  messages: list[dict] = [{"role": "system", "content": system_content}]
  for msg in payload.history:
    messages.append({"role": msg.role, "content": msg.content})
  messages.append({"role": "user", "content": payload.message})

  raw_output = openrouter.call_openrouter_messages(messages)

  try:
    ai_response = json.loads(raw_output)
  except json.JSONDecodeError:
    return AIChatResponse(
      assistant_text="The AI returned an unreadable response. Please try again.",
      board_updated=False,
    )

  assistant_text = ai_response.get("assistant_text", "")
  if not isinstance(assistant_text, str) or not assistant_text.strip():
    return AIChatResponse(
      assistant_text="The AI returned an invalid response. Please try again.",
      board_updated=False,
    )

  board_update_data = ai_response.get("board_update")
  if board_update_data is None:
    return AIChatResponse(assistant_text=assistant_text, board_updated=False)

  try:
    validated_board = BoardModel.model_validate(board_update_data)
  except Exception:
    return AIChatResponse(assistant_text=assistant_text, board_updated=False)

  with db.get_db() as conn:
    conn.execute(
      """
      INSERT INTO boards (user_id, payload, updated_at)
      VALUES (?, ?, ?)
      ON CONFLICT(user_id) DO UPDATE SET
        payload = excluded.payload,
        updated_at = excluded.updated_at
      """,
      (user["id"], json.dumps(validated_board.model_dump()), datetime.now(UTC).isoformat()),
    )

  return AIChatResponse(assistant_text=assistant_text, board_updated=True)
