"""Integration tests for the contract comparison and clause alignment pipeline."""

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.comparison.report import ComparisonReportGenerator
from termnova.pipeline.embedder import EmbeddingService
from termnova.pipeline.ingestion import IngestionPipeline


@pytest.mark.integration
@pytest.mark.asyncio
async def test_comparison_pipeline_end_to_end(
    test_session: AsyncSession,
    test_embedder: EmbeddingService,
):
    """Verify that two ingested contracts are aligned, compared, and generate a diff report."""
    pipeline = IngestionPipeline(test_session, test_embedder)

    pdf_a = (
        Path(__file__).parent.parent.parent
        / "data"
        / "eval"
        / "sample_contracts"
        / "sample_msa.pdf"
    )
    pdf_b = (
        Path(__file__).parent.parent.parent
        / "data"
        / "eval"
        / "sample_contracts"
        / "sample_sow.pdf"
    )

    if not pdf_a.exists() or not pdf_b.exists():
        pytest.skip("Sample PDF contracts not found")

    doc_a = await pipeline.ingest_file(pdf_a)
    doc_b = await pipeline.ingest_file(pdf_b)

    generator = ComparisonReportGenerator(test_session, embedder=test_embedder)
    report = await generator.compare_documents(doc_a.id, doc_b.id)

    assert report is not None
    assert report.document_a_name == "sample_msa.pdf"
    assert report.document_b_name == "sample_sow.pdf"
    assert len(report.alignments) > 0
    assert 0.0 <= report.overall_similarity <= 1.0
