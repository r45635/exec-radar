"""Worker entry point — runs the collect-normalize-rank pipeline.

When a database URL is configured, the worker persists every stage.
Otherwise it falls back to the in-memory pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import os

from packages.pipeline import run_pipeline, run_pipeline_with_persistence
from packages.services import build_pipeline_components

logger = logging.getLogger(__name__)


async def main() -> None:
    """Execute the pipeline once with default implementations.

    If ``EXEC_RADAR_DATABASE_URL`` is set, the persistence-aware
    pipeline is used and results are committed to the database.
    Otherwise the in-memory pipeline runs as before.

    Will be wired to a scheduler (e.g. APScheduler, Celery Beat, or
    a simple ``asyncio`` loop) in a future iteration.
    """
    collector, normalizer, ranker = build_pipeline_components()

    database_url = os.getenv("EXEC_RADAR_DATABASE_URL")

    if database_url:
        from packages.db.engine import get_session_factory, init_engine

        init_engine(database_url)
        session_factory = get_session_factory()
        async with session_factory() as session:
            scored_jobs = await run_pipeline_with_persistence(
                collector=collector,
                normalizer=normalizer,
                ranker=ranker,
                session=session,
            )
            await session.commit()
        logger.info("Persisted %d scored jobs to database", len(scored_jobs))
    else:
        scored_jobs = await run_pipeline(
            collector=collector,
            normalizer=normalizer,
            ranker=ranker,
        )

    for sj in scored_jobs:
        logger.info(
            "Job %s (%s): overall=%.2f",
            sj.job.id,
            sj.job.title,
            sj.score.overall,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
