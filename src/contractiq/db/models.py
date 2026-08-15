"""SQLAlchemy 2.0 declarative ORM models for ContractIQ."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative class with common helpers."""

    pass


class Document(Base):
    """Enterprise contract document metadata and processing status."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upload_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    processing_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )  # pending, processing, completed, failed
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        server_default="{}",
        nullable=False,
    )
    file_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="Chunk.chunk_index",
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename='{self.filename}', status='{self.processing_status}')>"


class Chunk(Base):
    """Extracted text chunk with embedding vector and source location metadata."""

    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index", name="uq_doc_chunk_index"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_header: Mapped[str | None] = mapped_column(String(500), nullable=True)
    char_offset_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_offset_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        ARRAY(Float(precision=53)),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    def __repr__(self) -> str:
        return (
            f"<Chunk(id={self.id}, doc_id={self.document_id}, "
            f"idx={self.chunk_index}, page={self.page_number})>"
        )


class Conversation(Base):
    """Conversation session grouping queries."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    queries: Mapped[list["QueryLog"]] = relationship(
        "QueryLog",
        back_populates="conversation",
        order_by="QueryLog.created_at",
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, title='{self.title}')>"


class QueryLog(Base):
    """Query audit trail with citations, scores, guardrail flags, and feedback."""

    __tablename__ = "query_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    rewritten_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        server_default="[]",
        nullable=False,
    )
    retrieved_chunk_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        default=list,
        server_default="{}",
        nullable=False,
    )
    retrieval_scores: Mapped[list[float]] = mapped_column(
        ARRAY(Float),
        default=list,
        server_default="{}",
        nullable=False,
    )
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    faithfulness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hallucination_flags: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        server_default="[]",
        nullable=False,
    )
    pii_redacted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    llm_tokens_prompt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_tokens_completion: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_feedback_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    conversation: Mapped[Conversation | None] = relationship(
        "Conversation",
        back_populates="queries",
    )

    def __repr__(self) -> str:
        return (
            f"<QueryLog(id={self.id}, query='{self.query_text[:30]}...', "
            f"confidence={self.confidence_score})>"
        )
