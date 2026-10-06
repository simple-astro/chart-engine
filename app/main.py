"""Chart Engine FastAPI application (AGPL-3.0).

Only this service links Swiss Ephemeris; the rest of the platform calls it over
this internal HTTP API (FR-3.9).

Stateless by design: it stores no user data and holds no third-party API keys, so
there is nothing here to leak if it is ever reached from outside. Keep it on the
internal network — the platform, not this service, owns users and their data.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.astro import router as astro_router
from app.routes import router
from core import ephemeris


@asynccontextmanager
async def lifespan(app: FastAPI):
    # If Swiss Ephemeris data files are provided, use them; else Moshier fallback.
    ephemeris.configure_ephe_path(os.environ.get("SE_EPHE_PATH"))
    yield


# Interactive docs are useful locally but needlessly advertise the API surface in
# production; ENV=production turns them off.
_PROD = os.environ.get("ENV", "").lower() in ("production", "prod")

app = FastAPI(
    title="SimpleJyotish Chart Engine",
    version="0.1.0",
    description="Vedic chart computation (grahas, KP, vargas, dasha, panchang, transits). "
                "Source offered under AGPL-3.0 per §13.",
    lifespan=lifespan,
    docs_url=None if _PROD else "/docs",
    redoc_url=None if _PROD else "/redoc",
    openapi_url=None if _PROD else "/openapi.json",
)

app.include_router(router)
app.include_router(astro_router)
