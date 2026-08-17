"""Unit tests for recursive text chunking, token bounding, and metadata preservation."""

import pytest

from termnova.pipeline import PageContent, ProcessedDocument, Section
from termnova.pipeline.chunker import RecursiveChunker


@pytest.mark.unit
def test_chunker_initialization():
    """Verify chunker parameter initialization and tokenizer availability."""
    chunker = RecursiveChunker(chunk_size=256, chunk_overlap=32, min_chunk_size=20)
    assert chunker.chunk_size == 256
    assert chunker.chunk_overlap == 32
    assert chunker.min_chunk_size == 20


@pytest.mark.unit
def test_token_counting():
    """Verify token count heuristic and tokenizer."""
    chunker = RecursiveChunker()
    count = chunker.count_tokens("This is a simple contract clause regarding termination.")
    assert count > 0
    assert chunker.count_tokens("") == 0


@pytest.mark.unit
def test_chunk_document_metadata_propagation(sample_processed_doc: ProcessedDocument):
    """Verify that chunks preserve page numbers, section headers, and sequential indices."""
    chunker = RecursiveChunker(chunk_size=100, chunk_overlap=20)
    chunks = chunker.chunk_document(sample_processed_doc)

    assert len(chunks) >= 2
    for idx, c in enumerate(chunks):
        assert c.chunk_index == idx
        assert c.page_number in [1, 2]
        assert c.token_count > 0
        assert len(c.content) >= chunker.min_chunk_size


@pytest.mark.unit
def test_empty_document_chunking():
    """Verify that empty documents return an empty list without raising exceptions."""
    chunker = RecursiveChunker()
    empty_doc = ProcessedDocument(
        filename="empty.pdf",
        file_type="pdf",
        file_hash="hash_empty",
        page_count=0,
        pages=[],
    )
    chunks = chunker.chunk_document(empty_doc)
    assert chunks == []


@pytest.mark.unit
def test_large_section_recursive_split():
    """Verify that sections exceeding chunk_size are recursively split into multiple chunks."""
    chunker = RecursiveChunker(chunk_size=30, chunk_overlap=5, min_chunk_size=10)
    long_text = " ".join(
        [f"Clause sentence number {i} regarding intellectual property rights." for i in range(25)]
    )

    doc = ProcessedDocument(
        filename="large.pdf",
        file_type="pdf",
        file_hash="hash_large",
        page_count=1,
        pages=[
            PageContent(
                page_number=1,
                text=long_text,
                sections=[Section(header="IP CLAUSE", text=long_text)],
            )
        ],
    )
    chunks = chunker.chunk_document(doc)
    assert len(chunks) > 1
    for c in chunks:
        assert chunker.count_tokens(c.content) <= 50  # Upper bound including header prefix
