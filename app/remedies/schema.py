"""What a valid remedy-library item looks like, and the content rules every item must pass.

Kinds: ``graha`` (the 9-planet correspondence table), ``remedy``, ``rule`` (a prohibition or contraindication:
when a planet sits in a house / sign / dignity, some remedy types or materials are blocked for that person),
``rin`` (Lal Kitab karmic debts) and ``home_audit``. Items are validated on import and on every edit.
"""
from __future__ import annotations

import re

GRAHAS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
KINDS = ("graha", "remedy", "rule", "rin", "home_audit")
TYPES = ("aacharan", "seva", "daan", "jal_pravah", "ahar", "vastra_rang", "vanaspati", "griha", "mantra", "vrat",
         "yantra_puja", "ratna")
SOURCES = ("parashari", "lal_kitab", "vastu", "folk")
INTENTS = ("strengthen", "pacify", "maintain")
COST = ("free", "low", "medium", "high")
STATUSES = ("pending_astrologer", "approved", "retired")
AUDIT_ACTIONS = ("keep", "clean", "donate", "throw", "respectful_disposal")
DURATIONS = (1, 7, 21, 40, 43)
SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{1,79}$")

# Never seeded or served: animal parts, wildlife products, anything illegal to own or trade.
BANNED = re.compile(r"\b(ivory|deer ?skin|tiger|leopard|animal parts?|bones?|tortoise shell|turtle shell|owl|"
                    r"hatha ?jodi|siyar ?singhi|musk|pangolin|snake ?skin|elephant tusk)\b", re.I)
# No fear-selling: user-facing text may not threaten consequences.
FEAR = re.compile(r"\b(death|die|dies|dying|murder|imprison\w*|jail|poverty|childless\w*|ruin\w*|curse[sd]?|"
                  r"destroy\w*|disaster|miscarriage|bankrupt\w*)\b", re.I)


class Invalid(ValueError):
    pass


def _text(item: dict) -> str:
    """All user-facing text of an item, for the banned-material and fear checks."""
    out = []

    def walk(v):
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for k, x in v.items():
                if k not in ("slug", "kind", "review_status", "review_note"):  # astrologer notes may discuss anything
                    walk(x)
    walk(item)
    return " \n ".join(out)


def _need(item: dict, *keys: str) -> None:
    missing = [k for k in keys if item.get(k) in (None, "", [], {})]
    if missing:
        raise Invalid(f"missing {', '.join(missing)}")


def _one_of(item: dict, key: str, allowed) -> None:
    if item.get(key) not in allowed:
        raise Invalid(f"{key} must be one of {', '.join(map(str, allowed))}")


def _list_of_str(item: dict, key: str, required: bool = False) -> None:
    v = item.get(key)
    if v is None and not required:
        return
    if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v) or (required and not v):
        raise Invalid(f"{key} must be a list of text")


def _graha(item: dict) -> None:
    _need(item, "planet", "colors", "beej_mantra", "japa_count")
    _one_of(item, "planet", GRAHAS)
    for k in ("colors", "metals", "gem_substitutes", "foods", "relationships", "donate_items", "keep_at_home",
              "clean_or_remove", "japa_count_alternates"):
        if k == "japa_count_alternates":
            if not all(isinstance(x, int) and x > 0 for x in item.get(k) or []):
                raise Invalid("japa_count_alternates must be whole numbers")
            continue
        _list_of_str(item, k)
    if not isinstance(item["japa_count"], int) or item["japa_count"] <= 0:
        raise Invalid("japa_count must be a whole number")
    if item.get("gem") and not item.get("gem_substitutes"):
        raise Invalid("a gem needs at least one substitute")


def _remedy(item: dict) -> None:
    _need(item, "planet", "type", "source", "intent", "cost_tier", "effort", "title", "steps", "why_template")
    _one_of(item, "planet", GRAHAS)
    _one_of(item, "type", TYPES)
    _one_of(item, "source", SOURCES)
    if not isinstance(item["intent"], list) or not item["intent"] or any(i not in INTENTS for i in item["intent"]):
        raise Invalid(f"intent must be a list drawn from {', '.join(INTENTS)}")
    _one_of(item, "cost_tier", COST)
    if not isinstance(item["effort"], int) or not 1 <= item["effort"] <= 5:
        raise Invalid("effort must be a whole number from 1 to 5")
    _list_of_str(item, "steps", required=True)
    _list_of_str(item, "materials")
    _list_of_str(item, "safety_notes")
    t = item.get("timing") or {}
    if not isinstance(t, dict):
        raise Invalid("timing must be an object")
    if t.get("weekday") is not None and t["weekday"] not in ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday",
                                                             "Friday", "Saturday"):
        raise Invalid("timing.weekday must be a weekday name")
    if t.get("duration_days", 43) not in DURATIONS:
        raise Invalid(f"timing.duration_days must be one of {DURATIONS}")
    if item["type"] == "jal_pravah" and not item.get("diaspora_alternative"):
        raise Invalid("a jal pravah (water immersion) remedy needs a diaspora_alternative — many places forbid "
                      "putting things in rivers")
    if item["type"] == "vrat" and (not item.get("safety_notes") or not item.get("light_variant")):
        raise Invalid("a vrat (fast) needs safety_notes (pregnancy, diabetes, eating concerns) and a light_variant")
    if item["type"] == "ratna":
        if not item.get("substitute") or item.get("requires_advisor_review") is not True:
            raise Invalid("a gemstone remedy needs a substitute and requires_advisor_review: true")
        if "pacify" in item["intent"]:
            raise Invalid("a gemstone strengthens a planet, so it can never be a pacify remedy")


def _rule(item: dict) -> None:
    _need(item, "planet", "when", "blocks", "reason")
    _one_of(item, "planet", GRAHAS + ["any"])  # "any": e.g. whichever planet is exalted
    w, b = item["when"], item["blocks"]
    if not isinstance(w, dict) or not set(w) <= {"house", "houses", "sign", "dignity", "system"}:
        raise Invalid("when may use house, houses, sign, dignity and system (lal_kitab | kp)")
    if not isinstance(b, dict) or not set(b) <= {"types", "materials", "slugs", "planet_types"} or not any(b.values()):
        raise Invalid("blocks must name types, materials or slugs")
    if any(t not in TYPES for t in b.get("types", [])):
        raise Invalid("blocks.types must be remedy types")


def _rin(item: dict) -> None:
    _need(item, "name", "when", "remedy_steps", "why_template")
    _list_of_str(item, "remedy_steps", required=True)
    w = item["when"]
    if not isinstance(w, dict) or not w.get("any_of") or not all(
            isinstance(c, dict) and c.get("planet") in GRAHAS and c.get("houses") for c in w["any_of"]):
        raise Invalid("when.any_of must list {planet, houses} conditions")


def _home(item: dict) -> None:
    _need(item, "zone", "planet", "prompt", "suggested_action", "explanation")
    _one_of(item, "planet", GRAHAS)
    _one_of(item, "suggested_action", AUDIT_ACTIONS)


CHECK = {"graha": _graha, "remedy": _remedy, "rule": _rule, "rin": _rin, "home_audit": _home}


def validate(kind: str, item: dict) -> dict:
    """Return a cleaned copy of ``item`` or raise ``Invalid`` with a plain reason."""
    if kind not in KINDS:
        raise Invalid(f"kind must be one of {', '.join(KINDS)}")
    if not isinstance(item, dict):
        raise Invalid("each item must be an object")
    slug = item.get("slug") or (item.get("planet", "").lower() if kind == "graha" else "")
    if not isinstance(slug, str) or not SLUG.match(slug):
        raise Invalid("slug must be 2–80 lowercase letters, digits, - or _")
    status = item.get("review_status", "pending_astrologer")
    if status not in STATUSES:
        raise Invalid(f"review_status must be one of {', '.join(STATUSES)}")
    CHECK[kind](item)
    text = _text(item)
    if (m := BANNED.search(text)):
        raise Invalid(f"banned material: {m.group(0)!r}")
    if (m := FEAR.search(text)):
        raise Invalid(f"fear wording is not allowed in user-facing text: {m.group(0)!r}")
    return {**item, "slug": slug, "review_status": status}
