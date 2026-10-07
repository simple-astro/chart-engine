"""Plain-language guidance for messages (Telegram): a first reading and a daily guide.
Mirrors the website's guidance rules; no LLM calls, so it is free to send every day.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app import muhurat
from core.constants import SIGN_LORDS

EXALT = {"Sun": 0, "Moon": 1, "Mars": 9, "Mercury": 5, "Jupiter": 3, "Venus": 11, "Saturn": 6}
REMEDY = {
    "Sun": "Offer water to the rising Sun and respect your father and seniors; chant “Om Suryaya Namah” on Sundays.",
    "Moon": "Respect your mother, keep a calm routine, and donate milk or rice on Mondays; chant “Om Chandraya Namah”.",
    "Mars": "Exercise, control anger and visit Hanuman ji on Tuesdays; chant “Om Mangalaya Namah”.",
    "Mercury": "Read, learn and keep promises; feed green fodder to cows on Wednesdays; chant “Om Budhaya Namah”.",
    "Jupiter": "Respect teachers and elders and donate yellow items or turmeric on Thursdays; chant “Om Gurave Namah”.",
    "Venus": "Respect women, keep your home clean and beautiful, and donate white sweets on Fridays; chant “Om Shukraya Namah”.",
    "Saturn": "Be fair to workers and the poor, stay disciplined, and donate black sesame or mustard oil on Saturdays; chant “Om Shanaye Namah”.",
    "Rahu": "Avoid shortcuts and intoxicants and feed birds or dogs; chant “Om Rahave Namah” on Saturdays.",
    "Ketu": "Meditate, support spiritual causes and feed dogs; chant “Om Ketave Namah”.",
}
GIFT = {"Sun": "confidence and recognition", "Moon": "emotional warmth and popularity", "Mars": "energy and courage",
        "Mercury": "intelligence and business sense", "Jupiter": "growth, wisdom and protection",
        "Venus": "love, comfort and harmony", "Saturn": "discipline and lasting results",
        "Rahu": "ambition and unusual opportunities", "Ketu": "insight and spiritual depth"}
RISK = {"Sun": "ego clashes", "Moon": "mood swings", "Mars": "anger and haste", "Mercury": "overthinking",
        "Jupiter": "over-promising", "Venus": "overspending", "Saturn": "delays and pressure",
        "Rahu": "confusion and shortcuts", "Ketu": "sudden breaks"}
PERIOD = {
    "Sun": "a time to step forward — authority, recognition and your father come into focus.",
    "Moon": "a time of feelings, home and public life — routines keep the mind steady.",
    "Mars": "a time of energy and action — property, siblings and bold moves.",
    "Mercury": "a time of learning and trade — studies, business, writing and skills.",
    "Jupiter": "a time of growth and wisdom — knowledge, children, money and faith expand.",
    "Venus": "a time of comforts and relationships — love, marriage, home and money matters.",
    "Saturn": "a time of hard work and slow, solid rise — patience pays later.",
    "Rahu": "a time of big ambitions and sudden changes — avoid shortcuts.",
    "Ketu": "a time of letting go and looking within — research and spirituality.",
}
RISING = {
    "Aries": "bold, energetic and quick to act", "Taurus": "calm, practical and loyal",
    "Gemini": "curious, talkative and quick-witted", "Cancer": "caring, sensitive and protective",
    "Leo": "confident, generous and proud", "Virgo": "careful, analytical and helpful",
    "Libra": "friendly, fair and charming", "Scorpio": "intense, private and determined",
    "Sagittarius": "optimistic, honest and freedom-loving", "Capricorn": "disciplined, patient and ambitious",
    "Aquarius": "independent, original and humane", "Pisces": "kind, imaginative and intuitive",
}
STONE = {"Sun": "Ruby (Manik)", "Moon": "Pearl (Moti)", "Mars": "Red Coral (Moonga)", "Mercury": "Emerald (Panna)",
         "Jupiter": "Yellow Sapphire (Pukhraj)", "Venus": "Diamond or White Sapphire", "Saturn": "Blue Sapphire (Neelam)"}
DAY_LORD = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]  # Sunday first


def _md(d: str) -> str:
    return datetime.fromisoformat(d).strftime("%b %Y")


def current_period(chart: dict, now: datetime) -> tuple[dict | None, dict | None]:
    cur = lambda d: datetime.fromisoformat(d["start"]) <= now < datetime.fromisoformat(d["end"])
    md = next((d for d in chart.get("dasha", []) if cur(d)), None)
    ad = next((d for d in (md or {}).get("children", []) if cur(d)), None)
    return md, ad


def weak_planet(chart: dict) -> tuple[str, str] | None:
    g = chart["grahas"]
    for p, ex in EXALT.items():
        if g[p]["sign_index"] == (ex + 6) % 12:
            return p, f"{p} is weak in your chart (debilitated), so it needs support."
    for p in EXALT:
        if g[p].get("combust"):
            return p, f"{p} sits too close to the Sun (combust), so its gifts stay hidden without support."
    return None


def first_reading(profile: dict, now: datetime) -> str:
    c = profile["chart"]
    lagna = c["lagna"]["sign"]
    moon = c["grahas"]["Moon"]
    md, ad = current_period(c, now)
    lord = SIGN_LORDS[c["lagna"]["sign_index"]]
    lines = ["✨ **Your kundli, in short**",
             f"🌅 **{lagna} rising** — you are {RISING[lagna]}.",
             f"🌙 **Moon in {moon['sign']}**, {moon['nakshatra']} nakshatra — this shapes your mind and moods."]
    if md:
        lines.append(f"🪐 **{md['lord']} period** until {_md(md['end'])} — {PERIOD[md['lord']]}"
                     + (f" Right now {ad['lord']} adds {GIFT[ad['lord']]} until {_md(ad['end'])}." if ad else ""))
    lines += ["", "🙏 **Your top remedies (upay)**"]
    n = 1
    if md:
        lines.append(f"{n}. For your current period: {REMEDY[md['lord']]}")
        n += 1
    weak = weak_planet(c)
    if weak and (not md or weak[0] != md["lord"]):
        lines.append(f"{n}. To strengthen {weak[0]}: {REMEDY[weak[0]]} _{weak[1]}_")
        n += 1
    if lord in STONE:
        lines.append(f"{n}. Your life stone: {STONE[lord]}, for {lord}, ruler of your {lagna} ascendant. "
                     "Try it for a few days first and consult before buying a costly stone.")
    return "\n".join(lines)


def _local(iso: str, tz_name: str) -> datetime:
    return datetime.fromisoformat(iso).astimezone(ZoneInfo(tz_name))


def day_guide(profile: dict, day: date, lat: float, lon: float, tz_name: str, place: str = "", now: datetime | None = None) -> str:
    c = profile["chart"]
    moon = c["grahas"]["Moon"]
    d = muhurat.muhurat_days(day, 1, lat, lon, tz_name, moon["nakshatra_index"], moon["sign_index"])[0]
    good = [a["name"] for a in d["activities"] if a["verdict"] in ("excellent", "good")]
    bad = [a["name"] for a in d["activities"] if a["verdict"] == "avoid"]
    w = d["windows"]
    icon = {"excellent": "🌟", "good": "☀️", "fair": "🌤", "avoid": "🌧"}[d["overall"]["verdict"]]
    _t = lambda iso: _local(iso, tz_name).strftime("%-I:%M %p")
    lines = [f"{icon} **{day.strftime('%A, %-d %b')}** — {d['overall']['label']}"]
    if d["tara"]:
        lines.append(f"Your star today: {d['tara']['name']} ({d['tara']['note']})")
    lines.append("")
    lines.append("✅ **Good for:** " + (", ".join(good) if good else "routine work — keep big starts for a better day"))
    if bad:
        lines.append("⛔ **Better to avoid:** " + ", ".join(bad))
    best = f"{_t(w['abhijit'][0])}–{_t(w['abhijit'][1])}" if w["abhijit"] else None
    rahu = f"{_t(w['rahu_kalam'][0])}–{_t(w['rahu_kalam'][1])}"
    lines.append("⏰ " + (f"**Best time:** {best} · " if best else "") + f"**Avoid starting:** {rahu} (Rahu kalam)")
    lines.append("")
    lines.append("👉 **Do:** " + (f"Use today for {good[0].lower()}" + (f" — begin around {best}." if best else ".")
                                if good else "Finish pending work and plan ahead; a better day for big starts is coming."))
    ch = d["chandra"]
    if ch and ch["house"] == 8:
        dont = "Arguments and big decisions — it’s a Chandrashtama day for you."
    elif d["tara"] and d["tara"]["score"] < 0:
        dont = f"Starting anything big — your star today ({d['tara']['name']}) brings obstacles."
    elif bad:
        dont = f"{bad[0]} today."
    else:
        dont = f"Beginning new work during Rahu kalam ({rahu})."
    lines.append("🚫 **Avoid:** " + dont)
    day_lord = DAY_LORD[(day.weekday() + 1) % 7]
    lines.append(f"🙏 **Today’s upay ({d['weekday']}, {day_lord}’s day):** {REMEDY[day_lord]}")
    md, _ = current_period(c, now or datetime.now(ZoneInfo(tz_name)))
    if md:
        lines.append(f"\n_{md['lord']} period tip: lean into {GIFT[md['lord']]}; watch for {RISK[md['lord']]}._")
    if place:
        lines.append(f"_Times for {place}._")
    return "\n".join(lines)


def week_summary(profile: dict, start: date, lat: float, lon: float, tz_name: str) -> str:
    moon = profile["chart"]["grahas"]["Moon"]
    days = muhurat.muhurat_days(start, 7, lat, lon, tz_name, moon["nakshatra_index"], moon["sign_index"])
    dot = {"excellent": "🟢", "good": "🟢", "fair": "🟡", "avoid": "🔴"}
    lines = ["📅 **Your week**"]
    for d in days:
        good = [a["name"] for a in d["activities"] if a["verdict"] == "excellent"] or \
               [a["name"] for a in d["activities"] if a["verdict"] == "good"]
        label = date.fromisoformat(d["date"]).strftime("%a %-d")
        lines.append(f"{dot[d['overall']['verdict']]} **{label}** — {d['overall']['label']}"
                     + (f" · best for {', '.join(good[:2]).lower()}" if good else ""))
    lines.append("\n🟢 good · 🟡 okay with care · 🔴 better to avoid big starts")
    return "\n".join(lines)


def remedies(profile: dict, now: datetime) -> str:
    text = first_reading(profile, now)
    return text[text.index("🙏"):]
