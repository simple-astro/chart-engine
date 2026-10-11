"""Database backups: consistent copies, the daily copy and pruning, and the admin download."""
import sqlite3
from datetime import datetime, timedelta, timezone

from app import backup, storage
from tests.test_admin import BODY, _admin, _tester, gated  # noqa: F401  (fixture)


def _profiles_in(path):
    with sqlite3.connect(path) as c:
        return [r[0] for r in c.execute("SELECT name FROM profiles")]


def test_daily_copy_once_a_day_and_old_copies_go(gated):
    _tester().post("/profiles", json=BODY)
    now = datetime(2026, 10, 11, 9, tzinfo=timezone.utc)
    first = backup.daily(now)
    assert first and first.name == "profiles-2026-10-11.db" and _profiles_in(first) == ["Asha"]
    assert backup.daily(now + timedelta(hours=5)) is None  # one copy per day
    old = backup.folder() / "profiles-2026-09-20.db"
    old.write_bytes(first.read_bytes())
    backup.daily(now + timedelta(days=1))
    names = [b["name"] for b in backup.listing()]
    assert names == ["profiles-2026-10-12.db", "profiles-2026-10-11.db"]  # 21 days old -> pruned
    assert not list(backup.folder().glob("*.tmp"))


def test_admin_can_list_make_and_download_backups(gated):
    t = _tester()
    pid = t.post("/profiles", json=BODY).json()["id"]
    t.post(f"/profiles/{pid}/mood", json={"valence": 2})
    a = _admin()
    assert a.get("/admin/api/backups").json()["backups"] == []
    made = a.post("/admin/api/backups").json()
    assert len(made["backups"]) == 1 and made["keep_days"] == backup.KEEP_DAYS
    r = a.get("/admin/api/backups/download")
    assert r.status_code == 200 and "simplejyotish-" in r.headers["content-disposition"]
    assert r.content.startswith(b"SQLite format 3")
    path = storage._db_path().parent / "dl.db"
    path.write_bytes(r.content)
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT COUNT(*) FROM mood_logs").fetchone()[0] == 1
    for url in ("/admin/api/backups", "/admin/api/backups/download"):
        assert t.get(url).status_code == 403
    assert t.post("/admin/api/backups").status_code == 403
