"""Scored job schema — a normalized posting paired with its fit score."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from packages.schemas.fit_score import FitScore
from packages.schemas.normalized_job import NormalizedJobPosting


class ScoredJob(BaseModel):
    """A normalized posting paired with its computed fit score.

    This is the primary output of the pipeline and the unit of data
    served to consumers via the API or notification channels.
    """

    model_config = ConfigDict(frozen=True)

    job: NormalizedJobPosting
    score: FitScore
