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
    if not request.state.admin:
        raise HTTPException(status_code=403, detail="Admin access required")


def _tester(owner: str | None, labels: dict[str, str] | None = None) -> str:
    if not owner:
        return "Local"
    label = (labels or {}).get(owner)
    return f"{label} · {owner[:6]}" if label else f"Tester {owner[:6]}"


def _cost(rows: list[dict]) -> float:
    return round(sum(config.cost(r["model"], r["inp"], r["out"], r["cr"], r["cw"]) or 0 for r in rows), 4)


@router.get("/me")
def me(request: Request) -> dict:
    return {"admin": bool(request.state.admin), "gated": access.enabled()}


@router.get("/admin")
def admin_page(request: Request):
    if not request.state.admin:
        return HTMLResponse(access.login_page(admin=True))
    return FileResponse(_PAGE, media_type="text/html", headers={"Cache-Control": "no-cache"})


@router.get("/admin/api/overview")
def overview(request: Request) -> dict:
    _require_admin(request)
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
    _require_admin(request)
    rows = storage.recent_queries(max(1, min(limit, 200)), before_id)
    labels = storage.owner_code_labels()
    for r in rows:
        r["tester"] = _tester(r.pop("owner"), labels)
        r["model_label"] = config.label(r["model"])
        r["cost"] = config.cost(r["model"], r["input_tokens"], r["output_tokens"], r["cache_read_tokens"],
                                r["cache_write_tokens"]) if r["kind"] == "llm" else 0.0
    return rows


@router.put("/admin/api/queries/{query_id}/remarks")
async def save_remarks(request: Request, query_id: int) -> dict:
    _require_admin(request)
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
    _require_admin(request)
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
