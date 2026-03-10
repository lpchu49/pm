# Project Execution Plan

This document is the execution checklist for the MVP described in `AGENTS.md`.
Each part includes:
- Scope and implementation steps
- Test checklist
- Success criteria

Status legend:
- [ ] Not started
- [x] Completed

## Handoff Snapshot (2026-03-10)

### Implemented so far
- Parts 1-4 are implemented and validated.
- Frontend static build is served by FastAPI at `/`.
- Backend auth is implemented with server-side SQLite session persistence:
	- `GET /api/auth/session`
	- `POST /api/auth/login`
	- `POST /api/auth/logout`
- MVP credentials are seeded in DB as `user` / `password`.
- Backend runtime DB path is `backend/data/app.db`.
- Dockerized startup mounts named volume `pm-mvp-data` to persist backend DB across container restarts.

### Test status
- Frontend unit tests pass.
- Frontend e2e tests pass (including auth-required flows).
- Backend API tests now exist and pass in `backend/tests/test_main.py`.
- Last backend test run result: `5 passed`.

### Verified run commands
- Start app:
	- `./scripts/start-server-mac.sh`
- Stop app:
	- `./scripts/stop-server-mac.sh`
- Frontend unit tests:
	- `cd frontend && npm run test:unit`
- Frontend e2e tests against running container:
	- `cd frontend && PLAYWRIGHT_BASE_URL=http://127.0.0.1:8000 npm run test:e2e`
- Backend tests (from repo root):
	- `/Users/lpc/Projects/pm/.venv/bin/python -m pytest backend/tests -q`

### Important current files
- Backend app: `backend/main.py`
- Backend tests: `backend/tests/test_main.py`
- Backend dependencies/lock: `backend/pyproject.toml`, `backend/uv.lock`
- Frontend auth gate: `frontend/src/components/AuthGate.tsx`
- Root page entry: `frontend/src/app/page.tsx`
- E2E suite: `frontend/tests/kanban.spec.ts`
- Docker build: `Dockerfile`
- Mac scripts: `scripts/start-server-mac.sh`, `scripts/stop-server-mac.sh`

### Known issues / caveats
- FastAPI `@app.on_event("startup")` emits deprecation warnings; migrate to lifespan handlers in a future cleanup.
- `uv` CLI behavior differs by version; current local test command is pinned above and should be treated as canonical for this repo state.
- Authentication currently stores plain-text password for seeded MVP user by design/scope; replace with proper hashing when auth is hardened.

### Next recommended steps (for next engineer)
1. Start Part 5 by drafting the Kanban persistence schema doc in `docs/` and get user sign-off.
2. Keep current auth/session tables as-is, then extend schema with board JSON storage tied to user.
3. Add/expand backend tests for new schema/data-access layer before implementing Part 6 API routes.

## Part 1: Planning and baseline documentation

### Goals
- Produce an actionable, testable plan for Parts 2-10.
- Document the current frontend implementation in `frontend/AGENTS.md`.
- Confirm user approval before implementation work beyond Part 1.

### Checklist
- [x] Expand `docs/PLAN.md` into detailed part-by-part checklists.
- [x] Add explicit tests and success criteria for every part.
- [x] Capture architectural decisions already approved:
	- FastAPI serves static frontend build at `/` for MVP.
	- Persistent backend database is required.
	- AI update handling uses strict validation mode (reject invalid/ambiguous outputs).
- [x] Create `frontend/AGENTS.md` describing current frontend code structure.
- [x] User approves this plan before code changes for Part 2+.

### Tests
- [x] User review confirms plan completeness and sequencing.
- [x] User review confirms no required scope is missing from Parts 2-10.

### Success criteria
- [x] User explicitly approves this plan.
- [x] Team can execute each part without needing hidden assumptions.

## Part 2: Scaffolding

### Goals
- Stand up baseline backend + container + scripts.
- Prove local containerized app works end-to-end with static page and API endpoint.

### Checklist
- [x] Create backend project in `backend/` using FastAPI + Pydantic with `uv`.
- [x] Add minimal app with:
	- [x] `GET /api/health` endpoint returning healthy status JSON.
	- [x] Temporary root page for hello-world validation.
- [x] Add Docker assets at repo root/backend as needed:
	- [x] `Dockerfile`
	- [x] `.dockerignore`
	- [x] Runtime command using `uv`.
- [x] Create scripts in `scripts/` for macOS:
	- [x] Start script (build/run container locally).
	- [x] Stop script (stop/remove running container).
- [x] Ensure environment variable loading from root `.env` is documented and used where required.

### Tests
- [x] Container builds successfully from clean checkout.
- [x] Start script launches app and logs show FastAPI serving.
- [x] `GET /` returns hello-world content.
- [x] `GET /api/health` returns expected JSON and status code `200`.
- [x] Stop script fully stops container and frees port.

### Success criteria
- [x] One-command start works on macOS.
- [x] One-command stop works on macOS.
- [x] App and API are reachable locally in containerized mode.

## Part 3: Add frontend static build and serving

### Goals
- Replace temporary root page with built frontend UI served by backend at `/`.

### Checklist
- [x] Configure frontend production build output for static serving.
- [x] Add backend static file serving for built frontend assets.
- [x] Route `/` to frontend app entry and preserve `/api/*` for backend APIs.
- [x] Integrate frontend build into Docker build process.
- [x] Keep local dev workflow straightforward for frontend and backend iteration.

### Tests
- [x] Frontend unit tests pass.
- [x] Frontend e2e tests pass against served app.
- [x] Containerized app serves Kanban UI at `/`.
- [x] Static asset requests return `200` and render correctly.
- [x] API route (`/api/health`) still works after static serving is enabled.

### Success criteria
- [x] Kanban demo board is visible at `/` from containerized app.
- [x] No regression in existing frontend interactions.

## Part 4: Fake user sign-in flow

### Goals
- Require login before access to board using MVP credentials.
- Keep architecture compatible with future real auth.

### Checklist
- [x] Add login UI at `/` (or route split) with username/password form.
- [x] Validate against hardcoded credentials: `user` / `password`.
- [x] Add logout action to clear authenticated session state.
- [x] Implement persistent backend-backed auth state mechanism compatible with scaling:
	- [x] Session/token state is managed server-side and persisted appropriately.
	- [x] Frontend does not store authoritative auth state only in memory.
- [x] Guard board view so unauthenticated users cannot access it.

### Tests
- [x] Unit tests for credential validation and auth guard logic.
- [x] Integration/e2e tests:
	- [x] Unauthenticated users see login form.
	- [x] Correct credentials allow access.
	- [x] Wrong credentials are rejected with clear message.
	- [x] Logout returns user to login view.

### Success criteria
- [x] Board is inaccessible without login.
- [x] Login/logout path is reliable and repeatable.

## Part 5: Database modeling

### Goals
- Define and document persistent schema for user + board state.
- Keep MVP simple while leaving migration path toward higher-scale database backends.

### Checklist
- [ ] Propose schema for:
	- [ ] Users
	- [ ] Single board per user
	- [ ] Board JSON payload persistence
	- [ ] Timestamps/versioning fields needed for updates
- [ ] Document design in `docs/` and request user sign-off before implementation.
- [ ] Define data access boundaries so storage backend can evolve from SQLite later.
- [ ] Specify migration/init strategy so DB is created automatically if missing.

### Tests
- [ ] Schema can be created from empty state.
- [ ] Seed and retrieval test for one user + one board JSON document.
- [ ] Update test verifies board JSON is replaced/updated correctly.

### Success criteria
- [ ] User approves documented schema.
- [ ] Backend can reliably persist and retrieve board state per user.

## Part 6: Backend Kanban API

### Goals
- Implement API routes for loading and mutating user board data.

### Checklist
- [ ] Add API endpoints for board fetch and board update operations.
- [ ] Enforce request/response validation with Pydantic models.
- [ ] Ensure board operations are scoped to authenticated user.
- [ ] Auto-create DB on first startup when missing.
- [ ] Add clear error handling and status codes.

### Tests
- [ ] Backend unit tests for service/data layers.
- [ ] API tests for success and failure cases:
	- [ ] Missing auth is rejected.
	- [ ] Invalid payload is rejected with validation error.
	- [ ] Valid payload persists and can be reloaded.
	- [ ] Nonexistent user/board handling is deterministic.

### Success criteria
- [ ] API is stable and fully covered for core CRUD paths used by frontend.
- [ ] Board state persists across app restarts.

## Part 7: Frontend + Backend integration

### Goals
- Switch frontend state source from local in-memory data to backend API.

### Checklist
- [ ] Replace direct `initialData` usage with API-backed load on authenticated entry.
- [ ] Persist board updates (rename/add/delete/move) through backend calls.
- [ ] Add optimistic or immediate refresh strategy with clear error fallback.
- [ ] Keep UI responsive during loading/saving states.

### Tests
- [ ] Frontend integration tests with API mocks.
- [ ] E2E tests against running backend:
	- [ ] Board loads from backend.
	- [ ] Board edits persist after page refresh.
	- [ ] Persistence remains after app restart.

### Success criteria
- [ ] User-visible board is truly persistent, not local-only.
- [ ] Core Kanban interactions remain functional.

## Part 8: AI connectivity (OpenRouter)

### Goals
- Prove backend can call OpenRouter using configured model and API key.

### Checklist
- [ ] Add backend AI client wrapper using OpenRouter API.
- [ ] Read API key from environment (`OPENROUTER_API_KEY`).
- [ ] Configure model `openai/gpt-oss-120b`.
- [ ] Add minimal diagnostic/test path for connectivity check.

### Tests
- [ ] Connectivity test prompt `2+2` returns expected semantic answer.
- [ ] Missing API key produces clear startup/runtime error.
- [ ] Non-200/OpenRouter error responses are handled safely.

### Success criteria
- [ ] AI call path is operational in local environment.
- [ ] Failure modes are explicit and non-destructive.

## Part 9: Structured AI board update contract

### Goals
- Send board context + user chat to AI and receive strict structured output.
- Allow optional AI-suggested board mutation.

### Checklist
- [ ] Define strict response schema containing:
	- [ ] Assistant text response.
	- [ ] Optional board update payload.
- [ ] Send current board JSON + conversation history + user message to AI endpoint.
- [ ] Implement strict mode validation policy:
	- [ ] Reject malformed/ambiguous outputs.
	- [ ] Do not apply partial or guessed updates.
	- [ ] Preserve current board when validation fails.
- [ ] Apply valid update in controlled backend transaction.

### Tests
- [ ] Unit tests for schema validation and update-application logic.
- [ ] Tests for invalid model outputs verifying no board mutation occurs.
- [ ] Tests for valid outputs verifying correct board mutation and persistence.
- [ ] Tests for conversation history inclusion and continuity.

### Success criteria
- [ ] AI response is reliable and schema-safe.
- [ ] Board changes only occur from validated structured outputs.

## Part 10: AI sidebar UI and live board refresh

### Goals
- Add chat sidebar that interacts with backend AI endpoint and reflects AI-applied board changes.

### Checklist
- [ ] Implement sidebar chat UI in frontend with message history.
- [ ] Send user messages to backend AI chat endpoint.
- [ ] Render assistant responses in chat thread.
- [ ] When AI update is applied, refresh/reconcile board state automatically.
- [ ] Preserve current visual design language while integrating sidebar.

### Tests
- [ ] Component tests for chat input, message rendering, and loading states.
- [ ] Integration/e2e tests:
	- [ ] Chat request succeeds and response renders.
	- [ ] Valid AI board update appears on board without manual reload.
	- [ ] Invalid AI output path surfaces safe error and leaves board unchanged.

### Success criteria
- [ ] User can converse with AI in-app.
- [ ] AI can safely update board through strict backend contract.
- [ ] UI remains usable and coherent on desktop and mobile.