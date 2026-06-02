"""GeoVision Pro — FastAPI application entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .core.logging import configure_logging
from .database import init_models
from .routers import analyze, health, jobs, reports

settings = get_settings()
configure_logging(settings.debug)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (dev). In prod, prefer sql/schema.sql or Alembic.
    await init_models()
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

origins = ["*"] if settings.cors_origins.strip() == "*" else \
    [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(analyze.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(reports.router, prefix="/api")


@app.get("/")
async def root() -> dict:
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/health"}
