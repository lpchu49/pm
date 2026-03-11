from typing import Literal

from pydantic import BaseModel, model_validator


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


class LoginRequest(BaseModel):
  username: str
  password: str


class DiagnosticAIRequest(BaseModel):
  prompt: str = "What is 2+2? Answer with just the number."


class ChatMessage(BaseModel):
  role: Literal["user", "assistant"]
  content: str


class AIChatRequest(BaseModel):
  message: str
  history: list[ChatMessage] = []


# Response models (M13)

class HealthResponse(BaseModel):
  status: str
  service: str


class SessionResponse(BaseModel):
  authenticated: bool
  username: str | None = None


class LoginResponse(BaseModel):
  authenticated: bool
  username: str


class LogoutResponse(BaseModel):
  ok: bool


class BoardResponse(BaseModel):
  board: BoardModel


class BoardUpdateResponse(BaseModel):
  ok: bool


class DiagnosticResponse(BaseModel):
  model: str
  output: str


class AIChatResponse(BaseModel):
  assistant_text: str
  board_updated: bool
