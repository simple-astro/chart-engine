"""Telegram webhook: secret check, linking, and routing chat to the linked chart."""
import pytest
from fastapi.testclient import TestClient

from app import storage, telegram_bot
from app.main import app

BIRTH = {"name": "Asha", "dob": "1990-05-01", "tob": "08:15:00", "lat": 28.6139, "lon": 77.209, "tz_name": "Asia/Kolkata"}


@pytest.fixture
def tg(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:test")
    sent, asked = [], []
    monkeypatch.setattr(telegram_bot, "_api", lambda m, p: sent.append((m, p)) or {"ok": True})
    monkeypatch.setattr(telegram_bot.chat, "chat", lambda prof, text: asked.append((prof["id"], text)) or {"reply": "**Yes**, a good year."})
    c = TestClient(app)
    hook = lambda text, secret=telegram_bot.webhook_secret(): c.post(
        "/telegram/webhook", json={"message": {"chat": {"id": 42}, "text": text}},
        headers={"x-telegram-bot-api-secret-token": secret})
    return c, hook, sent, asked


def texts(sent):
    return [p["text"] for m, p in sent if m == "sendMessage"]


def test_webhook_rejects_wrong_secret(tg):
    _, hook, sent, _ = tg
    assert hook("hi", secret="nope").status_code == 403 and not sent


def test_plain_start_gets_welcome(tg):
    _, hook, sent, _ = tg
    assert hook("/start").status_code == 200
    assert "Sukh" in texts(sent)[0]


def test_link_then_chat_uses_linked_profile(tg):
    c, hook, sent, asked = tg
    first = c.post("/profiles", json=BIRTH).json()["id"]
    second = c.post("/profiles", json={**BIRTH, "name": "Ravi"}).json()["id"]
    link = c.post("/api/telegram/link", json={"profile_id": first})
    # local mode has no owner, so linking needs a signed-in user
    assert link.status_code == 401
    token = "tok123"
    storage.set_setting(f"telegram_link_{token}", f"|{first}")
    hook(f"/start {token}")
    assert "Linked" in texts(sent)[-1]
    hook("Will this year be good for my career?")
    assert asked == [(first, "Will this year be good for my career?")] and second != first
    assert texts(sent)[-1] == "<b>Yes</b>, a good year."
    hook(f"/start {token}")  # links are single use
    assert "expired" in texts(sent)[-1]


def test_to_html_escapes_and_formats():
    assert telegram_bot.to_html("## Career\n- **Do** <this> & *that*") == "<b>Career</b>\n• <b>Do</b> &lt;this&gt; &amp; <i>that</i>"
