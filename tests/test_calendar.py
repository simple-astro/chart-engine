"""The month calendar on Today (app/hindu_calendar.py): festivals land on the published days, the Purnimanta /
Amanta month names, the personal layer, and both Nanakshahi reckonings."""
from fastapi.testclient import TestClient

from app.hindu_calendar import month_view
from app.main import app

CHD = dict(lat=30.7333, lon=76.7794, tz_name="Asia/Kolkata")


def _by_day(v):
    return {int(d["date"][8:]): d for d in v["days"]}


def test_november_2026_festivals_and_sikh_days():
    v = month_view(2026, 11, **CHD)
    d = _by_day(v)
    assert len(d) == 30 and v["vikram_samvat"] == 2083 and v["samvatsara"] == "Parabhava"
    assert "Rama Ekadashi" in d[5]["hindu"]
    assert "Diwali · Lakshmi Puja" in d[8]["hindu"] and "Bandi Chhor Divas" in d[8]["sikh"]
    assert d[9]["tithi"] == 30 and "Masya" in d[9]["sikh"]
    assert "Bhai Dooj" in d[11]["hindu"]
    assert "Vrishchika Sankranti" in d[16]["hindu"] and d[16]["sankranti"]["at"].startswith("2026-11-16T19:")
    # Shukla Ekadashi runs between two sunrises (kshaya): kept on the 20th.
    assert "Dev Uthani Ekadashi" in d[20]["hindu"] and d[21]["tithi"] == 12
    assert "Kartik Purnima" in d[24]["hindu"]
    assert "Prakash Purab, Guru Nanak Dev Ji" in d[24]["sikh"] and "Pooranmashi" in d[24]["sikh"]
    # Each festival appears once even when its tithi runs over two sunrises (Shukla Navami, 18th and 19th).
    names = [f for x in v["days"] for f in x["hindu"]]
    assert len(names) == len(set(names))


def test_festivals_read_at_their_part_of_the_day():
    hits = {(m, int(x["date"][8:])): f for m in (2, 9, 10) for x in month_view(2026, m, **CHD)["days"] for f in x["hindu"]}
    assert hits[(2, 15)] == "Maha Shivaratri"   # Chaturdashi at midnight
    assert hits[(9, 14)] == "Ganesh Chaturthi"  # Chaturthi at midday, not at sunrise (the 15th)
    assert hits[(10, 20)] == "Dussehra"         # Dashami in the afternoon


def test_purnimanta_renames_the_krishna_half():
    p, a = _by_day(month_view(2026, 11, **CHD)), _by_day(month_view(2026, 11, style="amanta", **CHD))
    assert p[5]["lunar_month"] == "Kartika" and a[5]["lunar_month"] == "Ashwayuja"
    assert p[24]["lunar_month"] == a[24]["lunar_month"] == "Kartika"
    assert p[25]["lunar_month"] == "Margashira" and a[25]["lunar_month"] == "Kartika"


def test_personal_stars_and_chandrashtama():
    d = _by_day(month_view(2026, 11, birth_nakshatra=17, birth_moon_sign=7, **CHD))  # Jyeshtha, Scorpio Moon
    assert d[12]["tara"] == {"name": "Janma", "kind": "janma"}
    assert d[24]["tara"]["name"] == "Kshema" and d[24]["tara"]["kind"] == "good"
    assert [n for n, x in d.items() if x["chandrashtama"]] == [27, 28]
    assert "tara" not in month_view(2026, 11, **CHD)["days"][0]


def test_nanakshahi_sgpc_and_original():
    s = _by_day(month_view(2026, 11, **CHD))
    assert (s[15]["nanakshahi"]["month"], s[16]["nanakshahi"]["month"], s[16]["nanakshahi"]["day"]) == ("Katik", "Maghar", 1)
    assert s[16]["sikh"][0] == "Sangrand · Maghar begins" and s[16]["nanakshahi"]["year"] == 558
    o = _by_day(month_view(2026, 11, nanakshahi="original", **CHD))
    assert (o[14]["nanakshahi"]["month"], o[14]["nanakshahi"]["day"]) == ("Maghar", 1)
    assert "Shaheedi Purab, Guru Tegh Bahadur Ji" in o[24]["sikh"]
    assert "Shaheedi Purab, Guru Tegh Bahadur Ji" not in s[24]["sikh"]  # SGPC keeps it on Maghar sudi 5


def test_calendar_endpoint():
    c = TestClient(app)
    r = c.post("/calendar", json={"year": 2026, "month": 2, **CHD, "birth_nakshatra": 3, "birth_moon_sign": 1})
    assert r.status_code == 200 and len(r.json()["days"]) == 28 and "tara" in r.json()["days"][0]
    assert c.post("/calendar", json={"year": 2026, "month": 2, **CHD, "style": "solar"}).status_code == 422
    assert c.post("/calendar", json={"year": 2026, "month": 2, "lat": 0, "lon": 0, "tz_name": "Nowhere/X"}).status_code == 422


def test_today_screen_has_the_calendar():
    html = TestClient(app).get("/").text
    assert 'id="gcal"' in html and "/static/calendar.js" in html and "today/calendar" in html
