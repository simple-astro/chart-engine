"""Ashtakavarga (BPHS): each of the seven planets gets a bindu in a sign when that sign
falls at a benefic place counted from each of the eight contributors (seven planets +
lagna). Bhinnashtakavarga (BAV) per planet, Sarvashtakavarga (SAV) is their sum (337).
"""
from __future__ import annotations

PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
CONTRIBUTORS = PLANETS + ["Lagna"]

# BENEFIC[planet][contributor] = houses (1-based) counted from the contributor's sign.
BENEFIC: dict[str, dict[str, tuple[int, ...]]] = {
    "Sun": {"Sun": (1, 2, 4, 7, 8, 9, 10, 11), "Moon": (3, 6, 10, 11), "Mars": (1, 2, 4, 7, 8, 9, 10, 11),
            "Mercury": (3, 5, 6, 9, 10, 11, 12), "Jupiter": (5, 6, 9, 11), "Venus": (6, 7, 12),
            "Saturn": (1, 2, 4, 7, 8, 9, 10, 11), "Lagna": (3, 4, 6, 10, 11, 12)},
    "Moon": {"Sun": (3, 6, 7, 8, 10, 11), "Moon": (1, 3, 6, 7, 10, 11), "Mars": (2, 3, 5, 6, 9, 10, 11),
             "Mercury": (1, 3, 4, 5, 7, 8, 10, 11), "Jupiter": (1, 4, 7, 8, 10, 11, 12),
             "Venus": (3, 4, 5, 7, 9, 10, 11), "Saturn": (3, 5, 6, 11), "Lagna": (3, 6, 10, 11)},
    "Mars": {"Sun": (3, 5, 6, 10, 11), "Moon": (3, 6, 11), "Mars": (1, 2, 4, 7, 8, 10, 11),
             "Mercury": (3, 5, 6, 11), "Jupiter": (6, 10, 11, 12), "Venus": (6, 8, 11, 12),
             "Saturn": (1, 4, 7, 8, 9, 10, 11), "Lagna": (1, 3, 6, 10, 11)},
    "Mercury": {"Sun": (5, 6, 9, 11, 12), "Moon": (2, 4, 6, 8, 10, 11), "Mars": (1, 2, 4, 7, 8, 9, 10, 11),
                "Mercury": (1, 3, 5, 6, 9, 10, 11, 12), "Jupiter": (6, 8, 11, 12),
                "Venus": (1, 2, 3, 4, 5, 8, 9, 11), "Saturn": (1, 2, 4, 7, 8, 9, 10, 11),
                "Lagna": (1, 2, 4, 6, 8, 10, 11)},
    "Jupiter": {"Sun": (1, 2, 3, 4, 7, 8, 9, 10, 11), "Moon": (2, 5, 7, 9, 11), "Mars": (1, 2, 4, 7, 8, 10, 11),
                "Mercury": (1, 2, 4, 5, 6, 9, 10, 11), "Jupiter": (1, 2, 3, 4, 7, 8, 10, 11),
                "Venus": (2, 5, 6, 9, 10, 11), "Saturn": (3, 5, 6, 12), "Lagna": (1, 2, 4, 5, 6, 7, 9, 10, 11)},
    "Venus": {"Sun": (8, 11, 12), "Moon": (1, 2, 3, 4, 5, 8, 9, 11, 12), "Mars": (3, 5, 6, 9, 11, 12),
              "Mercury": (3, 5, 6, 9, 11), "Jupiter": (5, 8, 9, 10, 11), "Venus": (1, 2, 3, 4, 5, 8, 9, 10, 11),
              "Saturn": (3, 4, 5, 8, 9, 10, 11), "Lagna": (1, 2, 3, 4, 5, 8, 9, 11)},
    "Saturn": {"Sun": (1, 2, 4, 7, 8, 10, 11), "Moon": (3, 6, 11), "Mars": (3, 5, 6, 10, 11, 12),
               "Mercury": (6, 8, 9, 10, 11, 12), "Jupiter": (5, 6, 11, 12), "Venus": (6, 11, 12),
               "Saturn": (3, 5, 6, 11), "Lagna": (1, 3, 4, 6, 10, 11)},
}


def ashtakavarga(signs: dict[str, int], lagna_sign: int) -> dict:
    """signs: planet -> sign index (0 = Aries). Returns BAV and SAV indexed by sign."""
    pos = {**{p: signs[p] for p in PLANETS}, "Lagna": lagna_sign}
    bav = {}
    for planet in PLANETS:
        row = [0] * 12
        for contrib, houses in BENEFIC[planet].items():
            for h in houses:
                row[(pos[contrib] + h - 1) % 12] += 1
        bav[planet] = row
    sav = [sum(bav[p][s] for p in PLANETS) for s in range(12)]
    return {
        "bav": bav,
        "sav": sav,
        "bav_totals": {p: sum(bav[p]) for p in PLANETS},
        "sav_total": sum(sav),
        "own_bindus": {p: bav[p][signs[p]] for p in PLANETS},
    }
