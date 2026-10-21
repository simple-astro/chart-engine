"""Admin page and its API: settings, usage and cost, testers, and the question log."""
from __future__ import annotations

import json
import re
import secrets
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from app import access, config, storage

router = APIRouter(include_in_schema=False)
_PAGE = Path(__file__).parent / "static" / "admin.html"


def _require_admin(request: Request) -> None:
    """The owner only (settings, tester codes, backups, importing the remedy library)."""
    if not request.state.admin:
        raise HTTPException(status_code=403, detail="Admin access required")


def _require_role(request: Request, *roles: str) -> str:
    """The owner, or a Studio code with one of these roles. Returns the role."""
    role = "owner" if request.state.admin else getattr(request.state, "role", None)
    if role != "owner" and role not in roles:
        raise HTTPException(status_code=403, detail="Not available for your access code")
    return role


def _actor(request: Request) -> tuple[str, str]:
    """(name, role) of whoever is signed in, for the change log."""
    if request.state.admin:
        return "Owner", "owner"
    code = storage.get_code(getattr(request.state, "code_id", 0) or 0) or {}
    return code.get("label") or code.get("code") or "Unknown", request.state.role or "?"


def _audit(request: Request, action: str, obj: str | None = None, detail: str | None = None) -> None:
    name, role = _actor(request)
    storage.log_audit(name, role, action, obj, detail)


def _tester(owner: str | None, labels: dict[str, str] | None = None) -> str:
    if not owner:
        return "Local"
    label = (labels or {}).get(owner)
    return f"{label} · {owner[:6]}" if label else f"Tester {owner[:6]}"


def _cost(rows: list[dict]) -> float:
    return round(sum(config.cost(r["model"], r["inp"], r["out"], r["cr"], r["cw"]) or 0 for r in rows), 4)


def _studio_cost(today_only: bool) -> float:
    """What Studio experiments cost: Playground answers, model comparisons and Quality runs."""
    return round(_cost(storage.token_totals(today_only, ("playground", "compare"))) + storage.eval_costs(today_only), 4)


@router.get("/me")
def me(request: Request) -> dict:
    role = "owner" if request.state.admin else getattr(request.state, "role", None)
    out = {"admin": bool(request.state.admin), "gated": access.enabled(), "role": role}
    if role in access.STUDIO:
        out["name"] = _actor(request)[0]
    return out


@router.get("/admin")
def admin_page(request: Request):
    if not request.state.admin and getattr(request.state, "role", None) not in access.STUDIO:
        return HTMLResponse(access.login_page(admin=True))
    return FileResponse(_PAGE, media_type="text/html", headers={"Cache-Control": "no-cache"})


@router.get("/admin/api/overview")
def overview(request: Request) -> dict:
    _require_role(request, "mentor")
    today, ever = storage.token_totals(today_only=True), storage.token_totals(today_only=False)
    testers, labels = storage.tester_summary(), storage.owner_code_labels()
    return {
        "settings": config.all_settings(),
        "models": config.MODELS,
        "providers": config.providers_status(),
        "gated": access.enabled(),
        "today": {"paid_questions": sum(r["n"] for r in today), "cost": _cost(today), "studio_cost": _studio_cost(True)},
        "all_time": {"paid_questions": sum(r["n"] for r in ever), "cost": _cost(ever), "studio_cost": _studio_cost(False)},
        "charts": sum(t["charts"] for t in testers),
        "testers": [{**t, "label": _tester(t["owner"], labels), "owner": None} for t in testers],
    }


@router.put("/admin/api/settings")
async def save_settings(request: Request) -> dict:
    _require_admin(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Expected a JSON object")
    try:
        return config.update(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/admin/api/queries")
def queries(request: Request, limit: int = 50, before_id: int | None = None) -> list[dict]:
    _require_role(request, "mentor", "astrologer")
    rows = storage.recent_queries(max(1, min(limit, 200)), before_id)
    labels = storage.owner_code_labels()
    for r in rows:
        r["tester"] = _tester(r.pop("owner"), labels)
        r["model_label"] = config.label(r["model"])
        r["cost"] = config.cost(r["model"], r["input_tokens"], r["output_tokens"], r["cache_read_tokens"],
                                r["cache_write_tokens"]) if r["kind"] == "llm" else 0.0
    return rows


@router.get("/admin/api/usage")
def usage_report(request: Request) -> dict:
    """Which sections testers open and which they leave untouched (app/usage.py), with tester labels."""
    from app import usage
    _require_role(request, "mentor")
    r = usage.report()
    labels = storage.owner_code_labels()
    for t in r["testers"]:
        t["tester"] = _tester(t.pop("owner"), labels)
    return r


@router.get("/admin/api/queries/export")
def export_queries(request: Request, q: str = ""):
    """Every question as a CSV file (or only those matching the page's filter), for a spreadsheet."""
    import csv
    import io
    from datetime import datetime, timezone
    from fastapi.responses import Response
    _require_role(request, "mentor", "astrologer")
    rows = queries(request, limit=200)
    while len(rows) % 200 == 0 and rows:            # page back through the whole log
        older = queries(request, limit=200, before_id=rows[-1]["id"])
        if not older:
            break
        rows += older
    words = q.strip().lower()
    if words:
        rows = [r for r in rows if any(words in str(r.get(k) or "").lower() for k in ("tester", "profile_name", "question", "answer"))]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["When (UTC)", "Tester", "Chart", "Question", "Answer", "Answered by", "Input tokens", "Output tokens",
                "Est. cost (USD)", "Fact check: caught", "Fact check: removed", "Your note"])
    for r in rows:
        fc = r.get("factcheck") or {}
        w.writerow([r["ts"], r["tester"], r.get("profile_name") or "", r.get("question") or "", r.get("answer") or "",
                    r["model_label"] if r["kind"] == "llm" else r["kind"], r["input_tokens"], r["output_tokens"],
                    f"{r['cost']:.4f}", " | ".join(fc.get("found") or []), " | ".join(fc.get("removed") or []),
                    r.get("admin_remarks") or ""])
    name = f"simplejyotish-questions-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.csv"
    return Response("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",   # BOM so Excel reads Hindi/Punjabi text
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})


@router.put("/admin/api/queries/{query_id}/remarks")
async def save_remarks(request: Request, query_id: int) -> dict:
    _require_role(request, "mentor", "astrologer")
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Expected a JSON object")
    remarks = body.get("remarks", "").strip()
    if not storage.update_remarks(query_id, remarks or None):
        raise HTTPException(status_code=404, detail="Query not found")
    return {"ok": True}


# ----- tester access codes -----
_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{6,40}$")
_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no look-alikes (0/o, 1/l/i)


def _new_code() -> str:
    return "sj-" + "".join(secrets.choice(_ALPHABET) for _ in range(8))


def _label(body: dict) -> str:
    label = body.get("label", "")
    if not isinstance(label, str) or len(label.strip()) > 60:
        raise HTTPException(status_code=422, detail="Label must be text of 60 characters or fewer")
    return label.strip()


@router.get("/admin/api/codes")
def list_codes(request: Request) -> dict:
    _require_admin(request)
    return {"gated": access.enabled(), "codes": storage.list_codes(),
            "default_limit": config.get("daily_limit_per_tester"),
            "env_codes": len(access._codes())}


@router.post("/admin/api/codes", status_code=201)
async def create_code(request: Request) -> dict:
    _require_admin(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Expected a JSON object")
    label, code = _label(body), (body.get("code") or "").strip()
    if code:
        if not _CODE_RE.match(code):
            raise HTTPException(status_code=422, detail="Codes need 6–40 letters, numbers, - or _")
        if access.check_code(code):
            raise HTTPException(status_code=409, detail="That code is already in use")
    else:
        code = _new_code()
    try:
        return storage.add_code(code, label)
    except sqlite3.IntegrityError as exc:  # a paused code with the same text
        raise HTTPException(status_code=409, detail="That code is already in use") from exc


@router.patch("/admin/api/codes/{code_id}")
async def edit_code(code_id: int, request: Request) -> dict:
    _require_admin(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Expected a JSON object")
    active = body.get("active")
    if active is not None and not isinstance(active, bool):
        raise HTTPException(status_code=422, detail="active must be true or false")
    label = _label(body) if "label" in body else None
    extra = {}
    if "daily_limit" in body:  # null = use the default from Settings
        lim = body["daily_limit"]
        if lim is not None and (isinstance(lim, bool) or not isinstance(lim, int) or not 0 <= lim <= 1000):
            raise HTTPException(status_code=422, detail="Questions per day must be a whole number from 0 to 1000, "
                                                        "or empty for the default")
        extra["daily_limit"] = lim
    if not storage.update_code(code_id, active=active, label=label, **extra):
        raise HTTPException(status_code=404, detail="Code not found")
    return {"ok": True}


@router.delete("/admin/api/codes/{code_id}")
def remove_code(code_id: int, request: Request) -> dict:
    _require_admin(request)
    if not storage.delete_code(code_id):
        raise HTTPException(status_code=404, detail="Code not found")
    return {"ok": True}


# ----- Studio team: the owner makes mentor and astrologer codes; a mentor makes astrologer codes -----
STUDIO_BUDGET = 30  # Playground answers per day for a new Studio code
ROLE_LABEL = {"mentor": "admin", "astrologer": "astrologer"}  # the mentor role is called "Admin" in the app
_an = lambda role: ("an " if ROLE_LABEL.get(role, role)[0] in "aeiou" else "a ") + ROLE_LABEL.get(role, role)


def _budget(body: dict, default: int | None) -> int | None:
    lim = body.get("daily_limit", default)
    if lim is not None and (isinstance(lim, bool) or not isinstance(lim, int) or not 0 <= lim <= 1000):
        raise HTTPException(status_code=422, detail="Daily budget must be a whole number from 0 to 1000")
    return lim


def _team_target(request: Request, code_id: int, role: str) -> dict:
    """The Studio code this person may change: the owner any, a mentor only astrologer codes."""
    code = storage.get_code(code_id)
    if not code or code.get("role") not in access.STUDIO:
        raise HTTPException(status_code=404, detail="Studio code not found")
    if role == "mentor" and code["role"] != "astrologer":
        raise HTTPException(status_code=403, detail="Admins can change astrologer codes only")
    return code


@router.get("/admin/api/team")
def team(request: Request) -> dict:
    role = _require_role(request, "mentor")
    codes = storage.studio_codes()
    if role == "mentor":
        codes = [c for c in codes if c["role"] == "astrologer"]
    return {"codes": codes, "can_make": ["mentor", "astrologer"] if role == "owner" else ["astrologer"],
            "default_budget": STUDIO_BUDGET}


@router.post("/admin/api/team", status_code=201)
async def team_add(request: Request) -> dict:
    role = _require_role(request, "mentor")
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Expected a JSON object")
    new_role = body.get("role", "astrologer")
    if new_role not in access.STUDIO:
        raise HTTPException(status_code=422, detail="Role must be Admin or Astrologer")
    if role == "mentor" and new_role != "astrologer":
        raise HTTPException(status_code=403, detail="Admins can create astrologer codes only")
    label = _label(body)
    if not label:
        raise HTTPException(status_code=422, detail="Add the person's name so their work is credited")
    lim = _budget(body, STUDIO_BUDGET)
    for _ in range(5):
        try:
            made = storage.add_code(_new_code(), label, role=new_role, daily_limit=lim,
                                    created_by=(request.state.code_id or None) if role == "mentor" else None)
            break
        except sqlite3.IntegrityError:
            continue
    else:
        raise HTTPException(status_code=500, detail="Could not make a unique code, please try again")
    _audit(request, f"created {_an(new_role)} code", label, f"daily budget {lim}")
    return made


@router.patch("/admin/api/team/{code_id}")
async def team_edit(code_id: int, request: Request) -> dict:
    role = _require_role(request, "mentor")
    code = _team_target(request, code_id, role)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Expected a JSON object")
    active = body.get("active")
    if active is not None and not isinstance(active, bool):
        raise HTTPException(status_code=422, detail="active must be true or false")
    label = _label(body) if "label" in body else None
    extra = {"daily_limit": _budget(body, None)} if "daily_limit" in body else {}
    storage.update_code(code_id, active=active, label=label, **extra)
    changes = [("paused" if active is False else "resumed") if active is not None else "",
               f"renamed to {label}" if label else "", f"daily budget {extra['daily_limit']}" if extra else ""]
    _audit(request, f"changed {_an(code['role'])} code", code["label"] or code["code"], ", ".join(c for c in changes if c))
    return {"ok": True}


@router.delete("/admin/api/team/{code_id}")
def team_remove(code_id: int, request: Request) -> dict:
    role = _require_role(request, "mentor")
    code = _team_target(request, code_id, role)
    storage.delete_code(code_id)
    _audit(request, f"deleted {_an(code['role'])} code", code["label"] or code["code"])
    return {"ok": True}


@router.get("/admin/api/audit")
def audit_log(request: Request, limit: int = 100) -> list[dict]:
    _require_role(request, "mentor")
    return storage.audit(max(1, min(limit, 500)))


# ----- remedy library (curated content lives in the database, imported from a private seed file) -----
def _parse_items(body) -> list:
    """Accept {"items": [...]}, a bare list, or {"text": "<JSON or YAML>"} (a pasted or uploaded seed file)."""
    import json as _json
    import yaml
    if isinstance(body, dict) and isinstance(body.get("text"), str):
        try:
            body = _json.loads(body["text"])
        except ValueError:
            try:
                body = yaml.safe_load(body["text"])
            except yaml.YAMLError as exc:
                raise HTTPException(status_code=422, detail=f"Not valid JSON or YAML: {exc}") from exc
    items = body.get("items") if isinstance(body, dict) else body
    if not isinstance(items, list):
        raise HTTPException(status_code=422, detail="Expected a list of items (or {items: [...]})")
    return items


@router.get("/admin/api/remedies")
def remedy_library(request: Request, kind: str | None = None, status: str | None = None) -> dict:
    from app.remedies import library
    _require_role(request, "mentor", "astrologer")
    return {"counts": library.counts(), "items": library.list_items(kind, status)}


@router.post("/admin/api/remedies/import")
async def remedy_import(request: Request) -> dict:
    from app.remedies import library
    from app.remedies.schema import Invalid
    _require_admin(request)
    try:
        r = library.import_items(_parse_items(await request.json()))
    except Invalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _audit(request, "imported the remedy library", None, f"added {r['added']}, updated {r['updated']}")
    return r


def _rl_name(kind: str, slug: str) -> str:
    return f"{kind.replace('_', ' ')} {slug}"


@router.post("/admin/api/remedies", status_code=201)
async def remedy_add(request: Request) -> dict:
    """A new remedy, rule or other item from the Studio; it waits for review before users see it."""
    from app.remedies import library
    from app.remedies.schema import Invalid
    _require_role(request, "mentor", "astrologer")
    body = await request.json()
    if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
        raise HTTPException(status_code=422, detail="Send {kind, data}")
    try:
        item = library.add_item(body.get("kind") or "", body["data"])
    except Invalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _audit(request, "added a remedy item", _rl_name(item["kind"], item["slug"]), "waiting for review")
    return item


@router.patch("/admin/api/remedies/{kind}/{slug}")
async def remedy_edit(kind: str, slug: str, request: Request) -> dict:
    """Approve / retire / send back (owner and Admin), or edit the content. An astrologer's edit to an approved
    item is kept as a suggested change, so the approved version stays with users until it is accepted; the owner's
    and Admin's edits to an approved item go live at once (they approve)."""
    from app.remedies import library
    from app.remedies.schema import STATUSES, Invalid
    role = _require_role(request, "mentor", "astrologer")
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Expected a JSON object")
    status = body.get("review_status")
    if status is not None and status not in STATUSES:
        raise HTTPException(status_code=422, detail=f"review_status must be one of {', '.join(STATUSES)}")
    if status is not None and role == "astrologer":
        raise HTTPException(status_code=403, detail="Only the Admin or the owner can approve or retire")
    data = body.get("data")
    if data is not None and not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="data must be an object")
    cur = library.get_item(kind, slug)
    if cur is None:
        raise HTTPException(status_code=404, detail="Not found")
    name, _ = _actor(request)
    try:
        if data is not None and cur["review_status"] == "approved" and role == "astrologer":
            item = library.propose(kind, slug, data, name, request.state.code_id)
            _audit(request, "suggested a change to a remedy item", _rl_name(kind, slug), "waiting for the Admin")
            return item
        if data is not None and cur["review_status"] == "approved" and status is None:
            status = "approved"  # an approver's edit to live content stays live
        item = library.update_item(kind, slug, data=data, review_status=status)
    except Invalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    words = {"approved": "approved", "retired": "retired", "pending_astrologer": "sent back for review"}
    _audit(request, "edited a remedy item" if data is not None else f"{words[status]} a remedy item",
           _rl_name(kind, slug), f"now {words[item['review_status']]}" if data is not None else None)
    return item


@router.post("/admin/api/remedies/{kind}/{slug}/proposal/{action}")
def remedy_proposal(kind: str, slug: str, action: str, request: Request) -> dict:
    """Accept a suggested change (owner and Admin) or discard it (they, or whoever suggested it)."""
    from app.remedies import library
    from app.remedies.schema import Invalid
    role = _require_role(request, "mentor", "astrologer")
    if action not in ("accept", "discard"):
        raise HTTPException(status_code=404, detail="Not found")
    cur = library.get_item(kind, slug)
    if not cur or "proposal" not in cur:
        raise HTTPException(status_code=404, detail="No suggested change here")
    if role == "astrologer" and (action == "accept" or cur["proposal"]["code"] != request.state.code_id):
        raise HTTPException(status_code=403, detail="Only the Admin or the owner can do that")
    try:
        item = library.settle_proposal(kind, slug, accept=action == "accept")
    except Invalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _audit(request, ("accepted" if action == "accept" else "discarded") + " a suggested remedy change",
           _rl_name(kind, slug), f"suggested by {cur['proposal']['by']}")
    return item


@router.get("/admin/api/remedies/export")
def remedy_export(request: Request) -> dict:
    """Everything with its review status, to save back into the private content repo."""
    from app.remedies import library
    _require_role(request, "mentor")
    keep = lambda i: {k: v for k, v in i.items() if k not in ("version", "updated_at", "proposal")}
    return {"items": [keep(i) for i in library.list_items()]}


# ----- compare two models on one chart and question (nothing is saved to the user's chat) -----
@router.get("/admin/api/profiles")
def all_profiles(request: Request) -> list[dict]:
    _require_role(request, "mentor", "astrologer")  # the Playground's chart picker
    labels = storage.owner_code_labels()
    return [{"id": p["id"], "name": p["name"], "dob": p["request"].get("dob"),
             "tester": _tester(p.get("owner"), labels) if p.get("owner") else "local"} for p in storage.list_all(None)]


# ----- saved charts: users' birth details for the owner, mentors and astrologers; every look is in the audit log -----
def _birth(p: dict, labels: dict[str, str]) -> dict:
    r = p["request"]
    return {"id": p["id"], "name": p["name"], "dob": r.get("dob"),
            "tob": None if r.get("tob_unknown") else (r.get("tob") or "")[:5], "tob_unknown": bool(r.get("tob_unknown")),
            "place": r.get("place") or None, "lat": r.get("lat"), "lon": r.get("lon"), "tz_name": r.get("tz_name"),
            "ayanamsha": r.get("ayanamsha"), "node_type": r.get("node_type") or "mean",
            "house_system": r.get("house_system"), "tester": _tester(p.get("owner"), labels), "created_at": p["created_at"]}


@router.get("/admin/api/charts")
def saved_charts(request: Request) -> list[dict]:
    _require_role(request, "mentor", "astrologer")
    labels = storage.owner_code_labels()
    rows = [_birth(p, labels) for p in storage.list_all(None)]
    _audit(request, "viewed saved charts", None, f"{len(rows)} charts")
    return rows


@router.get("/admin/api/charts/{profile_id}")
def saved_chart(profile_id: int, request: Request) -> dict:
    """One chart's birth details and a short summary (Lagna, Moon, the Dasha running now)."""
    from datetime import datetime, timezone
    from app.transit_view import dasha_on
    _require_role(request, "mentor", "astrologer")
    p = storage.get(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Chart not found")
    c, out = p["chart"], _birth(p, storage.owner_code_labels())
    moon = c["grahas"]["Moon"]
    out["summary"] = {"lagna": c["lagna"]["sign"], "moon": f"{moon['sign']} · {moon['nakshatra']}",
                      "house_system": c["meta"].get("house_system"), "dasha": dasha_on(c, datetime.now(timezone.utc))}
    _audit(request, "viewed birth details", p["name"], out["tester"])
    return out


@router.post("/admin/api/compare")
async def compare(request: Request) -> dict:
    from concurrent.futures import ThreadPoolExecutor
    from app import chat
    _require_admin(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Expected a JSON object")
    question = (body.get("question") or "").strip()
    models = body.get("models")
    if not 3 <= len(question) <= 2000:
        raise HTTPException(status_code=422, detail="Ask a question of 3 to 2000 characters")
    if not isinstance(models, list) or not 1 <= len(models) <= 3 or len(set(models)) != len(models):
        raise HTTPException(status_code=422, detail="Pick one to three different models")
    for m in models:
        if m not in config.MODELS:
            raise HTTPException(status_code=422, detail=f"Unknown model: {m}")
        prov = config.provider_of(m)
        if not config.provider_ready(prov):
            raise HTTPException(status_code=422, detail=f"{config.MODELS[m]['label']} needs "
                                                        f"{config.PROVIDERS[prov]['env']} set in Railway")
    profile = storage.get(int(body.get("profile_id") or 0))
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    if isinstance(body.get("here"), dict):
        profile = {**profile, "viewer": body["here"]}

    def run(m: str) -> dict:
        try:
            r = chat.answer_once(profile, question, m)
        except Exception as exc:  # one model failing must not hide the other's answer
            return {"model": m, "label": config.label(m), "error": str(exc)}
        u = r["usage"]
        storage.log_usage(profile["id"], "compare", question, model=m, input_tokens=u["input"],
                          output_tokens=u["output"], cache_read=u["cache_read"], cache_write=u["cache_write"],
                          tool_rounds=u["rounds"], words=len(r["text"].split()), owner=profile.get("owner"),
                          answer=r["text"], factcheck=r["factcheck"])
        return r

    with ThreadPoolExecutor(max_workers=len(models)) as pool:
        results = list(pool.map(run, models))
    return {"question": question, "profile": {"id": profile["id"], "name": profile["name"]}, "results": results}


# ----- Studio Playground: try any question on any chart with test settings; nothing reaches users -----
LIMIT_KEYS = ("word_limit", "daily_limit_per_tester", "daily_limit_total", "telegram_daily_limit")
LIMIT_NAMES = {"word_limit": "word limit", "daily_limit_per_tester": "questions per tester per day",
               "daily_limit_total": "questions per day, all testers", "telegram_daily_limit": "Telegram questions per day"}


def _budget_left(request: Request) -> dict:
    """Today's Playground budget for whoever is signed in (the owner has none)."""
    if request.state.admin:
        return {"limited": False}
    code = storage.get_code(request.state.code_id or 0) or {}
    limit = code.get("daily_limit") if code.get("daily_limit") is not None else STUDIO_BUDGET
    used = storage.playground_used_today(request.state.code_id or 0)
    return {"limited": True, "limit": limit, "used": used, "left": max(0, limit - used)}


def _ready_models() -> list[dict]:
    return [{"id": m, "label": config.label(m)} for m in config.MODELS if config.provider_ready(config.provider_of(m))]


@router.get("/admin/api/playground")
def playground_status(request: Request) -> dict:
    from app.usage import TOPICS
    _require_role(request, "mentor", "astrologer")
    return {"budget": _budget_left(request), "live": {"model": config.model(), "label": config.label(config.model()),
            "word_limit": config.word_limit()}, "models": _ready_models(),
            "topics": ["General"] + [t for t, _ in TOPICS], "limits": {k: config.get(k) for k in LIMIT_KEYS}}


def _playground_profile(body: dict) -> dict:
    """The Playground works on saved charts only (the chart picker), never new birth details."""
    try:
        profile = storage.get(int(body.get("profile_id")))
    except (TypeError, ValueError):
        profile = None
    if not profile:
        raise HTTPException(status_code=404, detail="Pick a saved chart")
    return profile


@router.post("/admin/api/playground")
async def playground(request: Request) -> dict:
    from concurrent.futures import ThreadPoolExecutor
    from app import chat
    _require_role(request, "mentor", "astrologer")
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Expected a JSON object")
    question = (body.get("question") or "").strip()
    if not 3 <= len(question) <= 2000:
        raise HTTPException(status_code=422, detail="Ask a question of 3 to 2000 characters")
    variants = body.get("variants") or [{}]
    if not isinstance(variants, list) or not 1 <= len(variants) <= 2:
        raise HTTPException(status_code=422, detail="Run one or two versions at a time")
    runs = []
    for i, v in enumerate(variants):
        v = v if isinstance(v, dict) else {}
        model = v.get("model") or config.model()
        if model not in config.MODELS or not config.provider_ready(config.provider_of(model)):
            raise HTTPException(status_code=422, detail=f"That model isn't available: {model}")
        wl = v.get("word_limit")
        if wl is not None and (isinstance(wl, bool) or not isinstance(wl, int) or not 100 <= wl <= 800):
            raise HTTPException(status_code=422, detail="Word limit must be a whole number from 100 to 800")
        ins = (v.get("instruction") or "").strip()
        if len(ins) > 1000:
            raise HTTPException(status_code=422, detail="Keep the instruction under 1000 characters")
        drafts = v.get("drafts") or []
        if not isinstance(drafts, list) or len(drafts) > 20 or not all(isinstance(d, int) for d in drafts):
            raise HTTPException(status_code=422, detail="drafts must be a list of draft ids")
        runs.append({"label": str(v.get("label") or ("Live" if i == 0 else "Test"))[:40], "model": model,
                     "test": {"word_limit": wl, "instruction": ins or None, "drafts": drafts,
                              "no_teaching": bool(v.get("no_teaching"))}})
    budget = _budget_left(request)
    if budget["limited"] and budget["left"] < len(runs):
        raise HTTPException(status_code=429, detail=f"Today's Playground budget is used up ({budget['used']} of "
                                                    f"{budget['limit']}). It resets tomorrow.")
    profile = _playground_profile(body)
    if isinstance(body.get("here"), dict):
        profile = {**profile, "viewer": body["here"]}

    def run(r: dict) -> dict:
        try:
            out = chat.answer_once(profile, question, r["model"], test=r["test"], explain=True)
        except Exception as exc:  # one version failing must not hide the other
            return {"label": r["label"], "error": str(exc)}
        u = out["usage"]
        storage.log_usage(profile["id"], "playground", question, model=r["model"], input_tokens=u["input"],
                          output_tokens=u["output"], cache_read=u["cache_read"], cache_write=u["cache_write"],
                          tool_rounds=u["rounds"], words=len(out["text"].split()), owner=request.state.owner,
                          answer=out["text"], factcheck=out["factcheck"])
        return {**out, "label": r["label"], "words": len(out["text"].split())}

    with ThreadPoolExecutor(max_workers=len(runs)) as pool:
        results = list(pool.map(run, runs))
    labels = storage.owner_code_labels()
    return {"question": question, "results": results, "budget": _budget_left(request),
            "chart": {"id": profile["id"], "name": profile["name"],
                      "tester": _tester(profile.get("owner"), labels) if profile.get("owner") else None}}


@router.get("/admin/api/studio/drafts")
def studio_drafts(request: Request) -> list[dict]:
    _require_role(request, "mentor", "astrologer")
    return storage.drafts()


def _kind(kind: str) -> str:
    return "gold answer" if kind == "gold" else "lesson"


def _draft_fields(body: dict, kind: str) -> tuple[str, str]:
    """A valid topic and text that pass the fixed rules (app/teach.check), or a 422 saying what to change."""
    from app import teach
    topic, text = body.get("topic") or "General", (body.get("text") or "").strip()
    if topic not in teach.TOPIC_NAMES:
        raise HTTPException(status_code=422, detail="Unknown topic")
    if not 10 <= len(text) <= (teach.GOLD_MAX_CHARS if kind == "gold" else teach.LESSON_CHARS):
        raise HTTPException(status_code=422, detail="A lesson needs 10–600 characters; a gold answer 10–4000")
    if problems := teach.check(text):
        raise HTTPException(status_code=422, detail="Please change this first: " + " ".join(problems))
    return topic, text


@router.post("/admin/api/studio/drafts", status_code=201)
async def studio_add_draft(request: Request) -> dict:
    _require_role(request, "mentor", "astrologer")
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Expected a JSON object")
    kind = body.get("kind")
    if kind not in ("gold", "lesson"):
        raise HTTPException(status_code=422, detail="kind must be gold or lesson")
    topic, text = _draft_fields(body, kind)
    name, _ = _actor(request)
    d = storage.add_draft(kind, topic, text, name, question=(body.get("question") or None),
                          answer=(body.get("answer") or None), profile_id=body.get("profile_id"),
                          author_code=None if request.state.admin else request.state.code_id)
    _audit(request, "saved a draft " + _kind(kind), topic, text[:120])
    return d


def _own_draft(request: Request, draft_id: int) -> dict:
    """A draft this person may change: the owner and the Admin (mentor) any, an astrologer only their own;
    and only while it is a draft (published or retired teaching stays as it was, so rollback restores it)."""
    role = _require_role(request, "mentor", "astrologer")
    d = storage.get_draft(draft_id)
    if not d:
        raise HTTPException(status_code=404, detail="Draft not found")
    if role == "astrologer" and (d["author_code"] is None or d["author_code"] != request.state.code_id):
        raise HTTPException(status_code=403, detail="You can change only your own drafts")
    if d["status"] != "draft":
        raise HTTPException(status_code=409, detail="Only drafts can be changed. Save a new draft instead.")
    return d


@router.patch("/admin/api/studio/drafts/{draft_id}")
async def studio_edit_draft(draft_id: int, request: Request) -> dict:
    d = _own_draft(request, draft_id)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Expected a JSON object")
    topic, text = _draft_fields({"topic": body.get("topic", d["topic"]), "text": body.get("text", d["text"])}, d["kind"])
    _audit(request, "edited a draft " + _kind(d["kind"]), topic, text[:120])
    return storage.update_draft(draft_id, topic, text)


@router.delete("/admin/api/studio/drafts/{draft_id}")
def studio_delete_draft(draft_id: int, request: Request) -> dict:
    d = _own_draft(request, draft_id)
    storage.delete_draft(draft_id)
    _audit(request, "deleted a draft " + _kind(d["kind"]), d["topic"], d["text"][:120])
    return {"deleted": draft_id}


def _teach_summary(v: dict) -> dict:
    items = storage.teaching_items(v["items"])
    return {**v, "lessons": sum(i["kind"] == "lesson" for i in items), "gold": sum(i["kind"] == "gold" for i in items)}


@router.get("/admin/api/studio/teach")
def studio_teach(request: Request) -> dict:
    """The live teaching version and the recent ones (each publish, retire and rollback makes one)."""
    _require_role(request, "mentor", "astrologer")
    return {"version": _teach_summary(storage.teach_version()),
            "versions": [_teach_summary(v) for v in storage.teach_versions()]}


@router.post("/admin/api/studio/drafts/{draft_id}/{action}")
async def studio_publish(draft_id: int, action: str, request: Request) -> dict:
    """Publish a draft (or a retired item) into the live teaching, or retire a published one: owner and Admin.
    Publishing first needs a Quality gate run when its topic has test questions (app/quality.py): 409 with
    code "needs_gate" until one has run, and code "drop" when the score fell, unless confirm_drop is sent."""
    from app import quality, teach
    _require_role(request, "mentor")
    body = (await request.json()) if (await request.body()) else {}
    confirm_drop = bool(isinstance(body, dict) and body.get("confirm_drop"))
    if action not in ("publish", "retire"):
        raise HTTPException(status_code=404, detail="Not found")
    d = storage.get_draft(draft_id)
    if not d:
        raise HTTPException(status_code=404, detail="Draft not found")
    live = storage.teach_version()["items"]
    if action == "publish":
        if d["status"] == "published":
            raise HTTPException(status_code=409, detail="Already published")
        if problems := teach.check(d["text"]):
            raise HTTPException(status_code=422, detail="Please change this first: " + " ".join(problems))
        tests = [g for g in quality.test_items(quality.topics_for(d)) if g["id"] != draft_id]
        if tests:
            gate = quality.latest_gate(draft_id)
            if not gate:
                raise HTTPException(status_code=409, detail={
                    "code": "needs_gate", "questions": len(tests), "estimate": quality.estimate(2 * len(tests)),
                    "message": f"Test it first: {len(tests)} test question{'s' if len(tests) != 1 else ''} on this "
                               "topic, answered with and without it."})
            if (fell := quality.drops(gate["scores"])) and not confirm_drop:
                raise HTTPException(status_code=409, detail={
                    "code": "drop", "run": gate["id"], "topics": fell, "scores": gate["scores"],
                    "message": "The score drops with this on " + ", ".join(fell) + ". Publish anyway?"})
        items = live + [draft_id]
    else:
        if d["status"] != "published":
            raise HTTPException(status_code=409, detail="Only published teaching can be retired")
        items = [i for i in live if i != draft_id]
    name, _ = _actor(request)
    done = {"publish": "published", "retire": "retired"}[action]
    v = storage.set_teaching(items, f"{done} {_kind(d['kind'])} #{draft_id}", name)
    _audit(request, f"{done} a {_kind(d['kind'])}", d["topic"],
           f"{d['text'][:120]} (teaching version {v['id']})" + (" — published although the score dropped"
                                                                if confirm_drop else ""))
    return _teach_summary(v)


@router.post("/admin/api/studio/rollback")
async def studio_rollback(request: Request) -> dict:
    """Make an earlier version's set live again, as a new version (so the rollback itself can be undone)."""
    _require_role(request, "mentor")
    body = await request.json() if (await request.body()) else {}
    live = storage.teach_version()
    target_id = body.get("version") if isinstance(body, dict) else None
    if target_id is None:  # one step back: the version before the live one
        older = [v for v in storage.teach_versions(2) if v["id"] != live["id"]]
        target = older[0] if older else {"id": 0, "items": []}
    elif target_id == 0:
        target = {"id": 0, "items": []}
    else:
        target = storage.get_teach_version(int(target_id)) if isinstance(target_id, int) else None
    if not live["id"]:
        raise HTTPException(status_code=409, detail="Nothing has been published yet")
    if not target or target["id"] >= live["id"]:
        raise HTTPException(status_code=422, detail="Pick an earlier version")
    name, _ = _actor(request)
    v = storage.set_teaching(target["items"], f"rolled back to version {target['id']}", name)
    _audit(request, "rolled back teaching", f"to version {target['id']}",
           f"version {live['id']} → {v['id']} ({len(target['items'])} item{'' if len(target['items']) == 1 else 's'} live)")
    return _teach_summary(v)


# ----- Studio review (app/review.py) -----
def _answer_row(r: dict, labels: dict) -> dict:
    return {"id": r["id"], "ts": r["ts"], "question": r["question"], "answer": r["answer"],
            "factcheck": r.get("factcheck"), "tester": _tester(r.get("owner"), labels), "profile_id": r["profile_id"],
            "profile_name": r.get("profile_name"), "model_label": config.label(r["model"]) if r.get("model") else None,
            "words": r.get("words")}


@router.get("/admin/api/review/queue")
def review_queue(request: Request) -> dict:
    from app import review
    _require_role(request, "mentor", "astrologer")
    q = review.queue(storage.review_candidates())
    labels = storage.owner_code_labels()
    counts = {k: sum(r["reason"] == k for r in q) for k in review.REASONS}
    return {"counts": counts | {"total": len(q)},
            "items": [_answer_row(r, labels) | {k: r[k] for k in ("reason", "reason_text", "topics")}
                      | {"check_set": review.check_set(r["question"])[0]} for r in q[:50]]}


def _checks(question: str | None) -> dict:
    from app import review
    name, checks, tags = review.check_set(question)
    return {"check_set": name, "checks": [{"key": k, "name": n} for k, n in checks], "tags": tags}


@router.get("/admin/api/review/{usage_id}")
def review_card(usage_id: int, request: Request) -> dict:
    """One answer to review: the question and tester, a short chart summary (Lagna, Moon, the Dasha running when
    it was asked), the chart facts Astropositivism is given, the KP verdicts, the answer and the fact check."""
    from datetime import datetime
    from app import ask, chat
    from app.transit_view import dasha_on
    _require_role(request, "mentor", "astrologer")
    r = storage.get_answer(usage_id)
    if not r or r["kind"] != "llm" or not r.get("answer"):
        raise HTTPException(status_code=404, detail="Answer not found")
    out = _answer_row(r, storage.owner_code_labels()) | {"review": storage.get_review(usage_id), "chart": None} \
        | _checks(r["question"])
    profile = storage.get(r["profile_id"]) if r["profile_id"] else None
    if profile:
        c = profile["chart"]
        moon = c["grahas"]["Moon"]
        out["chart"] = {"name": profile["name"], "lagna": c["lagna"]["sign"],
                        "moon": f"{moon['sign']} · {moon['nakshatra']} · house {moon['house']}",
                        "dasha": dasha_on(c, datetime.fromisoformat(r["ts"])),
                        "facts": ask.llm_context(profile), "kp": chat.kp_context(profile, r["question"] or "").strip()}
    return out


@router.post("/admin/api/review/{usage_id}", status_code=201)
async def review_save(usage_id: int, request: Request) -> dict:
    from app import review
    _require_role(request, "mentor", "astrologer")
    r = storage.get_answer(usage_id)
    if not r or r["kind"] != "llm" or not r.get("answer"):
        raise HTTPException(status_code=404, detail="Answer not found")
    body = await request.json()
    try:
        checks, tags, note = review.clean(body if isinstance(body, dict) else {}, r["question"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    name, _ = _actor(request)
    saved = storage.add_review(usage_id, name, None if request.state.admin else request.state.code_id, checks, tags, note)
    if not saved:
        raise HTTPException(status_code=409, detail="Someone has already reviewed this answer")
    fails = [n for k, n in review.check_set(r["question"])[1] if checks[k] == "fail"]
    _audit(request, "reviewed an answer", (r["question"] or "")[:80],
           ("failed: " + ", ".join(fails) if fails else "all checks passed") + (f"; tags: {', '.join(tags)}" if tags else ""))
    return saved


@router.get("/admin/api/reviews")
def reviews_done(request: Request) -> list[dict]:
    _require_role(request, "mentor", "astrologer")
    labels = storage.owner_code_labels()
    # checks_done: what the reviewer marked; checks: the list it was marked against (reading or remedy)
    return [{**r, "tester": _tester(r.pop("owner"), labels), "checks_done": r["checks"]} | _checks(r["question"])
            for r in storage.reviews()]


# ----- Studio quality (app/quality.py) -----
def _run_view(r: dict) -> dict:
    from app import quality
    return {**r, "drops": quality.drops(r["scores"]) if r["kind"] != "run" else [],
            "model_label": config.label(r["model"]), "judge_label": config.label(r["judge_model"])}


@router.get("/admin/api/quality")
def quality_home(request: Request) -> dict:
    """The test set, what a run would cost, recent runs and the quality dashboard."""
    from collections import Counter
    from app import quality, review
    _require_role(request, "mentor", "astrologer")
    tests = storage.test_set()
    candidates = [d for d in storage.drafts() if d["kind"] == "gold" and d["status"] == "published"
                  and not d["in_test_set"] and d.get("question") and d.get("profile_id")]
    done = storage.reviews(500)
    checks: dict[str, list[int]] = {}
    for r in done:
        names = dict(review.check_set(r["question"])[1])
        for k, v in r["checks"].items():
            if v in ("pass", "fail"):
                checks.setdefault(names.get(k, k), [0, 0])[v == "fail"] += 1
    runs = storage.runs(30)
    jk = storage.jk_outcomes()
    matched = lambda v, o: ((v in ("yes", "likely") and o in ("happened", "partly")) or (v == "no" and o == "not")
                            or (v == "mixed" and o == "partly"))
    return {
        "test_set": [{k: t[k] for k in ("id", "topic", "question", "text", "status", "profile_name", "author")}
                     for t in tests],
        "candidates": [{k: d[k] for k in ("id", "topic", "question")} for d in candidates],
        "estimate": quality.estimate(len(tests)), "max_questions": quality.MAX_QUESTIONS,
        "running": quality.busy(), "runs": [_run_view(r) for r in runs],
        "dashboard": {
            "factcheck": storage.factcheck_rate(30),
            "reviews": len(done),
            "checks": [{"name": n, "pass": p, "fail": f} for n, (p, f) in checks.items()],
            "tags": Counter(t for r in done for t in r["tags"]).most_common(6),
            "jamakkol": {"answered": len(jk), "matched": sum(matched(x["verdict"], x["outcome"]) for x in jk)},
            "scores": [{"id": r["id"], "at": r["created_at"], "score": (r["scores"] or {}).get("overall", {}).get("live"),
                        "version": r["teach_version"]} for r in reversed(runs)
                       if r["kind"] == "run" and r["status"] == "done"],
        },
    }


@router.post("/admin/api/quality/test-set/{draft_id}")
async def quality_test_set(draft_id: int, request: Request) -> dict:
    _require_role(request, "mentor")
    body = await request.json()
    on = bool(isinstance(body, dict) and body.get("on"))
    d = storage.get_draft(draft_id)
    if not d or d["kind"] != "gold":
        raise HTTPException(status_code=404, detail="Gold answer not found")
    if on and (d["status"] != "published" or not d.get("question") or not d.get("profile_id")):
        raise HTTPException(status_code=422, detail="Only a published gold answer with its question and chart can be a "
                                                    "test question")
    out = storage.set_test_set(draft_id, on)
    _audit(request, "added a test question" if on else "removed a test question", d["topic"], (d["question"] or "")[:120])
    return out


@router.post("/admin/api/quality/runs", status_code=201)
async def quality_run(request: Request) -> dict:
    """Start a run: every test question (or one topic's) with the live setup, or live and with drafts."""
    from app import quality
    _require_role(request, "mentor")
    body = (await request.json()) if (await request.body()) else {}
    body = body if isinstance(body, dict) else {}
    if quality.busy():
        raise HTTPException(status_code=409, detail="A run is already going. Wait for it to finish.")
    topic = body.get("topic") or None
    drafts = body.get("drafts") or []
    if not isinstance(drafts, list) or not all(isinstance(x, int) for x in drafts):
        raise HTTPException(status_code=422, detail="drafts must be a list of draft ids")
    gold = quality.test_items([topic] if topic else None)
    if not gold:
        raise HTTPException(status_code=422, detail="No test questions yet" + (f" on {topic}" if topic else ""))
    if len(gold) * (2 if drafts else 1) > quality.MAX_QUESTIONS:
        raise HTTPException(status_code=422, detail=f"That is more than {quality.MAX_QUESTIONS} answers. Pick a topic.")
    name, _ = _actor(request)
    run = quality.start("compare" if drafts else "run", gold, drafts, name, [topic] if topic else None)
    est = quality.estimate(run["total"])
    _audit(request, "started a quality run", topic or "all topics", f"{run['total']} answers, about ${est['cost']}")
    return _run_view(run)


@router.post("/admin/api/quality/gate/{draft_id}", status_code=201)
def quality_gate(draft_id: int, request: Request) -> dict:
    """Before publishing: this draft's topic answered live and with it."""
    from app import quality
    _require_role(request, "mentor")
    d = storage.get_draft(draft_id)
    if not d:
        raise HTTPException(status_code=404, detail="Draft not found")
    if quality.busy():
        raise HTTPException(status_code=409, detail="A run is already going. Wait for it to finish.")
    gold = [g for g in quality.test_items(quality.topics_for(d)) if g["id"] != draft_id][:quality.MAX_QUESTIONS // 2]
    if not gold:
        raise HTTPException(status_code=422, detail="No test questions on this topic")
    name, _ = _actor(request)
    run = quality.start("gate", gold, [draft_id], name, quality.topics_for(d))
    _audit(request, "tested a draft before publishing", d["topic"], f"{len(gold)} test questions")
    return _run_view(run)


@router.get("/admin/api/quality/runs/{run_id}")
def quality_run_view(run_id: int, request: Request) -> dict:
    from app import review
    _require_role(request, "mentor", "astrologer")
    r = storage.get_run(run_id)
    if not r:
        raise HTTPException(status_code=404, detail="Run not found")
    items = storage.eval_items(run_id)
    golds = {g["id"]: g for g in storage.teaching_items(sorted({i["gold_id"] for i in items}))}
    for i in items:
        i["gold"] = (golds.get(i["gold_id"]) or {}).get("text")
        i["checks"] = [{"key": k, "name": n} for k, n in review.check_set(i["question"])[1]]
    return {**_run_view(r), "items": items}


@router.post("/admin/api/quality/items/{item_id}/grade")
async def quality_grade(item_id: int, request: Request) -> dict:
    """An astrologer's own marks on a test answer, shown next to the judge's."""
    from app import review
    _require_role(request, "mentor", "astrologer")
    item = storage.get_eval_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    body = await request.json()
    try:
        checks, _, note = review.clean({**(body if isinstance(body, dict) else {}), "tags": []}, item["question"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc).replace("a problem tag or ", "")) from exc
    name, _ = _actor(request)
    storage.grade_eval_item(item_id, {"checks": checks, "note": note}, name)
    return {"ok": True}


@router.put("/admin/api/limits")
async def save_limits(request: Request) -> dict:
    """The word limit and daily limits: the owner and the Studio admin (mentor) may change them; each change is
    in the change log. The AI model stays with the owner (Settings)."""
    _require_role(request, "mentor")
    body = await request.json()
    if not isinstance(body, dict) or not body or set(body) - set(LIMIT_KEYS):
        raise HTTPException(status_code=422, detail="Send only: " + ", ".join(LIMIT_KEYS))
    before = {k: config.get(k) for k in body}
    try:
        after = config.update(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    changes = [f"{LIMIT_NAMES[k]} {before[k]} → {after[k]}" for k in body if before[k] != after[k]]
    if changes:
        _audit(request, "changed limits", None, "; ".join(changes))
    return {k: after[k] for k in LIMIT_KEYS}


# ----- backups -----
@router.get("/admin/api/backups")
def backups(request: Request) -> dict:
    from app import backup
    _require_admin(request)
    return {"backups": backup.listing(), "keep_days": backup.KEEP_DAYS, "folder": str(backup.folder())}


@router.post("/admin/api/backups")
def backup_now(request: Request) -> dict:
    """Make (or refresh) today's copy now."""
    from app import backup
    _require_admin(request)
    backup.daily(force=True)
    return {"backups": backup.listing(), "keep_days": backup.KEEP_DAYS, "folder": str(backup.folder())}


@router.get("/admin/api/backups/download")
def backup_download(request: Request):
    """A fresh, consistent copy of the whole database to keep somewhere else."""
    from datetime import datetime, timezone
    from starlette.background import BackgroundTask
    from app import backup
    _require_admin(request)
    path = backup.download_copy()
    name = f"simplejyotish-{datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M')}.db"
    return FileResponse(path, filename=name, media_type="application/vnd.sqlite3",
                        background=BackgroundTask(path.unlink, missing_ok=True))


# ----- real-life backtest: everyone's entered events against chance (no names) -----
@router.get("/admin/api/events")
def events_backtest(request: Request) -> dict:
    """How often real events fall in periods the engine supports, against how often chance would (exact-day and
    month dates only; year-only dates are too rough to test)."""
    from datetime import date, datetime, timezone
    from app import karaka_check as KC
    from app import life_events as L
    from app.routes import with_extras
    _require_admin(request)
    today = datetime.now(timezone.utc).date()
    by: dict[str, dict] = {}
    people: set[int] = set()
    for e in storage.all_events():
        if e["precision"] == "year" or not L.KINDS[e["kind"]][1]:
            continue  # a year-only date is too rough; a loss is never read against the chart
        chart = with_extras(e["chart"])
        c = L.check(chart, e["kind"], date.fromisoformat(e["date"]), e["precision"])
        base = L._base_rate(chart, c["topic"], date.fromisoformat(e["request"]["dob"]), today)
        t = by.setdefault(c["topic"], {"topic": c["topic"], "title": L.K.ALL_TOPICS[c["topic"]][0], "events": 0, "fits": 0,
                                       "expected": 0.0, "karaka_fits": 0, "karaka_expected": 0.0})
        t["events"] += 1
        t["fits"] += c["fit"] == "fits"
        t["expected"] += base
        lo, hi = L.span(date.fromisoformat(e["date"]), e["precision"])
        t["karaka_fits"] += KC.check(chart, c["topic"], lo, hi)["fit"] == "fits"
        t["karaka_expected"] += KC.base_rate(chart, c["topic"], date.fromisoformat(e["request"]["dob"]), today)
        people.add(e["profile_id"])
    rows = sorted(by.values(), key=lambda r: -r["events"])
    for r in rows:
        r["expected"], r["karaka_expected"] = round(r["expected"], 1), round(r["karaka_expected"], 1)
    n, fits, exp = sum(r["events"] for r in rows), sum(r["fits"] for r in rows), sum(r["expected"] for r in rows)
    kf, ke = sum(r["karaka_fits"] for r in rows), sum(r["karaka_expected"] for r in rows)
    return {"charts": len(people), "events": n, "fits": fits, "expected": round(exp, 1),
            "lift": round(fits / exp, 2) if exp else None, "by_topic": rows,
            "karaka": {"fits": kf, "expected": round(ke, 1), "lift": round(kf / ke, 2) if ke else None}}


@router.get("/admin/api/sbc-goods")
def sbc_goods_get(request: Request) -> dict:
    _require_role(request, "mentor", "astrologer")
    from app.astro import sbc_goods
    from core.sarvatobhadra import NAK28
    goods = sbc_goods()
    return {"rows": [{"index": k, "nakshatra": n, "goods": goods.get(k, "")} for k, n in enumerate(NAK28)]}


@router.put("/admin/api/sbc-goods")
async def sbc_goods_put(request: Request) -> dict:
    """The astrologer's table of which goods each nakshatra rules, for the Sarvatobhadra market reading."""
    _require_role(request, "mentor", "astrologer")
    body = await request.json()
    if not isinstance(body, dict) or not all(str(k).isdigit() and 0 <= int(k) < 28 and isinstance(v, str)
                                             and len(v) <= 300 for k, v in body.items()):
        raise HTTPException(status_code=422, detail="Expected {nakshatra index 0-27: goods text (max 300 chars)}")
    clean = {str(int(k)): v.strip() for k, v in body.items() if v.strip()}
    storage.set_setting("sbc.goods", json.dumps(clean))
    _audit(request, "sbc_goods", "sarvatobhadra", f"{len(clean)} nakshatras")
    return {"saved": len(clean)}
