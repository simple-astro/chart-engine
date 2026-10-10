"""The remedy library in the database: import, review, approve, and serve only what is approved.

Items are JSON documents keyed by (kind, slug) with a review status and a version that goes up on every edit.
Production (access gate on) serves only ``approved`` items; local mode also serves ``pending_astrologer`` so the
astrologer can preview content before approving it.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from app import access, storage
from app.remedies.schema import KINDS, Invalid, validate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row(r) -> dict:
    return {**json.loads(r["data"]), "kind": r["kind"], "slug": r["slug"], "review_status": r["review_status"],
            "version": r["version"], "updated_at": r["updated_at"]}


def import_items(items: list[dict]) -> dict:
    """Validate everything first, then upsert. Existing items keep their review status unless the file sets one,
    and their version goes up when the content changes. Nothing is written if any item is invalid."""
    if not isinstance(items, list) or not items:
        raise Invalid("expected a non-empty list of items")
    clean, errors = [], []
    for i, it in enumerate(items):
        try:
            kind = it.get("kind") if isinstance(it, dict) else None
            clean.append((kind, validate(kind, {k: v for k, v in it.items() if k != "kind"})))
        except Invalid as exc:
            errors.append(f"item {i + 1} ({(it or {}).get('slug') or (it or {}).get('planet') or '?'}): {exc}")
    if errors:
        raise Invalid("; ".join(errors[:20]) + (f" … and {len(errors) - 20} more" if len(errors) > 20 else ""))
    added = updated = unchanged = 0
    with storage._lock, storage._connect() as conn:
        for kind, it in clean:
            data = json.dumps({k: v for k, v in it.items() if k not in ("slug", "review_status", "version")},
                              sort_keys=True, ensure_ascii=False)
            old = conn.execute("SELECT data, review_status, version FROM remedy_items WHERE kind = ? AND slug = ?",
                               (kind, it["slug"])).fetchone()
            if old is None:
                conn.execute("INSERT INTO remedy_items (kind, slug, data, review_status, version, updated_at)"
                             " VALUES (?,?,?,?,1,?)", (kind, it["slug"], data, it["review_status"], _now()))
                added += 1
            else:
                changed = old["data"] != data
                # Changed content needs a fresh review unless the file itself marks it approved/retired.
                status = it["review_status"] if it["review_status"] != "pending_astrologer" else (
                    "pending_astrologer" if changed else old["review_status"])
                if not changed and status == old["review_status"]:
                    unchanged += 1
                    continue
                conn.execute("UPDATE remedy_items SET data = ?, review_status = ?, version = version + ?,"
                             " updated_at = ? WHERE kind = ? AND slug = ?",
                             (data, status, int(changed), _now(), kind, it["slug"]))
                updated += 1
    return {"added": added, "updated": updated, "unchanged": unchanged}


def list_items(kind: str | None = None, status: str | None = None) -> list[dict]:
    where, args = [], []
    if kind:
        where.append("kind = ?"); args.append(kind)
    if status:
        where.append("review_status = ?"); args.append(status)
    sql = "SELECT * FROM remedy_items" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY kind, slug"
    with storage._lock, storage._connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def get_item(kind: str, slug: str) -> dict | None:
    with storage._lock, storage._connect() as conn:
        r = conn.execute("SELECT * FROM remedy_items WHERE kind = ? AND slug = ?", (kind, slug)).fetchone()
    return _row(r) if r else None


def update_item(kind: str, slug: str, *, data: dict | None = None, review_status: str | None = None) -> dict | None:
    """Edit content (re-validated; an approved item goes back to pending) and/or change the review status."""
    cur = get_item(kind, slug)
    if cur is None:
        return None
    if data is not None:
        body = {**data, "slug": slug, "review_status": review_status or "pending_astrologer"}
        clean = validate(kind, {k: v for k, v in body.items() if k not in ("kind", "version", "updated_at")})
        blob = json.dumps({k: v for k, v in clean.items() if k not in ("slug", "review_status", "version")},
                          sort_keys=True, ensure_ascii=False)
        with storage._lock, storage._connect() as conn:
            conn.execute("UPDATE remedy_items SET data = ?, review_status = ?, version = version + 1, updated_at = ?"
                         " WHERE kind = ? AND slug = ?", (blob, clean["review_status"], _now(), kind, slug))
    elif review_status is not None:
        validate(kind, {**{k: v for k, v in cur.items() if k not in ("kind", "version", "updated_at")},
                        "review_status": review_status})
        with storage._lock, storage._connect() as conn:
            conn.execute("UPDATE remedy_items SET review_status = ?, updated_at = ? WHERE kind = ? AND slug = ?",
                         (review_status, _now(), kind, slug))
    return get_item(kind, slug)


def counts() -> dict:
    out = {k: {"pending_astrologer": 0, "approved": 0, "retired": 0} for k in KINDS}
    with storage._lock, storage._connect() as conn:
        for r in conn.execute("SELECT kind, review_status, COUNT(*) n FROM remedy_items GROUP BY kind, review_status"):
            out.setdefault(r["kind"], {})[r["review_status"]] = r["n"]
    return out


def served(kind: str) -> list[dict]:
    """What users may see: approved items; in local mode (no access gate) pending items too, for previewing."""
    statuses = ("approved",) if access.enabled() else ("approved", "pending_astrologer")
    return [i for i in list_items(kind) if i["review_status"] in statuses]
