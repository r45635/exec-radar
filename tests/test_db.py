"""Tests for ORM models, repository functions, and persistence pipeline.

Uses an in-memory SQLite async database (via aiosqlite) so no external
database is needed.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from packages.collectors.mock_collector import MockCollector
from packages.db.base import Base
from packages.db.models import (
    FitScoreRecord,
    NormalizedJobPostingRecord,
    RawJobPostingRecord,
    SourceRunRecord,
)
from packages.db.repository import (
    create_source_run,
    finish_source_run,
    get_scored_jobs,
    save_fit_scores,
    save_normalized_postings,
    save_raw_postings,
)
from packages.normalizers.simple_normalizer import SimpleNormalizer
from packages.pipeline import run_pipeline_with_persistence
from packages.rankers.rule_based_ranker import RuleBasedRanker
from packages.schemas.fit_score import FitScore
from packages.schemas.normalized_job import NormalizedJobPosting
from packages.schemas.raw_job import RawJobPosting
from packages.schemas.target_profile import TargetProfile

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
async def db_session():
    """Create an in-memory SQLite async session for testing."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def _make_raw_posting(
    source_id: str = "test-001",
    title: str = "COO",
    company: str = "TestCo",
) -> RawJobPosting:
    return RawJobPosting(
        source="test",
        source_id=source_id,
        title=title,
        company=company,
        location="Remote",
        description="Operations leadership role",
    )


def _make_normalized(
    source_id: str = "test-001",
    title: str = "COO",
) -> NormalizedJobPosting:
    return NormalizedJobPosting(
        source="test",
        source_id=source_id,
        title=title,
        company="TestCo",
        location="Remote",
        remote_policy="remote",
        seniority="c_level",
        description_plain="Operations leadership role",
        tags=["operations", "strategy"],
    )


# ===================================================================
# ORM model tests
# ===================================================================


class TestORMModels:
    """Basic ORM model instantiation and round-trip tests."""

    async def test_source_run_roundtrip(self, db_session: AsyncSession) -> None:
        """Create and read back a SourceRunRecord."""
        run = SourceRunRecord(source_name="test_source")
        db_session.add(run)
        await db_session.flush()

        assert run.id is not None
        assert run.source_name == "test_source"
        assert run.status == "running"

    async def test_raw_posting_roundtrip(self, db_session: AsyncSession) -> None:
        """Create a raw posting linked to a source run."""
        run = SourceRunRecord(source_name="test")
        db_session.add(run)
        await db_session.flush()

        raw = RawJobPostingRecord(
            run_id=run.id,
            source="test",
            source_id="raw-001",
            title="VP Operations",
            company="ACME",
            description="A great job",
            collected_at=datetime.now(UTC),
        )
        db_session.add(raw)
        await db_session.flush()

        assert raw.id is not None
        assert raw.source == "test"
        assert raw.run_id == run.id

    async def test_normalized_posting_roundtrip(self, db_session: AsyncSession) -> None:
        """Create a normalized posting linked to a raw posting."""
        run = SourceRunRecord(source_name="test")
        db_session.add(run)
        await db_session.flush()

        raw = RawJobPostingRecord(
            run_id=run.id,
            source="test",
            source_id="raw-002",
            title="COO",
            description="Chief ops",
            collected_at=datetime.now(UTC),
        )
        db_session.add(raw)
        await db_session.flush()

        norm = NormalizedJobPostingRecord(
            raw_posting_id=raw.id,
            job_id="abc123",
            source="test",
            source_id="raw-002",
            title="Chief Operating Officer",
            remote_policy="remote",
            seniority="c_level",
            tags_json=json.dumps(["operations"]),
            normalized_at=datetime.now(UTC),
        )
        db_session.add(norm)
        await db_session.flush()

        assert norm.id is not None
        assert norm.job_id == "abc123"
        assert norm.raw_posting_id == raw.id

    async def test_fit_score_roundtrip(self, db_session: AsyncSession) -> None:
        """Create a fit score linked to a normalized posting."""
        run = SourceRunRecord(source_name="test")
        db_session.add(run)
        await db_session.flush()

        raw = RawJobPostingRecord(
            run_id=run.id,
            source="test",
            source_id="raw-003",
            title="SVP",
            description="Senior VP",
            collected_at=datetime.now(UTC),
        )
        db_session.add(raw)
        await db_session.flush()

        norm = NormalizedJobPostingRecord(
            raw_posting_id=raw.id,
            job_id="def456",
            source="test",
            source_id="raw-003",
            title="SVP Operations",
            remote_policy="hybrid",
            seniority="svp",
            tags_json="[]",
            normalized_at=datetime.now(UTC),
        )
        db_session.add(norm)
        await db_session.flush()

        score = FitScoreRecord(
            normalized_posting_id=norm.id,
            job_id="def456",
            overall=0.85,
            title_match=0.9,
            seniority_match=1.0,
            location_match=0.5,
            skills_match=0.8,
            explanation="Good fit",
        )
        db_session.add(score)
        await db_session.flush()

        assert score.id is not None
        assert score.overall == 0.85
        assert score.normalized_posting_id == norm.id

    async def test_unique_constraint_raw(self, db_session: AsyncSession) -> None:
        """Duplicate (source, source_id) should raise IntegrityError."""
        from sqlalchemy.exc import IntegrityError

        run = SourceRunRecord(source_name="test")
        db_session.add(run)
        await db_session.flush()

        r1 = RawJobPostingRecord(
            run_id=run.id,
            source="mock",
            source_id="dup-001",
            title="COO",
            description="",
            collected_at=datetime.now(UTC),
        )
        db_session.add(r1)
        await db_session.flush()

        r2 = RawJobPostingRecord(
            run_id=run.id,
            source="mock",
            source_id="dup-001",
            title="COO duplicate",
            description="",
            collected_at=datetime.now(UTC),
        )
        db_session.add(r2)
        with pytest.raises(IntegrityError):
            await db_session.flush()

        await db_session.rollback()


# ===================================================================
# Repository function tests
# ===================================================================


class TestRepository:
    """Tests for the repository helper functions."""

    async def test_create_source_run(self, db_session: AsyncSession) -> None:
        """create_source_run should insert a record with status running."""
        run = await create_source_run(db_session, source_name="mock")
        assert run.status == "running"
        assert run.source_name == "mock"

    async def test_finish_source_run(self, db_session: AsyncSession) -> None:
        """finish_source_run should set status and finished_at."""
        run = await create_source_run(db_session, source_name="mock")
        await finish_source_run(db_session, run, status="completed", job_count=5)
        assert run.status == "completed"
        assert run.finished_at is not None
        assert run.job_count == 5

    async def test_save_raw_postings(self, db_session: AsyncSession) -> None:
        """save_raw_postings should persist raw postings."""
        run = await create_source_run(db_session, source_name="test")
        postings = [_make_raw_posting("p1"), _make_raw_posting("p2")]
        records = await save_raw_postings(db_session, postings, run_id=run.id)
        assert len(records) == 2
        assert records[0].source_id == "p1"

    async def test_save_raw_postings_deduplicate(self, db_session: AsyncSession) -> None:
        """Duplicate raw postings should be updated, not duplicated."""
        run = await create_source_run(db_session, source_name="test")
        postings = [_make_raw_posting("dup1")]
        records1 = await save_raw_postings(db_session, postings, run_id=run.id)
        records2 = await save_raw_postings(db_session, postings, run_id=run.id)
        assert len(records1) == 1
        assert len(records2) == 1
        assert records1[0].id == records2[0].id

    async def test_save_normalized_postings(self, db_session: AsyncSession) -> None:
        """save_normalized_postings should persist normalised jobs."""
        run = await create_source_run(db_session, source_name="test")
        raw_postings = [_make_raw_posting("n1")]
        raw_records = await save_raw_postings(db_session, raw_postings, run_id=run.id)
        raw_map = {f"{r.source}:{r.source_id}": r.id for r in raw_records}

        normalized = [_make_normalized("n1")]
        norm_records = await save_normalized_postings(
            db_session, normalized, raw_record_map=raw_map
        )
        assert len(norm_records) == 1
        assert norm_records[0].title == "COO"

    async def test_save_fit_scores(self, db_session: AsyncSession) -> None:
        """save_fit_scores should persist scores linked to normalised postings."""
        run = await create_source_run(db_session, source_name="test")
        raw_postings = [_make_raw_posting("s1")]
        raw_records = await save_raw_postings(db_session, raw_postings, run_id=run.id)
        raw_map = {f"{r.source}:{r.source_id}": r.id for r in raw_records}

        normalized = [_make_normalized("s1")]
        norm_records = await save_normalized_postings(
            db_session, normalized, raw_record_map=raw_map
        )
        norm_map = {r.job_id: r.id for r in norm_records}

        scores = [
            FitScore(
                job_id=normalized[0].id,
                overall=0.75,
                title_match=0.8,
                seniority_match=1.0,
                location_match=0.5,
                skills_match=0.6,
            )
        ]
        score_records = await save_fit_scores(db_session, scores, norm_record_map=norm_map)
        assert len(score_records) == 1
        assert score_records[0].overall == 0.75

    async def test_get_scored_jobs(self, db_session: AsyncSession) -> None:
        """get_scored_jobs should return ScoredJob instances from DB."""
        run = await create_source_run(db_session, source_name="test")
        raw_postings = [_make_raw_posting("q1")]
        raw_records = await save_raw_postings(db_session, raw_postings, run_id=run.id)
        raw_map = {f"{r.source}:{r.source_id}": r.id for r in raw_records}

        normalized = [_make_normalized("q1")]
        norm_records = await save_normalized_postings(
            db_session, normalized, raw_record_map=raw_map
        )
        norm_map = {r.job_id: r.id for r in norm_records}

        scores = [
            FitScore(
                job_id=normalized[0].id,
                overall=0.9,
                title_match=1.0,
                seniority_match=1.0,
                location_match=1.0,
                skills_match=0.7,
            )
        ]
        await save_fit_scores(db_session, scores, norm_record_map=norm_map)
        await db_session.flush()

        results = await get_scored_jobs(db_session, limit=10)
        assert len(results) == 1
        assert results[0].score.overall == 0.9
        assert results[0].job.title == "COO"


# ===================================================================
# Pipeline with persistence
# ===================================================================


class TestPipelineWithPersistence:
    """Integration test for run_pipeline_with_persistence."""

    async def test_full_pipeline_persists(self, db_session: AsyncSession) -> None:
        """The persistence pipeline should store all stages and return scored jobs."""
        collector = MockCollector()
        normalizer = SimpleNormalizer()
        ranker = RuleBasedRanker(profile=TargetProfile())

        scored = await run_pipeline_with_persistence(
            collector=collector,
            normalizer=normalizer,
            ranker=ranker,
            session=db_session,
        )
        await db_session.commit()

        # Should return the same 5 mock jobs
        assert len(scored) == 5

        # Should be sorted descending
        scores = [sj.score.overall for sj in scored]
        assert scores == sorted(scores, reverse=True)

        # Verify data in DB via get_scored_jobs
        from_db = await get_scored_jobs(db_session, limit=10)
        assert len(from_db) == 5
        assert from_db[0].score.overall == scored[0].score.overall

    async def test_pipeline_idempotent(self, db_session: AsyncSession) -> None:
        """Running the pipeline twice should not duplicate records."""
        collector = MockCollector()
        normalizer = SimpleNormalizer()
        ranker = RuleBasedRanker(profile=TargetProfile())

        await run_pipeline_with_persistence(
            collector=collector,
            normalizer=normalizer,
            ranker=ranker,
            session=db_session,
        )
        await db_session.commit()

        await run_pipeline_with_persistence(
            collector=collector,
            normalizer=normalizer,
            ranker=ranker,
            session=db_session,
        )
        await db_session.commit()

        from_db = await get_scored_jobs(db_session, limit=20)
        assert len(from_db) == 5  # no duplicates
