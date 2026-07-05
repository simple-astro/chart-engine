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
