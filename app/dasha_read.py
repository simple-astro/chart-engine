"""What each Vimshottari period means for this person — the Parashari reading shown in Chart → Dasha periods.

A period lord gives the results of:
- the houses it rules, counted from the Lagna sign (the themes that come forward);
- the house it sits in (where those results show);
- its dignity, combustion and retrogression (how easily they come);
- its role for this Lagna (helpful / needs care / mixed, as today.chart_planets) and its Jaimini karaka role;
- the planets sitting with it, and the yogas it forms (switched on in its period, core/yoga_eval.py);
- its star lord (Nadi: a planet also gives the results of the nakshatra lord it sits in).
An Antardasha is also read from its Mahadasha lord: a kendra or trikona between them runs smoothly, 6th/8th or
2nd/12th asks for patience (classical rule). Rahu and Ketu act for the lord of the sign they sit in. Houses are
whole-sign, as on the Rasi chart. No death, longevity or illness predictions; matter-by-matter timing verdicts
stay in My Life → Dasha (app/period_view.py).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.today import chart_planets, owned_houses
from core import yoga_eval
from core.bnn import ADDS
from core.constants import SIGN_LORDS, SIGNS
from core.dignity import dignity
from core import dasha as vim
from core.ephemeris import get_ayanamsha, set_sidereal_mode

THEME = {1: "yourself, your health and how you come across", 2: "money, savings, family and speech",
         3: "courage, effort, siblings and skills", 4: "home, mother, property and peace of mind",
         5: "children, studies, creativity and romance", 6: "work routines, service, competition and health habits",
         7: "marriage, partners and business deals", 8: "change, research, shared money and in-laws",
         9: "luck, father, teachers, faith and long journeys", 10: "career, status and reputation",
         11: "gains, income, friends and wishes", 12: "expenses, foreign lands, rest and spiritual life"}
SHORT = {1: "self and health", 2: "money and family", 3: "effort and skills", 4: "home and peace of mind",
         5: "children and studies", 6: "work and daily habits", 7: "partners", 8: "change and research",
         9: "luck and teachers", 10: "career and status", 11: "gains and friends", 12: "expenses and foreign lands"}
NATURAL = {"Sun": "authority, father, government and confidence", "Moon": "mind, mother, feelings and the public",
           "Mars": "energy, property, siblings and technical work", "Mercury": "learning, trade, writing and communication",
           "Jupiter": "wisdom, children, teachers and growth", "Venus": "relationships, comforts, art and money",
           "Saturn": "hard work, discipline, service and long-term results",
           "Rahu": "ambition, foreign links, technology and the unusual",
           "Ketu": "detachment, research, spirituality and letting go"}
DIGNITY = {"exalted": "is exalted: it can give its best results.",
           "own": "is in its own sign: its results come steadily and reliably.",
           "friendly": "sits in a friend's sign: its results come fairly easily.",
           "enemy": "sits in an unfriendly sign: its results come with some effort.",
           "debilitated": "is debilitated: its results need patience and steady effort."}
LEVELS = ["Mahadasha", "Antardasha", "Pratyantar"]
AYAN_LABEL = {"krishnamurti": "KP (Krishnamurti)", "lahiri": "Lahiri", "pushya": "Pushya Paksha", "raman": "Raman",
              "fagan": "Fagan-Bradley", "tropical": "Tropical (no ayanamsha)"}
# Tara Bala: the nine-star cycle counted from the birth star (the Moon's nakshatra) to the period lord's star.
# Traditional names with gentle meanings; the 7th star is named by its number only.
TARA = {1: ("Janma Tara", "the same star group as your Moon, so this period is personal and inward-looking"),
        2: ("Sampat Tara", "a star of gains: it supports income and resources"),
        3: ("Vipat Tara", "a star of obstacles: go step by step and keep a margin for delays"),
        4: ("Kshema Tara", "a star of well-being: it supports comfort and steady progress"),
        5: ("Pratyak Tara", "a star of opposition: expect some pushback and answer it with patience"),
        6: ("Sadhana Tara", "a star of achievement: effort turns into results"),
        7: ("the 7th star", "the most demanding of the nine: keep plans simple and steady"),
        8: ("Mitra Tara", "a friendly star: help comes through other people"),
        9: ("Parama Mitra Tara", "a very friendly star: strong support from others")}
NODES = ("Rahu", "Ketu")


def _ord(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _join(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def _themes(hs: list[int]) -> str:
    return "; ".join(SHORT[x] for x in hs)


def tara(chart: dict, lord: str) -> tuple[int, str, str]:
    """(1-9, name, meaning) of the period lord's star counted from the birth star."""
    g = chart["grahas"]
    n = (g[lord]["nakshatra_index"] - g["Moon"]["nakshatra_index"]) % 27 % 9 + 1
    return (n, *TARA[n])


def _vargottama(chart: dict, p: str) -> bool:
    d9 = (chart.get("vargas") or {}).get("D9") or {}
    return p in d9 and d9[p]["sign_index"] == chart["grahas"][p]["sign_index"]


def _house(chart: dict, p: str) -> int:
    return (chart["grahas"][p]["sign_index"] - chart["lagna"]["sign_index"]) % 12 + 1


def interpret(chart: dict, lord: str, over: str | None = None) -> dict:
    """The reading of one period lord. `over` is the lord of the period it runs inside (the Mahadasha lord for an
    Antardasha, the Antardasha lord for a Pratyantar)."""
    g, L = chart["grahas"], chart["lagna"]["sign_index"]
    signs = {p: v["sign_index"] for p, v in g.items()}
    h, sign = _house(chart, lord), signs[lord]
    rules = owned_houses(lord, L) if lord not in NODES else []
    good, bad = chart_planets(L)
    pts: list[str] = []

    if lord in NODES:
        disp = SIGN_LORDS[sign]
        head = (f"{lord} sits in your {_ord(h)} house: {SHORT[h]} come forward, coloured by {NATURAL[lord]}.")
        pts.append(f"{lord} rules no sign, so it acts for {disp}, the lord of {SIGNS[sign]}"
                   + (f", which rules your {_join([_ord(x) for x in owned_houses(disp, L)])} "
                      f"({_themes(owned_houses(disp, L))})." if owned_houses(disp, L) else "."))
    else:
        own_here = h in rules
        head = (f"{lord} rules your {_join([_ord(x) for x in rules])} and sits in "
                + (f"it: {_themes(rules)} are well supported in this period." if own_here and len(rules) == 1
                   else f"your {_ord(h)}: {_themes(rules)} come forward, through {SHORT[h]}."))
        pts.append(f"Themes of the houses it rules: " + "; ".join(f"{_ord(x)} — {THEME[x]}" for x in rules) + ".")
    pts.append(f"Where it works: your {_ord(h)} house — {THEME[h]}. By nature {lord} brings {NATURAL[lord]}.")

    if lord == SIGN_LORDS[L]:
        pts.append("It is your Lagna lord, so this period is about you, your health and your own direction.")
    if lord in good and set(rules) & {4, 10} and set(rules) & {5, 9}:
        pts.append("It is your Yogakaraka, the best planet for your Lagna: a period to build something lasting.")
    elif lord in good:
        pts.append("For your Lagna it is a helpful planet, so its period tends to support you.")
    elif lord in bad:
        pts.append("For your Lagna it rules a house of effort, so this period asks for care, routine and patience.")

    if lord not in NODES:
        d = dignity(lord, sign)
        if d in DIGNITY:
            line = f"In {SIGNS[sign]} it {DIGNITY[d]}"
            nb = ((chart.get("strength") or {}).get("neecha_bhanga") or {}).get(lord) or {}
            if d == "debilitated" and nb.get("cancelled"):
                line += " Its weakness is cancelled (Neecha Bhanga), so it can rise after a slow start."
            pts.append(line)
        if lord != "Sun" and yoga_eval._combust(g, lord):
            pts.append(f"It is combust (close to the Sun): its themes can feel overshadowed, so give them your "
                       f"conscious attention.")
        if g[lord].get("retrograde"):
            pts.append("It is retrograde: matters from the past may come back for a second look.")

    if _vargottama(chart, lord):
        pts.append(f"It is Vargottama (in {SIGNS[sign]} in both the birth chart and the Navamsa), so it works with "
                   f"the steadiness of its own sign.")
    n, tname, tmean = tara(chart, lord)
    pts.append(f"Tara Bala: {lord}'s star, {g[lord]['nakshatra']}, is {_ord(n)} in the nine-star cycle from your birth "
               f"star, {g['Moon']['nakshatra']}. That is {tname}, {tmean}." if lord != "Moon" else
               f"Tara Bala: the Moon is your birth star itself ({tname}), {tmean}.")

    with_ = [p for p, s in signs.items() if s == sign and p != lord]
    if with_:
        pts.append(f"It sits with {_join(with_)}, which add " + "; ".join(ADDS[p] for p in with_) + ".")

    karaka = next((k for k in (chart.get("jaimini") or {}).get("karakas", []) if k["planet"] == lord), None)
    if karaka:
        pts.append(f"In Jaimini it is your {karaka['karaka']} ({karaka['role']}).")

    star = g[lord].get("nakshatra_lord")
    if star and star != lord and star not in NODES:
        sr = owned_houses(star, L)
        pts.append(f"It sits in {g[lord]['nakshatra']}, ruled by {star}, so it also brings {star}'s houses: "
                   f"your {_join([_ord(x) for x in sr])} ({_themes(sr)}).")

    ys = [y for y in (chart.get("yoga_check") or {}).get("yogas", []) if lord in y["planets"] and y["status"] != "Cancelled"]
    bare = lambda n: n.removesuffix(" yoga")
    helpful = [bare(y["name"]) for y in ys if y["kind"] == "good"][:4]
    handle = [bare(y["name"]) for y in ys if y["kind"] == "challenging"][:2]
    if helpful:
        pts.append(f"This period switches on your {_join(helpful)} yoga{'s' if len(helpful) > 1 else ''}.")
    if handle:
        pts.append(f"It also brings up {_join(handle)}, to handle gently (see Yogas).")

    if over and over != lord:
        gap = (signs[lord] - signs[over]) % 12 + 1
        if gap in (1, 4, 7, 10, 5, 9):
            pts.append(f"{lord} sits in a good position from {over}, whose period it runs inside: the two work together smoothly.")
        elif gap in (6, 8):
            pts.append(f"{lord} is 6th/8th from {over}, whose period it runs inside: the two pull in different directions, "
                       f"so patience and clear plans help.")
        elif gap in (2, 12):
            pts.append(f"{lord} is 2nd/12th from {over}, whose period it runs inside: plan money and energy carefully.")
        else:
            pts.append(f"{lord} is 3rd/11th from {over}, whose period it runs inside: effort turns into gains.")
    return {"lord": lord, "headline": head, "points": pts}


def _birth(chart: dict) -> datetime:
    return datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=chart["meta"]["julian_day"] - 2451545.0)


def ayanamsha_note(chart: dict, md: dict) -> dict:
    """Which ayanamsha the dates use and, if it is not Lahiri (what most apps use), how far Lahiri moves the
    running Mahadasha: the same Moon, measured with the Lahiri ayanamsha, run through the same Vimshottari engine."""
    meta = chart["meta"]
    name = meta.get("ayanamsha", "")
    out = {"name": name, "label": AYAN_LABEL.get(name, name.title())}
    if name == "lahiri" or "ayanamsha_value" not in meta:
        return out
    try:
        lahiri = get_ayanamsha(meta["julian_day"], "lahiri")
    finally:
        set_sidereal_mode(name, meta["julian_day"])  # leave Swiss Ephemeris in the chart's own frame
    moon = (chart["grahas"]["Moon"]["longitude"] + meta["ayanamsha_value"] - lahiri) % 360
    same = next((p for p in vim.vimshottari_tree(moon, _birth(chart), max_level=1) if p.lord == md["lord"]), None)
    if same:
        out["lahiri"] = {"shift_days": round((same.start - datetime.fromisoformat(md["start"])).total_seconds() / 86400),
                         "md_start": same.start.isoformat()}
    return out


def _at(periods: list[dict], now: datetime) -> dict | None:
    return next((p for p in periods if datetime.fromisoformat(p["start"]) <= now < datetime.fromisoformat(p["end"])), None)


def summary(chart: dict, now: datetime | None = None) -> dict:
    """Readings for the running Mahadasha, Antardasha and Pratyantar, the next Antardasha and the next Mahadasha,
    plus a one-line headline for every Mahadasha lord (for the period tree)."""
    now = now or datetime.now(timezone.utc)
    md = _at(chart["dasha"], now)
    if not md:
        return {"now": [], "next": [], "headlines": {}}
    ad = _at(md.get("children") or [], now)
    pd = ad and _at(ad.get("children") or [], now)
    card = lambda level, p, over=None: {"level": level, "lord": p["lord"], "start": p["start"], "end": p["end"],
                                        "reading": interpret(chart, p["lord"], over)}
    cur = [card("Mahadasha", md)] + ([card("Antardasha", ad, md["lord"])] if ad else [])
    if pd and pd["lord"] == ad["lord"]:
        cur[-1]["level"] = "Antardasha and Pratyantar"   # the same planet: one reading, not two identical ones
    elif pd:
        cur.append(card("Pratyantar", pd, ad["lord"]))
    nxt = []
    subs = md.get("children") or []
    if ad and subs.index(ad) + 1 < len(subs):
        nxt.append(card("Next Antardasha", subs[subs.index(ad) + 1], md["lord"]))
    i = chart["dasha"].index(md)
    if i + 1 < len(chart["dasha"]):
        nxt.append(card("Next Mahadasha", chart["dasha"][i + 1]))
    return {"now": cur, "next": nxt,
            "headlines": {p["lord"]: interpret(chart, p["lord"])["headline"] for p in chart["dasha"]},
            "birth": _birth(chart).isoformat(), "ayanamsha": ayanamsha_note(chart, md)}
