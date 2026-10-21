"""Initial schema - transcripts and outbox tables.

Revision ID: 001_initial
Revises: None
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable UUID extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # Create transcripts table
    op.create_table(
        "transcripts",
        sa.Column("transcript_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("call_id", UUID(as_uuid=True), nullable=False),
        sa.Column("word_count", sa.Integer, nullable=True),
        sa.Column("turn_count", sa.Integer, nullable=True),
        sa.Column("duration_seconds", sa.Numeric(8, 2), nullable=True),
        sa.Column("sentiment_overall", sa.String(20), nullable=True),
        sa.Column("sentiment_customer", sa.String(20), nullable=True),
        sa.Column("sentiment_agent", sa.String(20), nullable=True),
        sa.Column("emotion_overall", sa.String(30), nullable=True),
        sa.Column("endcall_status", sa.String(20), nullable=True),
        sa.Column("transcript_json", JSONB, nullable=True),
        sa.Column("full_text_combined", sa.Text, nullable=True),
        sa.Column("call_summary", JSONB, nullable=True),
        sa.Column("churn_predictions", JSONB, nullable=True),
        sa.Column("diagnostics", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("call_id", name="uq_transcripts_call_id"),
    )

    # Indexes for transcripts
    op.create_index("ux_transcripts_tenant_id", "transcripts", ["tenant_id", "transcript_id"], unique=True)
    op.create_index(
        "idx_transcripts_created_at",
        "transcripts",
        ["tenant_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_table("transcripts")
