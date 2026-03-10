"""Pydantic response models for the API layer."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from packages.schemas.scored_job import ScoredJob
from packages.version import __version__


class HealthResponse(BaseModel):
    """Response payload for the health-check endpoint."""

    model_config = ConfigDict(frozen=True)

    status: str = Field(default="ok", description="Service status")
    version: str = Field(default=__version__, description="API version")


class JobsResponse(BaseModel):
    """Response payload for the jobs listing endpoint."""

    model_config = ConfigDict(frozen=True)

    count: int = Field(..., description="Number of jobs returned")
    jobs: list[ScoredJob] = Field(default_factory=list, description="Scored job postings")
