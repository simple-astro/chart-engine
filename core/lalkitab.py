"""Lal Kitab chart analysis from a natal chart dict.

Conventions (as used by most Lal Kitab software): whole-sign houses counted from the lagna sign
(lagna sign = house 1), sidereal Lahiri positions. Lal Kitab judges planets by HOUSE, not sign.
Rules below are the commonly published core; traditions differ in detail.
"""
from __future__ import annotations

GRAHAS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]

# Pakka ghar (permanent house) of each planet
PAKKA = {"Sun": [1], "Moon": [4], "Mars": [3, 8], "Mercury": [7], "Jupiter": [2, 5, 9, 12],
         "Venus": [7], "Saturn": [8, 10], "Rahu": [12], "Ketu": [6]}
# House-based exaltation / debilitation
UCCH = {"Sun": 1, "Moon": 2, "Mars": 10, "Mercury": 6, "Jupiter": 4, "Venus": 12, "Saturn": 7, "Rahu": 3, "Ketu": 9}
NEECH = {"Sun": 7, "Moon": 8, "Mars": 4, "Mercury": 12, "Jupiter": 10, "Venus": 6, "Saturn": 1, "Rahu": 9, "Ketu": 3}

HOUSE_THEME = {1: "self, body, personality", 2: "family, wealth, speech", 3: "courage, siblings, efforts",
               4: "mother, home, peace of mind", 5: "children, education, speculation", 6: "enemies, health, service",
               7: "spouse, partnerships, business", 8: "longevity, sudden events, secrets",
               9: "luck, father, dharma", 10: "career, status, authority", 11: "gains, elder siblings, friends",
               12: "expenses, sleep, foreign, losses"}

# Commonly quoted traditional remedies (general, low-risk). Not a substitute for advice.
REMEDIES = {
    "Sun": ["Offer water to the rising Sun daily.", "Donate wheat or jaggery on Sundays.",
            "Respect your father and elders; avoid taking free gifts or favours."],
    "Moon": ["Offer milk or water at a Shiva temple on Mondays.", "Keep water in a silver glass or a small silver piece with you.",
             "Respect and serve your mother; donate rice or milk on Mondays."],
    "Mars": ["Donate red lentils (masoor) on Tuesdays.", "Offer sweets to Hanuman on Tuesdays.",
             "Keep good relations with brothers; avoid anger and false promises."],
    "Mercury": ["Donate green moong or green fodder on Wednesdays.", "Feed green fodder to cows.",
                "Keep speech truthful; respect daughters, sisters and aunts."],
    "Jupiter": ["Donate chana dal or turmeric on Thursdays.", "Apply a saffron or turmeric tilak daily.",
                "Water a Peepal tree; respect teachers, father and elders."],
    "Venus": ["Donate curd, ghee or white items on Fridays.", "Serve or feed cows; keep clothing and home clean.",
              "Respect your wife and women of the household."],
    "Saturn": ["Donate mustard oil, black urad or iron on Saturdays.", "Feed crows and serve the poor or labourers.",
               "Avoid alcohol and be honest in work."],
    "Rahu": ["Flow a coconut or a little barley in running water.", "Donate radish or barley on Wednesdays.",
             "Keep the south-west corner of the home clean and uncluttered."],
    "Ketu": ["Feed dogs (especially brown or two-coloured) with chapati.", "Donate a blanket or sesame (til) to the needy.",
             "Worship Lord Ganesha; respect nephews, in-laws and sons."],
}

RIN_REMEDY = {
    "Pitru Rin": "Respect father and ancestors, do not take things free from others, and offer water to a Peepal tree on Saturdays.",
    "Matru Rin": "Serve your mother, avoid taking milk-related gifts, and offer milk or water at a temple on Mondays.",
}


def _house(chart: dict, planet: str) -> int:
    return (chart["grahas"][planet]["sign_index"] - chart["lagna"]["sign_index"]) % 12 + 1


def compute_lal_kitab(chart: dict) -> dict:
    houses_of = {p: _house(chart, p) for p in GRAHAS}
    by_house = {h: [p for p in GRAHAS if houses_of[p] == h] for h in range(1, 13)}

    planets = []
    for p in GRAHAS:
        h = houses_of[p]
        status = []
        if h in PAKKA[p]:
            status.append("In pakka ghar (strong)")
        if UCCH[p] == h:
            status.append("Exalted by house")
        if NEECH[p] == h:
            status.append("Debilitated by house")
        # Simplified 'sleeping planet': nobody sits in the house it looks at (the 7th from it).
        opposite = (h + 5) % 12 + 1
        sleeping = not by_house[opposite]
        if sleeping:
            status.append("Sleeping (no planet in its 7th)")
        planets.append({"planet": p, "house": h, "sign": chart["grahas"][p]["sign"],
                        "pakka_ghar": PAKKA[p], "theme": HOUSE_THEME[h], "status": status,
                        "sleeping": sleeping, "debilitated": NEECH[p] == h,
                        "retrograde": chart["grahas"][p]["retrograde"]})

    rin = []
    pit = [p for p in ("Venus", "Mercury", "Rahu") if houses_of[p] in (2, 5, 9, 12)]
    if pit:
        rin.append({"name": "Pitru Rin (debt of the father/ancestors)",
                    "why": ", ".join(f"{p} in house {houses_of[p]}" for p in pit),
                    "remedy": RIN_REMEDY["Pitru Rin"]})
    if houses_of["Ketu"] == 4 or houses_of["Moon"] in (3, 6, 8, 10, 11, 12):
        why = []
        if houses_of["Ketu"] == 4:
            why.append("Ketu in house 4")
        if houses_of["Moon"] in (3, 6, 8, 10, 11, 12):
            why.append(f"Moon in house {houses_of['Moon']}")
        rin.append({"name": "Matru Rin (debt of the mother)", "why": ", ".join(why),
                    "remedy": RIN_REMEDY["Matru Rin"]})

    priority = [p["planet"] for p in planets
                if p["debilitated"] or (p["sleeping"] and p["house"] not in p["pakka_ghar"])]
    remedies = [{"planet": p, "house": houses_of[p], "priority": p in priority, "actions": REMEDIES[p]} for p in GRAHAS]
    remedies.sort(key=lambda r: (not r["priority"], GRAHAS.index(r["planet"])))

    return {
        "convention": "Whole-sign houses from the lagna sign (lagna = house 1), Lahiri ayanamsha. "
                      "Lal Kitab judges planets by house, not sign.",
        "lagna_sign": chart["lagna"]["sign"],
        "houses": {str(h): by_house[h] for h in range(1, 13)},
        "planets": planets, "rin": rin, "remedies": remedies,
        "disclaimer": "Lal Kitab remedies are traditional beliefs, not scientific or guaranteed. "
                      "Do not use them in place of medical, legal or financial advice.",
    }
