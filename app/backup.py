"""Backups of the one SQLite database (profiles, chats, mood logs, the remedy library, settings, codes).

- A daily copy is kept next to the database (``<db dir>/backups``) for KEEP_DAYS days. It guards against bad
  writes, mistakes and corruption, but it lives on the same volume, so the admin page also offers a download to
  keep a copy somewhere else.
- Copies use SQLite's online backup API, so they are consistent even while the app is writing.
"""
from __future__ import annotations

import os
import re
import sqlite3
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from app import storage

KEEP_DAYS = 14
_NAME = re.compile(r"^profiles-(\d{4}-\d{2}-\d{2})\.db$")


def folder() -> Path:
    return storage._db_path().parent / "backups"


def copy_to(dest: Path) -> Path:
    """A consistent copy of the live database at ``dest``."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = storage._connect()  # also creates any missing tables, so an empty app still backs up cleanly
    try:
        dst = sqlite3.connect(dest)
        try:
            with storage._lock:
                src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return dest


def daily(now: datetime | None = None, force: bool = False) -> Path | None:
    """Today's copy (UTC date) if there isn't one yet, then drop copies older than KEEP_DAYS. Returns the new path."""
    now = now or datetime.now(timezone.utc)
    path = folder() / f"profiles-{now.date().isoformat()}.db"
    made = None
    if force or not path.exists():
        tmp = path.with_suffix(".tmp")
        copy_to(tmp)
        os.replace(tmp, path)  # never leave a half-written file under the real name
        made = path
    prune(now)
    return made


def prune(now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    gone = []
    for p in folder().glob("profiles-*.db"):
        m = _NAME.match(p.name)
        if m and (now.date() - datetime.fromisoformat(m.group(1)).date()).days >= KEEP_DAYS:
            p.unlink(missing_ok=True)
            gone.append(p.name)
    return gone


def listing() -> list[dict]:
    out = []
    for p in sorted(folder().glob("profiles-*.db"), reverse=True):
        if _NAME.match(p.name):
            st = p.stat()
            out.append({"name": p.name, "bytes": st.st_size,
                        "made": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds")})
    return out


def download_copy() -> Path:
    """A fresh copy in a temporary file, for the admin download (the caller deletes it)."""
    fd, name = tempfile.mkstemp(suffix=".db", prefix="simplejyotish-")
    os.close(fd)
    return copy_to(Path(name))


def _loop() -> None:
    while True:
        try:
            if daily():
                print("Daily database backup written")
        except Exception as e:  # keep the app running; the admin page shows when the last copy was made
            print(f"Backup failed: {e!r}")
        time.sleep(3600)


def start() -> None:
    """Run the daily backup in the background (checked hourly). BACKUPS=off turns it off."""
    if os.environ.get("BACKUPS", "on").lower() in ("off", "0", "false"):
        return
    threading.Thread(target=_loop, daemon=True, name="backups").start()
