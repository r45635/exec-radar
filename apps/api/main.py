"""FastAPI application factory for Exec Radar."""

from __future__ import annotations

from fastapi import FastAPI

from apps.api.config import get_settings
from apps.api.profile_routes import router as profile_router
from apps.api.routes import router
from apps.dashboard.app import dashboard_app
from packages.version import __version__


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application.

    Returns:
        A :class:`FastAPI` instance with all routes registered.
    """
    cfg = get_settings()
    app = FastAPI(
        title=cfg.app_name,
        version=__version__,
        description="AI-powered executive opportunity intelligence API",
        debug=cfg.debug,
    )
    app.include_router(router)
    app.include_router(profile_router)
    app.mount("/dashboard", dashboard_app, name="dashboard")
    return app


app = create_app()
