"""Telegram bot: webhook secret, in-chat onboarding, linking, commands, chat cap and morning guide."""
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import storage, telegram_bot as tb
from app.main import app

BIRTH = {"name": "Asha", "dob": "1990-05-01", "tob": "08:15:00", "lat": 28.6139, "lon": 77.209, "tz_name": "Asia/Kolkata"}
DELHI = {"label": "New Delhi, Delhi, India", "lat": 28.6139, "lon": 77.209, "tz": "Asia/Kolkata"}
CHAT = 42


@pytest.fixture
def bot(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:test")
    monkeypatch.setenv("TELEGRAM_DAILY_LIMIT", "2")
    calls, asked = [], []
    monkeypatch.setattr(tb, "_api", lambda m, p: calls.append((m, p)) or {"ok": True})
    monkeypatch.setattr(tb, "geocode", lambda q: [DELHI] if "delhi" in q.lower() else
                        [DELHI, {**DELHI, "label": "Delhi, Ontario, Canada", "tz": "America/Toronto"}] if q == "many" else [])

    def fake_chat(prof, text):
        asked.append((prof["id"], text))
        storage.log_usage(prof["id"], "llm", text, owner=prof.get("owner"))
        return {"reply": "**Yes**, a good year."}
    monkeypatch.setattr(tb.chat, "chat", fake_chat)
    c = TestClient(app)

    def say(text, secret=None):
        return c.post("/telegram/webhook", json={"message": {"chat": {"id": CHAT}, "from": {"first_name": "Ravi"}, "text": text}},
                      headers={"x-telegram-bot-api-secret-token": secret or tb.webhook_secret()})

    def tap(data):
        return c.post("/telegram/webhook", json={"callback_query": {"id": "cb", "data": data, "message": {"chat": {"id": CHAT}}}},
                      headers={"x-telegram-bot-api-secret-token": tb.webhook_secret()})
    return c, say, tap, calls, asked


def texts(calls):
    return [p["text"] for m, p in calls if m == "sendMessage"]


def buttons(calls):
    kb = [p["reply_markup"]["inline_keyboard"] for m, p in calls if m == "sendMessage" and "reply_markup" in p][-1]
    return [b["callback_data"] for row in kb for b in row]


def onboard(say, tap):
    say("/start")
    say("17 May 1990")
    say("7:05 pm")
    say("New Delhi")
    tap("confirm")


def test_webhook_rejects_wrong_secret(bot):
    _, say, _, calls, _ = bot
    assert say("hi", secret="nope").status_code == 403 and not calls


def test_onboarding_creates_chart_and_sends_guides(bot):
    _, say, tap, calls, _ = bot
    say("/start")
    assert "Astropositivism" in texts(calls)[-1] and "1 of 3" in texts(calls)[-1]
    say("31 Feb 1990")
    assert "couldn’t read that date" in texts(calls)[-1]
    say("17 May 1990")
    assert "2 of 3" in texts(calls)[-1] and buttons(calls) == ["tob:unknown"]
    say("7:05 pm")
    say("New Delhi")
    assert "17 May 1990" in texts(calls)[-1] and "19:05" in texts(calls)[-1]
    tap("confirm")
    u = storage.tg_get(CHAT)
    assert u["step"] == "done" and u["owner"] == f"tg:{CHAT}"
    p = storage.get(u["profile_id"])
    assert p["request"]["dob"] == "1990-05-17" and p["request"]["tob"].startswith("19:05")
    out = "\n".join(texts(calls))
    assert "Your kundli, in short" in out and "Good for" in out and "/today" in out
    assert u["last_sent"]  # today's guide counts as sent, so the scheduler won't repeat it


def test_unknown_time_and_place_choice(bot):
    _, say, tap, calls, _ = bot
    say("/start")
    say("1990-05-17")
    tap("tob:unknown")
    say("many")
    assert buttons(calls) == ["pick:0", "pick:1"]
    tap("pick:1")
    assert "Delhi, Ontario" in texts(calls)[-1] and "noon" in texts(calls)[-1]


def test_chat_cap(bot):
    _, say, tap, calls, asked = bot
    onboard(say, tap)
    say("Will this year be good for my career?")
    assert texts(calls)[-1] == "<b>Yes</b>, a good year." and len(asked) == 1
    say("And money?")
    say("And marriage?")
    assert len(asked) == 2 and "used today’s questions" in texts(calls)[-1]


def test_link_from_website(bot):
    c, say, _, calls, asked = bot
    pid = c.post("/profiles", json=BIRTH).json()["id"]
    storage.set_setting("telegram_link_tok", f"|{pid}")
    say("/start tok")
    assert any("Linked to Asha" in t for t in texts(calls))
    assert storage.tg_get(CHAT)["profile_id"] == pid
    say("/start tok")
    assert "expired" in texts(calls)[-1]


def test_commands_and_settings(bot):
    _, say, tap, calls, _ = bot
    say("/today")
    assert "/start" in texts(calls)[-1]
    onboard(say, tap)
    say("/week")
    assert "Your week" in texts(calls)[-1]
    say("/remedies")
    assert "upay" in texts(calls)[-1]
    say("/settings")
    assert "set:time" in buttons(calls)
    tap("time:06:00")
    assert storage.tg_get(CHAT)["send_time"] == "06:00"
    tap("set:live")
    say("New Delhi")
    assert storage.tg_get(CHAT)["live_place"] == DELHI["label"]


def test_morning_guide_sent_once_in_window(bot):
    _, say, tap, calls, _ = bot
    onboard(say, tap)
    storage.tg_save(CHAT, last_sent="2000-01-01", send_time="08:00")
    before = datetime(2026, 10, 8, 2, 0, tzinfo=timezone.utc)   # 07:30 IST
    at = datetime(2026, 10, 8, 2, 45, tzinfo=timezone.utc)      # 08:15 IST
    assert tb.morning_tick(before) == 0
    assert tb.morning_tick(at) == 1 and "Good morning" in texts(calls)[-1]
    assert tb.morning_tick(at) == 0  # only once a day
    storage.tg_save(CHAT, active=0, last_sent=None)
    assert tb.morning_tick(at) == 0


@pytest.mark.parametrize("text,want", [("1990-05-17", date(1990, 5, 17)), ("17.05.1990", date(1990, 5, 17)),
                                       ("17th May, 1990", date(1990, 5, 17)), ("May 17 1990", date(1990, 5, 17)),
                                       ("2999-01-01", None), ("hello", None)])
def test_parse_date(text, want):
    assert tb.parse_date(text) == want


@pytest.mark.parametrize("text,want", [("07:05", "07:05"), ("7:05 am", "07:05"), ("7 pm", "19:00"), ("12:30 am", "00:30"),
                                       ("19.30", "19:30"), ("25:00", None), ("7", None)])
def test_parse_time(text, want):
    assert tb.parse_time(text) == want


def test_to_html_escapes_and_formats():
    assert tb.to_html("## Career\n- **Do** <this> & *that*") == "<b>Career</b>\n• <b>Do</b> &lt;this&gt; &amp; <i>that</i>"


def test_coming_up_reminders_on_the_day_and_3_days_before_a_dasha_change(bot, monkeypatch):
    from app import upcoming
    _, say, tap, calls, _ = bot
    onboard(say, tap)
    storage.tg_save(CHAT, send_time="08:00")
    at = datetime(2026, 10, 30, 2, 45, tzinfo=timezone.utc)  # 08:15 IST on 30 Oct
    items = [{"kind": "sky", "date": "2026-10-30", "title": "Jupiter moves into your 10th house", "meaning": "Career gets support.",
              "prepare": "Learn something."},
             {"kind": "period", "date": "2026-11-02", "title": "A new stretch: the Ketu sub-period begins",
              "meaning": "Good for studies.", "prepare": "Finish pending work."},
             {"kind": "sky", "date": "2026-11-02", "title": "Mercury turns direct", "meaning": "x", "prepare": "y"}]
    monkeypatch.setattr(upcoming, "upcoming", lambda *a: {"items": items})
    assert tb.reminder_tick(datetime(2026, 10, 30, 1, 0, tzinfo=timezone.utc)) == 0  # before the morning window
    assert tb.reminder_tick(at) == 2
    sent = texts(calls)[-2:]
    assert "Today · Transit" in sent[0] and "Jupiter" in sent[0]
    assert "In 3 days" in sent[1] and "Ketu" in sent[1]          # Dasha change early; the 2 Nov transit waits
    assert tb.reminder_tick(at) == 0                              # each once
    storage.tg_save(CHAT, active=0)                               # pausing the guide keeps reminders
    tap("rem:dasha")
    assert storage.tg_get(CHAT)["reminders"] == "dasha"
    assert tb.reminders_due(items, date(2026, 11, 2), "dasha") == [("today", items[1])]
    tap("rem:off")
    assert tb.reminder_tick(datetime(2026, 11, 2, 2, 45, tzinfo=timezone.utc)) == 0


def test_answers_use_the_city_set_in_settings(bot, monkeypatch):
    _, say, tap, calls, _ = bot
    onboard(say, tap)
    seen = []
    monkeypatch.setattr(tb.chat, "chat", lambda prof, text: seen.append(prof) or {"reply": "ok"})
    say("When is Rahu Kalam today?")
    assert "viewer" not in seen[-1] and seen[-1]["channel"] == "telegram"   # no city set: the birthplace
    storage.tg_save(CHAT, live_lat=49.9, live_lon=-97.14, live_tz="America/Winnipeg", live_place="Winnipeg, Manitoba, Canada")
    say("When is Rahu Kalam today?")
    assert seen[-1]["viewer"] == {"lat": 49.9, "lon": -97.14, "tz_name": "America/Winnipeg", "name": "Winnipeg"}


def test_how_did_it_go_on_telegram(bot, monkeypatch):
    from app import checkins, upcoming
    _, say, tap, calls, _ = bot
    onboard(say, tap)
    storage.tg_save(CHAT, send_time="08:00")
    pid = storage.tg_get(CHAT)["profile_id"]
    monkeypatch.setattr(upcoming, "upcoming", lambda *a: {"items": []})
    ck = checkins.from_question(pid, 1, "My joining date is 20 Oct, is it good?", "The morning looks good.", date(2026, 10, 14))
    assert tb.reminder_tick(datetime(2026, 10, 22, 2, 45, tzinfo=timezone.utc)) == 1
    assert "How did it go?" in texts(calls)[-1] and f"ci:{ck['id']}:well" in buttons(calls)
    assert tb.reminder_tick(datetime(2026, 10, 22, 3, 0, tzinfo=timezone.utc)) == 0      # once a day
    tap(f"ci:{ck['id']}:well")
    assert "add it to Your life so far" in texts(calls)[-1] and f"ci:{ck['id']}:add" in buttons(calls)
    tap(f"ci:{ck['id']}:add")
    assert storage.event_list(pid)[0]["kind"] == "job"
