"""FastAPI application factory for Exec Radar."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import health, jobs


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        A fully configured :class:`FastAPI` instance ready for serving.
    """
    app = FastAPI(
        title="Exec Radar API",
        description=(
            "AI-powered executive job intelligence platform. "
            "Collects, normalizes, scores, and surfaces leadership job postings."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS – tighten this in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, tags=["Health"])
    app.include_router(jobs.router, prefix="/api/v1", tags=["Jobs"])

    return app


app = create_app()
