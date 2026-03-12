"""Fit-score schema — result of ranking a normalized posting."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class JobDecision(StrEnum):
    """Final decision classification for a scored posting."""

    APPLY_NOW = "apply_now"
    NETWORK_FIRST = "network_first"
    WATCH = "watch"
    IGNORE = "ignore"


class FitScore(BaseModel):
    """Quantified match between a ``NormalizedJobPosting`` and the target profile.

    Produced by a ranker.  ``overall`` is the weighted aggregate;
    individual dimension scores provide explainability.
    """

    model_config = ConfigDict(frozen=True)

    job_id: str = Field(..., description="ID of the scored NormalizedJobPosting")
    overall: float = Field(..., ge=0.0, le=1.0, description="Aggregate fit score 0-1")
    title_match: float = Field(default=0.0, ge=0.0, le=1.0, description="Title relevance")
    seniority_match: float = Field(default=0.0, ge=0.0, le=1.0, description="Seniority fit")
    location_match: float = Field(default=0.0, ge=0.0, le=1.0, description="Location fit")
    skills_match: float = Field(default=0.0, ge=0.0, le=1.0, description="Skills overlap")
    explanation: str = Field(default="", description="Human-readable reasoning")

    # ── New structured scoring fields ─────────────────────────────
    dimension_scores: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Per-dimension scores keyed by name "
            "(title, seniority, industry, scope, geography, keyword_clusters)."
        ),
    )
    why_matched: list[str] = Field(
        default_factory=list,
        description="Reasons the posting is a good fit.",
    )
    why_penalized: list[str] = Field(
        default_factory=list,
        description="Reasons the posting lost points.",
    )
    red_flags: list[str] = Field(
        default_factory=list,
        description="Hard negatives or deal-breakers.",
    )

    # ── Decision classification ───────────────────────────────────
    job_decision: JobDecision = Field(
        default=JobDecision.IGNORE,
        description="Final decision: apply_now, network_first, watch, or ignore.",
    )
