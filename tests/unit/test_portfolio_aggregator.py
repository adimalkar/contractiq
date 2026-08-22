"""Unit tests for PortfolioAggregator heatmap, scorecard, benchmark, and gap analysis."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.db.models import Chunk, Document, EntityNode, TriageResult
from termnova.intelligence.aggregator import PortfolioAggregator


@pytest.mark.unit
@pytest.mark.asyncio
async def test_heatmap_returns_all_documents_and_categories(test_session: AsyncSession):
    """Verify compute_clause_heatmap returns 2D matrix matching documents and 15 clause columns."""
    doc = Document(
        id=uuid.uuid4(),
        filename="acme_master_services.pdf",
        file_type="msa",
        processing_status="completed",
        metadata_={},
    )
    test_session.add(doc)
    await test_session.flush()

    chunk1 = Chunk(
        document_id=doc.id,
        chunk_index=0,
        content="ARTICLE 1: LIMITATION OF LIABILITY\nAggregate liability shall not exceed $1,000,000.",
        page_number=1,
    )
    chunk2 = Chunk(
        document_id=doc.id,
        chunk_index=1,
        content="ARTICLE 2: TERMINATION\nEither party may terminate for convenience with 30 days notice.",
        page_number=1,
    )
    test_session.add_all([chunk1, chunk2])

    triage = TriageResult(
        document_id=doc.id,
        contract_type_detected="msa",
        urgency_score=35,
        urgency_factors={"parties": ["Acme Global"], "financial_value": 150000.0},
    )
    test_session.add(triage)
    await test_session.flush()

    aggregator = PortfolioAggregator(test_session)
    heatmap = await aggregator.compute_clause_heatmap()

    assert heatmap.total_documents >= 1
    assert len(heatmap.columns) == 15
    assert len(heatmap.column_summaries) == 15

    # Find our doc row
    row = next((r for r in heatmap.rows if r.document_id == doc.id), None)
    assert row is not None
    assert row.contract_type == "msa"
    assert row.counterparty == "Acme Global"
    assert row.cells["liability"].present is True
    assert row.cells["termination"].present is True
    assert row.cells["insurance"].present is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_vendor_scorecard_aggregates_correctly(test_session: AsyncSession):
    """Verify vendor scorecard aggregates metrics, value, and clause coverage across contracts."""
    entity = EntityNode(
        name="NovaCloud Platforms",
        normalized_name="novacloud platforms",
        entity_type="vendor",
    )
    test_session.add(entity)
    await test_session.flush()

    doc = Document(
        id=uuid.uuid4(),
        filename="novacloud_hosting_agreement.pdf",
        file_type="vendor",
        processing_status="completed",
        metadata_={},
    )
    test_session.add(doc)
    await test_session.flush()

    chunk = Chunk(
        document_id=doc.id,
        chunk_index=0,
        content="PAYMENT TERMS: Invoices are due Net 30. LIABILITY: Cap is $2,000,000.",
        page_number=1,
    )
    triage = TriageResult(
        document_id=doc.id,
        contract_type_detected="vendor",
        urgency_score=20,
        urgency_factors={"parties": ["NovaCloud Platforms"], "financial_value": 75000.0},
    )
    test_session.add_all([chunk, triage])
    await test_session.flush()

    aggregator = PortfolioAggregator(test_session)
    scorecard = await aggregator.compute_vendor_scorecard(entity_id=entity.id)

    assert scorecard.entity_name == "NovaCloud Platforms"
    assert scorecard.contract_count >= 1
    assert scorecard.total_value >= 75000.0
    assert scorecard.clause_coverage["payment"] == 100.0
    assert scorecard.clause_coverage["liability"] == 100.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_benchmark_computes_percentiles_and_summary(test_session: AsyncSession):
    """Verify compute_benchmark evaluates percentile scores and summary narrative."""
    doc = Document(
        id=uuid.uuid4(),
        filename="benchmark_target_msa.pdf",
        file_type="msa",
        processing_status="completed",
        metadata_={},
    )
    test_session.add(doc)
    await test_session.flush()

    chunk = Chunk(
        document_id=doc.id,
        chunk_index=0,
        content="ARTICLE 1: CONFIDENTIALITY\nStrict confidentiality applies.\nARTICLE 2: TERMINATION\n30 days notice.",
        page_number=1,
    )
    triage = TriageResult(
        document_id=doc.id,
        contract_type_detected="msa",
        urgency_score=15,  # low risk
        urgency_factors={"parties": ["Target Corp"]},
    )
    test_session.add_all([chunk, triage])
    await test_session.flush()

    aggregator = PortfolioAggregator(test_session)
    benchmark = await aggregator.compute_benchmark(document_id=doc.id)

    assert benchmark.document_id == doc.id
    assert 0 <= benchmark.overall_percentile <= 100
    assert 0 <= benchmark.risk_percentile <= 100
    assert 0 <= benchmark.clause_coverage_percentile <= 100
    assert "safety percentile" in benchmark.comparison_summary
    assert len(benchmark.category_breakdown) == 15


@pytest.mark.unit
@pytest.mark.asyncio
async def test_trends_and_gap_detection(test_session: AsyncSession):
    """Verify compute_trends and detect_gaps identify missing mandatory clauses and trend directions."""
    doc = Document(
        id=uuid.uuid4(),
        filename="gap_msa_without_liability.pdf",
        file_type="msa",
        processing_status="completed",
        metadata_={},
    )
    test_session.add(doc)
    await test_session.flush()

    # Document only has confidentiality (missing liability, indemnification, etc.)
    chunk = Chunk(
        document_id=doc.id,
        chunk_index=0,
        content="CONFIDENTIALITY: All secrets shall remain confidential.",
        page_number=1,
    )
    triage = TriageResult(
        document_id=doc.id,
        contract_type_detected="msa",
        urgency_score=40,
        urgency_factors={"parties": ["Gap Party"]},
    )
    test_session.add_all([chunk, triage])
    await test_session.flush()

    aggregator = PortfolioAggregator(test_session)

    # 1. Test Trends
    trends = await aggregator.compute_trends(metric="risk", period="monthly")
    assert trends.metric == "risk"
    assert trends.trend_direction in ("improving", "declining", "stable")

    # 2. Test Gap Detection
    gaps = await aggregator.detect_gaps(contract_type="msa")
    target_gap = next((g for g in gaps if g.document_id == doc.id), None)
    assert target_gap is not None
    assert "liability" in target_gap.missing_clauses
    assert "indemnification" in target_gap.missing_clauses
    assert target_gap.severity == "critical"  # MSA missing liability is critical
