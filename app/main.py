"""
FastAPI application entry point.

Creates the app, mounts the router, and handles startup/shutdown events
(creating DB tables and shutting down the background thread pool).
"""

import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import database
from app.database import Base
from app.routers.jobs import router as jobs_router
from app.services.job_processor import shutdown_executor

STATIC_DIR = Path(__file__).resolve().parent / "static"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Startup: create all tables (safe to call multiple times)
    Base.metadata.create_all(bind=database.engine)
    logging.getLogger(__name__).info("Database tables created")
    yield
    # Shutdown: cleanly stop the background worker pool
    shutdown_executor()
    logging.getLogger(__name__).info("Worker pool shut down")


app = FastAPI(
    title="Bulk Certificate Generator",
    description=(
        "API for generating certificates in bulk. Submit a list of recipients "
        "and a course name, then poll for progress and download the generated PDFs."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(jobs_router)


@app.get("/", tags=["health"])
def health_check(request: Request):
    """
    Root endpoint: serves the interactive dashboard to browser clients,
    or returns a JSON status object for API clients and automated tests.
    """
    accept = request.headers.get("accept", "")
    if "text/html" in accept and not accept.startswith("*/*"):
        index_file = STATIC_DIR / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
    return {"status": "ok", "service": "Bulk Certificate Generator"}


@app.get("/dashboard", tags=["ui"])
def dashboard():
    """Direct URL for the web dashboard."""
    index_file = STATIC_DIR / "index.html"
    return FileResponse(index_file)
