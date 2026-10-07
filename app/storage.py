"""SQLite persistence for saved birth profiles (and their cached charts)."""
from __future__ import annotations

import json
import os
import secrets
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
    conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    for table, col in (("profiles", "owner"), ("usage_log", "owner"), ("usage_log", "answer"), ("usage_log", "admin_remarks")):
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
    return conn


def _scope(owner: str | None) -> tuple[str, tuple]:
    """SQL filter for one tester's rows. owner=None is local single-user mode: no filter."""
    return ("", ()) if owner is None else (" AND owner = ?", (owner,))


def get_setting(key: str) -> str | None:
    with _lock, _connect() as conn:
        r = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return r["value"] if r else None


def set_setting(key: str, value: str) -> None:
    with _lock, _connect() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))


def secret() -> str:
    """Per-database signing key for session cookies, created on first use."""
    with _lock, _connect() as conn:
        r = conn.execute("SELECT value FROM settings WHERE key = 'session_secret'").fetchone()
        if r:
            return r["value"]
        value = secrets.token_hex(32)
        conn.execute("INSERT INTO settings (key, value) VALUES ('session_secret', ?)", (value,))
        return value


def _row(r: sqlite3.Row, with_chart: bool) -> dict:
    out = {"id": r["id"], "name": r["name"], "created_at": r["created_at"],
           "request": json.loads(r["request"]), "owner": r["owner"]}
    if with_chart:
        out["chart"] = json.loads(r["chart"])
    return out


def save(name: str, request: dict, chart: dict, owner: str | None = None) -> dict:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO profiles (name, request, chart, created_at, owner) VALUES (?, ?, ?, ?, ?)",
            (name, json.dumps(request), json.dumps(chart), now, owner),
        )
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row(row, True)


def list_all(owner: str | None = None) -> list[dict]:
    where, args = _scope(owner)
    with _lock, _connect() as conn:
        rows = conn.execute(f"SELECT * FROM profiles WHERE 1=1{where} ORDER BY id DESC", args).fetchall()
    return [_row(r, False) for r in rows]


def get(profile_id: int, owner: str | None = None) -> dict | None:
    where, args = _scope(owner)
    with _lock, _connect() as conn:
        r = conn.execute(f"SELECT * FROM profiles WHERE id = ?{where}", (profile_id, *args)).fetchone()
    return _row(r, True) if r else None


def delete(profile_id: int, owner: str | None = None) -> bool:
    where, args = _scope(owner)
    with _lock, _connect() as conn:
        if not conn.execute(f"SELECT 1 FROM profiles WHERE id = ?{where}", (profile_id, *args)).fetchone():
            return False
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
              words: int = 0, owner: str | None = None, answer: str | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO usage_log (ts, profile_id, kind, model, input_tokens, output_tokens, cache_read_tokens,"
            " cache_write_tokens, tool_rounds, words, question, owner, answer) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (now, profile_id, kind, model, input_tokens, output_tokens, cache_read, cache_write, tool_rounds,
             words, question[:2000], owner, answer[:6000] if answer else None))


def llm_requests_today(owner: str | None = None) -> int:
    """Paid (LLM) chat turns today, for one tester or (owner=None) everyone."""
    where, args = _scope(owner)
    today = datetime.now(timezone.utc).date().isoformat()
    with _lock, _connect() as conn:
        return conn.execute(f"SELECT COUNT(*) FROM usage_log WHERE kind = 'llm' AND substr(ts, 1, 10) = ?{where}",
                            (today, *args)).fetchone()[0]


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


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def recent_queries(limit: int = 50, before_id: int | None = None) -> list[dict]:
    """Newest-first chat log with the chart name and admin remarks, for the admin page."""
    where, args = ("WHERE u.id < ?", (before_id,)) if before_id else ("", ())
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT u.id, u.ts, u.kind, u.model, u.input_tokens, u.output_tokens, u.cache_read_tokens,"
            " u.cache_write_tokens, u.tool_rounds, u.words, u.question, u.answer, u.admin_remarks, u.owner, u.profile_id,"
            f" p.name AS profile_name FROM usage_log u LEFT JOIN profiles p ON p.id = u.profile_id {where}"
            " ORDER BY u.id DESC LIMIT ?", (*args, limit)).fetchall()
    return [dict(r) for r in rows]


def token_totals(today_only: bool) -> list[dict]:
    """Paid-token sums per model, for cost estimates."""
    where, args = ("AND substr(ts, 1, 10) = ?", (_today(),)) if today_only else ("", ())
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT model, COUNT(*) n, COALESCE(SUM(input_tokens),0) inp, COALESCE(SUM(output_tokens),0) out,"
            " COALESCE(SUM(cache_read_tokens),0) cr, COALESCE(SUM(cache_write_tokens),0) cw"
            f" FROM usage_log WHERE kind = 'llm' {where} GROUP BY model", args).fetchall()
    return [dict(r) for r in rows]


def tester_summary() -> list[dict]:
    """One row per tester (owner): their charts and question counts."""
    with _lock, _connect() as conn:
        prof = conn.execute(
            "SELECT owner, COUNT(*) charts, GROUP_CONCAT(name, ', ') names, MIN(created_at) first_seen"
            " FROM profiles GROUP BY owner").fetchall()
        q = conn.execute(
            "SELECT owner, COUNT(*) total, SUM(substr(ts, 1, 10) = ?) today, SUM(kind = 'llm') paid,"
            " MAX(ts) last_seen FROM usage_log GROUP BY owner", (_today(),)).fetchall()
    rows = {r["owner"]: {"owner": r["owner"], "charts": r["charts"], "chart_names": r["names"],
                         "first_seen": r["first_seen"], "questions": 0, "questions_today": 0,
                         "paid_questions": 0, "last_seen": None} for r in prof}
    for r in q:
        row = rows.setdefault(r["owner"], {"owner": r["owner"], "charts": 0, "chart_names": "",
                                           "first_seen": None})
        row.update(questions=r["total"], questions_today=r["today"] or 0, paid_questions=r["paid"] or 0,
                   last_seen=r["last_seen"])
    return sorted(rows.values(), key=lambda r: r.get("last_seen") or r.get("first_seen") or "", reverse=True)


def update_remarks(query_id: int, remarks: str | None) -> bool:
    """Update admin remarks for a question (admin only, not visible to tester)."""
    with _lock, _connect() as conn:
        return conn.execute("UPDATE usage_log SET admin_remarks = ? WHERE id = ?",
                          (remarks, query_id)).rowcount > 0


def tester_remarks(owner: str | None) -> str | None:
    """Get most recent admin remarks about this tester (for subtle personalization)."""
    if not owner:
        return None
    with _lock, _connect() as conn:
        r = conn.execute("SELECT admin_remarks FROM usage_log WHERE owner = ? AND admin_remarks IS NOT NULL"
                        " ORDER BY id DESC LIMIT 1", (owner,)).fetchone()
    return r["admin_remarks"] if r else None
