"""API route definitions."""

from __future__ import annotations

from fastapi import APIRouter

from apps.api.models import HealthResponse, JobsResponse
from packages.db.profile_repository import resolve_active_target_profile
from packages.db.profile_session import get_session
from packages.pipeline import run_pipeline
from packages.services import build_pipeline_components

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health_check() -> HealthResponse:
    """Return a simple health-check response.

    Used by load balancers, container orchestrators, and monitoring.
    """
    return HealthResponse()


@router.get("/jobs", response_model=JobsResponse, tags=["jobs"])
async def list_jobs() -> JobsResponse:
    """Collect, normalize, rank, and return scored job postings.

    This endpoint demonstrates the full pipeline:
    1. **Collect** raw postings via the mock collector.
    2. **Normalize** each posting into canonical form.
    3. **Rank** normalized postings against the target profile.
    4. Return scored results sorted by fit.
    """
    session = await get_session()
    async with session:
        active_profile = await resolve_active_target_profile(session)
    collector, normalizer, ranker = build_pipeline_components(
        profile=active_profile,
    )
    scored_jobs = await run_pipeline(
        collector=collector,
        normalizer=normalizer,
        ranker=ranker,
    )
    return JobsResponse(count=len(scored_jobs), jobs=scored_jobs)
