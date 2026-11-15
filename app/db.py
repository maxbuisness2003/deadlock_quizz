"""SQLite storage for Deadlock Quiz.

The site never talks to the network while serving a request: `scripts/refresh.py`
pulls the community API, normalises the payload into this database and stores
the item art on disk. The quiz keeps working even when the API is down.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DQ_DATA_DIR", BASE_DIR / "data"))
RAW_DIR = DATA_DIR / "raw"
DB_PATH = Path(os.environ.get("DQ_DB_PATH", DATA_DIR / "quiz.db"))

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS items (
    id           INTEGER PRIMARY KEY,
    class_name   TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    slot         TEXT,
    tier         INTEGER,
    cost         INTEGER,
    is_active    INTEGER DEFAULT 0,
    shopable     INTEGER DEFAULT 0,
    description  TEXT,
    image        TEXT,
    stats        TEXT,
    upgrade      TEXT,
    raw          TEXT
);
CREATE INDEX IF NOT EXISTS idx_items_slot ON items(slot);
CREATE INDEX IF NOT EXISTS idx_items_cost ON items(cost);

CREATE TABLE IF NOT EXISTS meta (
    key     TEXT PRIMARY KEY,
    value   TEXT
);
"""


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def query(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    conn = connect()
    try:
        return conn.execute(sql, tuple(params)).fetchall()
    finally:
        conn.close()


def query_one(sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def set_meta(key: str, value: Any) -> None:
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()


def get_meta(key: str, default: Any = None) -> Any:
    row = query_one("SELECT value FROM meta WHERE key=?", (key,))
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except (json.JSONDecodeError, TypeError):
        return row["value"]


def items_count() -> int:
    row = query_one("SELECT COUNT(*) AS n FROM items")
    return int(row["n"]) if row else 0
