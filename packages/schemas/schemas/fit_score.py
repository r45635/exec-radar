"""Fit score schema – the result of ranking a job against an executive profile."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class FitScore(BaseModel):
    """Scoring result for a single job posting against a target executive profile.

    Scores are in the range [0, 100] where higher means a better fit.
    Individual dimension scores allow downstream explanation of the overall score.
    """

    job_id: str = Field(..., description="ID of the NormalizedJobPosting being scored")
    ranker: str = Field(..., description="Identifier of the ranker that produced this score")

    # Overall score
    score: float = Field(..., ge=0.0, le=100.0, description="Overall fit score (0–100)")

    # Dimension scores (each 0–100, all optional)
    title_score: float | None = Field(
        None, ge=0.0, le=100.0, description="Title / seniority match score"
    )
    skill_score: float | None = Field(
        None, ge=0.0, le=100.0, description="Skills match score"
    )
    location_score: float | None = Field(
        None, ge=0.0, le=100.0, description="Location / remote preference match score"
    )
    compensation_score: float | None = Field(
        None, ge=0.0, le=100.0, description="Compensation range match score"
    )

    # Human-readable explanation
    explanation: str | None = Field(
        None, description="Short explanation of the score for UI display"
    )
    details: dict | None = Field(
        None, description="Arbitrary extra details produced by the ranker"
    )

    scored_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this score was produced (UTC)",
    )

    model_config = {"json_schema_extra": {"example": {
        "job_id": "00000000-0000-0000-0000-000000000001",
        "ranker": "rule_based_v1",
        "score": 82.5,
        "title_score": 90.0,
        "skill_score": 80.0,
        "location_score": 75.0,
        "compensation_score": 85.0,
        "explanation": "Strong title and compensation match; moderate skills overlap.",
    }}}
