"""Add portal_tokens table

Revision ID: a3c9e5f7b012
Revises: 1f1bc84dae50
Create Date: 2026-03-03 20:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a3c9e5f7b012"
down_revision: Union[str, Sequence[str], None] = "64b0ebc20bca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create portal_tokens table for magic-link token management."""
    op.create_table(
        "portal_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token", sa.String(128), nullable=False, unique=True),
        sa.Column(
            "submission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lead_submissions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "edition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("newsletter_editions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("actor_email", sa.String(320), nullable=False),
        sa.Column("actor_name", sa.String(200), nullable=False),
        sa.Column("context_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("is_used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_portal_tokens_token", "portal_tokens", ["token"], unique=True)


def downgrade() -> None:
    """Drop portal_tokens table."""
    op.drop_index("ix_portal_tokens_token", table_name="portal_tokens")
    op.drop_table("portal_tokens")
