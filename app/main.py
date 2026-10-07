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
from fastapi.staticfiles import StaticFiles

from app import access, admin
from app.astro import router as astro_router
from app.profiles import router as profiles_router
from app.profiles import usage_router
from app.routes import router
from app.telegram_bot import register_webhook
from app.telegram_bot import router as telegram_router
from core import ephemeris


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Load KEY=VALUE lines from a local .env (git-ignored) without overriding real env vars."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


_load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # If Swiss Ephemeris data files are provided, use them; else Moshier fallback.
    ephemeris.configure_ephe_path(os.environ.get("SE_EPHE_PATH"))
    register_webhook()
    yield


app = FastAPI(
    title="SimpleJyotish Chart Engine",
    version="0.1.0",
    description="Vedic chart computation (grahas, KP, vargas, dasha, panchang, transits). "
                "Source offered under AGPL-3.0 per §13.",
    lifespan=lifespan,
)

app.middleware("http")(access.gate)
app.include_router(access.router)
app.include_router(admin.router)
app.include_router(router)
app.include_router(profiles_router)
app.include_router(astro_router)
app.include_router(usage_router)
app.include_router(telegram_router)

_STATIC = Path(__file__).parent / "static"
_INDEX = _STATIC / "index.html"


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(_INDEX, headers={"Cache-Control": "no-cache"})

app.mount("/static", StaticFiles(directory=_STATIC), name="static")
