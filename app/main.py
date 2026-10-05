"""Chart Engine FastAPI application (AGPL-3.0).

Only this service links Swiss Ephemeris; the rest of the platform calls it over
this internal HTTP API (FR-3.9).
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.routes import router
from core import ephemeris


@asynccontextmanager
async def lifespan(app: FastAPI):
    # If Swiss Ephemeris data files are provided, use them; else Moshier fallback.
    ephemeris.configure_ephe_path(os.environ.get("SE_EPHE_PATH"))
    yield


app = FastAPI(
    title="Jyotish Chart Engine",
    version="0.1.0",
    description="Vedic chart computation (grahas, KP, vargas, dasha, panchang, transits). "
                "Source offered under AGPL-3.0 per §13.",
    lifespan=lifespan,
)

app.include_router(router)

_INDEX = Path(__file__).parent / "static" / "index.html"


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(_INDEX)
