"""The Varshaphal reading in plain words, by rules: the year's tone and one-line theme, each life area, how the year
sits with the running Vimshottari Dasha, the Mudda dasha month by month, and the life by years from birth.

Reads core.tajika.annual() and the birth chart; says nothing the chart tables don't show. Rules, in short:
- Year tone: Muntha's house (1, 9, 10, 11 help; 4, 6, 7, 8, 12 ask for care), the year lord's dignity and house,
  and the annual Lagna lord's dignity.
- An area (work = 10th, money = 2nd and 11th, ...): its house lord in the annual chart (dignity, house, retrograde),
  planets in the house, the Tajika yoga between the annual Lagna lord and that house lord (Ithasala: it happens;
  Ishrafa: it fades; Radda: it starts and stalls), the area's Saham and its lord, and Muntha in the house.
- The Dasha: the classical rule that the annual chart times what the birth chart promises, so the running
  Mahadasha and Antardasha lords are read in the year's chart; an Antardasha whose lord is the year lord or the
  Muntha lord marks the year's key stretch.
Tones are the app's traffic-light words: go, good, steady, care.
"""
from __future__ import annotations

from datetime import date, datetime

from core import constants as C, tajika

DIG = {"exalted": 2, "own": 1.5, "friendly": 0.5, "neutral": 0, "enemy": -0.5, "debilitated": -1.5}
BENEFIC, MALEFIC = {"Jupiter", "Venus", "Mercury", "Moon"}, {"Saturn", "Mars", "Sun", "Rahu", "Ketu"}
GOOD_HOUSES, HARD_HOUSES, UPACHAYA = {1, 2, 4, 5, 7, 9, 10, 11}, {6, 8, 12}, {3, 6, 10, 11}
MUNTHA_SCORE = {1: 1, 2: .5, 3: .5, 4: -1, 5: .5, 6: -1, 7: -1, 8: -1.5, 9: 2, 10: 2, 11: 2, 12: -1.5}
THEME = {1: "Your own health and a fresh start", 2: "Money and family", 3: "Effort, siblings and short travel",
         4: "Home, mother and property", 5: "Children, learning and creativity", 6: "Effort, health and routine",
         7: "Partner and agreements", 8: "Changes and hidden matters", 9: "Luck, travel and teachers",
         10: "Career steps forward", 11: "Gains and friends", 12: "Expenses and distance"}
HOUSE_WORDS = {1: "you and your health", 2: "money and family", 3: "effort, siblings and short trips",
               4: "home and mother", 5: "children and learning", 6: "work, health and debts", 7: "partner and dealings",
               8: "changes and hidden matters", 9: "luck and travel", 10: "career", 11: "gains and friends",
               12: "expenses and rest"}
# key, label, houses (first is the main one), Saham, sentences by tone
AREAS = [
    ("work", "Work", (10,), "Karma", {
        "go": "A strong year for your career: push for the role you want.", "good": "Work moves forward steadily.",
        "steady": "Work holds steady; gains come slowly.", "care": "Work feels slow: prepare rather than switch."}),
    ("money", "Money", (11, 2), "Jeeva", {
        "go": "Money grows well this year.", "good": "Income comes in steadily.",
        "steady": "Money stays about the same: stick to your budget.", "care": "Money is tight: avoid big spending and lending."}),
    ("love", "Love and marriage", (7,), "Vivaha", {
        "go": "A warm year for love: a good time for big steps.", "good": "Relationships feel easy.",
        "steady": "Nothing big in love: stay close and kind.", "care": "Talks may stall: don't force decisions."}),
    ("health", "Health", (1,), None, {
        "go": "A healthy, energetic year.", "good": "Health is good: keep your routine.",
        "steady": "Health is steady: sleep, food and movement matter.", "care": "Keep a steady routine and don't skip check-ups."}),
    ("home", "Home and family", (4,), "Matri", {
        "go": "Good for home, property and mother.", "good": "Home life is settled.",
        "steady": "Home life carries on as usual.", "care": "Go gently at home; delay property decisions."}),
    ("learning", "Learning and children", (5,), "Vidya", {
        "go": "Strong for studies, children and creative work.", "good": "Learning goes well.",
        "steady": "Studies and children: steady effort pays.", "care": "Studies need extra effort; be patient with children."}),
    ("siblings", "Siblings, writing and short trips", (3,), "Bhratri", {
        "go": "Strong: talks, courses and short trips go well.", "good": "Good for siblings, writing and short trips.",
        "steady": "Siblings and short trips: nothing unusual.", "care": "Go easy on arguments with siblings; check travel plans."}),
]
TONE_ORDER = ["care", "steady", "good", "go"]
# Shorter words for the month lines, where two houses join: "money and gains", not a run of "and"s.
MONTH_WORDS = {1: "your energy", 2: "money", 3: "effort and short trips", 4: "home", 5: "children and studies",
               6: "daily work", 7: "your partner", 8: "changes", 9: "luck and travel", 10: "career",
               11: "gains", 12: "expenses"}
SHORT = {"work": "work", "money": "money", "love": "love", "health": "health", "home": "home", "learning": "studies",
         "siblings": "siblings and short trips"}
DIG_WORD = {"own": "own sign"}
# A practical line for the period's main house: (when it helps, when to go slow).
MONTH_TIP = {1: ("start something for yourself", "rest and look after your energy"),
             2: ("review money and meet family", "avoid big spending"),
             3: ("write, call, take short trips", "double-check travel and messages"),
             4: ("do home tasks and property paperwork", "delay property decisions"),
             5: ("study, plan, spend time with children", "be patient with studies and children"),
             6: ("clear pending work and book check-ups", "keep a calm routine at work"),
             7: ("meet people, agree terms, be with your partner", "avoid arguments and rushed agreements"),
             8: ("research, insure, reflect", "avoid risks and secrets"),
             9: ("travel, learn, meet a teacher", "keep plans flexible"),
             10: ("push work goals and meet seniors", "prepare rather than push at work"),
             11: ("follow up on gains and meet friends", "don't count on gains yet"),
             12: ("rest, plan spending, retreat", "watch your spending")}
MONTH_TEXT = {"go": "a strong stretch for {w}", "good": "good for {w}", "steady": "steady for {w}",
              "care": "go gently with {w}"}


def _tone(score: float, cut=(2, .75, -.5)) -> str:
    return "go" if score >= cut[0] else "good" if score >= cut[1] else "steady" if score >= cut[2] else "care"


def _ord(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _lord_of_house(r: dict, h: int) -> str:
    return C.SIGN_LORDS[(r["lagna"]["sign_index"] + h - 1) % 12]


def _planet_score(p: dict) -> float:
    s = DIG.get(p["dignity"], 0)
    if p["house"] in HARD_HOUSES:
        s -= 1
    elif p["house"] in GOOD_HOUSES:
        s += .5
    if p["retrograde"] and p["name"] not in ("Rahu", "Ketu"):
        s -= .5
    return s


def _yoga_between(r: dict, a: str, b: str) -> dict | None:
    for y in r["yogas"]:
        if y["yoga"] in ("Ithasala", "Ishrafa", "Radda", "Nakta", "Yamaya", "Kamboola") and a in y["planets"] and b in y["planets"]:
            return y
    return None


def year_score(r: dict) -> float:
    P, yl = r["planets"], r["year_lord"]["planet"]
    s = MUNTHA_SCORE[r["muntha"]["house"]]
    s += DIG.get(P[yl]["dignity"], 0) * .7 + (-.5 if P[yl]["house"] in HARD_HOUSES else 0)
    s += DIG.get(P[_lord_of_house(r, 1)]["dignity"], 0) * .35
    return s


def area(r: dict, key: str, label: str, houses: tuple, saham: str | None, texts: dict) -> dict:
    P, lag_lord = r["planets"], _lord_of_house(r, 1)
    score, why = 0.0, []
    for i, h in enumerate(houses):
        w = 1 if i == 0 else .6
        L = _lord_of_house(r, h)
        p = P[L]
        ls = _planet_score(p)
        score += ls * w
        if abs(ls) >= 1 or i == 0:
            why.append((abs(ls) * w, f"{_ord(h)} lord {L} {p['dignity'] if p['dignity'] != 'neutral' else ''} in the "
                        f"{_ord(p['house'])}{', retrograde' if p['retrograde'] and L not in ('Rahu', 'Ketu') else ''}".replace("  ", " ")))
        inside = [n for n, q in P.items() if q["house"] == h and n != L]
        for n in inside:
            d = .25 if (n in MALEFIC and h in UPACHAYA) else .5 if n in BENEFIC and P[n]["dignity"] != "debilitated" else -.5 if n in MALEFIC else 0
            score += d * w
            if P[n]["dignity"] in ("exalted", "own") and n in BENEFIC:
                score += .5 * w
                why.append((1 * w, f"{n} {P[n]['dignity']} in the {_ord(h)}"))
        if L != lag_lord:
            y = _yoga_between(r, lag_lord, L)
            if y:
                d = {"Ithasala": 1.5, "Nakta": 1, "Yamaya": 1, "Kamboola": 1.5, "Ishrafa": -.5, "Radda": -1}[y["yoga"]]
                score += d * w
                word = {"Ithasala": "applying", "Nakta": "joined through a third planet", "Yamaya": "joined through a third planet",
                        "Kamboola": "applying, with the Moon's help", "Ishrafa": "separating", "Radda": "applying but spoiled"}[y["yoga"]]
                why.append((abs(d) * w + .5, f"Lagna lord {lag_lord} and {L} {word} ({y['yoga']})"))
        else:
            score += .75 * w
        if r["muntha"]["house"] == h:
            d = 1 if h not in HARD_HOUSES else -1
            score += d
            why.append((1, f"Muntha in the {_ord(h)}"))
    if key == "health":  # the 1st shows the body; the 6th and 8th lords, and Muntha in 6/8/12, weigh on it
        for h in (6, 8):
            L6 = _lord_of_house(r, h)
            if L6 != lag_lord and P[L6]["house"] == 1:
                score -= .75
                why.append((.9, f"{_ord(h)} lord {L6} in the 1st"))
        if r["muntha"]["house"] in HARD_HOUSES:
            score -= 1
            why.append((1.2, f"Muntha in the {_ord(r['muntha']['house'])}"))
            m = P[r["muntha"]["lord"]]
            if m["dignity"] in ("debilitated", "enemy"):
                score -= .5
                why.append((.8, f"its lord {r['muntha']['lord']} {m['dignity']}"))
            score = min(score, .75)  # a hard Muntha caps health at "good"
    if saham:
        s = next((x for x in r["sahams"] if x["name"] == saham), None)
        if s:
            d = (.5 if s["lord_dignity"] in ("exalted", "own") else -.5 if s["lord_dignity"] == "debilitated" else 0) \
                + (-.5 if s["house"] in HARD_HOUSES else 0)
            score += d
            if d:
                why.append((abs(d), f"{saham} Saham in the {_ord(s['house'])}, its lord {s['lord']} {s['lord_dignity']}"))
    tone = _tone(score)
    why = [w for _, w in sorted(why, key=lambda x: -x[0])[:2]]
    return {"key": key, "label": label, "tone": tone, "score": round(score, 2), "text": texts[tone], "why": "; ".join(why)}


def dasha_link(chart: dict, r: dict) -> dict:
    P, yl, ml = r["planets"], r["year_lord"]["planet"], r["muntha"]["lord"]
    T = datetime.fromisoformat  # Dasha dates carry the birth zone's offset, the return is UTC: compare as times
    start, end = T(r["varsha_pravesh"]), T(r["next"])
    mds = [d for d in chart.get("dasha") or [] if T(d["start"]) < end and T(d["end"]) > start]
    if not mds:
        return {}
    md = next((d for d in mds if T(d["start"]) <= start), mds[0])
    newmd = next((d for d in mds if start < T(d["start"]) < end), None)
    lead = newmd or md
    p = P[lead["lord"]]
    s = _planet_score(p) + (1 if lead["lord"] in (yl, ml) else 0)
    verdict = "agrees" if s >= .5 else "softens" if s < -.5 else "neutral"
    began = f"began in {datetime.fromisoformat(newmd['start']).strftime('%B %Y')}" if newmd else "runs through this year"
    # The verdict word (Agrees / Softens / Neutral) is shown before this, so the sentence only gives the reason.
    text = (f"Your {lead['lord']} Mahadasha {began}; {lead['lord']} is {DIG_WORD.get(p['dignity'], p['dignity'])} in this "
            f"year's {_ord(p['house'])} house ({HOUSE_WORDS[p['house']]})"
            + {"agrees": ".", "softens": ", so expect slower results.", "neutral": "."}[verdict])
    key = []
    for d in mds:
        for a in d.get("children") or []:
            if T(a["start"]) < end and T(a["end"]) > start and a["lord"] in (yl, ml):
                a0, a1 = max(T(a["start"]), start), min(T(a["end"]), end)
                key.append({"start": a0.isoformat(), "end": a1.isoformat(), "lord": a["lord"],
                            "why": f"your Antardasha is then {a['lord']}, " + ("this year's lord" if a["lord"] == yl else "the Muntha lord")})
    return {"verdict": verdict, "text": text, "key": key[:2], "maha": lead["lord"]}


def _join(parts: list[str]) -> str:
    """"money and gains"; with a phrase that already has "and" in it, a comma first: "luck and travel, and career"."""
    if len(parts) < 2:
        return parts[0] if parts else ""
    return parts[0] + (", and " if " and " in parts[0] or " and " in parts[1] else " and ") + parts[1]


def _tip_house(houses: list[int], tone: str) -> int:
    """The house the tip speaks for: a supportive one in a good period (gains, not the 8th), a hard one in a slow one."""
    pick = [h for h in houses if (h in HARD_HOUSES) == (tone == "care")]
    return (pick or houses)[0]


def months(r: dict, yl: str) -> list[dict]:
    P, out, ml = r["planets"], [], r["muntha"]["lord"]
    for m in r["mudda_dasha"]:
        L = m["lord"]
        p = P[L]
        s = _planet_score(p) + (1 if L == yl else 0)
        ruled = [h for h in range(1, 13) if _lord_of_house(r, h) == L]
        houses = (ruled or [p["house"]])[:2]   # Rahu and Ketu rule no house: read them by where they sit
        tone = _tone(s, (1.5, .5, -.5))
        line = MONTH_TEXT[tone].format(w=_join([MONTH_WORDS[h] for h in houses]))
        role = ("year lord" if L == yl else "Muntha lord" if L == ml else
                ("rules your " + _join([_ord(h) for h in ruled[:2]])) if ruled else f"in your {_ord(p['house'])}")
        tip = {"go": "Good time to ", "good": "Good time to ", "care": "Take it slow: "}.get(tone)
        out.append({"lord": L, "start": m["start"], "end": m["end"], "tone": tone, "year_lord": L == yl, "score": round(s, 2),
                    "role": role, "text": line[0].upper() + line[1:] + ".",
                    "tip": (tip + MONTH_TIP[_tip_house(houses, tone)][tone == "care"] + ".") if tip else ""})
    best = max(out, key=lambda x: x["score"])
    if best["tone"] in ("go", "good"):
        best["best"] = True
    return out


def reading(chart: dict, r: dict) -> dict:
    yl = r["year_lord"]["planet"]
    areas = [area(r, *a) for a in AREAS]
    tone = _tone(year_score(r), (2, 1, -.5))
    ranked = sorted(areas, key=lambda a: -a["score"])
    best, worst = ranked[0], [a for a in ranked[::-1] if a["tone"] == "care"][:2]
    head = f"{THEME[r['muntha']['house']]}." + (f" Strongest this year: {SHORT[best['key']]}." if best["tone"] in ("go", "good") else "")
    if worst:
        head += " Go gently with " + " and ".join(SHORT[a["key"]] for a in worst) + "."
    P = r["planets"]
    chips = [f"Year lord: {yl}, {DIG_WORD.get(P[yl]['dignity'], P[yl]['dignity'])}", f"Muntha in the {_ord(r['muntha']['house'])}", f"Year Lagna: {r['lagna']['sign']}"]
    return {"tone": tone, "headline": head, "chips": chips, "areas": areas, "dasha": dasha_link(chart, r),
            "months": months(r, yl)}


def _event_fit(r: dict, areas_by_house: dict, topic: str) -> tuple[bool, str]:
    from core import kp_predict as K
    t = K.TOPICS.get(topic)
    if not t:
        return False, ""
    cusp, good = t[1], set(t[2])
    risk = t[6] == "risk"
    lag_lord, L = _lord_of_house(r, 1), _lord_of_house(r, cusp)
    if r["muntha"]["house"] in good | {cusp}:
        return True, f"Muntha in the {_ord(r['muntha']['house'])}"
    y = _yoga_between(r, lag_lord, L) if L != lag_lord else None
    if y and y["yoga"] in ("Ithasala", "Nakta", "Yamaya", "Kamboola"):
        return True, f"Lagna lord and {_ord(cusp)} lord applying ({y['yoga']})"
    a = areas_by_house.get(cusp)
    if a and ((a["tone"] in ("go", "good")) != risk):
        return True, f"{a['label']} {'strong' if not risk else 'under strain'} that year"
    return False, ""


def life(chart: dict, request: dict, upto: int, events: list[dict]) -> list[dict]:
    """One line per year of life, 0..upto: tone, theme, Muntha house, year lord, and the person's events that year."""
    from app import life_events as LE
    out = []
    for y in range(0, upto + 1):
        r = tajika.annual(chart, request, y)
        areas = None
        row = {"years": y, "year": int(r["varsha_pravesh"][:4]), "start": r["varsha_pravesh"], "end": r["next"],
               "tone": _tone(year_score(r), (2, 1, -.5)), "theme": THEME[r["muntha"]["house"]],
               "muntha_house": r["muntha"]["house"], "year_lord": r["year_lord"]["planet"], "events": []}
        for e in events:
            if not (r["varsha_pravesh"][:10] <= e["date"] < r["next"][:10]):
                continue
            topic = LE.KINDS.get(e["kind"], (None, None))[1]
            if areas is None:  # each house's area, worked out once per year and only when an event falls in it
                areas = {}
                for key, label, houses, saham, texts in AREAS:
                    a = area(r, key, label, houses, saham, texts)
                    for h in houses:
                        areas.setdefault(h, a)
            fit, why = _event_fit(r, areas, topic) if topic else (False, "")
            row["events"].append({"label": LE.KINDS[e["kind"]][0], "date": e["date"], "checked": bool(topic), "fit": fit, "why": why})
        out.append(row)
    return out


def years_now(request: dict, on: date) -> int:
    return max(0, tajika.years_for(request, on))
