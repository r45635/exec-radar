"""Health check endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Response body for the health endpoint."""

    status: str
    timestamp: str
    version: str


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health_check() -> HealthResponse:
    """Return the current health status of the API.

    This endpoint is suitable for use as a liveness probe in Kubernetes or
    any load-balancer health check.
    """
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(UTC).isoformat(),
        version="0.1.0",
    )
