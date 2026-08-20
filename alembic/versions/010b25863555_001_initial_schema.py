"""001_initial_schema

Revision ID: 010b25863555
Revises: 
Create Date: 2026-08-19 01:23:57.419083

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '010b25863555'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to initial baseline."""
    # 1. Documents
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("file_type", sa.String(length=20), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column(
            "upload_timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processing_status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("file_hash", sa.String(length=64), unique=True, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        if_not_exists=True,
    )

    # 2. Chunks
    op.create_table(
        "chunks",
        sa.Column("id", sa.UUID(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column(
            "document_id",
            sa.UUID(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_header", sa.String(length=500), nullable=True),
        sa.Column("char_offset_start", sa.Integer(), nullable=True),
        sa.Column("char_offset_end", sa.Integer(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("embedding", sa.ARRAY(sa.Float(precision=53)), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_doc_chunk_index"),
        if_not_exists=True,
    )

    # 3. Conversations
    op.create_table(
        "conversations",
        sa.Column("id", sa.UUID(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        if_not_exists=True,
    )

    # 4. Query Log
    op.create_table(
        "query_log",
        sa.Column("id", sa.UUID(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column(
            "conversation_id",
            sa.UUID(),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("rewritten_query", sa.Text(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column(
            "citations",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "retrieved_chunk_ids",
            sa.ARRAY(postgresql.UUID(as_uuid=True)),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("retrieval_scores", sa.ARRAY(sa.Float()), server_default="{}", nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("faithfulness_score", sa.Float(), nullable=True),
        sa.Column(
            "hallucination_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("pii_redacted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("llm_model", sa.String(length=100), nullable=True),
        sa.Column("llm_tokens_prompt", sa.Integer(), nullable=True),
        sa.Column("llm_tokens_completion", sa.Integer(), nullable=True),
        sa.Column("user_feedback_rating", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        if_not_exists=True,
    )

    # 5. Entity Nodes
    op.create_table(
        "entity_nodes",
        sa.Column("id", sa.UUID(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("normalized_name", sa.String(length=500), nullable=False, index=True),
        sa.Column("aliases", sa.ARRAY(sa.String()), server_default="{}", nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("normalized_name", "entity_type", name="uq_entity_name_type"),
        if_not_exists=True,
    )

    # 6. Document Entities (Junction)
    op.create_table(
        "document_entities",
        sa.Column(
            "document_id",
            sa.UUID(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entity_nodes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(length=100), nullable=False),
        sa.Column("first_mention_page", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        if_not_exists=True,
    )

    # 7. Document Relationships
    op.create_table(
        "document_relationships",
        sa.Column("id", sa.UUID(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column(
            "source_document_id",
            sa.UUID(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "target_document_id",
            sa.UUID(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("relationship_type", sa.String(length=50), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "source_document_id", "target_document_id", "relationship_type", name="uq_doc_rel"
        ),
        if_not_exists=True,
    )

    # 8. Workspaces
    op.create_table(
        "workspaces",
        sa.Column("id", sa.UUID(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "document_scope",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("is_archived", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_by", sa.String(length=100), server_default="Team Member", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        if_not_exists=True,
    )

    # 9. Workspace Members
    op.create_table(
        "workspace_members",
        sa.Column(
            "workspace_id",
            sa.UUID(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("user_name", sa.String(length=100), primary_key=True),
        sa.Column("role", sa.String(length=20), server_default="editor", nullable=False),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        if_not_exists=True,
    )

    # 10. Workspace Messages
    op.create_table(
        "workspace_messages",
        sa.Column("id", sa.UUID(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column(
            "workspace_id",
            sa.UUID(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("user_name", sa.String(length=100), nullable=True),
        sa.Column("message_type", sa.String(length=20), server_default="human", nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "citations",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "parent_message_id",
            sa.UUID(),
            sa.ForeignKey("workspace_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_pinned", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "reactions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "query_log_id",
            sa.UUID(),
            sa.ForeignKey("query_log.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        if_not_exists=True,
    )

    # 11. Triage Results
    op.create_table(
        "triage_results",
        sa.Column("id", sa.UUID(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column(
            "document_id",
            sa.UUID(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("organization_id", sa.UUID(), nullable=True, index=True),
        sa.Column("contract_type_detected", sa.String(length=50), nullable=False),
        sa.Column("type_confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("urgency_score", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "urgency_factors",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "summary_bullets",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("action_required", sa.Text(), server_default="Standard review", nullable=False),
        sa.Column("suggested_assignee", sa.String(length=100), nullable=True),
        sa.Column(
            "auto_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("inbox_status", sa.String(length=20), server_default="unreviewed", nullable=False),
        sa.Column("assigned_to", sa.String(length=100), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=100), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "triaged_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("document_id", name="uq_triage_per_document"),
        if_not_exists=True,
    )

    # 12. Triage Rules
    op.create_table(
        "triage_rules",
        sa.Column("id", sa.UUID(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", sa.UUID(), nullable=True, index=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "condition",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "action",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        if_not_exists=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("triage_rules", if_exists=True)
    op.drop_table("triage_results", if_exists=True)
    op.drop_table("workspace_messages", if_exists=True)
    op.drop_table("workspace_members", if_exists=True)
    op.drop_table("workspaces", if_exists=True)
    op.drop_table("document_relationships", if_exists=True)
    op.drop_table("document_entities", if_exists=True)
    op.drop_table("entity_nodes", if_exists=True)
    op.drop_table("query_log", if_exists=True)
    op.drop_table("conversations", if_exists=True)
    op.drop_table("chunks", if_exists=True)
    op.drop_table("documents", if_exists=True)
