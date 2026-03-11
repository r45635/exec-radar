"""Repository functions for persisting pipeline data.

All functions accept an ``AsyncSession`` that the caller is responsible
for committing / rolling back.  This keeps the repository layer thin
and transaction-control explicit.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.job_state import (
    classify_job_state,
    compute_content_hash,
)
from packages.db.models import (
    FitScoreRecord,
    NormalizedJobPostingRecord,
    RawJobPostingRecord,
    SourceRunRecord,
)
from packages.schemas.fit_score import FitScore
from packages.schemas.normalized_job import NormalizedJobPosting
from packages.schemas.raw_job import RawJobPosting
from packages.schemas.scored_job import ScoredJob

# ---------------------------------------------------------------------------
# Source run helpers
# ---------------------------------------------------------------------------


async def create_source_run(
    session: AsyncSession,
    *,
    source_name: str,
) -> SourceRunRecord:
    """Insert a new source-run record with status ``running``.

    Args:
        session: Active async session.
        source_name: Identifier of the collector source.

    Returns:
        The newly created :class:`SourceRunRecord`.
    """
    record = SourceRunRecord(source_name=source_name)
    session.add(record)
    await session.flush()
    return record


async def finish_source_run(
    session: AsyncSession,
    run: SourceRunRecord,
    *,
    status: str = "completed",
    job_count: int = 0,
) -> None:
    """Mark a source run as finished.

    Args:
        session: Active async session.
        run: The run to update.
        status: Final status string (e.g. ``completed``, ``failed``).
        job_count: Number of jobs collected in this run.
    """
    run.finished_at = datetime.now(UTC)
    run.status = status
    run.job_count = job_count
    session.add(run)
    await session.flush()


# ---------------------------------------------------------------------------
# Raw job postings
# ---------------------------------------------------------------------------


async def save_raw_postings(
    session: AsyncSession,
    postings: list[RawJobPosting],
    *,
    run_id: str,
) -> list[RawJobPostingRecord]:
    """Persist raw postings, skipping duplicates silently.

    Uses ``merge`` semantics based on the (source, source_id) natural
    key.  For simplicity we query-then-insert rather than attempting
    dialect-specific ``ON CONFLICT`` which differs between PostgreSQL
    and SQLite.

    Args:
        session: Active async session.
        postings: Pydantic raw postings to persist.
        run_id: FK to the owning source run.

    Returns:
        List of persisted :class:`RawJobPostingRecord` objects.
    """
    records: list[RawJobPostingRecord] = []
    for p in postings:
        # Check for existing record
        stmt = select(RawJobPostingRecord).where(
            RawJobPostingRecord.source == p.source,
            RawJobPostingRecord.source_id == p.source_id,
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            # Update the run_id to current run
            existing.run_id = run_id
            records.append(existing)
            continue

        record = RawJobPostingRecord(
            run_id=run_id,
            source=p.source,
            source_id=p.source_id,
            source_url=p.source_url,
            title=p.title,
            company=p.company,
            location=p.location,
            description=p.description,
            salary_raw=p.salary_raw,
            posted_at=p.posted_at,
            collected_at=p.collected_at,
            meta_json=json.dumps(p.meta),
        )
        session.add(record)
        records.append(record)

    await session.flush()
    return records


# ---------------------------------------------------------------------------
# Normalized job postings
# ---------------------------------------------------------------------------


async def save_normalized_postings(
    session: AsyncSession,
    postings: list[NormalizedJobPosting],
    *,
    raw_record_map: dict[str, str],
) -> list[NormalizedJobPostingRecord]:
    """Persist normalized postings, upserting by ``job_id`` with state tracking.

    Classifies each job as:
    - "new" if first time seen (job_id not in database)
    - "seen" if seen before and content hash unchanged
    - "updated" if seen before and content hash changed

    Args:
        session: Active async session.
        postings: Pydantic normalized postings.
        raw_record_map: Mapping ``source:source_id`` → ``RawJobPostingRecord.id``.

    Returns:
        List of persisted :class:`NormalizedJobPostingRecord` objects.
    """
    records: list[NormalizedJobPostingRecord] = []
    now = datetime.now(UTC)

    for p in postings:
        raw_key = f"{p.source}:{p.source_id}"
        raw_id = raw_record_map.get(raw_key)
        if raw_id is None:
            continue  # shouldn't happen, but guard

        # Compute current content hash
        current_hash = compute_content_hash(p)

        # Check existing
        stmt = select(NormalizedJobPostingRecord).where(
            NormalizedJobPostingRecord.job_id == p.id,
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            # Existing job: classify as seen or updated
            previous_hash = existing.content_hash or ""
            job_state = classify_job_state(
                is_new=False,
                previous_hash=previous_hash,
                current_hash=current_hash,
            )

            # Update fields
            existing.title = p.title
            existing.company = p.company
            existing.location = p.location
            existing.remote_policy = p.remote_policy.value
            existing.seniority = p.seniority.value
            existing.description_plain = p.description_plain
            existing.salary_min = p.salary_min
            existing.salary_max = p.salary_max
            existing.salary_currency = p.salary_currency
            existing.tags_json = json.dumps(p.tags)
            existing.normalized_at = p.normalized_at
            existing.job_state = job_state
            existing.content_hash = current_hash
            existing.last_seen_at = now
            records.append(existing)
            continue

        # New job
        record = NormalizedJobPostingRecord(
            raw_posting_id=raw_id,
            job_id=p.id,
            source=p.source,
            source_id=p.source_id,
            source_url=p.source_url,
            title=p.title,
            company=p.company,
            location=p.location,
            remote_policy=p.remote_policy.value,
            seniority=p.seniority.value,
            description_plain=p.description_plain,
            salary_min=p.salary_min,
            salary_max=p.salary_max,
            salary_currency=p.salary_currency,
            tags_json=json.dumps(p.tags),
            posted_at=p.posted_at,
            normalized_at=p.normalized_at,
            job_state="new",
            content_hash=current_hash,
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(record)
        records.append(record)

    await session.flush()
    return records


# ---------------------------------------------------------------------------
# Fit scores
# ---------------------------------------------------------------------------


async def save_fit_scores(
    session: AsyncSession,
    scores: list[FitScore],
    *,
    norm_record_map: dict[str, str],
) -> list[FitScoreRecord]:
    """Persist fit scores, upserting by ``job_id``.

    Args:
        session: Active async session.
        scores: Pydantic fit scores to persist.
        norm_record_map: Mapping ``job_id`` → ``NormalizedJobPostingRecord.id``.

    Returns:
        List of persisted :class:`FitScoreRecord` objects.
    """
    records: list[FitScoreRecord] = []
    for s in scores:
        norm_id = norm_record_map.get(s.job_id)
        if norm_id is None:
            continue

        stmt = select(FitScoreRecord).where(FitScoreRecord.job_id == s.job_id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.overall = s.overall
            existing.title_match = s.title_match
            existing.seniority_match = s.seniority_match
            existing.location_match = s.location_match
            existing.skills_match = s.skills_match
            existing.explanation = s.explanation
            records.append(existing)
            continue

        record = FitScoreRecord(
            normalized_posting_id=norm_id,
            job_id=s.job_id,
            overall=s.overall,
            title_match=s.title_match,
            seniority_match=s.seniority_match,
            location_match=s.location_match,
            skills_match=s.skills_match,
            explanation=s.explanation,
        )
        session.add(record)
        records.append(record)

    await session.flush()
    return records


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


async def get_scored_jobs(
    session: AsyncSession,
    *,
    limit: int = 50,
) -> list[ScoredJob]:
    """Load the top scored jobs from the database.

    Joins normalized postings with their fit scores and returns
    Pydantic :class:`ScoredJob` instances sorted by overall score.

    Args:
        session: Active async session.
        limit: Maximum number of results.

    Returns:
        List of :class:`ScoredJob` sorted descending by score.
    """
    stmt = (
        select(NormalizedJobPostingRecord, FitScoreRecord)
        .join(
            FitScoreRecord,
            FitScoreRecord.job_id == NormalizedJobPostingRecord.job_id,
        )
        .order_by(FitScoreRecord.overall.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.all()

    scored: list[ScoredJob] = []
    for norm_rec, score_rec in rows:
        job = NormalizedJobPosting(
            id=norm_rec.job_id,
            source=norm_rec.source,
            source_id=norm_rec.source_id,
            source_url=norm_rec.source_url,
            title=norm_rec.title,
            company=norm_rec.company,
            location=norm_rec.location,
            remote_policy=norm_rec.remote_policy,
            seniority=norm_rec.seniority,
            description_plain=norm_rec.description_plain,
            salary_min=norm_rec.salary_min,
            salary_max=norm_rec.salary_max,
            salary_currency=norm_rec.salary_currency,
            tags=json.loads(norm_rec.tags_json),
            posted_at=norm_rec.posted_at,
            normalized_at=norm_rec.normalized_at,
        )
        score = FitScore(
            job_id=score_rec.job_id,
            overall=score_rec.overall,
            title_match=score_rec.title_match,
            seniority_match=score_rec.seniority_match,
            location_match=score_rec.location_match,
            skills_match=score_rec.skills_match,
            explanation=score_rec.explanation,
        )
        scored.append(ScoredJob(job=job, score=score, job_state=norm_rec.job_state))

    return scored
