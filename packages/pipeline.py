"""Pipeline orchestration — single source of truth for collect-normalize-rank.

Two entry points:

* :func:`run_pipeline` — pure in-memory flow (unchanged, used by the API).
* :func:`run_pipeline_with_persistence` — same logic **plus** database
  persistence via the repository layer.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from packages.collectors.base import BaseCollector
from packages.db.repository import (
    create_source_run,
    finish_source_run,
    save_fit_scores,
    save_normalized_postings,
    save_raw_postings,
)
from packages.filters import filter_executive_postings
from packages.normalizers.base import BaseNormalizer
from packages.rankers.base import BaseRanker
from packages.schemas.scored_job import ScoredJob

logger = logging.getLogger(__name__)


async def run_pipeline(
    collector: BaseCollector,
    normalizer: BaseNormalizer,
    ranker: BaseRanker,
) -> list[ScoredJob]:
    """Execute the full collect → normalize → rank pipeline (in-memory).

    This is the single orchestration function used by the API.
    It accepts abstract interfaces so callers can inject any concrete
    implementation.

    Args:
        collector: Source-specific data fetcher.
        normalizer: Raw-to-canonical transformer.
        ranker: Scoring engine.

    Returns:
        A list of :class:`ScoredJob` instances sorted by overall score
        (descending).
    """
    raw_postings = await collector.collect()
    raw_postings = filter_executive_postings(raw_postings)
    normalized = [normalizer.normalize(raw) for raw in raw_postings]
    scores = ranker.score_batch(normalized)

    score_map = {s.job_id: s for s in scores}
    scored_jobs = [
        ScoredJob(job=job, score=score_map[job.id]) for job in normalized if job.id in score_map
    ]
    scored_jobs.sort(key=lambda sj: sj.score.overall, reverse=True)
    return scored_jobs


async def run_pipeline_with_persistence(
    collector: BaseCollector,
    normalizer: BaseNormalizer,
    ranker: BaseRanker,
    session: AsyncSession,
) -> list[ScoredJob]:
    """Execute the pipeline and persist every stage to the database.

    The caller must **commit** (or roll back) the session afterwards.

    Args:
        collector: Source-specific data fetcher.
        normalizer: Raw-to-canonical transformer.
        ranker: Scoring engine.
        session: Active async database session.

    Returns:
        A list of :class:`ScoredJob` sorted descending by score.
    """
    # 1. Record the run
    source_run = await create_source_run(session, source_name=collector.source_name)

    try:
        # 2. Collect
        raw_postings = await collector.collect()
        raw_postings = filter_executive_postings(raw_postings)

        # 3. Persist raw postings
        raw_records = await save_raw_postings(session, raw_postings, run_id=source_run.id)
        raw_record_map = {f"{rec.source}:{rec.source_id}": rec.id for rec in raw_records}

        # 4. Normalize
        normalized = [normalizer.normalize(raw) for raw in raw_postings]

        # 5. Persist normalized postings
        norm_records = await save_normalized_postings(
            session, normalized, raw_record_map=raw_record_map
        )
        norm_record_map = {rec.job_id: rec.id for rec in norm_records}

        # 6. Rank
        scores = ranker.score_batch(normalized)

        # 7. Persist scores
        await save_fit_scores(session, scores, norm_record_map=norm_record_map)

        # 8. Finish run
        await finish_source_run(
            session, source_run, status="completed", job_count=len(raw_postings)
        )

    except Exception:
        await finish_source_run(session, source_run, status="failed", job_count=0)
        raise

    # Build response (same as in-memory path)
    score_map = {s.job_id: s for s in scores}
    scored_jobs = [
        ScoredJob(job=job, score=score_map[job.id]) for job in normalized if job.id in score_map
    ]
    scored_jobs.sort(key=lambda sj: sj.score.overall, reverse=True)

    logger.info(
        "Pipeline run %s completed: %d jobs collected, %d scored",
        source_run.id,
        len(raw_postings),
        len(scored_jobs),
    )
    return scored_jobs
