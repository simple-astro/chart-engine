"""Admin page and its API: settings, usage and cost, testers, and the question log."""
from __future__ import annotations

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
    """The owner only (settings, tester codes, backups, the remedy library for now)."""
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
        "today": {"paid_questions": sum(r["n"] for r in today), "cost": _cost(today)},
        "all_time": {"paid_questions": sum(r["n"] for r in ever), "cost": _cost(ever)},
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
    _require_admin(request)
    return {"counts": library.counts(), "items": library.list_items(kind, status)}


@router.post("/admin/api/remedies/import")
async def remedy_import(request: Request) -> dict:
    from app.remedies import library
    from app.remedies.schema import Invalid
    _require_admin(request)
    try:
        return library.import_items(_parse_items(await request.json()))
    except Invalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/admin/api/remedies/{kind}/{slug}")
async def remedy_edit(kind: str, slug: str, request: Request) -> dict:
    from app.remedies import library
    from app.remedies.schema import STATUSES, Invalid
    _require_admin(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Expected a JSON object")
    status = body.get("review_status")
    if status is not None and status not in STATUSES:
        raise HTTPException(status_code=422, detail=f"review_status must be one of {', '.join(STATUSES)}")
    data = body.get("data")
    if data is not None and not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="data must be an object")
    try:
        item = library.update_item(kind, slug, data=data, review_status=status)
    except Invalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Not found")
    return item


@router.get("/admin/api/remedies/export")
def remedy_export(request: Request) -> dict:
    """Everything with its review status, to save back into the private content repo."""
    from app.remedies import library
    _require_admin(request)
    keep = lambda i: {k: v for k, v in i.items() if k not in ("version", "updated_at")}
    return {"items": [keep(i) for i in library.list_items()]}


# ----- compare two models on one chart and question (nothing is saved to the user's chat) -----
@router.get("/admin/api/profiles")
def all_profiles(request: Request) -> list[dict]:
    _require_role(request, "mentor", "astrologer")  # the Playground's chart picker
    labels = storage.owner_code_labels()
    return [{"id": p["id"], "name": p["name"], "dob": p["request"].get("dob"),
             "tester": _tester(p.get("owner"), labels) if p.get("owner") else "local"} for p in storage.list_all(None)]


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
        runs.append({"label": str(v.get("label") or ("Live" if i == 0 else "Test"))[:40], "model": model,
                     "test": {"word_limit": wl, "instruction": ins or None}})
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


@router.post("/admin/api/studio/drafts", status_code=201)
async def studio_add_draft(request: Request) -> dict:
    from app.usage import TOPICS
    _require_role(request, "mentor", "astrologer")
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Expected a JSON object")
    kind, topic, text = body.get("kind"), body.get("topic") or "General", (body.get("text") or "").strip()
    if kind not in ("gold", "lesson"):
        raise HTTPException(status_code=422, detail="kind must be gold or lesson")
    if topic not in ["General"] + [t for t, _ in TOPICS]:
        raise HTTPException(status_code=422, detail="Unknown topic")
    if not 10 <= len(text) <= (4000 if kind == "gold" else 600):
        raise HTTPException(status_code=422, detail="A lesson needs 10–600 characters; a gold answer 10–4000")
    name, _ = _actor(request)
    d = storage.add_draft(kind, topic, text, name, question=(body.get("question") or None),
                          answer=(body.get("answer") or None), profile_id=body.get("profile_id"))
    _audit(request, "saved a draft " + ("gold answer" if kind == "gold" else "lesson"), topic, text[:120])
    return d


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
    from app import life_events as L
    from app.routes import with_extras
    _require_admin(request)
    today = datetime.now(timezone.utc).date()
    by: dict[str, dict] = {}
    people: set[int] = set()
    for e in storage.all_events():
        if e["precision"] == "year":
            continue
        chart = with_extras(e["chart"])
        c = L.check(chart, e["kind"], date.fromisoformat(e["date"]), e["precision"])
        base = L._base_rate(chart, c["topic"], date.fromisoformat(e["request"]["dob"]), today)
        t = by.setdefault(c["topic"], {"topic": c["topic"], "title": L.K.TOPICS[c["topic"]][0], "events": 0, "fits": 0, "expected": 0.0})
        t["events"] += 1
        t["fits"] += c["fit"] == "fits"
        t["expected"] += base
        people.add(e["profile_id"])
    rows = sorted(by.values(), key=lambda r: -r["events"])
    for r in rows:
        r["expected"] = round(r["expected"], 1)
    n, fits, exp = sum(r["events"] for r in rows), sum(r["fits"] for r in rows), sum(r["expected"] for r in rows)
    return {"charts": len(people), "events": n, "fits": fits, "expected": round(exp, 1),
            "lift": round(fits / exp, 2) if exp else None, "by_topic": rows}
