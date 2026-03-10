"""Exec Radar dashboard — server-rendered Jinja2 UI.

A lightweight FastAPI sub-application that renders a dashboard page
using the existing ``/health`` and ``/jobs`` API endpoints.  Mounted
on the main application at ``/dashboard``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from packages.pipeline import run_pipeline
from packages.services import build_pipeline_components
from packages.version import __version__

logger = logging.getLogger(__name__)

_DIR = Path(__file__).resolve().parent

dashboard_app = FastAPI(
    title="Exec Radar Dashboard",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

dashboard_app.mount(
    "/static",
    StaticFiles(directory=_DIR / "static"),
    name="dashboard_static",
)

templates = Jinja2Templates(directory=_DIR / "templates")


@dashboard_app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Render the main dashboard page.

    Fetches health and jobs data from the pipeline in-process
    (no HTTP round-trip needed since we share the same Python process).
    """
    # ── Health check ───────────────────────────────────────
    health_ok = True
    health_version = __version__
    health_error = ""

    # ── Jobs ───────────────────────────────────────────────
    jobs: list = []
    jobs_error = ""
    try:
        collector, normalizer, ranker = build_pipeline_components()
        jobs = await run_pipeline(
            collector=collector,
            normalizer=normalizer,
            ranker=ranker,
        )
    except Exception as exc:
        logger.exception("Dashboard: failed to load jobs")
        jobs_error = str(exc)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "version": __version__,
            "health_ok": health_ok,
            "health_version": health_version,
            "health_error": health_error,
            "jobs": jobs,
            "job_count": len(jobs),
            "jobs_error": jobs_error,
        },
    )
