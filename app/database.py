import sqlite3
from pathlib import Path
from typing import Generator
from app.config import settings, BASE_DIR


def get_db_path() -> str:
    """Extract SQLite database file path from database URL."""
    db_url = settings.database_url
    if db_url.startswith("sqlite:///"):
        rel_or_abs_path = db_url.replace("sqlite:///", "")
        if rel_or_abs_path == ":memory:":
            return ":memory:"
        # Resolve relative paths against project root
        return str((BASE_DIR / rel_or_abs_path).resolve())
    return db_url


def get_db_connection() -> sqlite3.Connection:
    """Create and return a configured SQLite connection."""
    db_path = get_db_path()
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Minimal database initializer to verify connectivity."""
    conn = get_db_connection()
    try:
        # Enable WAL mode and foreign keys for SQLite performance & integrity
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
    finally:
        conn.close()
