"""The free daily panchang image: one card a day for New Delhi on India time, open to everyone without signing in.

GET /panchang                 a small public page with today's card, Download and Share
GET /panchang/today.png       today's card (India time), cached until midnight IST
GET /panchang/YYYY-MM-DD.png  any day within a year either side

The card (1080 x 1920, WhatsApp Status size) carries the full panchang (tithi, nakshatra, yoga, karana, Moon and Sun
signs, sunrise, sunset, moonrise and moonset, month, samvat, ritu, ayana), the good times and the times to avoid, and
a short "Do today" and "Avoid today" for everyone: no birth chart, so nothing personal.

Read in the Lahiri ayanamsha, as Drik Panchang and printed panchangs are, so the nakshatra and yoga end times match
what people compare them with (the app itself stays on KP). Festivals come from app/hindu_calendar.py. Good times
never overlap Rahu Kalam, Yamaganda or Gulika: a Choghadiya that does is left out. The day's advice comes from the
same rules as the app's muhurat (app/muhurat.py): which activities today's nakshatra, tithi, weekday, yoga and karana
favour, Bhadra, Rikta tithi and Disha Shool.
"""
from __future__ import annotations

import io
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

router = APIRouter(include_in_schema=False)

IST = ZoneInfo("Asia/Kolkata")
CITY, LAT, LON = "New Delhi", 28.6139, 77.2090
SITE = "simplejyotish.com"
LINK = "https://simplejyotish.com/?s=panchang"
FONTS = Path(__file__).resolve().parent / "fonts"
LOGO = Path(__file__).resolve().parent / "static" / "sun-card.png"  # static/sun.svg, drawn at 240px
TITHI = ["Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi", "Saptami", "Ashtami", "Navami",
         "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi"]
# Month names as North Indian panchangs print them (the app's calendar uses the pan-Indian spellings)
MONTH_NORTH = {"Vaishakha": "Vaishakh", "Shravana": "Shravan", "Ashwayuja": "Ashwin", "Kartika": "Kartik",
               "Margashira": "Margashirsha", "Pausha": "Paush", "Magha": "Magh", "Phalguna": "Phalgun"}
RASHI = ["Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya", "Tula", "Vrishchika", "Dhanu", "Makara",
         "Kumbha", "Meena"]
SIGN_EN = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn",
           "Aquarius", "Pisces"]
DAY_LORD = {"Sunday": "Sun", "Monday": "Moon", "Tuesday": "Mars", "Wednesday": "Mercury", "Thursday": "Jupiter",
            "Friday": "Venus", "Saturday": "Saturn"}
DAY_DO = {"Sun": "Sun’s day: government work, meeting seniors",
          "Moon": "Moon’s day: family time, calm creative work",
          "Mars": "Mars’s day: property, repairs, exercise",
          "Mercury": "Mercury’s day: paperwork, study, trade",
          "Jupiter": "Jupiter’s day: learning, worship, money plans",
          "Venus": "Venus’s day: shopping, arts, celebrations",
          "Saturn": "Saturn’s day: finish pending work, help someone"}
# What to do on the main festivals (matched by the start of the festival's name); others get a general line
FEST_DO = [("Diwali", "Diwali: Lakshmi Puja in the evening, lamps at the door"), ("Dhanteras", "Dhanteras: buy a metal utensil or gold; lamp for Yama at dusk"),
           ("Govardhan", "Govardhan Puja: Annakut offering to Krishna"), ("Bhai Dooj", "Bhai Dooj: tilak for your brother"),
           ("Chhath", "Chhath: arghya to the setting Sun"), ("Karva Chauth", "Karva Chauth: fast until moonrise"),
           ("Raksha Bandhan", "Raksha Bandhan: tie rakhi in the good times"), ("Krishna Janmashtami", "Janmashtami: fast and midnight puja"),
           ("Ganesh Chaturthi", "Ganesh Chaturthi: bring Ganesha home at midday"), ("Maha Shivaratri", "Maha Shivaratri: fast, night-long Shiva puja"),
           ("Holika Dahan", "Holika Dahan: the bonfire after sunset"), ("Holi", "Holi: colours with family and friends"),
           ("Ram Navami", "Ram Navami: Rama puja at midday"), ("Hanuman Jayanti", "Hanuman Jayanti: Hanuman Chalisa and temple visit"),
           ("Dussehra", "Dussehra: Shami puja; begin something new"), ("Akshaya Tritiya", "Akshaya Tritiya: buy gold, give charity"),
           ("Kartik Purnima", "Kartik Purnima: holy bath and lamps"), ("Prakash Purab", "Gurpurab: visit the Gurdwara, seva and langar"),
           ("Bandi Chhor", "Bandi Chhor Divas: lamps at the Gurdwara"), ("Vasant Panchami", "Vasant Panchami: Saraswati puja, wear yellow")]
# Sikh days the general card shows (Sangrand, Pooranmashi and Masya stay in the app's Nanakshahi view)
SIKH_SKIP = ("Sangrand", "Pooranmashi", "Masya", "1 ")


def today_ist() -> date:
    return datetime.now(IST).date()


def _tithi_name(n: int) -> str:
    if n == 15:
        return "Purnima"
    if n == 30:
        return "Amavasya"
    return f"{'Shukla' if n <= 15 else 'Krishna'} {TITHI[(n - 1) % 15]}"


def _t(iso: str) -> datetime:
    return datetime.fromisoformat(iso).astimezone(IST)


def _hm(d: datetime) -> str:
    return d.strftime("%-I:%M %p")


def _span(a: str, b: str) -> str:
    x, y = _t(a), _t(b)
    return f"{_hm(x)} – {_hm(y)}" if x.strftime("%p") != y.strftime("%p") else f"{x.strftime('%-I:%M')} – {_hm(y)}"


def _till(iso: str, day: date) -> str:
    """"till 2:35 PM", or "till 6:31 AM, Sat" when it ends after this day."""
    t = _t(iso)
    return f"till {_hm(t)}" + ("" if t.date() == day else f", {t.strftime('%a')}")


def _moon_times(d: date) -> tuple[str, str]:
    """Moonrise and moonset in New Delhi within this calendar day (India time), or "none today"."""
    import swisseph as swe
    from core.ephemeris import julian_day
    from core.panchang import _event, _jd_to_utc
    start = datetime(d.year, d.month, d.day, tzinfo=IST)
    out = []
    for rsmi in (swe.CALC_RISE, swe.CALC_SET):
        t = _jd_to_utc(_event(julian_day(start), swe.MOON, rsmi, LAT, LON)).astimezone(IST)
        out.append(_hm(t) if t.date() == d else "none today")
    return out[0], out[1]


def _advice(x: dict, p, fest: list[str], bhadra_till: str | None) -> tuple[list[str], list[str]]:
    """Three things to do and three to avoid today, for everyone (no birth chart)."""
    from app.muhurat import DISHA_SHOOL, RIKTA
    from app.today import SHOOL_FIX
    from core import constants as C
    acts = sorted(x["activities"], key=lambda a: -a["score"])
    good = [a["name"] for a in acts if a["verdict"] in ("excellent", "good")][:2]
    bad = [a["name"] for a in acts[::-1] if a["verdict"] == "avoid"][:2]
    do = [DAY_DO[DAY_LORD[p.weekday]]]
    do.append(f"Good for: {', '.join(good).lower().capitalize()}" if good else
              "A quiet day: keep to routine, no big launches")
    vrat = next((f for f in fest if "Ekadashi" in f), None)
    big = next((line for f in fest for key, line in FEST_DO if f.startswith(key)), None)
    if big:
        do.insert(0, big)
    if vrat:
        do.append(f"{vrat}: fast or eat light")
    elif any("Pradosh" in f for f in fest):
        do.append("Pradosh Vrat: Shiva puja around sunset")
    elif p.tithi_number == 15:
        do.append("Purnima: Satyanarayan katha, a holy bath or charity")
    elif p.tithi_number == 30:
        do.append("Amavasya: remember your ancestors, give charity")
    elif any("Sankranti" in f for f in fest):
        do.append("Sankranti: a holy bath and charity")
    else:
        do.append("Begin important work in the good times below")
    avoid = []
    if bad:
        avoid.append(f"Not for: {', '.join(bad).lower()}")
    if bhadra_till:
        avoid.append(f"Bhadra {bhadra_till}: no new beginnings")
    if p.tithi_number == 30:
        avoid.append("New beginnings on Amavasya")
    elif p.tithi_paksha_index in RIKTA:
        avoid.append(f"New beginnings: {_tithi_name(p.tithi_number).split()[-1]} is a Rikta tithi")
    wd = C.WEEKDAY_NAMES.index(p.weekday)
    avoid.append(f"Travel {DISHA_SHOOL[wd]} (Disha Shool): {SHOOL_FIX[wd]} first")
    return do[:3], avoid[:3]


def panchang_for(d: date) -> dict:
    """Everything the card shows for one day, in New Delhi, India time, Lahiri ayanamsha."""
    from app import daily_thoughts, hindu_calendar, muhurat
    from core.panchang import compute_panchang, lahiri_panchang
    with lahiri_panchang():
        x = muhurat.muhurat_days(d, 1, LAT, LON, "Asia/Kolkata", full=True)[0]
        month = hindu_calendar.month_view(d.year, d.month, LAT, LON, "Asia/Kolkata")
        pp = compute_panchang(d, LAT, LON, "Asia/Kolkata")
    cal = next(c for c in month["days"] if c["date"] == d.isoformat())
    w, e, extra = x["windows"], x["ends"], x["panchang"]
    avoid = [("Rahu Kalam", w["rahu_kalam"]), ("Yamaganda", w["yamaganda"]), ("Gulika", w["gulika"])]
    clash = lambda a, b: any(_t(a) < _t(z[1]) and _t(z[0]) < _t(b) for _, z in avoid)  # noqa: E731
    good = []
    if w.get("abhijit"):
        good.append(("Abhijit Muhurat", w["abhijit"]))
    good += [(f"{c['name']} Choghadiya", [c["start"], c["end"]]) for c in w["choghadiya"]
             if c["quality"] in ("best", "good") and not clash(c["start"], c["end"])][:2]  # four lines in all
    good.append(("Brahma Muhurat", w["brahma"]))
    fest = list(cal["hindu"]) + [s for s in cal["sikh"] if not s.startswith(SIKH_SKIP) and s not in cal["hindu"]]
    paksha = "Shukla" if x["tithi"]["number"] <= 15 else "Krishna"
    sun_sign = cal["sun_sign"]
    moonrise, moonset = _moon_times(d)
    bhadra = _till(e["karana"]["ends"], d) if x["karana"] == "Vishti" else None
    do, dont = _advice(x, pp, fest, bhadra)
    masa = " ".join(MONTH_NORTH.get(w_, w_) for w_ in cal["lunar_month"].split())
    return {
        "date": d, "weekday": d.strftime("%A"), "city": CITY,
        "sunrise": _hm(_t(w["sunrise"])), "sunset": _hm(_t(w["sunset"])), "moonrise": moonrise, "moonset": moonset,
        "tithi": (_tithi_name(x["tithi"]["number"]), _till(e["tithi"]["ends"], d)),
        "nakshatra": (x["nakshatra"], _till(e["nakshatra"]["ends"], d)),
        "yoga": (x["yoga"], _till(e["yoga"]["ends"], d)),
        "karana": (x["karana"], _till(e["karana"]["ends"], d)),
        "moon_sign": (RASHI[pp.moon_sign_index], SIGN_EN[pp.moon_sign_index]),
        "sun_sign": (RASHI[sun_sign], SIGN_EN[sun_sign]),
        "month": (f"{masa}, {paksha}", f"Vikram Samvat {month['vikram_samvat']}"), "masa": masa, "paksha": paksha,
        "samvat": f"Vikram {month['vikram_samvat']} · Shaka {month['vikram_samvat'] - 135} · {month['samvatsara']}",
        "ritu": extra["ritu"].split(" (")[0] + " Ritu",
        "ayana": "Uttarayana" if sun_sign in (9, 10, 11, 0, 1, 2) else "Dakshinayana",
        "festivals": fest,
        "do": do, "dont": dont,
        "thought": daily_thoughts.thought_for(fest, x["tithi"]["number"], x["nakshatra"]),
        "good": [(k, _span(*v)) for k, v in good],
        "avoid": [(k, _span(*v)) for k, v in avoid],
    }


# ----- drawing (Pillow) -----
CREAM, CARD, INK, MUT, LINE = "#FBF7EF", "#FFFFFF", "#241E31", "#5A536E", "#E9E1D2"
GOLD, GOLDTXT = "#E0B05F", "#6B470F"
GOOD_BG, GOOD_LN, GOOD_TX = "#EEF6F0", "#B9DCC3", "#1F5A37"
BAD_BG, BAD_LN, BAD_TX = "#FBEFE3", "#ECC7A2", "#8A4300"
W, H, M = 1080, 1920, 48
THOUGHT_MIN = 236  # two lines of the thought for today, with its label, source and margins


def _font(kind: str, size: int, weight: str = "Regular"):
    from PIL import ImageFont
    f = ImageFont.truetype(str(FONTS / ("CormorantGaramond.ttf" if kind == "serif" else "Inter.ttf")), size)
    f.set_variation_by_name(weight)
    return f


def _fit(draw, text: str, kind: str, size: int, weight: str, width: int):
    """The font at ``size`` or smaller, so ``text`` fits in ``width``."""
    while size > 14:
        f = _font(kind, size, weight)
        if draw.textlength(text, font=f) <= width:
            return f
        size -= 2
    return _font(kind, size, weight)


def _wrap(draw, text: str, font, width: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        nxt = f"{cur} {word}".strip()
        if draw.textlength(nxt, font=font) <= width or not cur:
            cur = nxt
        else:
            lines.append(cur)
            cur = word
    return lines + ([cur] if cur else [])


def _spaced(dr, x: float, y: float, text: str, font, fill, track: int = 3, anchor: str = "l") -> float:
    """Letter-spaced capitals, from ``x`` (anchor "l"), ending at it ("r") or centred on it ("m"); returns the width."""
    w = sum(dr.textlength(c, font=font) for c in text) + track * (len(text) - 1)
    x -= {"l": 0, "r": w, "m": w / 2}[anchor]
    for c in text:
        dr.text((x, y), c, font=font, fill=fill)
        x += dr.textlength(c, font=font) + track
    return w


def _gold_panel(im, box: tuple[int, int, int, int], radius: int):
    """The diagonal gold gradient behind the month and samvat."""
    from PIL import Image, ImageDraw
    x0, y0, x1, y1 = box
    grad = Image.new("RGB", (2, 2))
    grad.putdata([(0xF7, 0xE3, 0xB4), (0xF0, 0xD3, 0x96), (0xF0, 0xD3, 0x96), (0xE9, 0xC3, 0x77)])
    grad = grad.resize((x1 - x0, y1 - y0), Image.BILINEAR)
    mask = Image.new("L", grad.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, grad.size[0] - 1, grad.size[1] - 1], radius=radius, fill=255)
    im.paste(grad, (x0, y0), mask)


def _thought(dr, p: dict, top: int, bottom: int):
    """The thought for today, centred in the space left above the footer; left out if it can't fit."""
    text, src = p["thought"]
    for size in (46, 42, 38, 34):
        f = _font("serif", size, "SemiBold")
        lines = _wrap(dr, f"“{text}”", f, W - 2 * M - 96)
        lh = int(size * 1.15)
        h = 24 + 26 + 12 + len(lines) * lh + 8 + 28 + 22
        if len(lines) <= 3 and h <= bottom - top:
            break
    else:
        return
    y = top + (bottom - top - h) // 2
    dr.rounded_rectangle([M, y, W - M, y + h], radius=28, fill="#F4EBDA")
    lab = _font("sans", 21, "ExtraBold")
    w = _spaced(dr, W / 2, y + 24, "THOUGHT FOR TODAY", lab, GOLDTXT, anchor="m")
    for sx in (W / 2 - w / 2 - 92, W / 2 + w / 2 + 20):
        dr.line([(sx, y + 37), (sx + 72, y + 37)], fill="#C98F2E", width=2)
    yy = y + 24 + 26 + 12
    for ln_ in lines:
        dr.text((W / 2, yy), ln_, font=f, fill="#3D2A05", anchor="ma")
        yy += lh
    dr.text((W / 2, yy + 8), f"— {src}", font=_font("sans", 23, "Medium"), fill=MUT, anchor="ma")


def render(p: dict) -> bytes:
    from PIL import Image, ImageDraw
    import segno
    im = Image.new("RGB", (W, H), CREAM)
    dr = ImageDraw.Draw(im)
    for x in range(W):  # the gold band along the top
        t = x / W
        dr.line([(x, 0), (x, 14)], fill=tuple(int(a + (b - a) * t) for a, b in zip((0xE0, 0xB0, 0x5F), (0xC9, 0x8F, 0x2E))))
    # header: the sun mark and the name, and what the card is, kept small
    logo = Image.open(LOGO).convert("RGBA").resize((60, 60), Image.LANCZOS)
    im.paste(logo, (M - 6, 27), logo)
    f = _font("serif", 38, "SemiBold")
    dr.text((M + 62, 57), "Simple", font=f, fill=INK, anchor="lm")
    dr.text((M + 62 + dr.textlength("Simple", font=f), 57), "Jyotish", font=f, fill=GOLDTXT, anchor="lm")
    _spaced(dr, W - M, 46, "DAILY PANCHANG", _font("sans", 21, "ExtraBold"), GOLDTXT, anchor="r")
    # the gold panel: Hindu month, paksha and Vikram Samvat large, the date beside them
    py, ph, bw_, bh_ = 96, 252, 184, 200
    _gold_panel(im, (M, py, W - M, py + ph), 36)
    tx = W - 2 * M - 36 - bw_ - 60
    dr.text((M + 36, py + 104), p["masa"], font=_fit(dr, p["masa"], "serif", 96, "Bold", tx), fill="#2E1F04", anchor="ls")
    dr.text((M + 36, py + 162), f"{p['paksha']} Paksha", font=_font("serif", 54, "SemiBold"), fill="#2E1F04", anchor="ls")
    dr.text((M + 36, py + 220), p["month"][1], font=_fit(dr, p["month"][1], "serif", 54, "SemiBold", tx), fill="#5A3A08", anchor="ls")
    bx, by = W - M - 36 - bw_, py + (ph - bh_) // 2
    dr.rounded_rectangle([bx, by, bx + bw_, by + bh_], radius=28, fill="#FFFDF7")
    cx = bx + bw_ / 2
    _spaced(dr, cx, by + 28, p["date"].strftime("%a").upper(), _font("sans", 21, "ExtraBold"), "#8A5E14", anchor="m")
    dr.text((cx, by + 104), str(p["date"].day), font=_font("sans", 72, "Bold"), fill=INK, anchor="mm")
    dr.text((cx, by + 162), p["date"].strftime("%b %Y"), font=_font("sans", 24, "SemiBold"), fill=INK, anchor="mm")
    y = py + ph + 14
    line = " · ".join([p["city"], *p["samvat"].split(" · ")[1:], p["ritu"], p["ayana"]])
    dr.text((M + 4, y), line, font=_fit(dr, line, "sans", 25, "Medium", W - 2 * M), fill="#4A4258")
    y += 50
    # festival ribbon
    if p["festivals"]:
        text = " · ".join(p["festivals"][:3])
        dr.rounded_rectangle([M, y, W - M, y + 76], radius=24, fill="#EFD49B")
        dr.text((M + 28, y + 38), text, font=_fit(dr, text, "sans", 36, "Bold", W - 2 * M - 56), fill="#3D2A05", anchor="lm")
        y += 96
    # six tiles: the five limbs and the two signs
    tiles = [("TITHI", *p["tithi"]), ("NAKSHATRA", *p["nakshatra"]), ("YOGA", *p["yoga"]), ("KARANA", *p["karana"]),
             ("MOON SIGN", *p["moon_sign"]), ("SUN SIGN", *p["sun_sign"])]
    gap = 12
    tw, th = (W - 2 * M - 2 * gap) // 3, 128
    for i, (k, name, sub) in enumerate(tiles):
        x0, y0 = M + (i % 3) * (tw + gap), y + (i // 3) * (th + gap)
        dr.rounded_rectangle([x0, y0, x0 + tw, y0 + th], radius=22, fill=CARD, outline=LINE, width=2)
        dr.text((x0 + 20, y0 + 14), k, font=_font("sans", 22, "Bold"), fill="#6B6280")
        dr.text((x0 + 20, y0 + 80), name, font=_fit(dr, name, "sans", 38, "Bold", tw - 40), fill=INK, anchor="ls")
        dr.text((x0 + 20, y0 + 114), sub, font=_fit(dr, sub, "sans", 26, "Regular", tw - 40), fill="#4A4258", anchor="ls")
    y += 2 * th + gap + 16
    # sun and moon times
    cw = (W - 2 * M - 3 * gap) // 4
    for i, (k, v) in enumerate((("SUNRISE", p["sunrise"]), ("SUNSET", p["sunset"]), ("MOONRISE", p["moonrise"]),
                                ("MOONSET", p["moonset"]))):
        x0 = M + i * (cw + gap)
        dr.rounded_rectangle([x0, y, x0 + cw, y + 90], radius=20, fill="#F4EBDA")
        dr.text((x0 + 18, y + 12), k, font=_font("sans", 21, "Bold"), fill="#6B6280")
        dr.text((x0 + 18, y + 76), v, font=_fit(dr, v, "sans", 34, "Bold", cw - 36), fill=INK, anchor="ls")
    y += 90 + 18
    # do today / avoid today
    gap = 16
    bw = (W - 2 * M - gap) // 2
    fy = H - 164  # the footer's top
    n = max(len(p["good"]), len(p["avoid"]))
    tbh = 72 + n * 42 + 10
    for size in (29, 27, 25):  # as large as leaves room for the thought for today
        body, lh = _font("sans", size, "Medium"), size + 8
        blocks = [[_wrap(dr, it, body, bw - 88) for it in items] for items in (p["do"], p["dont"])]
        bh = 70 + max(sum(len(r) * lh + 12 for r in rows) for rows in blocks) + 8
        if fy - (y + bh + gap + tbh) >= THOUGHT_MIN:
            break
    for j, (title, rows, bg, ln, tx_, mark) in enumerate((("DO TODAY", blocks[0], GOOD_BG, GOOD_LN, GOOD_TX, "✓"),
                                                         ("AVOID TODAY", blocks[1], BAD_BG, BAD_LN, BAD_TX, "!"))):
        x0 = M + j * (bw + gap)
        dr.rounded_rectangle([x0, y, x0 + bw, y + bh], radius=28, fill=bg, outline=ln, width=2)
        _spaced(dr, x0 + 24, y + 22, title, _font("sans", 26, "ExtraBold"), tx_, track=2)
        yy = y + 70
        for lines in rows:
            dr.ellipse([x0 + 24, yy + 5, x0 + 50, yy + 31], fill=tx_)
            dr.text((x0 + 37, yy + 18), mark, font=_font("sans", 18, "ExtraBold"), fill="#FFFFFF", anchor="mm")
            for k, ln_ in enumerate(lines):
                dr.text((x0 + 64, yy + k * lh), ln_, font=body, fill=INK)
            yy += len(lines) * lh + 12
    y += bh + gap
    # good times / times to avoid, one line each
    for j, (title, items, ln, tx_) in enumerate((("GOOD TIMES", p["good"], GOOD_LN, GOOD_TX),
                                                ("AVOID NEW WORK", p["avoid"], BAD_LN, BAD_TX))):
        x0 = M + j * (bw + gap)
        dr.rounded_rectangle([x0, y, x0 + bw, y + tbh], radius=28, fill="#FFFFFF", outline=ln, width=2)
        _spaced(dr, x0 + 24, y + 22, title, _font("sans", 26, "ExtraBold"), tx_, track=2)
        for i, (k, v) in enumerate(items):
            yy = y + 72 + i * 42
            k = k.replace(" Muhurat", "").replace(" Choghadiya", "")
            lf = _font("sans", 28)
            dr.text((x0 + 24, yy), k, font=lf, fill="#3F3F3F")
            room = bw - 48 - dr.textlength(k, font=lf) - 16
            dr.text((x0 + bw - 24, yy), v, font=_fit(dr, v, "sans", 28, "Bold", room), fill=INK, anchor="ra")
    y += tbh
    _thought(dr, p, y + 18, fy - 18)
    # footer: QR, address, what it is
    dr.rectangle([0, fy, W, H], fill="#F3EADA")
    dr.line([(0, fy), (W, fy)], fill=LINE, width=2)
    buf = io.BytesIO()
    segno.make(LINK, error="m").save(buf, kind="png", scale=5, border=2, dark=INK, light="#FFFFFF")
    qr = Image.open(io.BytesIO(buf.getvalue())).convert("RGB").resize((116, 116), Image.NEAREST)
    im.paste(qr, (M, fy + 24))
    dr.text((M + 142, fy + 30), SITE, font=_font("sans", 46, "Bold"), fill=GOLDTXT)
    dr.text((M + 142, fy + 94), "Free daily panchang · times for New Delhi (IST)", font=_font("sans", 27), fill="#4A4258")
    out = io.BytesIO()
    im.save(out, "PNG", optimize=True)
    return out.getvalue()


@lru_cache(maxsize=64)
def card(d: date) -> bytes:
    return render(panchang_for(d))


def _png(d: date, max_age: int) -> Response:
    return Response(card(d), media_type="image/png", headers={
        "Cache-Control": f"public, max-age={max_age}",
        "Content-Disposition": f'inline; filename="panchang-{d.isoformat()}.png"'})


@router.get("/panchang/today.png")
def today_png() -> Response:
    now = datetime.now(IST)
    midnight = datetime(now.year, now.month, now.day, tzinfo=IST) + timedelta(days=1)
    return _png(now.date(), max(60, int((midnight - now).total_seconds())))


@router.get("/panchang/{day}.png")
def day_png(day: str) -> Response:
    try:
        d = date.fromisoformat(day)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc
    if abs((d - today_ist()).days) > 366:
        raise HTTPException(status_code=404, detail="Pick a day within a year of today.")
    return _png(d, 86400)


@router.get("/panchang")
def page(d: str | None = None) -> HTMLResponse:
    """A small public page: the card, with Download and Share, and the days either side."""
    try:
        day = date.fromisoformat(d) if d else today_ist()
    except ValueError:
        day = today_ist()
    if abs((day - today_ist()).days) > 366:
        day = today_ist()
    p = panchang_for(day)
    iso, prev, nxt = day.isoformat(), (day - timedelta(days=1)).isoformat(), (day + timedelta(days=1)).isoformat()
    title = f"Panchang {day.strftime('%-d %B %Y')} · {CITY} · SimpleJyotish"
    desc = f"{p['tithi'][0]}, {p['nakshatra'][0]} nakshatra. Sunrise {p['sunrise']}, Rahu Kalam {p['avoid'][0][1]}."
    is_today = day == today_ist()
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><meta name="description" content="{desc}">
<meta property="og:title" content="{title}"><meta property="og:description" content="{desc}">
<meta property="og:image" content="https://{SITE}/panchang/{iso}.png"><meta property="og:type" content="website">
<link rel="icon" type="image/svg+xml" href="/static/sun.svg">
<style>
:root{{--bg:#fbf7ef;--ink:#241e31;--mut:#5a536e;--line:#e3d8c4;--gold:#c98f2e;--acc:#8a5e14}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}}
main{{max-width:520px;margin:0 auto;padding:18px 16px 40px;display:flex;flex-direction:column;gap:14px}}
h1{{margin:0;font:600 1.6rem Georgia,serif}} p{{margin:0;color:var(--mut)}}
img{{width:100%;height:auto;border-radius:16px;border:1px solid var(--line);box-shadow:0 8px 24px #24193d1f;background:#fff}}
.row{{display:flex;gap:10px;flex-wrap:wrap;position:sticky;bottom:12px}} .btn{{flex:1;min-height:52px;display:flex;align-items:center;justify-content:center;border-radius:14px;
  font-weight:700;text-decoration:none;border:1px solid var(--line);background:#fff;color:var(--ink);cursor:pointer;font-size:1rem}}
.btn.gold{{background:linear-gradient(135deg,#e0b05f,#c98f2e);color:#241903;border:0}}
nav{{display:flex;justify-content:space-between;align-items:center}} nav a{{color:var(--acc);font-weight:600;text-decoration:none;padding:10px 0}}
small{{color:var(--mut)}}
</style></head><body><main>
<h1>Daily Panchang</h1>
<p>{day.strftime('%A, %-d %B %Y')}{' · today' if is_today else ''} · times for {CITY} (IST)</p>
<img src="/panchang/{iso}.png" alt="Panchang for {day.strftime('%-d %B %Y')}: {desc}" width="1080" height="1920">
<div class="row">
  <a class="btn gold" href="/panchang/{iso}.png" download="panchang-{iso}.png">Download image</a>
  <button class="btn" type="button" id="share">Share</button>
</div>
<nav><a href="/panchang?d={prev}">‹ {(day - timedelta(days=1)).strftime('%-d %b')}</a>{'' if is_today else '<a href="/panchang">Today</a>'}<a href="/panchang?d={nxt}">{(day + timedelta(days=1)).strftime('%-d %b')} ›</a></nav>
<small>Calculated with the Swiss Ephemeris (Lahiri). Festival dates follow common North Indian practice; please confirm with your temple. The do's and don'ts are general, from the day's panchang. Your own chart and daily guidance: <a href="/">simplejyotish.com</a></small>
</main>
<script>
document.getElementById('share').onclick=async()=>{{
  const url=location.origin+'/panchang?d={iso}', text='Panchang for {day.strftime('%-d %B')}: {p['tithi'][0]}, {p['nakshatra'][0]}.';
  try{{const r=await fetch('/panchang/{iso}.png'),b=await r.blob(),f=new File([b],'panchang-{iso}.png',{{type:'image/png'}});
    if(navigator.canShare&&navigator.canShare({{files:[f]}})){{await navigator.share({{files:[f],text,url}});return}}}}catch(e){{if(e.name==='AbortError')return}}
  if(navigator.share){{try{{await navigator.share({{title:'Daily Panchang',text,url}})}}catch(e){{}}return}}
  location.href='https://wa.me/?text='+encodeURIComponent(text+' '+url);
}};
</script></body></html>""")
