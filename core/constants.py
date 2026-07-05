"""Static Jyotisa constants: signs, planets, nakshatras, Vimsottari data."""
from __future__ import annotations

import swisseph as swe

# --- Ayanamsha modes (name -> Swiss Ephemeris sidereal mode) ---
AYANAMSHA_MODES = {
    "krishnamurti": swe.SIDM_KRISHNAMURTI,  # KP (default)
    "lahiri": swe.SIDM_LAHIRI,
}
DEFAULT_AYANAMSHA = "krishnamurti"

# House system is bound to the ayanamsha mode (FR-3.3a).
HOUSE_SYSTEM_FOR_AYANAMSHA = {
    "krishnamurti": "placidus",   # KP mode
    "lahiri": "whole_sign",       # classical mode
}

# --- Rashis (signs), 0-indexed from Aries ---
SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# Sign (rashi) lords, indexed by sign 0..11.
SIGN_LORDS = [
    "Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
    "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter",
]

# --- Grahas we compute (name -> swe planet id). Rahu/Ketu handled specially. ---
GRAHAS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]

SWE_PLANET = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mars": swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS,
    "Saturn": swe.SATURN,
    # Rahu via node (mean/true chosen at runtime); Ketu = Rahu + 180.
}

# Combustion orbs (degrees from Sun) per planet — standard classical values.
COMBUSTION_ORB = {
    "Moon": 12.0,
    "Mars": 17.0,
    "Mercury": 14.0,   # 12 when retrograde; simplified to 14 for v1
    "Jupiter": 11.0,
    "Venus": 10.0,     # 8 when retrograde; simplified to 10 for v1
    "Saturn": 15.0,
}

# --- Nakshatras (27), 13°20' each, with Vimsottari lords in order ---
NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]

# Vimsottari sequence and dasha years (total 120). The nakshatra lords cycle
# through this same 9-lord sequence starting at Ashwini = Ketu.
VIMSOTTARI_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
VIMSOTTARI_YEARS = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
    "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17,
}
VIMSOTTARI_TOTAL_YEARS = 120

# Nakshatra lord for each of the 27 nakshatras (index 0..26).
NAKSHATRA_LORDS = [VIMSOTTARI_ORDER[i % 9] for i in range(27)]

NAKSHATRA_ARC = 360.0 / 27.0      # 13°20'
PADA_ARC = NAKSHATRA_ARC / 4.0    # 3°20'

# --- Panchang tables ---
WEEKDAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

YOGAS = [
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda",
    "Sukarma", "Dhriti", "Shula", "Ganda", "Vriddhi", "Dhruva",
    "Vyaghata", "Harshana", "Vajra", "Siddhi", "Vyatipata", "Variyana",
    "Parigha", "Shiva", "Siddha", "Sadhya", "Shubha", "Shukla",
    "Brahma", "Indra", "Vaidhriti",
]

# The 60 karana half-tithis map onto 11 karana names: 7 movable repeat, 4 fixed.
# Sequence: karana index 0 = first half of tithi 1 (Kimstughna, fixed), then the
# 7 movable cycle for indices 1..57, and the last 3 (58,59,60) are the fixed
# Shakuni, Chatushpada, Naga. Index here is 0-based half-tithi (0..59).
_MOVABLE_KARANAS = ["Bava", "Balava", "Kaulava", "Taitila", "Gara", "Vanija", "Vishti"]


def karana_name(karana_index_0based: int) -> str:
    i = karana_index_0based
    if i == 0:
        return "Kimstughna"
    if i >= 57:
        return {57: "Shakuni", 58: "Chatushpada", 59: "Naga"}[i]
    return _MOVABLE_KARANAS[(i - 1) % 7]


# Segment (1..8 of daytime) for each window, indexed by Vedic weekday (Sunday=0).
RAHU_KALAM_SEGMENT = {0: 8, 1: 2, 2: 7, 3: 5, 4: 6, 5: 4, 6: 3}
YAMAGANDA_SEGMENT = {0: 5, 1: 4, 2: 3, 3: 2, 4: 1, 5: 7, 6: 6}
GULIKA_SEGMENT = {0: 7, 1: 6, 2: 5, 3: 4, 4: 3, 5: 2, 6: 1}
