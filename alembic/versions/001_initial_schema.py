"""Initial schema — source_runs, raw/normalized postings, fit_scores.

Revision ID: 001
Revises: (none)
Create Date: 2026-03-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: tuple[str, ...] | None = None
depends_on: str | None = None


def upgrade() -> None:
    # --- source_runs ---
    op.create_table(
        "source_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_name", sa.String(128), nullable=False, index=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="running"),
        sa.Column("job_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- raw_job_postings ---
    op.create_table(
        "raw_job_postings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("source_runs.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("source", sa.String(128), nullable=False, index=True),
        sa.Column("source_id", sa.String(256), nullable=False),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("company", sa.String(256), nullable=True),
        sa.Column("location", sa.String(256), nullable=True),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("salary_raw", sa.String(256), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meta_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("source", "source_id", name="uq_raw_source_source_id"),
    )

    # --- normalized_job_postings ---
    op.create_table(
        "normalized_job_postings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "raw_posting_id",
            sa.String(36),
            sa.ForeignKey("raw_job_postings.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("job_id", sa.String(64), nullable=False, index=True),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("source_id", sa.String(256), nullable=False),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("company", sa.String(256), nullable=True),
        sa.Column("location", sa.String(256), nullable=True),
        sa.Column("remote_policy", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("seniority", sa.String(32), nullable=False, server_default="other"),
        sa.Column("description_plain", sa.Text, nullable=False, server_default=""),
        sa.Column("salary_min", sa.Float, nullable=True),
        sa.Column("salary_max", sa.Float, nullable=True),
        sa.Column("salary_currency", sa.String(8), nullable=True),
        sa.Column("tags_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("normalized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("job_id", name="uq_norm_job_id"),
    )

    # --- fit_scores ---
    op.create_table(
        "fit_scores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "normalized_posting_id",
            sa.String(36),
            sa.ForeignKey("normalized_job_postings.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("job_id", sa.String(64), nullable=False, index=True),
        sa.Column("overall", sa.Float, nullable=False),
        sa.Column("title_match", sa.Float, nullable=False, server_default="0"),
        sa.Column("seniority_match", sa.Float, nullable=False, server_default="0"),
        sa.Column("location_match", sa.Float, nullable=False, server_default="0"),
        sa.Column("skills_match", sa.Float, nullable=False, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("job_id", name="uq_fit_job_id"),
    )


def downgrade() -> None:
    op.drop_table("fit_scores")
    op.drop_table("normalized_job_postings")
    op.drop_table("raw_job_postings")
    op.drop_table("source_runs")
