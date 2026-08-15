"""Integration tests for hybrid retrieval, grading, generation, guardrails, and audit logging."""

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from contractiq.config import Settings
from contractiq.pipeline.embedder import EmbeddingService
from contractiq.pipeline.ingestion import IngestionPipeline
from contractiq.rag.engine import RAGEngine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_rag_query_pipeline(
    test_session: AsyncSession,
    test_settings: Settings,
    test_embedder: EmbeddingService,
):
    """Verify that a question against ingested contracts returns grounded answers and logs audit trail."""
    sample_pdf = (
        Path(__file__).parent.parent.parent
        / "data"
        / "eval"
        / "sample_contracts"
        / "sample_msa.pdf"
    )
    if not sample_pdf.exists():
        pytest.skip("sample_msa.pdf not generated yet")

    # Ingest document
    pipeline = IngestionPipeline(test_session, test_embedder, test_settings)
    doc = await pipeline.ingest_file(sample_pdf, force_reindex=False)
    assert doc.processing_status == "completed"

    # Query RAG Engine
    rag_engine = RAGEngine(test_session, test_embedder, test_settings)
    result = await rag_engine.query("What is the limitation of liability cap?")

    assert result.query_id is not None
    assert result.answer != ""
    assert result.confidence_score >= 0.0
    assert result.faithfulness_score >= 0.0
    assert result.latency_ms > 0
    assert len(result.citations) > 0

    # Verify query logged in database
    log = await pipeline.repository.get_query_log(result.query_id)
    assert log is not None
    assert log.query_text == "What is the limitation of liability cap?"
    assert log.confidence_score == result.confidence_score
