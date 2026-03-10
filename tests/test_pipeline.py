"""Tests for the pipeline orchestration module."""

from __future__ import annotations

from packages.collectors.mock_collector import MockCollector
from packages.normalizers.simple_normalizer import SimpleNormalizer
from packages.pipeline import run_pipeline
from packages.rankers.rule_based_ranker import RuleBasedRanker
from packages.schemas.target_profile import TargetProfile


def _make_pipeline_args() -> dict:
    """Return keyword arguments for a standard pipeline run."""
    return {
        "collector": MockCollector(),
        "normalizer": SimpleNormalizer(),
        "ranker": RuleBasedRanker(profile=TargetProfile()),
    }


class TestRunPipeline:
    """Integration tests for the pipeline orchestration."""

    async def test_returns_scored_jobs(self) -> None:
        """Pipeline should return a non-empty list of ScoredJob."""
        results = await run_pipeline(**_make_pipeline_args())
        assert len(results) > 0

    async def test_results_sorted_descending(self) -> None:
        """Results should be sorted by overall score, descending."""
        results = await run_pipeline(**_make_pipeline_args())
        scores = [sj.score.overall for sj in results]
        assert scores == sorted(scores, reverse=True)

    async def test_job_id_matches_score_job_id(self) -> None:
        """Each ScoredJob's score.job_id should reference its job.id."""
        results = await run_pipeline(**_make_pipeline_args())
        for sj in results:
            assert sj.score.job_id == sj.job.id
