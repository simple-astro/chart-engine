"""Telegram bot integration: link web profiles to Telegram chat and enable telegram messaging."""
from __future__ import annotations

import json
import os
import secrets
import urllib.request
import urllib.parse
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

from app import chat, storage

router = APIRouter(tags=["telegram"])

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_BOT_NAME = os.environ.get("TELEGRAM_BOT_NAME", "aiastrolober_bot").strip()


def _send_telegram_message(chat_id: int | str, text: str) -> None:
    """Send a message to a Telegram chat using the Bot API."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode("utf-8")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data)) as resp:
            result = json.loads(resp.read())
            if not result.get("ok"):
                print(f"Telegram API error: {result.get('description')}")
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")


def _process_chat_message(chat_id: int, owner: str, text: str) -> None:
    """Process a message from Telegram: look up the user's profile and send a reply."""
    try:
        profiles = storage.list_all(owner=owner)
        if not profiles:
            _send_telegram_message(chat_id, "No profile found. Please create one on the web app first.")
            return
        profile = storage.get(profiles[0]["id"], owner=owner)
        if not profile:
            _send_telegram_message(chat_id, "Profile not found. Please try again.")
            return
        reply = chat.chat(profile, text)
        _send_telegram_message(chat_id, reply["reply"])
    except Exception as e:
        print(f"Error processing Telegram message: {e}")
        _send_telegram_message(chat_id, f"Sorry, I encountered an error. Please try again.")


class TelegramLinkRequest(BaseModel):
    pass


class TelegramWebhookPayload(BaseModel):
    message: dict | None = None
    update_id: int | None = None


@router.post("/api/telegram/link")
def telegram_link(request: Request) -> dict:
    """Generate a secure deep link to start the Telegram bot and link it to the user's session."""
    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=503, detail="Telegram bot not configured. Set TELEGRAM_BOT_TOKEN in Railway.")
    owner = request.state.owner
    if not owner:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = secrets.token_urlsafe(32)
    storage.set_setting(f"telegram_link_{token}", owner)
    deep_link = f"https://t.me/{TELEGRAM_BOT_NAME}?start={token}"
    return {"deep_link": deep_link, "bot_name": TELEGRAM_BOT_NAME}


@router.post("/telegram/webhook")
def telegram_webhook(payload: TelegramWebhookPayload, background_tasks: BackgroundTasks) -> dict:
    """Handle incoming Telegram messages. /start <token> links the account, subsequent messages are chat."""
    if not payload.message:
        return {"ok": True}
    chat_id = payload.message.get("chat", {}).get("id")
    text = payload.message.get("text", "").strip()
    if not chat_id or not text:
        return {"ok": True}
    owner = None
    if text.startswith("/start "):
        token = text.split(" ", 1)[1].strip()
        owner = storage.get_setting(f"telegram_link_{token}")
        if not owner:
            _send_telegram_message(chat_id, "Invalid link. Please generate a new one from the web app.")
            return {"ok": True}
        storage.set_setting(f"telegram_chat_{chat_id}", owner)
        _send_telegram_message(chat_id, "✓ Your Telegram is linked! You can now chat about your chart here.")
        return {"ok": True}
    owner = storage.get_setting(f"telegram_chat_{chat_id}")
    if not owner:
        _send_telegram_message(chat_id, "Please start by visiting the web app and clicking 'Continue on Telegram'.")
        return {"ok": True}
    background_tasks.add_task(_process_chat_message, chat_id, owner, text)
    return {"ok": True}
