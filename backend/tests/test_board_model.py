from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models import BoardModel


def build_valid_board() -> dict[str, object]:
    return {
        "columns": [
            {"id": "col-backlog", "title": "Backlog", "cardIds": ["card-1"]},
            {"id": "col-review", "title": "Review", "cardIds": ["card-2"]},
        ],
        "cards": {
            "card-1": {"id": "card-1", "title": "Card 1", "details": "Details 1"},
            "card-2": {"id": "card-2", "title": "Card 2", "details": "Details 2"},
        },
    }


def test_board_model_accepts_valid_payload() -> None:
    payload = build_valid_board()
    board = BoardModel.model_validate(payload)

    assert len(board.columns) == 2
    assert set(board.cards.keys()) == {"card-1", "card-2"}


def test_board_model_rejects_duplicate_card_reference() -> None:
    payload = build_valid_board()
    payload["columns"][1]["cardIds"] = ["card-1"]

    with pytest.raises(ValidationError):
        BoardModel.model_validate(payload)


def test_board_model_rejects_orphan_card() -> None:
    payload = build_valid_board()
    payload["cards"]["card-3"] = {
        "id": "card-3",
        "title": "Orphan",
        "details": "Not in any column",
    }

    with pytest.raises(ValidationError):
        BoardModel.model_validate(payload)
