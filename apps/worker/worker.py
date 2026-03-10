"""Exec Radar background worker – collection, normalization, and scoring pipeline."""

import asyncio
import logging
import os

from collectors import MockCollector
from normalizers import SimpleNormalizer
from rankers import ExecutiveProfile, RuleBasedRanker
from schemas.normalized_job_posting import SeniorityLevel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

INTERVAL_SECONDS = int(os.getenv("WORKER_INTERVAL_SECONDS", "3600"))


def _build_default_profile() -> ExecutiveProfile:
    """Return a sample executive profile used for scoring.

    Replace this with a database-backed profile or configuration file in
    production so that users can personalise their target profile.
    """
    return ExecutiveProfile(
        desired_titles=["CTO", "VP of Engineering", "Chief Technology Officer"],
        desired_seniority=[SeniorityLevel.C_SUITE, SeniorityLevel.VP, SeniorityLevel.DIRECTOR],
        required_skills=["python", "leadership"],
        preferred_skills=["aws", "kubernetes", "strategy"],
        preferred_locations=["San Francisco", "New York", "Remote"],
        remote_only=False,
        min_salary=180_000.0,
    )


async def run_pipeline() -> None:
    """Execute one full collect → normalize → score cycle."""
    logger.info("Starting pipeline run")

    collector = MockCollector()
    normalizer = SimpleNormalizer()
    ranker = RuleBasedRanker()
    profile = _build_default_profile()

    raw_postings = await collector.collect()
    logger.info("Collected %d raw postings", len(raw_postings))

    for raw in raw_postings:
        normalized = normalizer.normalize(raw)
        score = ranker.score(normalized, profile)
        logger.info(
            "Job '%s' at %s → score %.1f  [%s]",
            normalized.title,
            normalized.company,
            score.score,
            score.explanation,
        )

    logger.info("Pipeline run complete")


async def main() -> None:
    """Run the pipeline on a fixed interval until interrupted."""
    logger.info("Worker started (interval=%ds)", INTERVAL_SECONDS)
    while True:
        try:
            await run_pipeline()
        except Exception:
            logger.exception("Pipeline run failed")
        logger.info("Sleeping for %d seconds", INTERVAL_SECONDS)
        await asyncio.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
