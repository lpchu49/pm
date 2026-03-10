# Backend Notes

Current backend scaffold for Parts 2-4:

- Runtime: FastAPI app in `backend/main.py`
- Package manager: `uv` via `backend/pyproject.toml`
- Endpoints:
	- `GET /` serves static frontend from `backend/static` when available
	- `GET /api/health` returns health JSON
	- `GET /api/auth/session` returns authenticated session state
	- `POST /api/auth/login` validates MVP credentials and issues session cookie
	- `POST /api/auth/logout` clears session cookie and session record
- Data:
	- SQLite database at `backend/data/app.db`
	- Auto-creates `users` and `sessions` tables on startup
	- Seeds MVP user `user` / `password`
- Containerization:
	- Root `Dockerfile` builds and runs backend service
	- Root `.dockerignore` excludes unnecessary files from image context
- Tests:
	- Backend API tests live in `backend/tests/test_main.py`
	- Run with `cd /Users/lpc/Projects/pm && /Users/lpc/Projects/pm/.venv/bin/python -m pytest backend/tests -q`

This remains intentionally simple; later parts will extend persistence for Kanban data and AI features.