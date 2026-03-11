"""Add job state tracking to normalized_job_postings.

Revision ID: 002
Revises: 001
Create Date: 2026-03-10

Adds columns to track job state (new/seen/updated), content hash, and first/last seen timestamps.
"""

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add job state tracking columns."""
    op.add_column(
        "normalized_job_postings",
        sa.Column("job_state", sa.String(32), nullable=False, server_default="new"),
    )
    op.add_column(
        "normalized_job_postings",
        sa.Column("content_hash", sa.String(64), nullable=False, server_default=""),
    )
    op.add_column(
        "normalized_job_postings",
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "normalized_job_postings",
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # Index for job_state for queries
    op.create_index(
        "ix_normalized_job_postings_job_state",
        "normalized_job_postings",
        ["job_state"],
    )


def downgrade() -> None:
    """Remove job state tracking columns."""
    op.drop_index(
        "ix_normalized_job_postings_job_state",
        table_name="normalized_job_postings",
    )
    op.drop_column("normalized_job_postings", "last_seen_at")
    op.drop_column("normalized_job_postings", "first_seen_at")
    op.drop_column("normalized_job_postings", "content_hash")
    op.drop_column("normalized_job_postings", "job_state")
