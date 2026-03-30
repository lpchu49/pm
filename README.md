# Kanban Studio

A single-user Kanban project management board. FastAPI backend with SQLite persistence, Next.js static frontend, and an AI chat sidebar powered by OpenRouter.

Default credentials: `user` / `password`

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Node.js 22+](https://nodejs.org/) (for frontend development and tests)
- [uv](https://docs.astral.sh/uv/) (for backend development and tests)
- An [OpenRouter](https://openrouter.ai/) API key (for AI chat features)

## Quick start

1. Create a `.env` file in the project root:

```
OPENROUTER_API_KEY=sk-or-...
```

2. Build and start the Docker container:

```bash
./scripts/start-server-mac.sh
```

3. Open http://127.0.0.1:8000 and log in with `user` / `password`.

4. To stop:

```bash
./scripts/stop-server-mac.sh
```

## Development setup

### Backend

```bash
cd backend
uv sync            # creates .venv and installs dependencies
```

Run from the project root:

```bash
.venv/bin/python -m pytest backend/tests -q
```

The live OpenRouter test requires the API key exported:

```bash
export $(grep -v '^#' .env | xargs)
.venv/bin/python -m pytest backend/tests -q
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # local dev server (API calls require the Docker container)
```

## Tests

### Backend unit tests

```bash
export $(grep -v '^#' .env | xargs)
.venv/bin/python -m pytest backend/tests -q
```

### Frontend unit tests

```bash
cd frontend
npm run test:unit
```

### Frontend e2e tests

Requires the Docker container to be running:

```bash
cd frontend
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8000 npm run test:e2e
```

### Run all frontend tests

```bash
cd frontend
npm run test:all
```

### Lint

```bash
cd frontend
npm run lint
```

## Architecture

```
backend/
  main.py            app, lifespan, static mount
  models.py          Pydantic request + response models
  db.py              SQLite connection, migrations, board queries
  auth.py            password hashing, sessions, auth helpers
  openrouter.py      OpenRouter API calls
  seed.py            default board data, AI system prompt
  routes/
    health.py        GET /api/health
    auth_routes.py   session, login, logout
    board.py         GET/PUT board
    ai.py            diagnostic, chat
  alembic/           database migrations
  data/              SQLite database (created at runtime)

frontend/
  src/
    app/page.tsx     root page
    components/      AuthGate, KanbanBoard, KanbanColumn, AIChatSidebar
    lib/kanban.ts    board types and helpers
```

The Docker build produces a static Next.js export (`frontend/out/`) and serves it from FastAPI at `/`. All `/api/*` routes are handled by FastAPI. Auth uses an httponly cookie backed by SQLite sessions.
