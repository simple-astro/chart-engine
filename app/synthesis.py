"""Compressed, pre-synthesised chart context for the chat model.

Instead of raw positions, each house and planet arrives with the factors that pull it
up or down already weighed (dignity, lordship, conjunctions, benefic/malefic aspects,
Neecha Bhanga, Ashtakavarga), plus the running daśā and today's heavy transits. The model
then reasons over the whole chart rather than reading single placements in isolation.
Houses are whole-sign from the lagna (as drawn); KP cusp data is kept in its own block.
"""
from __future__ import annotations

from datetime import datetime, timezone

from core.ashtakavarga import ashtakavarga
from core.constants import SIGN_LORDS, SIGNS
from core.dignity import dignity
from core.parivartana import exchanges
from core.transits import transit_positions
from core.yogas import aspects, neecha_bhanga, yogas

NINE = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
KENDRA, TRIKONA, DUSTHANA, UPACHAYA = {1, 4, 7, 10}, {1, 5, 9}, {6, 8, 12}, {3, 6, 10, 11}
STONE = {"Sun": "Ruby", "Moon": "Pearl", "Mars": "Red Coral", "Mercury": "Emerald", "Jupiter": "Yellow Sapphire",
         "Venus": "Diamond/White Sapphire", "Saturn": "Blue Sapphire", "Rahu": "Hessonite", "Ketu": "Cat's Eye"}
DAY = {"Sun": "Sunday", "Moon": "Monday", "Mars": "Tuesday", "Mercury": "Wednesday", "Jupiter": "Thursday",
       "Venus": "Friday", "Saturn": "Saturday", "Rahu": "Saturday", "Ketu": "Tuesday"}
THEME = {1: "self, health", 2: "wealth, family, speech", 3: "courage, siblings, effort", 4: "home, mother, property, peace",
         5: "children, intellect, romance", 6: "work, debts, disease, rivals", 7: "marriage, partners",
         8: "longevity, sudden events, in-laws", 9: "luck, father, dharma", 10: "career, status",
         11: "gains, income, friends", 12: "expenses, foreign, sleep, moksha"}


def _h(sign: int, base: int) -> int:
    return (sign - base) % 12 + 1


def _date(iso: str) -> str:
    return iso[:10]


def flat_periods(maha: dict) -> list[dict]:
    """Every pratyantar inside one mahadasha, labelled at all three levels so nothing is misread."""
    out = []
    for ad in maha.get("children", []):
        for pd in ad.get("children", []) or [ad]:
            out.append({"maha": maha["lord"], "antar": ad["lord"], "pratyantar": pd["lord"] if pd is not ad else None,
                        "starts": _date(pd["start"]), "ends": _date(pd["end"])})
    return out


def timeline(dasha: list[dict], now: datetime, months: int = 24) -> list[dict]:
    """Flat MD/AD/PD periods overlapping the next ``months`` months."""
    start, stop = now.isoformat()[:10], f"{now.year + months // 12:04d}{now.isoformat()[4:10]}"
    return [p for md in dasha if md["end"][:10] > start and md["start"][:10] < stop
            for p in flat_periods(md) if p["ends"] > start and p["starts"] < stop]


def _place(profile: dict) -> dict:
    """Where the user is now (their chosen location in the app, else the birthplace) — times are for here."""
    v, req = profile.get("viewer") or {}, profile.get("request") or {}
    if v.get("tz_name"):
        return {"place": v.get("name") or "current location", "time_zone": v["tz_name"]}
    return {"place": (req.get("place") or "birthplace").split(",")[0], "time_zone": req.get("tz_name") or "UTC"}


def _local(profile: dict, now: datetime) -> datetime:
    from zoneinfo import ZoneInfo
    try:
        return now.astimezone(ZoneInfo(_place(profile)["time_zone"]))
    except Exception:  # an unknown zone name: fall back to UTC rather than fail the chat
        return now


def build(profile: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    c, req = profile["chart"], profile.get("request") or {}
    g = c["grahas"]
    L = c["lagna"]["sign_index"]
    signs = {p: g[p]["sign_index"] for p in NINE}
    house = {p: _h(signs[p], L) for p in NINE}
    lord_of = lambda h: SIGN_LORDS[(L + h - 1) % 12]
    owns = {p: [h for h in range(1, 13) if lord_of(h) == p] for p in NINE}
    dig = {p: dignity(p, signs[p]) for p in NINE}
    asp = aspects(signs, L)
    nb = neecha_bhanga(signs, L, {p: v["sign_index"] for p, v in c["vargas"].get("D9", {}).items()} or None)
    waxing = (g["Moon"]["longitude"] - g["Sun"]["longitude"]) % 360 < 180
    benefic = {"Jupiter", "Venus", "Mercury"} | ({"Moon"} if waxing else set())
    nature = lambda p: "benefic" if p in benefic else "malefic"
    akv = ashtakavarga(signs, L)
    sav = {h: akv["sav"][(L + h - 1) % 12] for h in range(1, 13)}
    strong = lambda p: dig[p] in ("exalted", "own") or (dig[p] == "debilitated" and nb.get(p, {}).get("cancelled"))

    def by(target_sign: int) -> dict:
        """Planets casting drishti on a sign, split by nature."""
        h = _h(target_sign, L)
        hit = {"benefic": [], "malefic": []}
        for p in NINE:
            if signs[p] != target_sign and h in asp[p]["houses"]:
                hit[nature(p)].append(p)
        return {k: v for k, v in hit.items() if v}

    planets = {}
    for p in NINE:
        d = {"sign": SIGNS[signs[p]], "h": house[p], "deg": int(g[p]["degrees_in_sign"]), "dignity": dig[p],
             "nature": nature(p), "owns": owns[p], "nak": f"{g[p]['nakshatra']} ({g[p]['nakshatra_lord']})"}
        flags = [f for f, on in (("retrograde", g[p]["retrograde"] and p not in ("Rahu", "Ketu")), ("combust", g[p]["combust"])) if on]
        if flags:
            d["flags"] = flags
        mates = [q for q in NINE if q != p and signs[q] == signs[p]]
        if mates:
            d["with"] = mates
        d["aspects_h"] = asp[p]["houses"]
        got = by(signs[p])
        if got:
            d["aspected_by"] = got
        if p in nb:
            d["neecha_bhanga"] = ("cancelled: " + "; ".join(nb[p]["reasons"])) if nb[p]["cancelled"] else "not cancelled"
        planets[p] = d

    houses = {}
    for h in range(1, 13):
        lord, plus, minus = lord_of(h), [], []
        at = house[lord]
        if at == h:
            plus.append(f"lord {lord} in own house")
        elif h in DUSTHANA and at in DUSTHANA:
            plus.append(f"lord {lord} in H{at} (Viparita: troubles cancel)")
        elif at in KENDRA | TRIKONA:
            plus.append(f"lord {lord} well placed in H{at}")
        elif at in (2, 11):
            plus.append(f"lord {lord} in gain house H{at}")
        elif at in DUSTHANA:
            minus.append(f"lord {lord} in difficult H{at}")
        if dig[lord] in ("exalted", "own"):
            plus.append(f"lord {dig[lord]}")
        elif dig[lord] == "debilitated":
            (plus if nb.get(lord, {}).get("cancelled") else minus).append(
                "lord debilitated" + (" but Neecha Bhanga" if nb.get(lord, {}).get("cancelled") else ""))
        occ = [p for p in NINE if house[p] == h]
        for p in occ:
            if nature(p) == "benefic":
                plus.append(f"{p} (benefic) here" + (", softens the difficulty" if h in DUSTHANA else ""))
            elif h in UPACHAYA:
                plus.append(f"{p} (malefic) here, good in upachaya")
            elif strong(p):
                minus.append(f"{p} (malefic) here but {dig[p] if dig[p] != 'debilitated' else 'Neecha Bhanga'}: delay, then durable results")
            else:
                minus.append(f"{p} (malefic) here")
        hits = by((L + h - 1) % 12)
        if hits.get("benefic"):
            plus.append("aspected by " + ", ".join(hits["benefic"]) + " (benefic)")
        if hits.get("malefic"):
            minus.append("aspected by " + ", ".join(hits["malefic"]) + " (malefic)")
        (plus if sav[h] >= 28 else minus if sav[h] < 25 else []).append(f"SAV {sav[h]}")
        score = len(plus) - len(minus) + (1 if at == h else 0)
        houses[h] = {"theme": THEME[h], "sign": SIGNS[(L + h - 1) % 12], "lord": lord, "in": occ,
                     "net": "strong" if score >= 3 else "good" if score >= 1 else "mixed" if score >= -1 else "weak",
                     "+": plus, "-": minus}

    md = next((d for d in c["dasha"] if d["start"] <= now.isoformat() < d["end"]), None)
    role = lambda p: {"lord": p, "in_h": house[p], "owns": owns[p], "dignity": dig[p]}
    dasha = {}
    if md:
        subs = md.get("children", [])
        ad = next((d for d in subs if d["start"] <= now.isoformat() < d["end"]), None)
        dasha["maha"] = {**role(md["lord"]), "started": _date(md["start"]), "ends": _date(md["end"])}
        if ad:
            dasha["antar"] = {**role(ad["lord"]), "started": _date(ad["start"]), "ends": _date(ad["end"])}
            i = subs.index(ad)
            dasha["next_antars"] = [{**role(d["lord"]), "starts": _date(d["start"]), "ends": _date(d["end"])}
                                    for d in subs[i + 1:i + 3]]
        j = c["dasha"].index(md)
        if j + 1 < len(c["dasha"]):
            nx = c["dasha"][j + 1]
            dasha["next_maha"] = {**role(nx["lord"]), "starts": _date(nx["start"])}
        dasha["next_24_months"] = timeline(c["dasha"], now)

    tr = transit_positions(now, c["meta"].get("ayanamsha", "krishnamurti"))
    moon = signs["Moon"]
    transits = {}
    for p in ("Saturn", "Jupiter", "Rahu", "Ketu"):
        s = tr[p].sign_index
        reach = {"Saturn": (3, 7, 10), "Jupiter": (5, 7, 9)}.get(p, (5, 7, 9))
        transits[p] = {"sign": SIGNS[s], "h_from_lagna": _h(s, L), "h_from_moon": _h(s, moon), "sav": akv["sav"][s],
                       "aspects_h": sorted(_h((s + n - 1) % 12, L) for n in reach)}
        if tr[p].retrograde and p in ("Saturn", "Jupiter"):
            transits[p]["retrograde"] = True
    sm = transits["Saturn"]["h_from_moon"]
    if sm in (12, 1, 2):
        transits["sade_sati"] = {12: "rising phase", 1: "peak phase", 2: "setting phase"}[sm]
    elif sm in (4, 8):
        transits["saturn_note"] = "Ashtama Shani (8th from Moon)" if sm == 8 else "Kantaka Shani (4th from Moon)"
    jm = transits["Jupiter"]["h_from_moon"]
    transits["jupiter_note"] = "favourable from Moon" if jm in (2, 5, 7, 9, 11) else "neutral/unfavourable from Moon"

    good_lords = list(dict.fromkeys([lord_of(1), lord_of(5), lord_of(9)]))
    remedy_guide = {
        "suitable_stones": {p: STONE[p] for p in good_lords},
        "avoid_stones": {p: STONE[p] for p in dict.fromkeys(lord_of(h) for h in (6, 8, 12)) if p not in good_lords},
        "planet_days": DAY,
        "rule": "Prefer free upay (mantra, daan, service, fasting on the planet's day). Suggest a stone only from "
                "suitable_stones, never from avoid_stones, and advise a trial and consultation before buying.",
    }
    d9 = {p: v["sign_index"] for p, v in c["vargas"].get("D9", {}).items()}
    out = {
        "native": {k: req.get(k) for k in ("name", "dob", "tob", "place") if req.get(k)} | (
            {"birth_time_unknown": "lagna and houses are uncertain; lean on Moon, nakshatra and dasha"} if req.get("tob_unknown") else {}),
        "today": _local(profile, now).date().isoformat(),
        "user_location": _place(profile),
        "lagna": {"sign": SIGNS[L], "lord": lord_of(1), "lord_in_h": house[lord_of(1)], "lord_dignity": dig[lord_of(1)]},
        "moon": {"sign": SIGNS[moon], "nakshatra": g["Moon"]["nakshatra"], "pada": g["Moon"]["pada"],
                 "paksha": "waxing" if waxing else "waning"},
        "planets": planets,
        "houses": houses,
        "yogas": [f"{y['name']} [{y['kind']}]: {y['meaning']}" for y in yogas(signs, L)],
        "exchanges": [f"{a}⇄{b} (H{ha}/H{hb}, {k})" for a, b, ha, hb, k in
                      ((x["planets"][0], x["planets"][1], x["houses"][0], x["houses"][1], x["type"]) for x in exchanges(signs, L))],
        "dasha": dasha,
        "transits_now": transits,
        "remedy_guide": remedy_guide,
        "navamsa": {"signs": {p: SIGNS[s][:3] for p, s in d9.items()},
                    "vargottama": [p for p, s in d9.items() if s == signs.get(p)]},
        "kp": {"cusp_sub_lords": {h["house"]: h["kp"]["sub_lord"] for h in c["houses"]},
               "significators": {p: v["houses"] for p, v in c.get("significators", {}).get("by_planet", {}).items()},
               "note": "KP uses Placidus cusps; houses elsewhere are whole-sign."},
    }
    return out
