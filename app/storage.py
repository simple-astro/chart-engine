"""SQLite persistence for saved birth profiles (and their cached charts)."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_lock = threading.Lock()


def _db_path() -> Path:
    return Path(os.environ.get("CHART_DB_PATH", "data/profiles.db"))


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS profiles ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " name TEXT NOT NULL,"
        " request TEXT NOT NULL,"
        " chart TEXT NOT NULL,"
        " created_at TEXT NOT NULL)"
    )
    return conn


def _row(r: sqlite3.Row, with_chart: bool) -> dict:
    out = {"id": r["id"], "name": r["name"], "created_at": r["created_at"],
           "request": json.loads(r["request"])}
    if with_chart:
        out["chart"] = json.loads(r["chart"])
    return out


def save(name: str, request: dict, chart: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO profiles (name, request, chart, created_at) VALUES (?, ?, ?, ?)",
            (name, json.dumps(request), json.dumps(chart), now),
        )
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row(row, True)


def list_all() -> list[dict]:
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT * FROM profiles ORDER BY id DESC").fetchall()
    return [_row(r, False) for r in rows]


def get(profile_id: int) -> dict | None:
    with _lock, _connect() as conn:
        r = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    return _row(r, True) if r else None


def delete(profile_id: int) -> bool:
    with _lock, _connect() as conn:
        return conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,)).rowcount > 0
