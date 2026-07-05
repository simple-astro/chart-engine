"""Shodashavarga: the 16 classical divisional charts, computed from D1 longitudes.

Each function maps a sidereal longitude to a divisional sign index (0..11) using
the standard Parasari rules (per BPHS / Jagannatha Hora conventions).
"""
from __future__ import annotations

from core import constants as C

VARGA_DIVISIONS = [1, 2, 3, 4, 7, 9, 10, 12, 16, 20, 24, 27, 30, 40, 45, 60]


def _sd(longitude: float) -> tuple[int, float]:
    longitude = longitude % 360.0
    s = int(longitude // 30)
    d = longitude - s * 30.0
    return s, d


def _is_odd_sign(s: int) -> bool:
    return s % 2 == 0  # index 0 = Aries = 1st sign = odd


def _movability(s: int) -> int:
    return s % 3  # 0 movable, 1 fixed, 2 dual


def _element(s: int) -> int:
    return s % 4  # 0 fiery, 1 earthy, 2 airy, 3 watery


def _equal(s: int, d: float, n: int, start: int) -> int:
    part = int(d // (30.0 / n))
    return (start + part) % 12


def _d1(s, d): return s
def _d3(s, d): return (s + 4 * int(d // 10.0)) % 12
def _d4(s, d): return (s + 3 * int(d // 7.5)) % 12
def _d9(s, d): return (9 * s + int(d // (30.0 / 9))) % 12
def _d12(s, d): return (s + int(d // 2.5)) % 12
def _d60(s, d): return (s + int(d // 0.5)) % 12


def _d2(s, d):
    # Odd sign: 0-15 Leo, 15-30 Cancer. Even sign reversed.
    first_half = d < 15.0
    if _is_odd_sign(s):
        return 4 if first_half else 3       # Leo / Cancer
    return 3 if first_half else 4           # Cancer / Leo


def _d7(s, d):
    start = s if _is_odd_sign(s) else (s + 6) % 12
    return _equal(s, d, 7, start)


def _d10(s, d):
    start = s if _is_odd_sign(s) else (s + 8) % 12
    return _equal(s, d, 10, start)


def _d16(s, d):
    start = {0: 0, 1: 4, 2: 8}[_movability(s)]   # movable Aries, fixed Leo, dual Sag
    return _equal(s, d, 16, start)


def _d20(s, d):
    start = {0: 0, 1: 8, 2: 4}[_movability(s)]   # movable Aries, fixed Sag, dual Leo
    return _equal(s, d, 20, start)


def _d24(s, d):
    start = 4 if _is_odd_sign(s) else 3          # odd Leo, even Cancer
    return _equal(s, d, 24, start)


def _d27(s, d):
    start = {0: 0, 1: 3, 2: 6, 3: 9}[_element(s)]  # fiery Aries, earthy Cancer, airy Libra, watery Cap
    return _equal(s, d, 27, start)


def _d40(s, d):
    start = 0 if _is_odd_sign(s) else 6          # odd Aries, even Libra
    return _equal(s, d, 40, start)


def _d45(s, d):
    start = {0: 0, 1: 4, 2: 8}[_movability(s)]   # movable Aries, fixed Leo, dual Sag
    return _equal(s, d, 45, start)


# Trimshamsha (D30): unequal divisions ruled by planets; result is the lord's sign.
_D30_ODD = [(5.0, "Mars"), (10.0, "Saturn"), (18.0, "Jupiter"), (25.0, "Mercury"), (30.0, "Venus")]
_D30_EVEN = [(5.0, "Venus"), (12.0, "Mercury"), (20.0, "Jupiter"), (25.0, "Saturn"), (30.0, "Mars")]
# A representative sign owned by each Trimshamsha lord (odd->fiery/masculine side).
_D30_SIGN = {"Mars": 0, "Saturn": 10, "Jupiter": 8, "Mercury": 2, "Venus": 6}      # odd signs
_D30_SIGN_EVEN = {"Venus": 1, "Mercury": 5, "Jupiter": 11, "Saturn": 9, "Mars": 7}  # even signs


def _d30(s, d):
    table = _D30_ODD if _is_odd_sign(s) else _D30_EVEN
    signs = _D30_SIGN if _is_odd_sign(s) else _D30_SIGN_EVEN
    for upper, lord in table:
        if d < upper:
            return signs[lord]
    return signs[table[-1][1]]


_DISPATCH = {
    1: _d1, 2: _d2, 3: _d3, 4: _d4, 7: _d7, 9: _d9, 10: _d10, 12: _d12,
    16: _d16, 20: _d20, 24: _d24, 27: _d27, 30: _d30, 40: _d40, 45: _d45, 60: _d60,
}


def varga_sign(longitude: float, n: int) -> int:
    """Divisional sign index (0..11) for a sidereal longitude in the Dn chart."""
    if n not in _DISPATCH:
        raise ValueError(f"unsupported varga: D{n}")
    s, d = _sd(longitude)
    return _DISPATCH[n](s, d)


def compute_vargas(grahas: dict) -> dict:
    """Compute all 16 vargas for every graha.

    Returns {"D9": {"Sun": {"sign_index": .., "sign": ..}, ...}, ...}.
    """
    result: dict[str, dict] = {}
    for n in VARGA_DIVISIONS:
        chart: dict[str, dict] = {}
        for name, graha in grahas.items():
            si = varga_sign(graha.longitude, n)
            chart[name] = {"sign_index": si, "sign": C.SIGNS[si]}
        result[f"D{n}"] = chart
    return result
