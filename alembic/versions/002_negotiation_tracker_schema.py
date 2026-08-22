"""002_negotiation_tracker_schema

Revision ID: b7d8e9f01a23
Revises: 010b25863555
Create Date: 2026-08-20 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b7d8e9f01a23'
down_revision: Union[str, Sequence[str], None] = '010b25863555'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create negotiation tracking tables."""
    # 1. negotiation_tracks
    op.create_table(
        "negotiation_tracks",
        sa.Column("id", sa.UUID(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", sa.UUID(), nullable=True, index=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("counterparty", sa.String(length=500), nullable=False),
        sa.Column("contract_type", sa.String(length=50), server_default="other", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("started_by", sa.String(length=100), server_default="Legal Counsel", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        if_not_exists=True,
    )

    # 2. negotiation_versions
    op.create_table(
        "negotiation_versions",
        sa.Column("id", sa.UUID(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column(
            "track_id",
            sa.UUID(),
            sa.ForeignKey("negotiation_tracks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "document_id",
            sa.UUID(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=20), server_default="internal", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("risk_delta", sa.Float(), nullable=True),
        sa.Column("uploaded_by", sa.String(length=100), server_default="Legal Counsel", nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("track_id", "version_number", name="uq_track_version"),
        if_not_exists=True,
    )

    # 3. negotiation_changes
    op.create_table(
        "negotiation_changes",
        sa.Column("id", sa.UUID(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column(
            "track_id",
            sa.UUID(),
            sa.ForeignKey("negotiation_tracks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("from_version", sa.Integer(), nullable=False),
        sa.Column("to_version", sa.Integer(), nullable=False),
        sa.Column("clause_category", sa.String(length=50), server_default="other", nullable=False),
        sa.Column("change_type", sa.String(length=20), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("modified_text", sa.Text(), nullable=False),
        sa.Column("diff_html", sa.Text(), nullable=True),
        sa.Column("risk_impact", sa.String(length=20), server_default="neutral", nullable=False),
        sa.Column("concession_party", sa.String(length=20), nullable=True),
        sa.Column("concession_summary", sa.Text(), nullable=True),
        sa.Column("significance", sa.String(length=10), server_default="medium", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        if_not_exists=True,
    )


def downgrade() -> None:
    """Drop negotiation tracking tables."""
    op.drop_table("negotiation_changes", if_exists=True)
    op.drop_table("negotiation_versions", if_exists=True)
    op.drop_table("negotiation_tracks", if_exists=True)
