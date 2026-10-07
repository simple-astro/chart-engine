"""Admin-editable runtime settings.

Each value comes from the database if an admin saved one, else the environment,
else a default, so the admin page takes effect without a redeploy.
"""
from __future__ import annotations

import json
import os

from app import storage

# USD per million tokens. cache_write is the 5-minute TTL rate (1.25x input).
MODELS = {
    "claude-haiku-4-5": {"label": "Claude Haiku 4.5", "note": "Fastest and cheapest",
                         "in": 1.0, "out": 5.0, "cache_read": 0.10, "cache_write": 1.25},
    "claude-sonnet-5-5": {"label": "Claude Sonnet 5.5", "note": "Balanced quality and cost",
                          "in": 2.0, "out": 10.0, "cache_read": 0.20, "cache_write": 2.50},
    "claude-opus-5-5": {"label": "Claude Opus 5.5", "note": "Deeper answers, about 4x Haiku",
                        "in": 4.0, "out": 20.0, "cache_read": 0.20, "cache_write": 5.00},
    "claude-fable-5-1": {"label": "Claude Fable 5.1", "note": "Most capable, about 10x Haiku, slower",
                         "in": 10.0, "out": 50.0, "cache_read": 0.25, "cache_write": 12.50},
}

FIELDS = {
    # key: (env var, default, validator)
    "model": ("CHART_LLM_MODEL", "claude-haiku-4-5", lambda v: v in MODELS),
    "word_limit": ("CHAT_WORD_LIMIT", 300, lambda v: isinstance(v, int) and 100 <= v <= 800),
    "daily_limit_per_tester": ("CHAT_DAILY_LIMIT_PER_TESTER", 30, lambda v: isinstance(v, int) and 0 <= v <= 1000),
    "daily_limit_total": ("CHAT_DAILY_LIMIT_TOTAL", 300, lambda v: isinstance(v, int) and 0 <= v <= 10000),
    "telegram_daily_limit": ("TELEGRAM_DAILY_LIMIT", 5, lambda v: isinstance(v, int) and 0 <= v <= 1000),
}
LIMITS_TEXT = {
    "model": "must be one of the listed models",
    "word_limit": "must be a whole number from 100 to 800",
    "daily_limit_per_tester": "must be a whole number from 0 to 1000",
    "daily_limit_total": "must be a whole number from 0 to 10000",
    "telegram_daily_limit": "must be a whole number from 0 to 1000",
}


def _model_id(raw: str) -> str:
    """Accept dated or legacy ids (e.g. claude-haiku-4-5-20251001) by prefix."""
    return next((m for m in MODELS if raw == m or raw.startswith(m + "-")), raw)


def get(key: str):
    env, default, valid = FIELDS[key]
    saved = storage.get_setting(f"config.{key}")
    if saved is not None:
        value = json.loads(saved)
        if valid(value):
            return value
    raw = os.environ.get(env)
    if raw:
        value = _model_id(raw) if key == "model" else (int(raw) if raw.strip().isdigit() else None)
        if value is not None and valid(value):
            return value
    return default


def all_settings() -> dict:
    return {k: get(k) for k in FIELDS}


def update(values: dict) -> dict:
    """Validate everything first, then save; raises ValueError naming the bad field."""
    clean = {}
    for key, value in values.items():
        if key not in FIELDS:
            raise ValueError(f"Unknown setting: {key}")
        if key != "model" and isinstance(value, bool):
            raise ValueError(f"{key} {LIMITS_TEXT[key]}")
        if not FIELDS[key][2](value):
            raise ValueError(f"{key} {LIMITS_TEXT[key]}")
        clean[key] = value
    for key, value in clean.items():
        storage.set_setting(f"config.{key}", json.dumps(value))
    return all_settings()


def model() -> str:
    return get("model")


def word_limit() -> int:
    return get("word_limit")


def label(model_id: str | None) -> str | None:
    p = MODELS.get(_model_id(model_id or ""))
    return p["label"] if p else model_id


def cost(model_id: str | None, inp: int, out: int, cache_read: int, cache_write: int) -> float | None:
    """Estimated USD for one request's tokens; None when the model's price is unknown."""
    p = MODELS.get(_model_id(model_id or ""))
    if not p:
        return None
    return (inp * p["in"] + out * p["out"] + cache_read * p["cache_read"] + cache_write * p["cache_write"]) / 1e6
