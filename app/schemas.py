"""Pydantic request models for the Chart Engine HTTP API."""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field

Ayanamsha = Literal["krishnamurti", "lahiri"]
NodeType = Literal["mean", "true"]


class ChartRequest(BaseModel):
    name: str = Field(default="", max_length=200)
    dob: date
    tob: time
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    tz_name: str = Field(description="IANA timezone, e.g. Asia/Kolkata")
    tob_unknown: bool = False
    ayanamsha: Ayanamsha = "krishnamurti"
    node_type: NodeType = "mean"


class TransitRequest(BaseModel):
    when: datetime = Field(description="Timezone-aware datetime")
    ayanamsha: Ayanamsha = "krishnamurti"
    node_type: NodeType = "mean"


class PanchangRequest(BaseModel):
    on: date
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    tz_name: str = Field(description="IANA timezone, e.g. Asia/Kolkata")


class TransitScanRequest(BaseModel):
    start: datetime = Field(description="Timezone-aware UTC datetime; naive is treated as UTC")
    days: int = Field(default=7, ge=1, le=31)
    ayanamsha: Ayanamsha = "krishnamurti"
    node_type: NodeType = "mean"
