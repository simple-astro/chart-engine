"""SQLite persistence for saved birth profiles (and their cached charts)."""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
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
    conn.execute(
        "CREATE TABLE IF NOT EXISTS access_codes ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE, label TEXT NOT NULL DEFAULT '',"
        " active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, uses INTEGER NOT NULL DEFAULT 0,"
        " last_used TEXT)"
    )
    conn.execute("CREATE TABLE IF NOT EXISTS owner_codes (owner TEXT PRIMARY KEY, code_id INTEGER NOT NULL)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS tg_users ("
        " chat_id INTEGER PRIMARY KEY, owner TEXT, profile_id INTEGER, first_name TEXT,"
        " step TEXT NOT NULL DEFAULT 'date', draft TEXT NOT NULL DEFAULT '{}',"
        " send_time TEXT NOT NULL DEFAULT '08:00', active INTEGER NOT NULL DEFAULT 1, last_sent TEXT,"
        " live_lat REAL, live_lon REAL, live_tz TEXT, live_place TEXT, created_at TEXT NOT NULL)"
    )
    # "How did it go?" (app/checkins.py): a question that named a day ahead, asked about once afterwards.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS checkins (id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER NOT NULL,"
        " usage_id INTEGER, question TEXT NOT NULL, said TEXT, event_date TEXT NOT NULL, due_date TEXT NOT NULL,"
        " topic TEXT, answer TEXT, answered_at TEXT, created_at TEXT NOT NULL)")
    # Married life (app/marriage.py): one row per person and couple (groom and bride are saved charts).
    conn.execute(
        "CREATE TABLE IF NOT EXISTS couples (id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT, groom_id INTEGER NOT NULL,"
        " bride_id INTEGER NOT NULL, married INTEGER NOT NULL DEFAULT 0, ratings TEXT NOT NULL DEFAULT '{}', trend TEXT,"
        " plan_start TEXT, ticks TEXT NOT NULL DEFAULT '[]', updated_at TEXT NOT NULL,"
        " UNIQUE (owner, groom_id, bride_id))")
    ucols = {r["name"] for r in conn.execute("PRAGMA table_info(usage_log)")}
    if "rating" not in ucols:  # 👍 (1) / 👎 (-1) from the person who asked, with an optional reason
        conn.execute("ALTER TABLE usage_log ADD COLUMN rating INTEGER")
        conn.execute("ALTER TABLE usage_log ADD COLUMN rating_reason TEXT")
    if "reminders" not in {r["name"] for r in conn.execute("PRAGMA table_info(tg_users)")}:
        # Coming-up reminders on Telegram: all (transits and Dasha changes), dasha (Dasha changes only) or off.
        conn.execute("ALTER TABLE tg_users ADD COLUMN reminders TEXT NOT NULL DEFAULT 'all'")
    # One row per reminder sent, so each goes out once (key: event date, lead time and title).
    conn.execute("CREATE TABLE IF NOT EXISTS tg_reminders (chat_id INTEGER NOT NULL, key TEXT NOT NULL,"
                 " sent_at TEXT NOT NULL, PRIMARY KEY (chat_id, key))")
    for table, col in (("profiles", "owner"), ("usage_log", "owner"), ("usage_log", "answer"), ("usage_log", "admin_remarks"), ("usage_log", "factcheck")):
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
    # The remedy library: reviewable JSON documents (app/remedies). Curated content lives here, not in the repo.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS remedy_items ("
        " kind TEXT NOT NULL, slug TEXT NOT NULL, data TEXT NOT NULL,"
        " review_status TEXT NOT NULL DEFAULT 'pending_astrologer', version INTEGER NOT NULL DEFAULT 1,"
        " updated_at TEXT NOT NULL, PRIMARY KEY (kind, slug))"
    )
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(remedy_items)")}
    if "proposed" not in cols:
        # An astrologer's suggested change to an approved item (JSON), kept apart so the approved version stays
        # live until the Studio admin or the owner accepts it.
        for col in ("proposed TEXT", "proposed_by TEXT", "proposed_code INTEGER", "proposed_at TEXT"):
            conn.execute(f"ALTER TABLE remedy_items ADD COLUMN {col}")
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(access_codes)")}
    if "daily_limit" not in cols:
        # Questions per day for each tester on this code; NULL = the default from Settings.
        conn.execute("ALTER TABLE access_codes ADD COLUMN daily_limit INTEGER")
    if "role" not in cols:
        # tester (the app) | astrologer / mentor (the Studio section of Admin). A Studio code's daily_limit is its
        # daily experiment budget. created_by: the code id of the mentor who made it (NULL = the owner).
        conn.execute("ALTER TABLE access_codes ADD COLUMN role TEXT NOT NULL DEFAULT 'tester'")
        conn.execute("ALTER TABLE access_codes ADD COLUMN created_by INTEGER")
    # Studio teaching (STUDIO_PLAN.md, app/teach.py): ideal answers ("gold") and short lessons. status follows the
    # live teaching version: draft (never published) | published (in it) | retired (published once, not now).
    conn.execute("CREATE TABLE IF NOT EXISTS studio_drafts (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,"
                 " topic TEXT NOT NULL, text TEXT NOT NULL, question TEXT, answer TEXT, profile_id INTEGER,"
                 " status TEXT NOT NULL DEFAULT 'draft', author TEXT NOT NULL, created_at TEXT NOT NULL)")
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(studio_drafts)")}
    if "author_code" not in cols:  # the author's code id (NULL = the owner), so astrologers edit only their own
        conn.execute("ALTER TABLE studio_drafts ADD COLUMN author_code INTEGER")
        conn.execute("ALTER TABLE studio_drafts ADD COLUMN updated_at TEXT")
    # Studio reviews (STUDIO_PLAN.md step 4): one review per answer — five checks, problem tags and a note.
    conn.execute("CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, usage_id INTEGER NOT NULL"
                 " UNIQUE, reviewer TEXT NOT NULL, reviewer_code INTEGER, checks TEXT NOT NULL, tags TEXT NOT NULL,"
                 " note TEXT, created_at TEXT NOT NULL)")
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(studio_drafts)")}
    if "in_test_set" not in cols:  # a published gold answer the Quality runs score answers against
        conn.execute("ALTER TABLE studio_drafts ADD COLUMN in_test_set INTEGER NOT NULL DEFAULT 0")
    # Quality runs (app/quality.py): each test-set question answered (live, or live and with drafts), judged
    # against its gold answer. kind: run (live) | compare (live vs drafts) | gate (before publishing a draft).
    conn.execute("CREATE TABLE IF NOT EXISTS eval_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,"
                 " status TEXT NOT NULL, topics TEXT, drafts TEXT, teach_version INTEGER, model TEXT, judge_model TEXT,"
                 " total INTEGER NOT NULL DEFAULT 0, done INTEGER NOT NULL DEFAULT 0, cost REAL NOT NULL DEFAULT 0,"
                 " scores TEXT, error TEXT, actor TEXT NOT NULL, created_at TEXT NOT NULL, finished_at TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS eval_items (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL,"
                 " gold_id INTEGER NOT NULL, variant TEXT NOT NULL, topic TEXT NOT NULL, question TEXT NOT NULL,"
                 " answer TEXT, factcheck TEXT, judge TEXT, score REAL, cost REAL, error TEXT, human TEXT, human_by TEXT,"
                 " created_at TEXT NOT NULL)")
    # Every publish, retire or rollback makes a new teaching version: the full set of published item ids.
    # The live version is the newest row; rolling back = a new version with an older set.
    conn.execute("CREATE TABLE IF NOT EXISTS teach_versions (id INTEGER PRIMARY KEY AUTOINCREMENT, items TEXT NOT NULL,"
                 " action TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL)")
    # Who did what in Admin and the Studio (codes, publishes, rollbacks), for the owner and the mentor.
    conn.execute("CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL,"
                 " actor TEXT NOT NULL, actor_role TEXT NOT NULL, action TEXT NOT NULL, object TEXT, detail TEXT)")
    # State of mind: private mood logs, each with that moment's astrology (app/mood.py), for finding patterns.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS mood_logs ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER NOT NULL, ts TEXT NOT NULL, local_date TEXT NOT NULL,"
        " valence INTEGER NOT NULL, feelings TEXT NOT NULL, causes TEXT NOT NULL, note TEXT, scope TEXT NOT NULL,"
        " snapshot TEXT NOT NULL)"
    )
    # Jamakkol questions asked from a chart (core/jamakkol.py): ask each once (81 days), then "did it happen?".
    conn.execute("CREATE TABLE IF NOT EXISTS jamakkol_asks (id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER"
                 " NOT NULL, kind TEXT NOT NULL, question TEXT, asked_at TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT"
                 " NULL, tz_name TEXT NOT NULL, verdict TEXT NOT NULL, label TEXT NOT NULL, outcome TEXT, outcome_at TEXT)")
    if "place" not in {r["name"] for r in conn.execute("PRAGMA table_info(jamakkol_asks)")}:
        conn.execute("ALTER TABLE jamakkol_asks ADD COLUMN place TEXT")  # the place name the asker picked
    # Life events the person entered (app/life_events.py): checked against their chart, and the real-life backtest.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS life_events ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER NOT NULL, kind TEXT NOT NULL, date TEXT NOT NULL,"
        " precision TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    # Ticked "get ready" steps for upcoming changes (app/upcoming.py): one row per ticked step.
    conn.execute("CREATE TABLE IF NOT EXISTS prep_done (profile_id INTEGER NOT NULL, step TEXT NOT NULL,"
                 " done_at TEXT NOT NULL, PRIMARY KEY (profile_id, step))")
    # Which sections testers open (app/usage.py): a short name per event, no chart data. Kept for 90 days.
    conn.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL,"
                 " owner TEXT, name TEXT NOT NULL, detail TEXT)")
    conn.execute("CREATE INDEX IF NOT EXISTS events_ts ON events (ts)")
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


def update(profile_id: int, name: str, request: dict, chart: dict, owner: str | None = None) -> dict | None:
    """Replace a profile's birth details and chart; cached answers no longer apply."""
    where, args = _scope(owner)
    with _lock, _connect() as conn:
        cur = conn.execute(f"UPDATE profiles SET name = ?, request = ?, chart = ? WHERE id = ?{where}",
                           (name, json.dumps(request), json.dumps(chart), profile_id, *args))
        if not cur.rowcount:
            return None
        conn.execute("DELETE FROM answer_cache WHERE profile_id = ?", (profile_id,))
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
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
        conn.execute("DELETE FROM mood_logs WHERE profile_id = ?", (profile_id,))
        conn.execute("DELETE FROM life_events WHERE profile_id = ?", (profile_id,))
        conn.execute("DELETE FROM jamakkol_asks WHERE profile_id = ?", (profile_id,))
        conn.execute("DELETE FROM prep_done WHERE profile_id = ?", (profile_id,))
        conn.execute("DELETE FROM settings WHERE key = ?", (f"mood_share:{profile_id}",))
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
              words: int = 0, owner: str | None = None, answer: str | None = None, factcheck: dict | None = None) -> int:
    """Log one answer; returns its id (the 👍/👎 buttons refer to it)."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO usage_log (ts, profile_id, kind, model, input_tokens, output_tokens, cache_read_tokens,"
            " cache_write_tokens, tool_rounds, words, question, owner, answer, factcheck)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (now, profile_id, kind, model, input_tokens, output_tokens, cache_read, cache_write, tool_rounds,
             words, question[:2000], owner, answer[:6000] if answer else None,
             json.dumps(factcheck) if factcheck else None))
        return cur.lastrowid


def rate_answer(profile_id: int, usage_id: int, rating: int, reason: str | None = None) -> bool:
    """Record the asker's 👍/👎 on one of the answers to this chart; False if the answer isn't theirs."""
    with _lock, _connect() as conn:
        cur = conn.execute("UPDATE usage_log SET rating = ?, rating_reason = ? WHERE id = ? AND profile_id = ?"
                           " AND answer IS NOT NULL", (rating, reason, usage_id, profile_id))
        return cur.rowcount == 1


def checkin_add(profile_id: int, usage_id: int | None, question: str, said: str, event_date: str, due_date: str,
                topic: str | None) -> dict | None:
    """One check-in per chart per event day (asking twice about the same day makes one)."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _lock, _connect() as conn:
        if conn.execute("SELECT 1 FROM checkins WHERE profile_id = ? AND event_date = ?", (profile_id, event_date)).fetchone():
            return None
        cur = conn.execute("INSERT INTO checkins (profile_id, usage_id, question, said, event_date, due_date, topic,"
                           " created_at) VALUES (?,?,?,?,?,?,?,?)",
                           (profile_id, usage_id, question, said, event_date, due_date, topic, now))
        return dict(conn.execute("SELECT * FROM checkins WHERE id = ?", (cur.lastrowid,)).fetchone())


def checkin_get(profile_id: int, checkin_id: int) -> dict | None:
    with _lock, _connect() as conn:
        r = conn.execute("SELECT * FROM checkins WHERE id = ? AND profile_id = ?", (checkin_id, profile_id)).fetchone()
    return dict(r) if r else None


def checkin_due(profile_id: int, today: str) -> dict | None:
    with _lock, _connect() as conn:
        r = conn.execute("SELECT * FROM checkins WHERE profile_id = ? AND answer IS NULL AND due_date <= ?"
                         " ORDER BY due_date, id LIMIT 1", (profile_id, today)).fetchone()
    return dict(r) if r else None


def checkin_answer(profile_id: int, checkin_id: int, answer: str) -> bool:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _lock, _connect() as conn:
        return conn.execute("UPDATE checkins SET answer = ?, answered_at = ? WHERE id = ? AND profile_id = ?",
                            (answer, now, checkin_id, profile_id)).rowcount == 1


def checkin_snooze(profile_id: int, checkin_id: int, due_date: str) -> bool:
    with _lock, _connect() as conn:
        return conn.execute("UPDATE checkins SET due_date = ? WHERE id = ? AND profile_id = ? AND answer IS NULL",
                            (due_date, checkin_id, profile_id)).rowcount == 1


def checkin_counts(since: str) -> dict:
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT answer, COUNT(*) AS n FROM checkins WHERE created_at >= ? GROUP BY answer",
                            (since,)).fetchall()
    out = {(r["answer"] or "waiting"): r["n"] for r in rows}
    return {"asked": sum(out.values()), **out}


def _couple(r) -> dict:
    d = dict(r)
    d["ratings"], d["ticks"] = json.loads(d["ratings"] or "{}"), json.loads(d["ticks"] or "[]")
    return d


def couple_get(owner: str | None, groom_id: int, bride_id: int) -> dict | None:
    with _lock, _connect() as conn:
        r = conn.execute("SELECT * FROM couples WHERE owner IS ? AND groom_id = ? AND bride_id = ?",
                         (owner, groom_id, bride_id)).fetchone()
    return _couple(r) if r else None


def couple_save(owner: str | None, groom_id: int, bride_id: int, **fields) -> dict:
    allowed = {"married", "ratings", "trend", "plan_start", "ticks"}
    bad = set(fields) - allowed
    if bad:
        raise ValueError(f"unknown couple fields: {bad}")
    for k in ("ratings", "ticks"):
        if k in fields:
            fields[k] = json.dumps(fields[k])
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _lock, _connect() as conn:
        conn.execute("INSERT OR IGNORE INTO couples (owner, groom_id, bride_id, updated_at) VALUES (?,?,?,?)",
                     (owner, groom_id, bride_id, now))
        if fields:
            cols = ", ".join(f"{k} = ?" for k in fields)
            conn.execute(f"UPDATE couples SET {cols}, updated_at = ? WHERE owner IS ? AND groom_id = ? AND bride_id = ?",
                         (*fields.values(), now, owner, groom_id, bride_id))
    return couple_get(owner, groom_id, bride_id)


def couples_for(owner: str | None, profile_id: int) -> list[dict]:
    """Married couples this chart belongs to (for the talk and patience days on Today)."""
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT * FROM couples WHERE owner IS ? AND married = 1 AND (groom_id = ? OR bride_id = ?)",
                            (owner, profile_id, profile_id)).fetchall()
    return [_couple(r) for r in rows]


def rating_counts(since: str) -> dict:
    with _lock, _connect() as conn:
        r = conn.execute("SELECT SUM(rating = 1) AS up, SUM(rating = -1) AS down FROM usage_log WHERE ts >= ?",
                         (since,)).fetchone()
    return {"up": r["up"] or 0, "down": r["down"] or 0}


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
    # Studio Playground runs are experiments, not testers' questions: they stay out of this log.
    where, args = ("WHERE u.kind != 'playground' AND u.id < ?", (before_id,)) if before_id else \
        ("WHERE u.kind != 'playground'", ())
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT u.id, u.ts, u.kind, u.model, u.input_tokens, u.output_tokens, u.cache_read_tokens,"
            " u.cache_write_tokens, u.tool_rounds, u.words, u.question, u.answer, u.admin_remarks, u.factcheck, u.owner, u.profile_id,"
            f" p.name AS profile_name FROM usage_log u LEFT JOIN profiles p ON p.id = u.profile_id {where}"
            " ORDER BY u.id DESC LIMIT ?", (*args, limit)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["factcheck"] = json.loads(d["factcheck"]) if d.get("factcheck") else None
        out.append(d)
    return out


def token_totals(today_only: bool, kinds: tuple[str, ...] = ("llm",)) -> list[dict]:
    """Paid-token sums per model, for cost estimates (testers' answers; or other kinds, e.g. Studio experiments)."""
    where, args = ("AND substr(ts, 1, 10) = ?", (_today(),)) if today_only else ("", ())
    where = f"AND kind IN ({','.join('?' * len(kinds))}) " + where
    args = (*kinds, *args)
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT model, COUNT(*) n, COALESCE(SUM(input_tokens),0) inp, COALESCE(SUM(output_tokens),0) out,"
            " COALESCE(SUM(cache_read_tokens),0) cr, COALESCE(SUM(cache_write_tokens),0) cw"
            f" FROM usage_log WHERE 1=1 {where} GROUP BY model", args).fetchall()
    return [dict(r) for r in rows]


def tester_summary() -> list[dict]:
    """One row per tester (owner): their charts and question counts."""
    with _lock, _connect() as conn:
        prof = conn.execute(
            "SELECT owner, COUNT(*) charts, GROUP_CONCAT(name, ', ') names, MIN(created_at) first_seen"
            " FROM profiles GROUP BY owner").fetchall()
        q = conn.execute(
            "SELECT owner, COUNT(*) total, SUM(substr(ts, 1, 10) = ?) today, SUM(kind = 'llm') paid,"
            " MAX(ts) last_seen FROM usage_log WHERE kind != 'playground' GROUP BY owner", (_today(),)).fetchall()
    rows = {r["owner"]: {"owner": r["owner"], "charts": r["charts"], "chart_names": r["names"],
                         "first_seen": r["first_seen"], "questions": 0, "questions_today": 0,
                         "paid_questions": 0, "last_seen": None} for r in prof}
    for r in q:
        row = rows.setdefault(r["owner"], {"owner": r["owner"], "charts": 0, "chart_names": "",
                                           "first_seen": None})
        row.update(questions=r["total"], questions_today=r["today"] or 0, paid_questions=r["paid"] or 0,
                   last_seen=r["last_seen"])
    return sorted(rows.values(), key=lambda r: r.get("last_seen") or r.get("first_seen") or "", reverse=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def list_codes() -> list[dict]:
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM owner_codes o WHERE o.code_id = c.id) testers,"
            " (SELECT COUNT(*) FROM usage_log u JOIN owner_codes o ON o.owner = u.owner"
            "  WHERE o.code_id = c.id AND u.kind = 'llm' AND substr(u.ts, 1, 10) = ?) asked_today"
            " FROM access_codes c WHERE c.role = 'tester' ORDER BY c.id DESC",  # Studio codes: storage.studio_codes
            (datetime.now(timezone.utc).date().isoformat(),)).fetchall()
    return [dict(r) | {"active": bool(r["active"])} for r in rows]


def add_code(code: str, label: str, role: str = "tester", created_by: int | None = None,
             daily_limit: int | None = None) -> dict:
    """Raises sqlite3.IntegrityError when the code already exists."""
    with _lock, _connect() as conn:
        cur = conn.execute("INSERT INTO access_codes (code, label, created_at, role, created_by, daily_limit)"
                           " VALUES (?, ?, ?, ?, ?, ?)", (code, label, _now(), role, created_by, daily_limit))
        r = conn.execute("SELECT * FROM access_codes WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(r) | {"active": bool(r["active"]), "testers": 0, "asked_today": 0}


_UNSET = object()


def update_code(code_id: int, *, active: bool | None = None, label: str | None = None, daily_limit=_UNSET) -> bool:
    """daily_limit: an int, or None to fall back to the default; leave it out to keep it unchanged."""
    sets, args = [], []
    if daily_limit is not _UNSET:
        sets.append("daily_limit = ?"); args.append(daily_limit)
    if active is not None:
        sets.append("active = ?"); args.append(int(active))
    if label is not None:
        sets.append("label = ?"); args.append(label)
    if not sets:
        return False
    with _lock, _connect() as conn:
        return conn.execute(f"UPDATE access_codes SET {', '.join(sets)} WHERE id = ?", (*args, code_id)).rowcount > 0


def delete_code(code_id: int) -> bool:
    with _lock, _connect() as conn:
        return conn.execute("DELETE FROM access_codes WHERE id = ?", (code_id,)).rowcount > 0


def active_codes() -> list[tuple[int, str, str]]:
    with _lock, _connect() as conn:
        return [(r["id"], r["code"], r["role"]) for r in
                conn.execute("SELECT id, code, role FROM access_codes WHERE active = 1")]


def code_role(code_id: int) -> str | None:
    """The role of an active code, or None when it is paused or deleted (checked on every request)."""
    with _lock, _connect() as conn:
        r = conn.execute("SELECT role FROM access_codes WHERE id = ? AND active = 1", (code_id,)).fetchone()
    return r["role"] if r else None


def get_code(code_id: int) -> dict | None:
    with _lock, _connect() as conn:
        r = conn.execute("SELECT * FROM access_codes WHERE id = ?", (code_id,)).fetchone()
    return dict(r) | {"active": bool(r["active"])} if r else None


def studio_codes() -> list[dict]:
    """Mentor and astrologer codes, newest first, with who made them and today's paid answers."""
    today = datetime.now(timezone.utc).date().isoformat()
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT c.*, m.label AS created_by_label,"
            " (SELECT COUNT(*) FROM usage_log u JOIN owner_codes o ON o.owner = u.owner"
            "  WHERE o.code_id = c.id AND u.kind = 'llm' AND substr(u.ts, 1, 10) = ?) used_today"
            " FROM access_codes c LEFT JOIN access_codes m ON m.id = c.created_by"
            " WHERE c.role IN ('mentor', 'astrologer') ORDER BY c.id DESC", (today,)).fetchall()
    return [dict(r) | {"active": bool(r["active"])} for r in rows]


def log_audit(actor: str, actor_role: str, action: str, obj: str | None = None, detail: str | None = None) -> None:
    with _lock, _connect() as conn:
        conn.execute("INSERT INTO audit_log (ts, actor, actor_role, action, object, detail) VALUES (?, ?, ?, ?, ?, ?)",
                     (_now(), actor, actor_role, action, obj, detail))


def audit(limit: int = 100) -> list[dict]:
    with _lock, _connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))]


def code_is_active(code_id: int) -> bool:
    with _lock, _connect() as conn:
        return conn.execute("SELECT 1 FROM access_codes WHERE id = ? AND active = 1", (code_id,)).fetchone() is not None


def note_code_login(code_id: int, owner: str) -> None:
    with _lock, _connect() as conn:
        conn.execute("UPDATE access_codes SET uses = uses + 1, last_used = ? WHERE id = ?", (_now(), code_id))
        conn.execute("INSERT OR REPLACE INTO owner_codes (owner, code_id) VALUES (?, ?)", (owner, code_id))


def owner_daily_limit(owner: str | None) -> int | None:
    """The questions-per-day limit set on the code this tester signed in with, or None for the default."""
    if owner is None:
        return None
    with _lock, _connect() as conn:
        r = conn.execute("SELECT c.daily_limit FROM owner_codes o JOIN access_codes c ON c.id = o.code_id"
                         " WHERE o.owner = ?", (owner,)).fetchone()
    return r["daily_limit"] if r else None


def owner_code_labels() -> dict[str, str]:
    """owner -> label of the database code they last signed in with."""
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT o.owner, c.label, c.code FROM owner_codes o"
                            " JOIN access_codes c ON c.id = o.code_id").fetchall()
    return {r["owner"]: r["label"] or r["code"] for r in rows}


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


# ----- Telegram users: onboarding state, morning-guide schedule -----
TG_FIELDS = {"owner", "profile_id", "first_name", "step", "draft", "send_time", "active", "last_sent",
             "live_lat", "live_lon", "live_tz", "live_place", "reminders"}


def tg_get(chat_id: int) -> dict | None:
    with _lock, _connect() as conn:
        r = conn.execute("SELECT * FROM tg_users WHERE chat_id = ?", (chat_id,)).fetchone()
    if not r:
        return None
    u = dict(r)
    u["draft"] = json.loads(u["draft"] or "{}")
    return u


def tg_save(chat_id: int, **fields) -> dict:
    bad = set(fields) - TG_FIELDS
    if bad:
        raise ValueError(f"unknown tg_users fields: {bad}")
    if "draft" in fields:
        fields["draft"] = json.dumps(fields["draft"])
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _lock, _connect() as conn:
        conn.execute("INSERT OR IGNORE INTO tg_users (chat_id, created_at) VALUES (?, ?)", (chat_id, now))
        if fields:
            cols = ", ".join(f"{k} = ?" for k in fields)
            conn.execute(f"UPDATE tg_users SET {cols} WHERE chat_id = ?", (*fields.values(), chat_id))
    return tg_get(chat_id)


def tg_ready() -> list[dict]:
    """Onboarded, active users who may be due a morning guide."""
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT * FROM tg_users WHERE step = 'done' AND active = 1 AND profile_id IS NOT NULL").fetchall()
    return [dict(r) for r in rows]


def tg_claim_send(chat_id: int, day: str) -> bool:
    """Atomically mark today's guide as sent; False if it already was (so it goes out once)."""
    with _lock, _connect() as conn:
        cur = conn.execute("UPDATE tg_users SET last_sent = ? WHERE chat_id = ? AND (last_sent IS NULL OR last_sent <> ?)",
                           (day, chat_id, day))
        return cur.rowcount == 1


def tg_reminder_users() -> list[dict]:
    """Onboarded users with reminders switched on (independent of pausing the morning guide)."""
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT * FROM tg_users WHERE step = 'done' AND profile_id IS NOT NULL"
                            " AND reminders <> 'off'").fetchall()
    return [dict(r) for r in rows]


def tg_claim_reminder(chat_id: int, key: str) -> bool:
    """Atomically record a reminder as sent; False if it already was."""
    with _lock, _connect() as conn:
        cur = conn.execute("INSERT OR IGNORE INTO tg_reminders (chat_id, key, sent_at) VALUES (?, ?, ?)",
                           (chat_id, key, datetime.now(timezone.utc).isoformat(timespec="seconds")))
        return cur.rowcount == 1


def tg_for_profile(profile_id: int) -> dict | None:
    """The Telegram link for a chart, if any (for the Coming up card)."""
    with _lock, _connect() as conn:
        r = conn.execute("SELECT reminders FROM tg_users WHERE profile_id = ? AND step = 'done' LIMIT 1",
                         (profile_id,)).fetchone()
    return dict(r) if r else None


# ----- state of mind (mood logs); callers check the profile belongs to the person first -----
def _mood(r: sqlite3.Row) -> dict:
    d = dict(r)
    for k in ("feelings", "causes", "snapshot"):
        d[k] = json.loads(d[k])
    return d


def mood_add(profile_id: int, local_date: str, valence: int, feelings: list[str], causes: list[str],
             note: str | None, scope: str, snapshot: dict) -> dict:
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO mood_logs (profile_id, ts, local_date, valence, feelings, causes, note, scope, snapshot)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (profile_id, _now(), local_date, valence, json.dumps(feelings), json.dumps(causes), note, scope,
             json.dumps(snapshot)))
        r = conn.execute("SELECT * FROM mood_logs WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _mood(r)


def mood_list(profile_id: int, limit: int | None = None) -> list[dict]:
    """Newest first."""
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT * FROM mood_logs WHERE profile_id = ? ORDER BY id DESC" + (" LIMIT ?" if limit else ""),
                            (profile_id, limit) if limit else (profile_id,)).fetchall()
    return [_mood(r) for r in rows]


def mood_count_on(profile_id: int, local_date: str) -> int:
    with _lock, _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM mood_logs WHERE profile_id = ? AND local_date = ?",
                            (profile_id, local_date)).fetchone()[0]


def mood_delete(profile_id: int, log_id: int | None = None) -> int:
    """Delete one log, or all of this profile's logs when log_id is None. Returns how many went."""
    with _lock, _connect() as conn:
        if log_id is None:
            return conn.execute("DELETE FROM mood_logs WHERE profile_id = ?", (profile_id,)).rowcount
        return conn.execute("DELETE FROM mood_logs WHERE profile_id = ? AND id = ?", (profile_id, log_id)).rowcount


def mood_shared(profile_id: int) -> bool:
    """Whether the person agreed to let Astropositivism see their mood log in chat."""
    return get_setting(f"mood_share:{profile_id}") == "1"


def set_mood_shared(profile_id: int, share: bool) -> None:
    with _lock, _connect() as conn:
        if share:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, '1')", (f"mood_share:{profile_id}",))
        else:
            conn.execute("DELETE FROM settings WHERE key = ?", (f"mood_share:{profile_id}",))


# ----- life events; callers check the profile belongs to the person first -----
def event_add(profile_id: int, kind: str, date: str, precision: str) -> dict:
    with _lock, _connect() as conn:
        cur = conn.execute("INSERT INTO life_events (profile_id, kind, date, precision, created_at) VALUES (?, ?, ?, ?, ?)",
                           (profile_id, kind, date, precision, _now()))
        return dict(conn.execute("SELECT * FROM life_events WHERE id = ?", (cur.lastrowid,)).fetchone())


def event_list(profile_id: int) -> list[dict]:
    """Oldest first, as a life story reads."""
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT * FROM life_events WHERE profile_id = ? ORDER BY date, id", (profile_id,)).fetchall()
    return [dict(r) for r in rows]


def event_delete(profile_id: int, event_id: int) -> bool:
    with _lock, _connect() as conn:
        return conn.execute("DELETE FROM life_events WHERE profile_id = ? AND id = ?", (profile_id, event_id)).rowcount > 0


def all_events() -> list[dict]:
    """Every person's events with their chart (admin's real-life backtest; no names leave this module)."""
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT e.*, p.chart, p.request FROM life_events e JOIN profiles p ON p.id = e.profile_id").fetchall()
    return [{**dict(r), "chart": json.loads(r["chart"]), "request": json.loads(r["request"])} for r in rows]


# ----- ticked preparation steps; callers check the profile belongs to the person first -----
def prep_done(profile_id: int) -> set[str]:
    with _lock, _connect() as conn:
        return {r[0] for r in conn.execute("SELECT step FROM prep_done WHERE profile_id = ?", (profile_id,))}


def prep_tick(profile_id: int, step: str, done: bool) -> None:
    with _lock, _connect() as conn:
        if done:
            conn.execute("INSERT OR IGNORE INTO prep_done (profile_id, step, done_at) VALUES (?, ?, ?)", (profile_id, step, _now()))
        else:
            conn.execute("DELETE FROM prep_done WHERE profile_id = ? AND step = ?", (profile_id, step))


# ----- usage: section events and the activity already stored (app/usage.py) -----
EVENT_DAYS = 90


def log_events(owner: str | None, rows: list[tuple[str, str | None]]) -> None:
    now = _now()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=EVENT_DAYS)).isoformat(timespec="seconds")
    with _lock, _connect() as conn:
        conn.executemany("INSERT INTO events (ts, owner, name, detail) VALUES (?, ?, ?, ?)",
                         [(now, owner, n, d) for n, d in rows])
        conn.execute("DELETE FROM events WHERE ts < ?", (cutoff,))


def usage_sources(since: str) -> dict:
    """Everything the usage report counts, from `since` (ISO time): section events, questions, mood logs,
    life events, Get-ready ticks and new charts, each with its owner."""
    with _lock, _connect() as conn:
        q = lambda sql: [dict(r) for r in conn.execute(sql, (since,)).fetchall()]
        first = conn.execute("SELECT MIN(ts) FROM events").fetchone()[0]
        return {
            "events": q("SELECT ts, owner, name, detail FROM events WHERE ts >= ?"),
            "questions": q("SELECT ts, owner, question FROM usage_log WHERE ts >= ? AND kind NOT IN ('compare', 'playground')"),
            "mood": q("SELECT m.ts AS ts, p.owner AS owner FROM mood_logs m JOIN profiles p ON p.id = m.profile_id WHERE m.ts >= ?"),
            "lifeevents": q("SELECT e.created_at AS ts, p.owner AS owner FROM life_events e JOIN profiles p ON p.id = e.profile_id WHERE e.created_at >= ?"),
            "getready": q("SELECT d.done_at AS ts, p.owner AS owner FROM prep_done d JOIN profiles p ON p.id = d.profile_id WHERE d.done_at >= ?"),
            "charts": q("SELECT created_at AS ts, owner FROM profiles WHERE created_at >= ?"),
            "chart_owners": [r[0] for r in conn.execute("SELECT DISTINCT owner FROM profiles").fetchall()],
            "tracking_since": first,
        }


# ----- Studio Playground -----
def playground_used_today(code_id: int) -> int:
    """Playground answers made today by the people signed in with this code."""
    with _lock, _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM usage_log u JOIN owner_codes o ON o.owner = u.owner"
                            " WHERE o.code_id = ? AND u.kind = 'playground' AND substr(u.ts, 1, 10) = ?",
                            (code_id, _today())).fetchone()[0]


def add_draft(kind: str, topic: str, text: str, author: str, question: str | None = None,
              answer: str | None = None, profile_id: int | None = None, author_code: int | None = None) -> dict:
    with _lock, _connect() as conn:
        cur = conn.execute("INSERT INTO studio_drafts (kind, topic, text, question, answer, profile_id, author,"
                           " author_code, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (kind, topic, text, question, answer, profile_id, author, author_code, _now()))
        return dict(conn.execute("SELECT * FROM studio_drafts WHERE id = ?", (cur.lastrowid,)).fetchone())


def drafts(limit: int = 200) -> list[dict]:
    with _lock, _connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM studio_drafts ORDER BY id DESC LIMIT ?", (limit,))]


def get_draft(draft_id: int) -> dict | None:
    with _lock, _connect() as conn:
        r = conn.execute("SELECT * FROM studio_drafts WHERE id = ?", (draft_id,)).fetchone()
    return dict(r) if r else None


def update_draft(draft_id: int, topic: str, text: str) -> dict:
    with _lock, _connect() as conn:
        conn.execute("UPDATE studio_drafts SET topic = ?, text = ?, updated_at = ? WHERE id = ?",
                     (topic, text, _now(), draft_id))
        return dict(conn.execute("SELECT * FROM studio_drafts WHERE id = ?", (draft_id,)).fetchone())


def delete_draft(draft_id: int) -> None:
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM studio_drafts WHERE id = ?", (draft_id,))


def _version(r) -> dict:
    return dict(r) | {"items": json.loads(r["items"])}


def teach_version() -> dict:
    """The live teaching version ({"id": 0, "items": []} before anything is published)."""
    with _lock, _connect() as conn:
        r = conn.execute("SELECT * FROM teach_versions ORDER BY id DESC LIMIT 1").fetchone()
    return _version(r) if r else {"id": 0, "items": [], "action": None, "actor": None, "created_at": None}


def teach_versions(limit: int = 20) -> list[dict]:
    with _lock, _connect() as conn:
        return [_version(r) for r in conn.execute("SELECT * FROM teach_versions ORDER BY id DESC LIMIT ?", (limit,))]


def get_teach_version(version_id: int) -> dict | None:
    with _lock, _connect() as conn:
        r = conn.execute("SELECT * FROM teach_versions WHERE id = ?", (version_id,)).fetchone()
    return _version(r) if r else None


def set_teaching(items: list[int], action: str, actor: str) -> dict:
    """Make a new live teaching version with exactly these published items, and bring each item's status in line."""
    items = sorted(set(items))
    with _lock, _connect() as conn:
        cur = conn.execute("INSERT INTO teach_versions (items, action, actor, created_at) VALUES (?, ?, ?, ?)",
                           (json.dumps(items), action, actor, _now()))
        marks = ",".join("?" * len(items))
        conn.execute(f"UPDATE studio_drafts SET status = 'retired' WHERE status = 'published'"
                     f"{f' AND id NOT IN ({marks})' if items else ''}", items)
        if items:
            conn.execute(f"UPDATE studio_drafts SET status = 'published' WHERE id IN ({marks})", items)
        return _version(conn.execute("SELECT * FROM teach_versions WHERE id = ?", (cur.lastrowid,)).fetchone())


def teaching_items(ids: list[int]) -> list[dict]:
    """These lessons and gold answers, oldest first (the order they were written)."""
    if not ids:
        return []
    with _lock, _connect() as conn:
        return [dict(r) for r in conn.execute(
            f"SELECT * FROM studio_drafts WHERE id IN ({','.join('?' * len(ids))}) ORDER BY id", list(ids))]


# ----- Studio reviews -----
def review_candidates(limit: int = 3000) -> list[dict]:
    """Recent AI answers to testers (not cache reuse, comparisons or Playground runs) with any review, newest first."""
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT u.id, u.ts, u.profile_id, u.question, u.answer, u.factcheck, u.owner, u.model, u.words,"
            " u.rating, u.rating_reason,"
            " p.name AS profile_name, r.id AS review_id FROM usage_log u LEFT JOIN profiles p ON p.id = u.profile_id"
            " LEFT JOIN reviews r ON r.usage_id = u.id WHERE u.kind = 'llm' AND u.answer IS NOT NULL"
            " ORDER BY u.id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["factcheck"] = json.loads(d["factcheck"]) if d.get("factcheck") else None
        out.append(d)
    return out


def get_answer(usage_id: int) -> dict | None:
    with _lock, _connect() as conn:
        r = conn.execute("SELECT u.*, p.name AS profile_name FROM usage_log u LEFT JOIN profiles p ON p.id = u.profile_id"
                         " WHERE u.id = ?", (usage_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["factcheck"] = json.loads(d["factcheck"]) if d.get("factcheck") else None
    return d


def _review(r) -> dict:
    return dict(r) | {"checks": json.loads(r["checks"]), "tags": json.loads(r["tags"])}


def add_review(usage_id: int, reviewer: str, reviewer_code: int | None, checks: dict, tags: list[str],
               note: str | None) -> dict | None:
    """None when this answer already has a review."""
    with _lock, _connect() as conn:
        try:
            cur = conn.execute("INSERT INTO reviews (usage_id, reviewer, reviewer_code, checks, tags, note, created_at)"
                               " VALUES (?, ?, ?, ?, ?, ?, ?)", (usage_id, reviewer, reviewer_code, json.dumps(checks),
                                                                json.dumps(tags), note, _now()))
        except sqlite3.IntegrityError:
            return None
        return _review(conn.execute("SELECT * FROM reviews WHERE id = ?", (cur.lastrowid,)).fetchone())


def get_review(usage_id: int) -> dict | None:
    with _lock, _connect() as conn:
        r = conn.execute("SELECT * FROM reviews WHERE usage_id = ?", (usage_id,)).fetchone()
    return _review(r) if r else None


def reviews(limit: int = 50) -> list[dict]:
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT r.*, u.question, u.owner, p.name AS profile_name FROM reviews r"
                            " LEFT JOIN usage_log u ON u.id = r.usage_id LEFT JOIN profiles p ON p.id = u.profile_id"
                            " ORDER BY r.id DESC LIMIT ?", (limit,)).fetchall()
    return [_review(r) for r in rows]


# ----- Studio quality runs -----
def set_test_set(draft_id: int, on: bool) -> dict:
    with _lock, _connect() as conn:
        conn.execute("UPDATE studio_drafts SET in_test_set = ? WHERE id = ?", (int(on), draft_id))
        return dict(conn.execute("SELECT * FROM studio_drafts WHERE id = ?", (draft_id,)).fetchone())


def test_set() -> list[dict]:
    with _lock, _connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT d.*, p.name AS profile_name FROM studio_drafts d LEFT JOIN profiles p ON p.id = d.profile_id"
            " WHERE d.in_test_set = 1 ORDER BY d.topic, d.id")]


def _run(r) -> dict:
    d = dict(r)
    for k in ("topics", "drafts", "scores"):
        d[k] = json.loads(d[k]) if d.get(k) else None
    return d


def add_run(kind: str, topics: list[str] | None, drafts: list[int], teach_version: int, model: str,
            judge_model: str, total: int, actor: str) -> dict:
    with _lock, _connect() as conn:
        cur = conn.execute("INSERT INTO eval_runs (kind, status, topics, drafts, teach_version, model, judge_model, total,"
                           " actor, created_at) VALUES (?, 'running', ?, ?, ?, ?, ?, ?, ?, ?)",
                           (kind, json.dumps(topics) if topics else None, json.dumps(drafts), teach_version, model,
                            judge_model, total, actor, _now()))
        return _run(conn.execute("SELECT * FROM eval_runs WHERE id = ?", (cur.lastrowid,)).fetchone())


def get_run(run_id: int) -> dict | None:
    with _lock, _connect() as conn:
        r = conn.execute("SELECT * FROM eval_runs WHERE id = ?", (run_id,)).fetchone()
    return _run(r) if r else None


def runs(limit: int = 30) -> list[dict]:
    with _lock, _connect() as conn:
        return [_run(r) for r in conn.execute("SELECT * FROM eval_runs ORDER BY id DESC LIMIT ?", (limit,))]


def running_run() -> dict | None:
    with _lock, _connect() as conn:
        r = conn.execute("SELECT * FROM eval_runs WHERE status = 'running' ORDER BY id DESC LIMIT 1").fetchone()
    return _run(r) if r else None


def add_eval_item(run_id: int, item: dict) -> None:
    with _lock, _connect() as conn:
        conn.execute("INSERT INTO eval_items (run_id, gold_id, variant, topic, question, answer, factcheck, judge, score,"
                     " cost, error, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (run_id, item["gold_id"], item["variant"], item["topic"], item["question"], item.get("answer"),
                      json.dumps(item.get("factcheck")) if item.get("factcheck") is not None else None,
                      json.dumps(item.get("judge")) if item.get("judge") is not None else None, item.get("score"),
                      item.get("cost") or 0, item.get("error"), _now()))
        conn.execute("UPDATE eval_runs SET done = done + 1, cost = cost + ? WHERE id = ?", (item.get("cost") or 0, run_id))


def finish_run(run_id: int, scores: dict | None, error: str | None = None) -> None:
    with _lock, _connect() as conn:
        conn.execute("UPDATE eval_runs SET status = ?, scores = ?, error = ?, finished_at = ? WHERE id = ?",
                     ("failed" if error else "done", json.dumps(scores) if scores else None, error, _now(), run_id))


def eval_items(run_id: int) -> list[dict]:
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT * FROM eval_items WHERE run_id = ? ORDER BY gold_id, variant DESC", (run_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("factcheck", "judge", "human"):
            d[k] = json.loads(d[k]) if d.get(k) else None
        out.append(d)
    return out


def get_eval_item(item_id: int) -> dict | None:
    with _lock, _connect() as conn:
        r = conn.execute("SELECT * FROM eval_items WHERE id = ?", (item_id,)).fetchone()
    return dict(r) if r else None


def grade_eval_item(item_id: int, human: dict, by: str) -> None:
    with _lock, _connect() as conn:
        conn.execute("UPDATE eval_items SET human = ?, human_by = ? WHERE id = ?", (json.dumps(human), by, item_id))


def eval_costs(today_only: bool) -> float:
    with _lock, _connect() as conn:
        where = " WHERE substr(created_at, 1, 10) = ?" if today_only else ""
        return conn.execute(f"SELECT COALESCE(SUM(cost), 0) FROM eval_runs{where}",
                            (_today(),) if today_only else ()).fetchone()[0]


def factcheck_rate(days: int = 30) -> dict:
    """Of the AI answers testers got in the last ``days``, how many the fact check caught something in."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT factcheck FROM usage_log WHERE kind = 'llm' AND ts >= ? AND factcheck IS NOT NULL",
                            (since,)).fetchall()
    caught = sum(1 for r in rows if (json.loads(r["factcheck"]) or {}).get("found"))
    return {"answers": len(rows), "caught": caught}


# ----- Jamakkol questions; callers check the profile belongs to the person first -----
def jk_add(profile_id: int, kind: str, question: str | None, asked_at: str, lat: float, lon: float, tz_name: str,
           verdict: str, label: str, place: str | None = None) -> dict:
    with _lock, _connect() as conn:
        cur = conn.execute("INSERT INTO jamakkol_asks (profile_id, kind, question, asked_at, lat, lon, tz_name, verdict,"
                           " label, place) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (profile_id, kind, question, asked_at, lat, lon, tz_name, verdict, label, place))
        return dict(conn.execute("SELECT * FROM jamakkol_asks WHERE id = ?", (cur.lastrowid,)).fetchone())


def jk_list(profile_id: int) -> list[dict]:
    with _lock, _connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM jamakkol_asks WHERE profile_id = ? ORDER BY id DESC",
                                              (profile_id,))]


def jk_get(profile_id: int, ask_id: int) -> dict | None:
    with _lock, _connect() as conn:
        r = conn.execute("SELECT * FROM jamakkol_asks WHERE profile_id = ? AND id = ?", (profile_id, ask_id)).fetchone()
    return dict(r) if r else None


def jk_outcome(profile_id: int, ask_id: int, outcome: str | None) -> bool:
    with _lock, _connect() as conn:
        return conn.execute("UPDATE jamakkol_asks SET outcome = ?, outcome_at = ? WHERE profile_id = ? AND id = ?",
                            (outcome, _now() if outcome else None, profile_id, ask_id)).rowcount > 0


def jk_outcomes() -> list[dict]:
    """Every answered Jamakkol question (verdict and outcome only), for Studio › Quality."""
    with _lock, _connect() as conn:
        return [dict(r) for r in conn.execute("SELECT kind, verdict, outcome FROM jamakkol_asks WHERE outcome IS NOT NULL")]
