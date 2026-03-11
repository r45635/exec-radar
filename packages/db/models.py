"""ORM models for persisting pipeline data.

These are SQLAlchemy 2.x mapped classes — intentionally separate from
the Pydantic schemas in ``packages.schemas``.  Conversion helpers live
in the repository module.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.db.base import Base, TimestampMixin

# Job state enum values
JOB_STATE_NEW = "new"
JOB_STATE_SEEN = "seen"
JOB_STATE_UPDATED = "updated"
_VALID_JOB_STATES = {JOB_STATE_NEW, JOB_STATE_SEEN, JOB_STATE_UPDATED}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Use String(36) for portability (SQLite doesn't have a native UUID type).
_UUID_COL = String(36)


def _new_uuid() -> str:
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# SourceRun
# ---------------------------------------------------------------------------


class SourceRunRecord(Base, TimestampMixin):
    """A single execution of a collector against one source."""

    __tablename__ = "source_runs"

    id: Mapped[str] = mapped_column(_UUID_COL, primary_key=True, default=_new_uuid)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    job_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    raw_postings: Mapped[list[RawJobPostingRecord]] = relationship(
        back_populates="source_run", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# RawJobPostingRecord
# ---------------------------------------------------------------------------


class RawJobPostingRecord(Base, TimestampMixin):
    """Persisted version of a ``RawJobPosting``."""

    __tablename__ = "raw_job_postings"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_raw_source_source_id"),)

    id: Mapped[str] = mapped_column(_UUID_COL, primary_key=True, default=_new_uuid)
    run_id: Mapped[str] = mapped_column(
        _UUID_COL, ForeignKey("source_runs.id"), nullable=False, index=True
    )

    source: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(256), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    company: Mapped[str | None] = mapped_column(String(256), nullable=True)
    location: Mapped[str | None] = mapped_column(String(256), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    salary_raw: Mapped[str | None] = mapped_column(String(256), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    meta_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

    # Relationships
    source_run: Mapped[SourceRunRecord] = relationship(back_populates="raw_postings")
    normalized_posting: Mapped[NormalizedJobPostingRecord | None] = relationship(
        back_populates="raw_posting", uselist=False
    )


# ---------------------------------------------------------------------------
# NormalizedJobPostingRecord
# ---------------------------------------------------------------------------


class NormalizedJobPostingRecord(Base, TimestampMixin):
    """Persisted version of a ``NormalizedJobPosting``."""

    __tablename__ = "normalized_job_postings"
    __table_args__ = (UniqueConstraint("job_id", name="uq_norm_job_id"),)

    id: Mapped[str] = mapped_column(_UUID_COL, primary_key=True, default=_new_uuid)
    raw_posting_id: Mapped[str] = mapped_column(
        _UUID_COL, ForeignKey("raw_job_postings.id"), nullable=False, index=True
    )

    # The deterministic SHA-256 id from the Pydantic schema
    job_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    source: Mapped[str] = mapped_column(String(128), nullable=False)
    source_id: Mapped[str] = mapped_column(String(256), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    company: Mapped[str | None] = mapped_column(String(256), nullable=True)
    location: Mapped[str | None] = mapped_column(String(256), nullable=True)
    remote_policy: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    seniority: Mapped[str] = mapped_column(String(32), default="other", nullable=False)
    description_plain: Mapped[str] = mapped_column(Text, default="", nullable=False)
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    normalized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Job state tracking
    job_state: Mapped[str] = mapped_column(
        String(32), default=JOB_STATE_NEW, nullable=False, index=True
    )
    content_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    raw_posting: Mapped[RawJobPostingRecord] = relationship(back_populates="normalized_posting")
    fit_score: Mapped[FitScoreRecord | None] = relationship(
        back_populates="normalized_posting", uselist=False
    )


# ---------------------------------------------------------------------------
# FitScoreRecord
# ---------------------------------------------------------------------------


class FitScoreRecord(Base, TimestampMixin):
    """Persisted version of a ``FitScore``."""

    __tablename__ = "fit_scores"
    __table_args__ = (UniqueConstraint("job_id", name="uq_fit_job_id"),)

    id: Mapped[str] = mapped_column(_UUID_COL, primary_key=True, default=_new_uuid)
    normalized_posting_id: Mapped[str] = mapped_column(
        _UUID_COL,
        ForeignKey("normalized_job_postings.id"),
        nullable=False,
        index=True,
    )

    job_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    overall: Mapped[float] = mapped_column(Float, nullable=False)
    title_match: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    seniority_match: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    location_match: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    skills_match: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # Relationships
    normalized_posting: Mapped[NormalizedJobPostingRecord] = relationship(
        back_populates="fit_score"
    )


# ---------------------------------------------------------------------------
# ProfileRecord
# ---------------------------------------------------------------------------

# Valid source_type values
PROFILE_SOURCE_UI = "ui"
PROFILE_SOURCE_FILE_IMPORT = "file_import"
PROFILE_SOURCE_UPLOAD = "upload"
_VALID_PROFILE_SOURCES = {PROFILE_SOURCE_UI, PROFILE_SOURCE_FILE_IMPORT, PROFILE_SOURCE_UPLOAD}


class ProfileRecord(Base, TimestampMixin):
    """Persisted target profile for multi-profile management."""

    __tablename__ = "profiles"
    __table_args__ = (UniqueConstraint("slug", name="uq_profile_slug"),)

    id: Mapped[str] = mapped_column(_UUID_COL, primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    slug: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(32), default=PROFILE_SOURCE_UI, nullable=False
    )
    profile_data_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
