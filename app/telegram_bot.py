"""Telegram bot: link a web profile to a Telegram chat, then chat with Sukh there."""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import secrets
import threading
import urllib.error
import urllib.request

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

from app import chat, storage

router = APIRouter(tags=["telegram"])

WEBHOOK_PATH = "/telegram/webhook"
WELCOME = ("Namaste! I’m Sukh, the AI Jyotishi of SimpleJyotish.\n\n"
           "To chat about your kundli here, open SimpleJyotish, load your saved chart, open “Ask Sukh” "
           "and tap the ✈️ button. I’ll know your chart from then on.")


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
        return json.loads(e.read() or b"{}") or {"ok": False}
    except Exception as e:  # network trouble: log and carry on
        print(f"Telegram {method} failed: {e}")
        return {"ok": False}


def to_html(md: str) -> str:
    """The chat replies in light markdown; Telegram accepts a small HTML subset."""
    out = []
    for line in html.escape(md, quote=False).split("\n"):
        h = re.match(r"^#{1,4}\s+(.*)", line)
        if h:
            line = f"<b>{h.group(1)}</b>"
        line = re.sub(r"^\s*[-*•]\s+", "• ", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
        line = re.sub(r"(?<![*\w])\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", line)
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


def send(chat_id: int | str, text: str) -> None:
    for part in _chunks(text):
        r = _api("sendMessage", {"chat_id": chat_id, "text": to_html(part), "parse_mode": "HTML"})
        if not r.get("ok"):  # formatting rejected: fall back to plain text
            _api("sendMessage", {"chat_id": chat_id, "text": part})


def _linked_profile(owner: str, profile_id: str | None) -> dict | None:
    if profile_id:
        p = storage.get(int(profile_id), owner=owner)
        if p:
            return p
    profiles = storage.list_all(owner)
    return storage.get(profiles[0]["id"], owner=owner) if profiles else None


def _reply(chat_id: int, link: str, text: str) -> None:
    owner, _, profile_id = link.partition("|")
    try:
        profile = _linked_profile(owner or None, profile_id or None)
        if not profile:
            send(chat_id, "I couldn’t find a saved chart. Please save one on SimpleJyotish and link again.")
            return
        _api("sendChatAction", {"chat_id": chat_id, "action": "typing"})
        send(chat_id, chat.chat(profile, text)["reply"] or "Sorry, I couldn’t form an answer. Please try again.")
    except Exception as e:
        print(f"Telegram chat failed: {e}")
        send(chat_id, "Sorry, something went wrong on my side. Please try again in a moment.")


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
    msg = (await request.json()).get("message") or {}
    chat_id, text = (msg.get("chat") or {}).get("id"), (msg.get("text") or "").strip()
    if not chat_id or not text:
        return {"ok": True}
    if text.startswith("/start"):
        token = text[len("/start"):].strip()
        link = storage.get_setting(f"telegram_link_{token}") if token else None
        if not link:
            background.add_task(send, chat_id, WELCOME if not token else
                                "That link has expired. Tap the ✈️ button in SimpleJyotish again for a fresh one.")
            return {"ok": True}
        storage.set_setting(f"telegram_link_{token}", "")
        storage.set_setting(f"telegram_chat_{chat_id}", link)
        background.add_task(send, chat_id, "✓ Linked! Namaste — I’m Sukh, your AI Jyotishi. Ask me anything about "
                                           "your career, marriage, money, health or remedies.")
        return {"ok": True}
    link = storage.get_setting(f"telegram_chat_{chat_id}")
    if link:
        background.add_task(_reply, chat_id, link, text)
    else:
        background.add_task(send, chat_id, WELCOME)
    return {"ok": True}


def register_webhook() -> None:
    """Point Telegram at this deployment (Railway exposes its domain) so a new token needs no manual step."""
    domain = os.environ.get("TELEGRAM_WEBHOOK_BASE") or os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    if not _token() or not domain:
        return
    base = domain if domain.startswith("http") else f"https://{domain}"

    def run() -> None:
        r = _api("setWebhook", {"url": base.rstrip("/") + WEBHOOK_PATH, "secret_token": webhook_secret(),
                                "allowed_updates": ["message"], "drop_pending_updates": False})
        print(f"Telegram webhook {'registered' if r.get('ok') else 'NOT registered: ' + str(r.get('description'))}")

    threading.Thread(target=run, daemon=True).start()
