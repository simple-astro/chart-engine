"""The Pro dashboard for professional astrologers: a desktop page of widgets (/pro), the tables it needs beyond the
chart itself, and each astrologer's saved layout. Open to the owner and to mentor and astrologer codes."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import storage

router = APIRouter(include_in_schema=False)
_PAGE = Path(__file__).resolve().parent / "static" / "pro.html"
PRO_ROLES = ("owner", "mentor", "astrologer")


def _role(request: Request) -> str | None:
    return "owner" if request.state.admin else getattr(request.state, "role", None)


def _layout_key(request: Request) -> str:
    """One saved layout per astrologer: their code when they sign in with one, else this browser's private space."""
    cid = getattr(request.state, "code_id", 0) or 0
    return f"pro_layout_code_{cid}" if cid else f"pro_layout_{request.state.owner or 'owner'}"


@router.get("/pro")
def pro_page(request: Request):
    if _role(request) not in PRO_ROLES:
        return RedirectResponse("/", status_code=303)  # testers keep the everyday app
    from app.main import stamped
    return HTMLResponse(stamped(_PAGE), headers={"Cache-Control": "no-cache"})


@router.get("/pro/api/tables/{profile_id}")
def pro_tables(profile_id: int, request: Request) -> dict:
    """Avasthas, friendships, Vimshopaka, upagrahas and Sade Sati for one of the caller's charts."""
    from app.profiles import _require
    from app.routes import with_extras
    from core.pro_tables import pro_tables as tables
    if _role(request) not in PRO_ROLES:
        raise HTTPException(status_code=403, detail="The Pro dashboard is for astrologers")
    p = _require(profile_id, request)
    return tables(with_extras(p["chart"]))


@router.get("/pro/api/layout")
def get_layout(request: Request) -> dict:
    raw = storage.get_setting(_layout_key(request))
    return json.loads(raw) if raw else {"widgets": None}


@router.put("/pro/api/layout")
async def put_layout(request: Request) -> dict:
    if _role(request) not in PRO_ROLES:
        raise HTTPException(status_code=403, detail="The Pro dashboard is for astrologers")
    body = await request.json()
    widgets = body.get("widgets")
    ok = isinstance(widgets, list) and len(widgets) <= 200 and all(
        isinstance(w, dict) and isinstance(w.get("id"), str) and len(w["id"]) <= 40 and w.get("w") in (1, 2, 3, 4)
        for w in widgets)
    if not ok:
        raise HTTPException(status_code=422, detail="Expected widgets: [{id, w: 1-4}]")
    clean = {"widgets": [{"id": w["id"], "w": w["w"]} for w in widgets], "preset": str(body.get("preset") or "")[:30]}
    storage.set_setting(_layout_key(request), json.dumps(clean))
    return clean
