import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from alembic import command
from alembic.config import Config

from seed import DEFAULT_BOARD

DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "app.db"
ALEMBIC_INI_PATH = Path(__file__).resolve().parent / "alembic.ini"
ALEMBIC_SCRIPT_PATH = Path(__file__).resolve().parent / "alembic"


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
  connection = sqlite3.connect(DB_PATH)
  connection.row_factory = sqlite3.Row
  try:
    yield connection
    connection.commit()
  except Exception:
    connection.rollback()
    raise
  finally:
    connection.close()


def run_migrations() -> None:
  DATA_DIR.mkdir(parents=True, exist_ok=True)
  config = Config(str(ALEMBIC_INI_PATH))
  config.set_main_option("script_location", str(ALEMBIC_SCRIPT_PATH))
  config.set_main_option("sqlalchemy.url", f"sqlite:///{DB_PATH}")

  with sqlite3.connect(DB_PATH) as tmp_conn:
    table_names = {
      row[0]
      for row in tmp_conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }

    has_alembic_version = "alembic_version" in table_names
    alembic_version_rows = (
      tmp_conn.execute("SELECT version_num FROM alembic_version").fetchall()
      if has_alembic_version
      else []
    )
  tmp_conn.close()

  has_any_legacy_table = bool({"users", "sessions", "boards"}.intersection(table_names))
  has_empty_alembic_version = has_alembic_version and not alembic_version_rows

  if has_any_legacy_table and (not has_alembic_version or has_empty_alembic_version):
    command.stamp(config, "head")

    with sqlite3.connect(DB_PATH) as tmp_conn:
      tmp_conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT NOT NULL UNIQUE,
          password TEXT NOT NULL
        )
        """
      )
      tmp_conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
          token TEXT PRIMARY KEY,
          user_id INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          expires_at TEXT NOT NULL,
          FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
      )
      tmp_conn.execute(
        """
        CREATE TABLE IF NOT EXISTS boards (
          user_id INTEGER PRIMARY KEY,
          payload TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
      )
    tmp_conn.close()
    return

  command.upgrade(config, "head")


def get_or_create_board(user_id: int) -> dict:
  with get_db() as conn:
    row = conn.execute(
      "SELECT payload FROM boards WHERE user_id = ?",
      (user_id,),
    ).fetchone()
    if row:
      return json.loads(row["payload"])
    payload = json.dumps(DEFAULT_BOARD)
    conn.execute(
      "INSERT INTO boards (user_id, payload, updated_at) VALUES (?, ?, ?)",
      (user_id, payload, datetime.now(UTC).isoformat()),
    )
    return dict(DEFAULT_BOARD)
