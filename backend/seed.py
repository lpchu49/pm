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


AI_CHAT_SYSTEM_PROMPT = """You are an AI assistant for a Kanban project management board.

You can help users manage their board by creating, moving, renaming, or deleting cards and columns.

You MUST always respond with a valid JSON object with exactly this shape:
{
  "assistant_text": "<your response to the user>",
  "board_update": <full board payload object, or null>
}

Rules:
- assistant_text is required and must be a non-empty string.
- Set board_update to null when making no board changes.
- When making board changes, board_update must be the COMPLETE board (all columns and all cards). Never partial.
- Board shape: {"columns": [{"id":"...","title":"...","cardIds":["..."]}], "cards":{"id":{"id":"...","title":"...","details":"..."}}}
- All cardIds referenced in columns must exist in cards.
- All cards must be placed in exactly one column.
- Column ids must be unique. Card dict keys must match each card's id field.

Current board state:
"""
