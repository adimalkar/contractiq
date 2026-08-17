"""Integration tests for file parsing, chunking, embedding, and database persistence."""

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.config import Settings
from termnova.pipeline.embedder import EmbeddingService
from termnova.pipeline.ingestion import IngestionPipeline


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pdf_ingestion_end_to_end(
    test_session: AsyncSession,
    test_settings: Settings,
    test_embedder: EmbeddingService,
):
    """Verify that a sample PDF contract is completely parsed, chunked, and stored."""
    sample_pdf = (
        Path(__file__).parent.parent.parent
        / "data"
        / "eval"
        / "sample_contracts"
        / "sample_nda.pdf"
    )
    if not sample_pdf.exists():
        pytest.skip("sample_nda.pdf not generated yet")

    pipeline = IngestionPipeline(test_session, test_embedder, test_settings)
    doc = await pipeline.ingest_file(sample_pdf, force_reindex=True)

    assert doc.id is not None
    assert doc.filename == "sample_nda.pdf"
    assert doc.processing_status == "completed"
    assert doc.page_count is not None and doc.page_count > 0

    chunks = await pipeline.repository.get_chunks_by_document(doc.id)
    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk.content != ""
        assert chunk.page_number is not None
        assert chunk.token_count is not None and chunk.token_count > 0
        assert chunk.embedding is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ingestion_idempotency(
    test_session: AsyncSession,
    test_settings: Settings,
    test_embedder: EmbeddingService,
):
    """Verify that ingesting the same contract file twice does not create duplicate documents."""
    sample_pdf = (
        Path(__file__).parent.parent.parent
        / "data"
        / "eval"
        / "sample_contracts"
        / "sample_nda.pdf"
    )
    if not sample_pdf.exists():
        pytest.skip("sample_nda.pdf not generated yet")

    pipeline = IngestionPipeline(test_session, test_embedder, test_settings)
    doc1 = await pipeline.ingest_file(sample_pdf, force_reindex=False)
    doc2 = await pipeline.ingest_file(sample_pdf, force_reindex=False)

    assert doc1.id == doc2.id
    assert doc1.file_hash == doc2.file_hash
