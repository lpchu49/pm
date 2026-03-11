from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

import auth
import db
from routes.health import router as health_router
from routes.auth_routes import router as auth_router
from routes.board import router as board_router
from routes.ai import router as ai_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
  db.run_migrations()
  auth.initialize_database()
  yield


app = FastAPI(title="Project Management MVP API", lifespan=lifespan)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(board_router)
app.include_router(ai_router)

STATIC_DIR = Path(__file__).resolve().parent / "static"

if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
else:
    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>PM MVP Backend</title>
    <style>
      body {
        margin: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: #f7f8fb;
        color: #032147;
      }
      main {
        max-width: 760px;
        margin: 48px auto;
        padding: 24px;
      }
      .card {
        background: #ffffff;
        border: 1px solid rgba(3, 33, 71, 0.08);
        border-radius: 16px;
        padding: 20px;
      }
      h1 {
        margin-top: 0;
      }
      code {
        background: #eef2f8;
        padding: 2px 6px;
        border-radius: 6px;
      }
    </style>
  </head>
  <body>
    <main>
      <div class="card">
        <h1>Frontend build not found</h1>
        <p>Build frontend assets and place them in <code>backend/static</code>.</p>
      </div>
    </main>
  </body>
</html>
"""
