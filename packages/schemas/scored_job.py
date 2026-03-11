"""Scored job schema — a normalized posting paired with its fit score."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from packages.schemas.fit_score import FitScore
from packages.schemas.normalized_job import NormalizedJobPosting


class ScoredJob(BaseModel):
    """A normalized posting paired with its computed fit score and job state.

    This is the primary output of the pipeline and the unit of data
    served to consumers via the API or notification channels.

    The ``job_state`` field indicates whether this job is:
    - ``"new"`` — First time seen (first pipeline run with this source_id)
    - ``"seen"`` — Seen before, content unchanged
    - ``"updated"`` — Seen before, content changed (title, description, salary, tags)
    """

    model_config = ConfigDict(frozen=True)

    job: NormalizedJobPosting
    score: FitScore
    job_state: str = Field(
        default="seen",
        description="Job state: 'new', 'seen', or 'updated'"
    )
