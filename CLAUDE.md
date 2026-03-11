# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Kanban project management MVP. Single user (`user`/`password`), single board per user. FastAPI backend serves the static Next.js build at `/`, with SQLite persistence and an AI chat sidebar that can modify the board via structured OpenRouter calls.

## Commands

### Run the app (Docker)
```bash
./scripts/start-server-mac.sh   # build image and start container on port 8000
./scripts/stop-server-mac.sh    # stop and remove container
```

### Frontend (from `frontend/`)
```bash
npm run dev           # local dev server
npm run build         # production static build (output: frontend/out/)
npm run lint          # eslint
npm run test:unit     # vitest unit/component tests
npm run test:e2e      # playwright e2e (requires running server)
npm run test:all      # unit + e2e
```
E2E against running container:
```bash
cd frontend && PLAYWRIGHT_BASE_URL=http://127.0.0.1:8000 npm run test:e2e
```

### Backend (from repo root)
```bash
.venv/bin/python -m pytest backend/tests -q
```
Live OpenRouter test (opt-in):
```bash
RUN_OPENROUTER_LIVE_TEST=1 .venv/bin/python -m pytest backend/tests -q
```

## Architecture

### Request flow
1. Browser hits `http://localhost:8000/`
2. FastAPI serves the static Next.js build from `backend/static/` (copied in during Docker build from `frontend/out/`)
3. All `/api/*` routes are handled by FastAPI; auth uses an httponly `pm_session` cookie backed by SQLite sessions

### Backend (`backend/main.py`)
Single-file FastAPI app. Key sections:
- **Pydantic models**: `CardModel`, `ColumnModel`, `BoardModel` (with strict integrity validator), `AIChatRequest`/`ChatMessage`
- **Auth**: cookie-based sessions; `get_session_user()` validates every protected route
- **Board API**: `GET /api/board` (lazy-creates default board), `PUT /api/board` (full-replace)
- **AI**: `POST /api/ai/chat` sends system prompt with full board JSON + conversation history to OpenRouter (`openai/gpt-oss-120b`); AI must return `{"assistant_text": "...", "board_update": <board or null>}`; board is only mutated if `BoardModel.model_validate()` succeeds
- **Startup**: runs Alembic migrations then seeds the `user`/`password` account and clears all sessions (so app always opens at login)
- **Static serving**: mounts `backend/static/` at `/` when directory exists; falls back to an HTML stub

Database: SQLite at `backend/data/app.db`, managed with Alembic migrations in `backend/alembic/`.

### Frontend (`frontend/src/`)
Next.js App Router. Key components:
- `app/page.tsx` — root; renders `<AuthGate>` wrapping `<KanbanBoard>`
- `components/AuthGate.tsx` — checks `/api/auth/session` on mount; shows login form or board
- `components/KanbanBoard.tsx` — loads board from `/api/board`, saves on every mutation via `PUT /api/board`; exposes `refreshBoardSilently()` (no loading flag) for AI-triggered refreshes
- `components/AIChatSidebar.tsx` — toggleable sidebar; sends messages to `/api/ai/chat` with local history; calls `refreshBoardSilently()` when `board_updated: true`
- `lib/kanban.ts` — `BoardData`/`Column`/`Card` types, `moveCard()`, `createId()`

Board save policy: optimistic local update + explicit `saving`/`error` state with manual retry. Do NOT call `loadBoard()` from AI callback — use `refreshBoardSilently()` to avoid unmounting the sidebar and losing chat history.

### Docker build
Multi-stage: Node 22 Alpine builds the Next.js static export (`npm run build` → `frontend/out/`), then the Python 3.12 slim stage copies the output to `backend/static/` and runs `uv sync --no-dev` before starting uvicorn.

Environment variable `OPENROUTER_API_KEY` must be present at runtime (read from `.env` by the start script).

## Coding Standards

- No over-engineering, no extra features, no unnecessary defensive programming
- No emojis anywhere
- Identify root cause before fixing; prove with evidence
- Use latest idiomatic library APIs
- `BoardModel` validation is strict — reject, never auto-heal invalid payloads
- AI board mutations only apply after successful `BoardModel.model_validate()`; never partially apply
