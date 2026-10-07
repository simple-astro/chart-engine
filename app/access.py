"""Tester access gate.

Off unless TESTER_ACCESS_CODES or ADMIN_ACCESS_CODE is set, so local use is unchanged.
When on, an access code unlocks a signed cookie carrying a random owner id: each
browser gets its own private set of profiles and chats. The admin code also
unlocks /usage.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict, deque
from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app import storage

COOKIE = "sj_session"
MAX_AGE = 180 * 24 * 3600
OPEN_PATHS = {"/health", "/version", "/login", "/favicon.ico"}
NEXT_PAGES = {"/admin"}  # where a login form may send the browser afterwards
FAIL_WINDOW, FAIL_PER_IP, FAIL_TOTAL = 15 * 60, 10, 100
_fails: dict[str, deque] = defaultdict(deque)

router = APIRouter(include_in_schema=False)


def _codes() -> list[str]:
    return [c.strip() for c in os.environ.get("TESTER_ACCESS_CODES", "").split(",") if c.strip()]


def _admin_code() -> str:
    return os.environ.get("ADMIN_ACCESS_CODE", "").strip()


def enabled() -> bool:
    return bool(_codes() or _admin_code())


def _eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def check_code(code: str) -> str | None:
    code = code.strip()
    if not code:
        return None
    if _admin_code() and _eq(code, _admin_code()):
        return "admin"
    return "tester" if any(_eq(code, c) for c in _codes()) else None


def _sign(value: str) -> str:
    return hmac.new(storage.secret().encode(), value.encode(), hashlib.sha256).hexdigest()


def make_session(owner: str, admin: bool) -> str:
    value = f"{owner}.{int(admin)}"
    return f"{value}.{_sign(value)}"


def read_session(raw: str) -> tuple[str, bool] | None:
    parts = raw.split(".")
    if len(parts) != 3 or parts[1] not in ("0", "1"):
        return None
    owner, admin, sig = parts
    if not _eq(sig, _sign(f"{owner}.{admin}")):
        return None
    return owner, admin == "1"


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "?")


def _too_many_failures(ip: str) -> bool:
    now = time.monotonic()
    for q in _fails.values():
        while q and now - q[0] > FAIL_WINDOW:
            q.popleft()
    return len(_fails[ip]) >= FAIL_PER_IP or sum(len(q) for q in _fails.values()) >= FAIL_TOTAL


async def gate(request: Request, call_next):
    """Middleware: attach request.state.owner / .admin, or block until a code is entered."""
    request.state.owner, request.state.admin = None, True  # local single-user mode
    if not enabled():
        return await call_next(request)
    session = read_session(request.cookies.get(COOKIE, ""))
    if session:
        request.state.owner, request.state.admin = session
        return await call_next(request)
    request.state.admin = False
    path = request.url.path
    if path in OPEN_PATHS or path.startswith("/static/"):
        return await call_next(request)
    if path == "/":
        return HTMLResponse(login_page())
    if path == "/admin":
        return HTMLResponse(login_page(admin=True))
    return JSONResponse({"detail": "Access code required"}, status_code=401)


@router.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@router.get("/login")
def login_form(request: Request):
    if read_session(request.cookies.get(COOKIE, "")):
        return RedirectResponse("/", status_code=303)
    return HTMLResponse(login_page())


@router.post("/login")
async def login(request: Request):
    ip = _client_ip(request)
    if _too_many_failures(ip):
        return HTMLResponse(login_page("Too many attempts. Please wait 15 minutes and try again."), status_code=429)
    form = parse_qs((await request.body()).decode("utf-8", "replace"))
    code = (form.get("code") or [""])[0]
    nxt = (form.get("next") or ["/"])[0]
    nxt = nxt if nxt in NEXT_PAGES else "/"
    want_admin = nxt == "/admin"
    role = check_code(code)
    if role is None:
        _fails[ip].append(time.monotonic())
        return HTMLResponse(login_page("That code isn't right. Please check it and try again.", admin=want_admin),
                            status_code=401)
    if want_admin and role != "admin":
        return HTMLResponse(login_page("That's a tester code. The admin page needs the admin code.", admin=True),
                            status_code=401)
    existing = read_session(request.cookies.get(COOKIE, ""))
    owner = existing[0] if existing else secrets.token_hex(16)  # keep the same private space
    admin = role == "admin" or bool(existing and existing[1])  # a tester code never removes admin
    resp = RedirectResponse(nxt, status_code=303)
    resp.set_cookie(COOKIE, make_session(owner, admin), max_age=MAX_AGE, httponly=True,
                    samesite="lax", secure=request.headers.get("x-forwarded-proto", request.url.scheme) == "https")
    return resp


def login_page(error: str = "", admin: bool = False) -> str:
    err = f'<p class="err" role="alert">{error}</p>' if error else ""
    if admin:
        intro = "Admin sign-in. Enter your admin code to manage settings and review questions."
        label, hidden, foot = "Admin code", '<input type="hidden" name="next" value="/admin">', \
            '<small><a href="/">Back to the app</a></small>'
    else:
        intro = "This is a private test version. Enter the access code you were given."
        label, hidden = "Access code", ""
        foot = ("<small>The charts you save are private to this browser, so come back on the same browser to "
                "see them. The SimpleJyotish team may review questions and answers to improve the service.</small>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>SimpleJyotish — {label}</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%23d9a54d'/%3E%3Ctext x='16' y='22' font-size='17' text-anchor='middle' fill='%231a1322'%3E%E2%9C%A6%3C/text%3E%3C/svg%3E">
<style>
:root{{--bg:#fbf7ef;--card:#fffdf9;--ink:#241e31;--mut:#6d6682;--acc:#8a5e14;--line:rgba(36,30,49,.12);--bad:#c0392b}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0a0812;--card:#1b162b;--ink:#f1ecf7;--mut:#9f98b8;--acc:#e5bb72;--line:rgba(255,255,255,.1);--bad:#ff8a80}}}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;padding:16px;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
.card{{width:100%;max-width:400px;background:var(--card);border:1px solid var(--line);border-radius:18px;padding:30px}}
h1{{font:600 1.7rem Georgia,serif;margin:0 0 6px}}h1 em{{font-style:normal;color:var(--acc)}}p{{color:var(--mut);margin:0 0 18px}}
label{{display:block;font-size:.78rem;font-weight:600;letter-spacing:.4px;text-transform:uppercase;color:var(--mut);margin-bottom:7px}}
input{{width:100%;padding:12px 14px;border-radius:12px;border:1px solid var(--line);background:var(--bg);color:var(--ink);font:inherit}}
button{{width:100%;margin-top:14px;padding:13px;border:0;border-radius:12px;font:600 1rem system-ui,sans-serif;cursor:pointer;color:#1a1322;background:linear-gradient(140deg,#e0b05f,#c98f2e)}}
.err{{color:var(--bad);font-size:.9rem;margin:0 0 14px}}small{{display:block;margin-top:16px;color:var(--mut);font-size:.8rem}}a{{color:var(--acc)}}
</style></head><body><form class="card" method="post" action="/login">
<h1>Simple<em>Jyotish</em></h1><p>{intro}</p>{err}{hidden}
<label for="code">{label}</label><input id="code" name="code" type="password" autocomplete="off" autofocus required>
<button type="submit">Continue</button>{foot}
</form></body></html>"""
