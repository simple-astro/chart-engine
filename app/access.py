"""Tester access gate.

Off unless TESTER_ACCESS_CODES or ADMIN_ACCESS_CODE is set, so local use is unchanged.
When on, an access code unlocks a signed cookie carrying a random owner id: each
browser gets its own private set of profiles and chats. Tester codes come from the
environment or from codes the admin creates on /admin; a session made with an admin
-created code ends when that code is paused or deleted.

Roles: owner (the admin code), mentor and astrologer (Studio codes, made by the owner or, for astrologers, by a
mentor) and tester. A code's role is looked up on every request, so pausing it takes effect at once.
request.state.admin stays true only for the owner; request.state.role says who is signed in.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app import storage

COOKIE = "sj_session"
SPACE = "sj_space"  # one cookie per role and code remembers that code's private space, so logging out and in keeps charts


def space_cookie(role: str, code_id: int) -> str:
    return f"{SPACE}_{role}_{code_id}"
STUDIO = ("mentor", "astrologer")  # roles that may open the admin page (each sees only its own sections)
MAX_AGE = 180 * 24 * 3600
def _public_panchang(method: str, path: str) -> bool:
    """The free daily panchang page and images (app/daily_panchang.py): GET only, so the POST /panchang API stays private."""
    return method in ("GET", "HEAD") and (path == "/panchang" or (path.startswith("/panchang/") and path.endswith(".png")))


OPEN_PATHS = {"/health", "/version", "/home", "/login", "/logout", "/favicon.ico", "/telegram/webhook"}  # webhook checks its own secret
NEXT_PAGES = {"/admin", "/pro"}  # where a login form may send the browser afterwards
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


def check_code(code: str) -> tuple[str, int] | None:
    """(role, code_id) for a valid code; code_id is 0 for the admin and environment codes."""
    code = code.strip()
    if not code:
        return None
    if _admin_code() and _eq(code, _admin_code()):
        return "admin", 0
    if any(_eq(code, c) for c in _codes()):
        return "tester", 0
    return next(((role, cid) for cid, c, role in storage.active_codes() if _eq(code, c)), None)


def _sign(value: str) -> str:
    return hmac.new(storage.secret().encode(), value.encode(), hashlib.sha256).hexdigest()


def make_session(owner: str, admin: bool, code_id: int = 0) -> str:
    value = f"{owner}.{int(admin)}.{code_id}"
    return f"{value}.{_sign(value)}"


def read_session(raw: str) -> tuple[str, bool, int] | None:
    """(owner, admin, code_id). Sessions issued before code ids existed have 3 parts."""
    parts = raw.split(".")
    if len(parts) == 3:
        parts.insert(2, "")
    if len(parts) != 4 or parts[1] not in ("0", "1") or not (parts[2] == "" or parts[2].isdigit()):
        return None
    owner, admin, cid, sig = parts
    if not _eq(sig, _sign(".".join(p for p in (owner, admin, cid) if p != ""))):
        return None
    return owner, admin == "1", int(cid or 0)


def make_space(owner: str, role: str, code_id: int) -> str:
    value = f"{owner}.{role}.{code_id}"
    return f"{value}.{_sign('space:' + value)}"


def read_space(raw: str, role: str, code_id: int) -> str | None:
    """The owner this browser last had, only for the same kind of code (never another role's or code's space)."""
    parts = raw.split(".")
    if len(parts) != 4 or parts[1] != role or parts[2] != str(code_id):
        return None
    owner, r, cid, sig = parts
    return owner if _eq(sig, _sign(f"space:{owner}.{r}.{cid}")) else None


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
    """Middleware: attach request.state.owner / .admin / .role / .code_id, or block until a code is entered."""
    request.state.owner, request.state.admin, request.state.role, request.state.code_id = None, True, "owner", 0
    if not enabled():  # local single-user mode
        return await call_next(request)
    session = read_session(request.cookies.get(COOKIE, ""))
    role = None
    if session:
        role = "owner" if session[1] else storage.code_role(session[2]) if session[2] else "tester"
    revoked = bool(session and role is None)
    if session and not revoked:
        request.state.owner, request.state.admin = session[0], session[1]
        request.state.role, request.state.code_id = role, session[2]
        return await call_next(request)
    request.state.admin, request.state.role = False, None
    path = request.url.path
    if revoked and path not in OPEN_PATHS and not path.startswith("/static/"):
        msg = "Your access code has been turned off. Please ask for a new one."
        resp = HTMLResponse(login_page(msg), status_code=401) if path == "/" else \
            JSONResponse({"detail": msg}, status_code=401)
        resp.delete_cookie(COOKIE)
        return resp
    if path in OPEN_PATHS or path.startswith("/static/") or _public_panchang(request.method, path):
        return await call_next(request)
    if path == "/":  # signed out: the homepage, whose buttons open the access-code form
        return HTMLResponse(home_page())
    if path == "/admin":
        return HTMLResponse(login_page(admin=True))
    if path == "/pro":
        return HTMLResponse(login_page(admin=True, nxt="/pro"))
    return JSONResponse({"detail": "Access code required"}, status_code=401)


@router.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@router.get("/login")
def login_form(request: Request):
    if not enabled():  # no access codes here (local use): nothing to log in to
        nxt = request.query_params.get("next", "/")
        return RedirectResponse(nxt if nxt in NEXT_PAGES else "/", status_code=303)
    if read_session(request.cookies.get(COOKIE, "")):
        return RedirectResponse("/", status_code=303)
    return HTMLResponse(login_page())


@router.post("/login")
async def login(request: Request):
    if not enabled():  # local use: no codes exist, so go straight in instead of rejecting every code
        form = parse_qs((await request.body()).decode("utf-8", "replace"))
        nxt = (form.get("next") or ["/"])[0]
        return RedirectResponse(nxt if nxt in NEXT_PAGES else "/", status_code=303)
    ip = _client_ip(request)
    if _too_many_failures(ip):
        return HTMLResponse(login_page("Too many attempts. Please wait 15 minutes and try again."), status_code=429)
    form = parse_qs((await request.body()).decode("utf-8", "replace"))
    code = (form.get("code") or [""])[0]
    nxt = (form.get("next") or ["/"])[0]
    nxt = nxt if nxt in NEXT_PAGES else "/"
    want_admin = nxt in ("/admin", "/pro")  # both need an admin, mentor or astrologer code
    found = check_code(code)
    role, code_id = found or (None, 0)
    if role is None:
        _fails[ip].append(time.monotonic())
        return HTMLResponse(login_page("That code isn't right. Please check it and try again.", admin=want_admin, nxt=nxt),
                            status_code=401)
    if want_admin and role != "admin" and role not in STUDIO:
        page = "Pro dashboard" if nxt == "/pro" else "admin page"
        return HTMLResponse(login_page(f"That's a tester code. The {page} needs an admin, mentor or astrologer code.",
                                       admin=True, nxt=nxt), status_code=401)
    existing = read_session(request.cookies.get(COOKIE, ""))
    # keep the same private space: from the open session, else the one this browser had before logging out
    owner = existing[0] if existing else read_space(request.cookies.get(space_cookie(role, code_id), ""), role, code_id) or secrets.token_hex(16)
    admin = role == "admin" or bool(existing and existing[1])  # a tester code never removes admin
    if code_id:
        storage.note_code_login(code_id, owner)
    resp = RedirectResponse(nxt, status_code=303)
    resp.set_cookie(COOKIE, make_session(owner, admin, 0 if admin else code_id), max_age=MAX_AGE, httponly=True,
                    samesite="lax", secure=request.headers.get("x-forwarded-proto", request.url.scheme) == "https")
    return resp


TITHIS = ["Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi", "Saptami", "Ashtami", "Navami",
          "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi"]
_HOME = Path(__file__).resolve().parent / "home.html"
_today_chip: tuple[str, str] = ("", "")


def today_chip() -> str:
    """'Today in India · Shukla Ekadashi · Shatabhisha': the day's tithi and nakshatra at sunrise in Delhi."""
    global _today_chip
    from datetime import datetime
    from zoneinfo import ZoneInfo
    day = datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
    if _today_chip[0] != day:
        try:
            from datetime import date
            from core.panchang import compute_panchang
            p = compute_panchang(date.fromisoformat(day), 28.6139, 77.209, "Asia/Kolkata")
            n = p.tithi_number
            tithi = "Purnima" if n == 15 else "Amavasya" if n == 30 else f"{p.paksha} {TITHIS[(n - 1) % 15]}"
            _today_chip = (day, f"Today in India · {tithi} · {p.nakshatra}")
        except Exception:  # the page must still load if the panchang can't be worked out
            return "Today in India"
    return _today_chip[1]


def home_page() -> str:
    return _HOME.read_text().replace("{{TODAY}}", today_chip())


@router.get("/home")
def home():
    """The homepage, for anyone (signed-out visitors also get it at /)."""
    return HTMLResponse(home_page(), headers={"Cache-Control": "no-cache"})


@router.post("/logout")
def logout(request: Request):
    """End this browser's session. The private space is remembered for the same code, so the charts are still
    there after signing back in; nobody else's code can open them."""
    session = read_session(request.cookies.get(COOKIE, ""))
    resp = Response(status_code=204)
    resp.delete_cookie(COOKIE)
    if session:
        owner, admin, cid = session
        role = "admin" if admin else (storage.code_role(cid) if cid else None) or "tester"
        resp.set_cookie(space_cookie(role, cid), make_space(owner, role, cid), max_age=MAX_AGE, httponly=True, samesite="lax",
                        secure=request.headers.get("x-forwarded-proto", request.url.scheme) == "https")
    return resp


def login_page(error: str = "", admin: bool = False, nxt: str = "/admin") -> str:
    err = f'<p class="err" role="alert">{error}</p>' if error else ""
    if admin:
        intro = ("Pro dashboard sign-in. Enter your astrologer, mentor or admin code." if nxt == "/pro" else
                 "Admin sign-in. Enter your admin code to manage settings and review questions.")
        label, hidden, foot = "Astrologer code" if nxt == "/pro" else "Admin code", \
            f'<input type="hidden" name="next" value="{nxt if nxt in NEXT_PAGES else "/admin"}">', \
            '<small><a href="/">Back to the app</a></small>'
    else:
        intro = "This is a private test version. Enter the access code you were given."
        label, hidden = "Access code", ""
        foot = ("<small>The charts you save are private to this browser, so come back on the same browser to "
                "see them. The SimpleJyotish team may review questions and answers, and which sections people open, to "
                "improve the service.</small>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="theme-color" content="#fbf7ef" media="(prefers-color-scheme: light)"><meta name="theme-color" content="#0a0907" media="(prefers-color-scheme: dark)"><title>SimpleJyotish — {label}</title>
<link rel="icon" type="image/svg+xml" href="/static/sun.svg">
<link rel="apple-touch-icon" href="/static/apple-touch-icon.png">
<style>
:root{{--bg:#fbf7ef;--card:#fffdf9;--ink:#241e31;--mut:#6d6682;--acc:#8a5e14;--line:rgba(36,30,49,.12);--bad:#c0392b}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0a0907;--card:#14120f;--ink:#f3eee4;--mut:#a29a8b;--acc:#e5bb72;--line:rgba(238,224,196,.11);--bad:#ff8a80}}}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;padding:16px;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
.card{{width:100%;max-width:400px;background:var(--card);border:1px solid var(--line);border-radius:18px;padding:30px}}
h1{{font:600 1.7rem Georgia,serif;margin:0 0 6px}}h1 em{{font-style:normal;color:var(--acc)}}p{{color:var(--mut);margin:0 0 18px}}
label{{display:block;font-size:.78rem;font-weight:600;letter-spacing:.4px;text-transform:uppercase;color:var(--mut);margin-bottom:7px}}
input{{width:100%;padding:12px 14px;border-radius:12px;border:1px solid var(--line);background:var(--bg);color:var(--ink);font:inherit;font-size:16px}}
button{{width:100%;margin-top:14px;padding:13px;border:0;border-radius:12px;font:600 1rem system-ui,sans-serif;cursor:pointer;color:#241903;background:linear-gradient(140deg,#e0b05f,#c98f2e)}}
.logo{{display:block;width:72px;height:72px;margin:0 0 12px}}.err{{color:var(--bad);font-size:.9rem;margin:0 0 14px}}small{{display:block;margin-top:16px;color:var(--mut);font-size:.8rem}}a{{color:var(--acc)}}
</style></head><body><form class="card" method="post" action="/login">
<img class="logo" src="/static/sun.svg" alt=""><h1>Simple<em>Jyotish</em></h1><p>{intro}</p>{err}{hidden}
<label for="code">{label}</label><input id="code" name="code" type="password" autocomplete="off" autofocus required>
<button type="submit">Continue</button>{foot}
</form></body></html>"""
