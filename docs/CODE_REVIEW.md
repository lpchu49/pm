# Code Review

Original review: 2026-03-11 (Sonnet)
Second pass: 2026-03-11 (Opus)
Fixes applied: 2026-03-11 (Opus) — all High and Medium issues resolved
Low-severity fixes: 2026-03-30 (Opus) — all Low issues resolved
Scope: entire repository (backend, frontend, tests, infra)

Status legend: H = High, M = Medium, L = Low

---

## H1 - Column rename fires a PUT on every keystroke [FIXED]

**File:** `frontend/src/components/KanbanColumn.tsx`

**Was:** The column title `<input>` called `onRename` on every `onChange` event,
firing a `PUT /api/board` per keystroke.

**Fix:** `KanbanColumn` now maintains local title state, synced from props via
the render-time derivation pattern (no `useEffect`). `onRename` is debounced
at 400ms and also fires on blur for immediate feedback when the user clicks
away.

---

## H2 - Concurrent saves can produce stale state [FIXED]

**File:** `frontend/src/components/KanbanBoard.tsx`

**Was:** Each `persistBoard` call launched an independent fetch. Overlapping
responses could corrupt `saveState` or allow a stale write to overwrite a
newer one.

**Fix:** `persistBoard` now uses an `AbortController`. Each new save aborts the
previous in-flight request. Aborted fetches return silently without updating
state, so only the latest save's result is honored.

---

## H3 - `get_db()` leaks connections [FIXED]

**File:** `backend/db.py`

**Was:** `get_db()` returned a raw `sqlite3.Connection`. Callers used it as a
context manager, which managed the transaction but never called `close()`,
leaking a file descriptor per request.

**Fix:** `get_db()` is now a `@contextmanager` that yields the connection,
calls `commit()` on success / `rollback()` on exception, and always calls
`connection.close()` in the `finally` block. The redundant
`DATA_DIR.mkdir()` call (L11) was also removed — directory creation happens
once in `run_migrations()`.

---

## M1 - `board_get` accesses `row` outside the DB connection block [FIXED]

**File:** `backend/routes/board.py`, `backend/db.py`

**Was:** The `return json.loads(row["payload"])` was outside the `with get_db()`
block.

**Fix:** Extracted to `db.get_or_create_board()` — a shared helper where the
return is inside the `with` block. Both `board_get` and `ai_chat` (M4) now
use it.

---

## M2 - `initialData` fallback silently hides API failures [FIXED]

**File:** `frontend/src/components/KanbanBoard.tsx`, `frontend/src/lib/kanban.ts`

**Was:** `setBoard(payload.board ?? initialData)` silently fell back to
hardcoded data when the API returned a missing board field.

**Fix:** `loadBoard` now throws if `payload.board` is missing, triggering the
error state. `refreshBoardSilently` keeps the existing board if the field is
absent. The `initialData` export in `kanban.ts` has been deleted entirely —
the backend `DEFAULT_BOARD` is the single source of truth (partially
addresses L2).

---

## M3 - Expired sessions accumulate in the database [FIXED]

**File:** `backend/auth.py`

**Was:** Expired sessions were only deleted lazily when a request carried that
specific token. Abandoned sessions accumulated indefinitely.

**Fix:** `auth.cleanup_expired_sessions()` runs a bulk
`DELETE FROM sessions WHERE expires_at < ?` on every server start, called
from `initialize_database()`. Lazy per-request cleanup in
`get_session_user()` is still in place for mid-session expiry.

---

## M4 - `ai_chat` does not lazily create the board record [FIXED]

**File:** `backend/routes/ai.py`, `backend/db.py`

**Was:** `ai_chat` fell back to `DEFAULT_BOARD` in memory without persisting,
creating inconsistency if `board_update` was `null`.

**Fix:** Both `board_get` and `ai_chat` now call `db.get_or_create_board()`,
which inserts the default board if none exists and returns the persisted data.

---

## M5 - Migration version hardcoded in test [FIXED]

**File:** `backend/tests/test_main.py`

**Was:** `assert row[0] == "20260310_0001"` — brittle against future migrations.

**Fix:** Changed to `assert row[0] is not None`. The test still verifies that
the expected tables (`users`, `sessions`, `boards`) exist, which is the
actual intent.

---

## M6 - `AuthGate` pre-populates credentials in form state [FIXED]

**File:** `frontend/src/components/AuthGate.tsx`

**Was:** `useState("user")` and `useState("password")` leaked credentials in
screenshots and recordings.

**Fix:** Both fields initialised to `""`. The AuthGate unit test was updated
to fill in credentials explicitly before submitting.

---

## M7 - No tests for `hash_password` / `verify_password` directly [FIXED]

**File:** `backend/tests/test_main.py`

**Was:** Password functions only exercised indirectly via login tests.

**Fix:** Three dedicated tests added:
- `test_hash_password_round_trip` — correct password verifies
- `test_verify_password_rejects_wrong_password` — wrong password fails
- `test_verify_password_rejects_malformed_stored_hash` — missing `:` and
  empty string both return `False`

---

## M8 - No test for the expired-session code path [FIXED]

**File:** `backend/tests/test_main.py`

**Was:** The `expires_at <= now_iso` branch was never exercised by tests.

**Fix:** `test_expired_session_returns_unauthenticated` logs in, manually
backdates the session's `expires_at`, then asserts that the session endpoint
returns `authenticated: false` and the expired row is deleted from the DB.

---

## M9 - `initialize_database` re-hashes the password on every server start [FIXED]

**File:** `backend/auth.py`

**Was:** `ON CONFLICT(username) DO UPDATE SET password = excluded.password`
overwrote the hash with a new salt on every boot — 100k PBKDF2 iterations
for nothing.

**Fix:** Changed to `ON CONFLICT(username) DO NOTHING`. The seed user is
inserted once; subsequent boots skip it.

---

## M10 - `auth_login` returns 401 via `response.status_code` instead of raising `HTTPException` [FIXED]

**File:** `backend/routes/auth_routes.py`

**Was:** Failed login set `response.status_code = 401` and returned a dict
with an extra `"message"` key, bypassing FastAPI's exception pipeline.

**Fix:** Now raises `HTTPException(status_code=401, detail="Invalid credentials")`,
consistent with all other auth failure paths. The test was updated to assert
the standard `{"detail": "Invalid credentials"}` response shape.

---

## M11 - Playwright e2e tests cannot run against Next.js dev server [FIXED]

**File:** `frontend/playwright.config.ts`

**Was:** A `webServer` fallback started `npm run dev` when `PLAYWRIGHT_BASE_URL`
was unset, but the Next.js dev server cannot serve `/api/*` routes.

**Fix:** `PLAYWRIGHT_BASE_URL` is now required. If unset, the config throws
a clear error message explaining that e2e tests require the Docker container.
The misleading `webServer` block was removed.

---

## M12 - `main.py` is a 593-line monolith [FIXED]

**File:** `backend/`

**Was:** Models, auth, routes, DB, AI, migrations, seed data, and static
serving all in one file.

**Fix:** Split into modules using `APIRouter`:

```
backend/
  main.py            — app, lifespan, static mount (~65 lines)
  models.py          — Pydantic request + response models
  db.py              — get_db(), run_migrations(), get_or_create_board()
  auth.py            — hash/verify password, sessions, initialize_database()
  openrouter.py      — OpenRouter API calls
  seed.py            — DEFAULT_BOARD, AI_CHAT_SYSTEM_PROMPT
  routes/
    health.py        — GET /api/health
    auth_routes.py   — session, login, logout
    board.py         — GET/PUT board
    ai.py            — diagnostic, chat
```

All tests updated to import from the correct modules.

---

## M13 - Pydantic models used for validation but not for serialization [FIXED]

**File:** `backend/models.py`, `backend/routes/`

**Was:** Every route returned raw `dict[str, object]` — no response contract,
no serialization validation, inaccurate OpenAPI docs.

**Fix:** Response models defined in `models.py`:
- `HealthResponse`, `SessionResponse`, `LoginResponse`, `LogoutResponse`
- `BoardResponse`, `BoardUpdateResponse`
- `DiagnosticResponse`, `AIChatResponse`

All route handlers now return typed response model instances. FastAPI
generates accurate OpenAPI schemas and validates responses at the server.

---

## Low severity findings (all resolved)

| ID | Area | Description | Status |
|----|------|-------------|--------|
| L1 | Frontend | Array index used as React key in chat messages | FIXED — `ChatMessage` now carries a monotonic `id` field used as the React key |
| L2 | Both | Fixture data duplicated across locations | FIXED — frontend `initialData` removed (M2); test fixture is intentionally separate |
| L3 | Frontend | `Math.random()` used for ID generation | FIXED — `createId()` now uses `crypto.getRandomValues()` |
| L4 | Frontend | 4-space indentation in `AIChatSidebar.tsx` | FIXED — reformatted to 2-space indentation matching the rest of the frontend |
| L5 | Backend | Two DB connections opened per authenticated request | FIXED — added `get_request_db()` FastAPI dependency; all routes share a single connection per request |
| L6 | Backend | AI prompt does not require stable IDs on rename | FIXED — system prompt now instructs the model to preserve existing IDs on rename |
| L7 | Frontend tests | Large inline fixture in `KanbanBoard.test.tsx` | FIXED — extracted to `BOARD_FIXTURE` const |
| L8 | Backend | `secure=False` cookie not documented for deployment | FIXED — comment added explaining localhost-only usage and production guidance |
| L9 | Frontend | `handleLogout` does not handle fetch failure | FIXED — side effect of M6 work |
| L10 | Backend | OpenRouter error body not truncated | FIXED — side effect of module split (`[:500]` in `openrouter.py`) |
| L11 | Backend | `get_db()` creates `DATA_DIR` on every call | FIXED — side effect of H3 |
