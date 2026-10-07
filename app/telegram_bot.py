"""Telegram bot: Sukh onboards people in-chat, sends a free morning guide, and answers questions
(capped per day). People who already use the website can link their saved chart with the ✈️ button."""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

from app import chat, config, guidance, storage

router = APIRouter(tags=["telegram"])

WEBHOOK_PATH = "/telegram/webhook"
COMMANDS = [("today", "Today’s guide"), ("week", "Good and bad days this week"), ("remedies", "Your upay"),
            ("settings", "Morning time, location, birth details"), ("help", "What I can do")]
HELP = ("Ask me anything about your life — for example <i>When is a good time to change jobs?</i>\n\n"
        "/today — today’s guide\n/week — good and bad days this week\n/remedies — your upay\n"
        "/settings — morning time, where you live, birth details")


# ----- Telegram API -----

def _token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def _bot_name() -> str:
    return os.environ.get("TELEGRAM_BOT_NAME", "aiastrolober_bot").strip().lstrip("@")


def webhook_secret(token: str | None = None) -> str:
    """Shared secret Telegram echoes in X-Telegram-Bot-Api-Secret-Token; derived so no extra variable is needed."""
    return hashlib.sha256(f"sj-telegram-webhook:{token or _token()}".encode()).hexdigest()[:48]


def _api(method: str, payload: dict) -> dict:
    req = urllib.request.Request(f"https://api.telegram.org/bot{_token()}/{method}",
                                 data=json.dumps(payload).encode(), headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read() or b"{}")
        except ValueError:
            return {"ok": False}
    except Exception as e:  # network trouble: log and carry on
        print(f"Telegram {method} failed: {e}")
        return {"ok": False}


def to_html(md: str) -> str:
    """Light markdown (as the chat writes it) to the HTML subset Telegram accepts."""
    out = []
    for line in html.escape(md, quote=False).split("\n"):
        h = re.match(r"^#{1,4}\s+(.*)", line)
        if h:
            line = f"<b>{h.group(1)}</b>"
        line = re.sub(r"^\s*[-*•]\s+", "• ", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
        line = re.sub(r"(?<![*\w])[*_]([^*_\n]+?)[*_](?![*\w])", r"<i>\1</i>", line)
        line = re.sub(r"`([^`]+)`", r"<code>\1</code>", line)
        out.append(line)
    return "\n".join(out)


def _chunks(text: str, size: int = 3800) -> list[str]:
    parts, cur = [], ""
    for para in text.split("\n"):
        if len(cur) + len(para) + 1 > size and cur:
            parts.append(cur)
            cur = ""
        cur = f"{cur}\n{para}" if cur else para
    return parts + ([cur] if cur else [])


def send(chat_id: int, text: str, buttons: list[list[tuple[str, str]]] | None = None, raw_html: bool = False) -> None:
    parts = _chunks(text)
    for i, part in enumerate(parts):
        payload = {"chat_id": chat_id, "text": part if raw_html else to_html(part), "parse_mode": "HTML",
                   "disable_web_page_preview": True}
        if buttons and i == len(parts) - 1:
            payload["reply_markup"] = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in buttons]}
        if not _api("sendMessage", payload).get("ok"):  # formatting rejected: plain text
            payload.pop("parse_mode")
            payload["text"] = part
            _api("sendMessage", payload)


# ----- parsing & places -----

DATE_FORMATS = ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y"]


def parse_date(text: str) -> date | None:
    t = re.sub(r"[,]|(?<=\d)(st|nd|rd|th)\b", "", text.strip(), flags=re.I)
    t = re.sub(r"\s+", " ", t)
    for f in DATE_FORMATS:
        try:
            d = datetime.strptime(t, f).date()
        except ValueError:
            continue
        return d if date(1900, 1, 1) <= d <= date.today() else None
    return None


def parse_time(text: str) -> str | None:
    t = text.strip().lower().replace(".", ":")
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t)
    if not m or (m.group(2) is None and not m.group(3)):
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ap:
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if ap == "pm" else 0)
    return f"{h:02d}:{mi:02d}" if h < 24 and mi < 60 else None


def geocode(query: str) -> list[dict]:
    """Open-Meteo geocoding (free, no key). 'Springfield, US' filters by the part after the comma."""
    name, _, hint = (s.strip() for s in query.partition(","))
    url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
        {"name": name, "count": 10, "language": "en"})
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            res = json.loads(r.read()).get("results") or []
    except Exception as e:
        print(f"geocode failed: {e}")
        return []
    out = []
    for p in res:
        label = ", ".join(x for x in (p.get("name"), p.get("admin1"), p.get("country")) if x)
        if hint and hint.lower() not in (label + " " + (p.get("country_code") or "")).lower():
            continue
        if p.get("timezone"):
            out.append({"label": label, "lat": round(p["latitude"], 4), "lon": round(p["longitude"], 4), "tz": p["timezone"]})
    return out[:5]


# ----- onboarding -----

def _intro(name: str) -> str:
    return (f"Namaste{', ' + name if name else ''} 🙏 I’m **Sukh**, the AI Jyotishi of SimpleJyotish.\n"
            "I’ll read your kundli once, then send you a short guide every morning at 8:00 — what the day is good for, "
            "what to avoid, and a simple upay.\n\nThree quick questions (you can change them later in /settings).\n\n"
            "**1 of 3 — your date of birth?**\nFor example: 1990-05-17 · 17.05.1990 · 17 May 1990")


ASK_TIME = ("**2 of 3 — your time of birth?**\nLocal clock time at your birthplace, as on the birth certificate. "
            "For example: 07:05 · 7:05 am · 19:30")
ASK_PLACE = "**3 of 3 — where were you born?**\nType the town or city — add the country if the name is common, e.g. Springfield, US."
UNKNOWN_TIME = [[("🤷 I don’t know", "tob:unknown")]]


def _confirm(chat_id: int, d: dict) -> None:
    storage.tg_save(chat_id, step="confirm", draft=d)
    born = date.fromisoformat(d["dob"]).strftime("%-d %B %Y")
    tob = "time unknown — I’ll use noon" if d.get("tob_unknown") else f"{d['tob']} (local time)"
    send(chat_id, f"Let me check I’ve got this right:\n\n🎂 {born}\n🕑 {tob}\n📍 {d['place']}\n🌍 {d['tz']}",
         [[("✅ Yes, that’s right", "confirm"), ("✏️ Start again", "restart")]])


def _place_step(chat_id: int, u: dict, text: str, live: bool = False) -> None:
    found = geocode(text)
    if not found:
        send(chat_id, "I couldn’t find that place. Try just the city name, or add the country (e.g. Patiala, India).")
        return
    d = {**u["draft"], "choices": found}
    if len(found) == 1:
        return _picked(chat_id, {**u, "draft": d}, 0, live)
    storage.tg_save(chat_id, draft=d)
    pre = "live" if live else "pick"
    send(chat_id, "Which one?", [[(f["label"][:60], f"{pre}:{i}")] for i, f in enumerate(found)])


def _picked(chat_id: int, u: dict, i: int, live: bool) -> None:
    choices = u["draft"].get("choices") or []
    if not 0 <= i < len(choices):
        send(chat_id, "That list has expired — please type the city again.")
        return
    p = choices[i]
    if live:
        storage.tg_save(chat_id, live_lat=p["lat"], live_lon=p["lon"], live_tz=p["tz"], live_place=p["label"],
                        step="done", draft={})
        send(chat_id, f"📍 Got it — your daily guide will use times for {p['label']}.")
        return
    d = {k: v for k, v in u["draft"].items() if k != "choices"}
    d.update(place=p["label"], lat=p["lat"], lon=p["lon"], tz=p["tz"])
    _confirm(chat_id, d)


def _create_chart(chat_id: int, u: dict) -> None:
    from app.routes import chart as compute_chart
    from app.schemas import ChartRequest
    d = u["draft"]
    req = ChartRequest(name=u.get("first_name") or "Me", place=d["place"], dob=d["dob"],
                       tob=("12:00" if d.get("tob_unknown") else d["tob"]) + ":00",
                       lat=d["lat"], lon=d["lon"], tz_name=d["tz"], tob_unknown=bool(d.get("tob_unknown")))
    owner = u.get("owner") or f"tg:{chat_id}"
    profile = storage.save(req.name or "Me", req.model_dump(mode="json"), compute_chart(req), owner=owner)
    storage.tg_save(chat_id, owner=owner, profile_id=profile["id"], step="done", draft={})
    _welcome(chat_id, profile)


def _welcome(chat_id: int, profile: dict) -> None:
    _api("sendChatAction", {"chat_id": chat_id, "action": "typing"})
    send(chat_id, guidance.first_reading(profile, datetime.now(timezone.utc)))
    u = storage.tg_get(chat_id)
    send_today(chat_id, u, profile, intro="Here’s your guide for today:")
    limit = config.get("telegram_daily_limit")
    send(chat_id, HELP + (f"\n\nYou can ask me {limit} questions a day; the morning guide is free." if limit else ""), raw_html=True)


# ----- guides -----

def _where(u: dict, profile: dict) -> tuple[float, float, str, str]:
    if u.get("live_tz"):
        return u["live_lat"], u["live_lon"], u["live_tz"], u.get("live_place") or ""
    r = profile["request"]
    return r["lat"], r["lon"], r["tz_name"], (r.get("place") or "").split(",")[0] or "your birthplace"


def _profile(u: dict | None) -> dict | None:
    if not u or not u.get("profile_id"):
        return None
    return storage.get(u["profile_id"], owner=u.get("owner") or None)


def send_today(chat_id: int, u: dict, profile: dict, intro: str = "", claim: bool = True) -> None:
    lat, lon, tz, place = _where(u, profile)
    today = datetime.now(ZoneInfo(tz)).date()
    if claim:
        storage.tg_claim_send(chat_id, today.isoformat())
    send(chat_id, (intro + "\n\n" if intro else "") + guidance.day_guide(profile, today, lat, lon, tz, place))


# ----- chat -----

def _quota_left(owner: str | None) -> int:
    limit = config.get("telegram_daily_limit")
    if storage.llm_requests_today() >= config.get("daily_limit_total"):
        return 0
    return max(0, limit - storage.llm_requests_today(owner))


def _ask(chat_id: int, profile: dict, text: str) -> None:
    if _quota_left(profile.get("owner")) <= 0:
        send(chat_id, "You’ve used today’s questions with me 🙏 Your morning guide still comes as usual — ask again tomorrow. "
                      "Meanwhile /today and /week are always free.")
        return
    _api("sendChatAction", {"chat_id": chat_id, "action": "typing"})
    try:
        reply = chat.chat(profile, text)["reply"]
    except Exception as e:
        print(f"Telegram chat failed: {e}")
        reply = ""
    send(chat_id, reply or "Sorry, something went wrong on my side. Please try again in a moment.")


# ----- update handling -----

def _settings(chat_id: int, u: dict) -> None:
    on = u.get("active", 1)
    send(chat_id, "⚙️ **Settings**", [
        [(f"⏰ Morning guide at {u.get('send_time', '08:00')}", "set:time")],
        [(f"📍 Where I live: {u.get('live_place') or 'my birthplace'}", "set:live")],
        [("🎂 Change birth details", "set:birth")],
        [("🔕 Pause morning guide", "set:pause") if on else ("🔔 Resume morning guide", "set:resume")],
    ])


def handle_command(chat_id: int, u: dict | None, cmd: str, arg: str, first_name: str) -> None:
    if cmd == "start":
        if arg:
            link = storage.get_setting(f"telegram_link_{arg}")
            if not link:
                send(chat_id, "That link has expired. Tap the ✈️ button in SimpleJyotish again for a fresh one.")
                return
            storage.set_setting(f"telegram_link_{arg}", "")
            owner, _, pid = link.partition("|")
            prof = (storage.get(int(pid), owner=owner or None) if pid else None) or \
                   next(iter(storage.list_all(owner or None)), None)
            if not prof:
                send(chat_id, "I couldn’t find a saved chart. Please save one on SimpleJyotish and try again.")
                return
            storage.tg_save(chat_id, owner=owner or None, profile_id=prof["id"], first_name=first_name, step="done", draft={})
            send(chat_id, f"✓ Linked to {prof['name']}’s chart.")
            _welcome(chat_id, storage.get(prof["id"]))
            return
        if u and u["step"] == "done" and _profile(u):
            send(chat_id, f"Welcome back{', ' + first_name if first_name else ''} 🙏\n\n" + HELP, raw_html=True)
            return
        storage.tg_save(chat_id, first_name=first_name, step="date", draft={})
        send(chat_id, _intro(first_name))
        return
    profile = _profile(u)
    if cmd in ("today", "week", "remedies") and not profile:
        send(chat_id, "Let’s set up your kundli first — send /start.")
        return
    if cmd == "today":
        send_today(chat_id, u, profile, claim=False)
    elif cmd == "week":
        lat, lon, tz, _ = _where(u, profile)
        send(chat_id, guidance.week_summary(profile, datetime.now(ZoneInfo(tz)).date(), lat, lon, tz))
    elif cmd == "remedies":
        send(chat_id, guidance.remedies(profile, datetime.now(timezone.utc)))
    elif cmd == "settings":
        if not u or u["step"] != "done":
            send(chat_id, "Let’s finish setting up first — send /start.")
        else:
            _settings(chat_id, u)
    elif cmd == "stop":
        if u:
            storage.tg_save(chat_id, active=0)
        send(chat_id, "🔕 Morning guide paused. Turn it back on anytime in /settings.")
    else:
        send(chat_id, HELP, raw_html=True)


def handle_callback(chat_id: int, u: dict | None, data: str) -> None:
    if not u:
        return
    kind, _, val = data.partition(":")
    if data == "tob:unknown" and u["step"] == "time":
        storage.tg_save(chat_id, step="place", draft={**u["draft"], "tob": "12:00", "tob_unknown": True})
        send(chat_id, "No problem — I’ll use noon. Your rising sign may be off, but Moon, nakshatra and daśā are still reliable.\n\n" + ASK_PLACE)
    elif kind in ("pick", "live") and val.isdigit():
        _picked(chat_id, u, int(val), kind == "live")
    elif data == "confirm" and u["step"] == "confirm":
        send(chat_id, "🔮 Reading your kundli…")
        _create_chart(chat_id, u)
    elif data == "restart":
        storage.tg_save(chat_id, step="date", draft={})
        send(chat_id, "Let’s start again.\n\n**1 of 3 — your date of birth?**\nFor example: 1990-05-17 · 17.05.1990 · 17 May 1990")
    elif data == "set:time":
        hours = ["05:00", "06:00", "07:00", "08:00", "09:00", "10:00"]
        send(chat_id, "What time should your morning guide arrive?", [[(h, f"time:{h}") for h in hours[:3]], [(h, f"time:{h}") for h in hours[3:]]])
    elif kind == "time" and re.fullmatch(r"\d\d:00", val):
        storage.tg_save(chat_id, send_time=val, active=1)
        send(chat_id, f"⏰ Done — your guide will arrive at {val} each morning.")
    elif data == "set:live":
        storage.tg_save(chat_id, step="live", draft={})
        send(chat_id, "Which city do you live in now? I’ll use its sunrise and times for your daily guide.")
    elif data == "set:birth":
        storage.tg_save(chat_id, step="date", draft={})
        send(chat_id, "Let’s update your birth details.\n\n**1 of 3 — your date of birth?**\nFor example: 1990-05-17 · 17.05.1990")
    elif data in ("set:pause", "set:resume"):
        storage.tg_save(chat_id, active=int(data == "set:resume"))
        send(chat_id, "🔔 Morning guide is back on." if data == "set:resume" else "🔕 Morning guide paused.")


def handle_text(chat_id: int, u: dict | None, text: str) -> None:
    step = (u or {}).get("step")
    if not u or (step != "done" and step not in ("date", "time", "place", "pick", "confirm", "live")):
        send(chat_id, "Namaste 🙏 Send /start and I’ll set up your kundli.")
        return
    if step == "date":
        d = parse_date(text)
        if not d:
            send(chat_id, "I couldn’t read that date. Please send it like 1990-05-17 or 17 May 1990.")
            return
        storage.tg_save(chat_id, step="time", draft={**u["draft"], "dob": d.isoformat()})
        send(chat_id, ASK_TIME, UNKNOWN_TIME)
    elif step == "time":
        t = parse_time(text)
        if not t:
            send(chat_id, "I couldn’t read that time. Please send it like 07:05, 7:05 am or 19:30.", UNKNOWN_TIME)
            return
        storage.tg_save(chat_id, step="place", draft={**u["draft"], "tob": t, "tob_unknown": False})
        send(chat_id, ASK_PLACE)
    elif step in ("place", "pick"):
        storage.tg_save(chat_id, step="place")
        _place_step(chat_id, u, text)
    elif step == "live":
        _place_step(chat_id, u, text, live=True)
    elif step == "confirm":
        send(chat_id, "Please tap ✅ if the details are right, or ✏️ to start again.")
    else:
        profile = _profile(u)
        if not profile:
            send(chat_id, "I couldn’t find your chart — send /start to set it up again.")
            return
        _ask(chat_id, profile, text)


def handle_update(update: dict) -> None:
    try:
        cb = update.get("callback_query")
        if cb:
            _api("answerCallbackQuery", {"callback_query_id": cb["id"]})
            chat_id = (cb.get("message") or {}).get("chat", {}).get("id")
            if chat_id:
                handle_callback(chat_id, storage.tg_get(chat_id), cb.get("data") or "")
            return
        msg = update.get("message") or {}
        chat_id, text = (msg.get("chat") or {}).get("id"), (msg.get("text") or "").strip()
        if not chat_id or not text:
            return
        u = storage.tg_get(chat_id)
        m = re.match(r"^/(\w+)(?:@\w+)?\s*(.*)$", text, re.S)
        if m:
            handle_command(chat_id, u, m.group(1).lower(), m.group(2).strip(), (msg.get("from") or {}).get("first_name") or "")
        else:
            handle_text(chat_id, u, text)
    except Exception as e:  # never let one bad update break the webhook
        print(f"Telegram update failed: {e!r}")


# ----- HTTP -----

class LinkRequest(BaseModel):
    profile_id: int | None = None


@router.post("/api/telegram/link")
def telegram_link(request: Request, body: LinkRequest | None = None) -> dict:
    if not _token():
        raise HTTPException(status_code=503, detail="Telegram bot not configured. Set TELEGRAM_BOT_TOKEN in Railway.")
    owner = request.state.owner
    if not owner:
        raise HTTPException(status_code=401, detail="Sign in with an access code to link Telegram.")
    token = secrets.token_urlsafe(24)
    pid = body.profile_id if body and body.profile_id and storage.get(body.profile_id, owner=owner) else None
    storage.set_setting(f"telegram_link_{token}", f"{owner}|{pid or ''}")
    return {"deep_link": f"https://t.me/{_bot_name()}?start={token}", "bot_name": _bot_name()}


@router.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request, background: BackgroundTasks) -> dict:
    if not _token() or not secrets.compare_digest(
            request.headers.get("x-telegram-bot-api-secret-token", ""), webhook_secret()):
        raise HTTPException(status_code=403, detail="Forbidden")
    background.add_task(handle_update, await request.json())
    return {"ok": True}


# ----- startup: webhook, commands, morning scheduler -----

def due(u: dict, now_utc: datetime, tz: str) -> str | None:
    """Local date to send for, if this user's morning guide is due (within 3 hours of their time)."""
    local = now_utc.astimezone(ZoneInfo(tz))
    hh, mm = map(int, (u.get("send_time") or "08:00").split(":"))
    start = local.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if start <= local < start + timedelta(hours=3) and u.get("last_sent") != local.date().isoformat():
        return local.date().isoformat()
    return None


def morning_tick(now_utc: datetime | None = None) -> int:
    now_utc = now_utc or datetime.now(timezone.utc)
    sent = 0
    for u in storage.tg_ready():
        profile = _profile(u)
        if not profile:
            continue
        _, _, tz, _ = _where(u, profile)
        day = due(u, now_utc, tz)
        if day and storage.tg_claim_send(u["chat_id"], day):
            try:
                send_today(u["chat_id"], u, profile, intro=f"Good morning{', ' + u['first_name'] if u.get('first_name') else ''} ☀️", claim=False)
                sent += 1
            except Exception as e:
                print(f"Morning guide failed for {u['chat_id']}: {e!r}")
    return sent


def _scheduler() -> None:
    while True:
        try:
            morning_tick()
        except Exception as e:
            print(f"Morning scheduler error: {e!r}")
        time.sleep(60)


def register_webhook() -> None:
    """Point Telegram at this deployment and start the morning scheduler (Railway exposes its domain)."""
    domain = os.environ.get("TELEGRAM_WEBHOOK_BASE") or os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    if not _token() or not domain:
        return
    base = domain if domain.startswith("http") else f"https://{domain}"

    def run() -> None:
        r = _api("setWebhook", {"url": base.rstrip("/") + WEBHOOK_PATH, "secret_token": webhook_secret(),
                                "allowed_updates": ["message", "callback_query"]})
        print(f"Telegram webhook {'registered' if r.get('ok') else 'NOT registered: ' + str(r.get('description'))}")
        _api("setMyCommands", {"commands": [{"command": c, "description": d} for c, d in COMMANDS]})

    threading.Thread(target=run, daemon=True).start()
    threading.Thread(target=_scheduler, daemon=True).start()
