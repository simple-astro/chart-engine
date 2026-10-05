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
    conn.execute(
        "CREATE TABLE IF NOT EXISTS chat_messages ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " profile_id INTEGER NOT NULL,"
        " role TEXT NOT NULL,"
        " content TEXT NOT NULL,"
        " created_at TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS answer_cache ("
        " profile_id INTEGER NOT NULL, qkey TEXT NOT NULL, day TEXT NOT NULL, answer TEXT NOT NULL,"
        " PRIMARY KEY (profile_id, qkey, day))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS usage_log ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, profile_id INTEGER, kind TEXT NOT NULL,"
        " model TEXT, input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0,"
        " cache_read_tokens INTEGER DEFAULT 0, cache_write_tokens INTEGER DEFAULT 0,"
        " tool_rounds INTEGER DEFAULT 0, words INTEGER DEFAULT 0, question TEXT)"
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
        conn.execute("DELETE FROM chat_messages WHERE profile_id = ?", (profile_id,))
        conn.execute("DELETE FROM answer_cache WHERE profile_id = ?", (profile_id,))
        return conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,)).rowcount > 0


def add_message(profile_id: int, role: str, content: str) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO chat_messages (profile_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (profile_id, role, content, now),
        )


def get_messages(profile_id: int, limit: int | None = None) -> list[dict]:
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM chat_messages WHERE profile_id = ? ORDER BY id",
            (profile_id,),
        ).fetchall()
    out = [dict(r) for r in rows]
    return out[-limit:] if limit else out


def clear_messages(profile_id: int) -> None:
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM chat_messages WHERE profile_id = ?", (profile_id,))


def cache_get(profile_id: int, qkey: str, day: str) -> str | None:
    with _lock, _connect() as conn:
        r = conn.execute("SELECT answer FROM answer_cache WHERE profile_id=? AND qkey=? AND day=?",
                         (profile_id, qkey, day)).fetchone()
    return r["answer"] if r else None


def cache_put(profile_id: int, qkey: str, day: str, answer: str) -> None:
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM answer_cache WHERE profile_id=? AND day<>?", (profile_id, day))  # drop stale days
        conn.execute("INSERT OR REPLACE INTO answer_cache (profile_id, qkey, day, answer) VALUES (?,?,?,?)",
                     (profile_id, qkey, day, answer))


def log_usage(profile_id: int, kind: str, question: str, *, model: str | None = None, input_tokens: int = 0,
              output_tokens: int = 0, cache_read: int = 0, cache_write: int = 0, tool_rounds: int = 0,
              words: int = 0) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO usage_log (ts, profile_id, kind, model, input_tokens, output_tokens, cache_read_tokens,"
            " cache_write_tokens, tool_rounds, words, question) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (now, profile_id, kind, model, input_tokens, output_tokens, cache_read, cache_write, tool_rounds,
             words, question[:200]))


def usage_summary(recent: int = 20) -> dict:
    with _lock, _connect() as conn:
        tot = conn.execute(
            "SELECT kind, COUNT(*) n, COALESCE(SUM(input_tokens),0) inp, COALESCE(SUM(output_tokens),0) out,"
            " COALESCE(SUM(cache_read_tokens),0) cr, COALESCE(SUM(cache_write_tokens),0) cw"
            " FROM usage_log GROUP BY kind").fetchall()
        day = conn.execute(
            "SELECT COUNT(*) n, COALESCE(SUM(input_tokens+output_tokens),0) t FROM usage_log"
            " WHERE kind='llm' AND substr(ts,1,10)=?", (datetime.now(timezone.utc).date().isoformat(),)).fetchone()
        rows = conn.execute("SELECT * FROM usage_log ORDER BY id DESC LIMIT ?", (recent,)).fetchall()
    return {"by_kind": {r["kind"]: {"requests": r["n"], "input_tokens": r["inp"], "output_tokens": r["out"],
                                    "cache_read_tokens": r["cr"], "cache_write_tokens": r["cw"]} for r in tot},
            "today_llm": {"requests": day["n"], "tokens": day["t"]},
            "recent": [dict(r) for r in rows]}
