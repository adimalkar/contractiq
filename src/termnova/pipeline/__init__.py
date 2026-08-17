"""Document ingestion, parsing, chunking, and embedding pipeline."""

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Section:
    """Detected section within a document page."""

    header: str | None
    text: str
    start_offset: int = 0


@dataclass
class PageContent:
    """Extracted text and structure for a single page."""

    page_number: int
    text: str
    sections: list[Section] = field(default_factory=list)


@dataclass
class ProcessedDocument:
    """Structured representation of a parsed document."""

    filename: str
    file_type: str
    file_hash: str
    page_count: int
    pages: list[PageContent]
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""


@dataclass
class ChunkData:
    """A single semantic text chunk ready for vectorization and indexing."""

    content: str
    page_number: int
    section_header: str | None
    chunk_index: int
    char_offset_start: int
    char_offset_end: int
    token_count: int
    document_id: uuid.UUID | None = None
    embedding: list[float] | None = None


__all__ = [
    "Section",
    "PageContent",
    "ProcessedDocument",
    "ChunkData",
]
