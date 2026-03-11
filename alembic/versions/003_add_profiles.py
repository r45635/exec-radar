"""Add profiles table for multi-profile management.

Revision ID: 003
Revises: 002
Create Date: 2026-03-10
"""

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create profiles table."""
    op.create_table(
        "profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("slug", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("is_suspended", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("source_type", sa.String(32), nullable=False, server_default="ui"),
        sa.Column("profile_data_json", sa.Text, nullable=False, server_default="{}"),
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
    op.create_index("ix_profiles_slug", "profiles", ["slug"], unique=True)
    op.create_index("ix_profiles_is_active", "profiles", ["is_active"])


def downgrade() -> None:
    """Drop profiles table."""
    op.drop_index("ix_profiles_is_active", table_name="profiles")
    op.drop_index("ix_profiles_slug", table_name="profiles")
    op.drop_table("profiles")
