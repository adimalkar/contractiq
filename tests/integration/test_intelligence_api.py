"""Integration tests for Cross-Contract Intelligence and Clause Heatmap REST API endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.db.models import Chunk, Document, EntityNode, TriageResult


@pytest.mark.integration
@pytest.mark.asyncio
async def test_clause_heatmap_endpoint(api_client: AsyncClient, test_session: AsyncSession):
    """Verify GET /api/v1/intelligence/clause-heatmap returns 2D matrix with summaries."""
    doc = Document(
        id=uuid.uuid4(),
        filename="vendor_cloud_services.pdf",
        file_type="vendor",
        processing_status="completed",
        metadata_={"parties": ["OmniCloud Systems"]},
    )
    test_session.add(doc)
    await test_session.flush()

    chunk = Chunk(
        document_id=doc.id,
        chunk_index=0,
        content="ARTICLE 1: LIMITATION OF LIABILITY\nLiability is capped at $1,000,000.\nARTICLE 2: PAYMENT TERMS\nNet 30 days.",
        page_number=1,
    )
    triage = TriageResult(
        document_id=doc.id,
        contract_type_detected="vendor",
        urgency_score=25,
        urgency_factors={"parties": ["OmniCloud Systems"], "financial_value": 80000.0},
    )
    test_session.add_all([chunk, triage])
    await test_session.commit()

    resp = await api_client.get("/api/v1/intelligence/clause-heatmap")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_documents"] >= 1
    assert len(data["columns"]) == 15
    assert len(data["column_summaries"]) == 15

    # Filter by contract type
    resp_filtered = await api_client.get("/api/v1/intelligence/clause-heatmap?contract_type=vendor")
    assert resp_filtered.status_code == 200
    data_filtered = resp_filtered.json()
    assert any(r["document_id"] == str(doc.id) for r in data_filtered["rows"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_vendor_scorecard_endpoints(api_client: AsyncClient, test_session: AsyncSession):
    """Verify GET /api/v1/intelligence/vendor-scorecard/{entity_id} and by vendor_name."""
    entity = EntityNode(
        name="Starlight Tech Corp",
        normalized_name="starlight tech corp",
        entity_type="vendor",
    )
    test_session.add(entity)
    await test_session.flush()

    doc = Document(
        id=uuid.uuid4(),
        filename="starlight_saas_agreement.pdf",
        file_type="msa",
        processing_status="completed",
        metadata_={"parties": ["Starlight Tech Corp"]},
    )
    test_session.add(doc)
    await test_session.flush()

    chunk = Chunk(
        document_id=doc.id,
        chunk_index=0,
        content="ARTICLE 1: CONFIDENTIALITY\nStrict confidentiality applies.",
        page_number=1,
    )
    triage = TriageResult(
        document_id=doc.id,
        contract_type_detected="msa",
        urgency_score=15,
        urgency_factors={"parties": ["Starlight Tech Corp"], "financial_value": 120000.0},
    )
    test_session.add_all([chunk, triage])
    await test_session.commit()

    # 1. Fetch by entity_id
    resp_id = await api_client.get(f"/api/v1/intelligence/vendor-scorecard/{entity.id}")
    assert resp_id.status_code == 200
    data_id = resp_id.json()
    assert data_id["entity_name"] == "Starlight Tech Corp"
    assert data_id["contract_count"] >= 1
    assert data_id["total_value"] >= 120000.0

    # 2. Fetch by name
    resp_name = await api_client.get("/api/v1/intelligence/vendor-scorecard?vendor_name=Starlight")
    assert resp_name.status_code == 200
    data_name = resp_name.json()
    assert data_name["contract_count"] >= 1

    # 3. 404 for unknown entity ID
    resp_404 = await api_client.get(f"/api/v1/intelligence/vendor-scorecard/{uuid.uuid4()}")
    assert resp_404.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_benchmark_endpoint(api_client: AsyncClient, test_session: AsyncSession):
    """Verify GET /api/v1/intelligence/benchmark/{document_id} ranks contract against portfolio."""
    doc = Document(
        id=uuid.uuid4(),
        filename="quantum_msa_v1.pdf",
        file_type="msa",
        processing_status="completed",
        metadata_={"parties": ["Quantum Leap Labs"]},
    )
    test_session.add(doc)
    await test_session.flush()

    chunk = Chunk(
        document_id=doc.id,
        chunk_index=0,
        content="ARTICLE 1: LIMITATION OF LIABILITY\nLiability is capped at $500,000.\nARTICLE 2: INDEMNIFICATION\nMutual indemnification.",
        page_number=1,
    )
    triage = TriageResult(
        document_id=doc.id,
        contract_type_detected="msa",
        urgency_score=20,
        urgency_factors={"parties": ["Quantum Leap Labs"]},
    )
    test_session.add_all([chunk, triage])
    await test_session.commit()

    resp = await api_client.get(f"/api/v1/intelligence/benchmark/{doc.id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["document_id"] == str(doc.id)
    assert 0 <= data["overall_percentile"] <= 100
    assert 0 <= data["risk_percentile"] <= 100
    assert 0 <= data["clause_coverage_percentile"] <= 100
    assert len(data["category_breakdown"]) == 15

    # 404 for non-existent document
    resp_bad = await api_client.get(f"/api/v1/intelligence/benchmark/{uuid.uuid4()}")
    assert resp_bad.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_trends_gaps_and_summary_endpoints(
    api_client: AsyncClient, test_session: AsyncSession
):
    """Verify GET /api/v1/intelligence/trends, /gaps, and /summary endpoints."""
    # 1. Trends
    resp_trends = await api_client.get("/api/v1/intelligence/trends?metric=risk&period=monthly")
    assert resp_trends.status_code == 200
    trends_data = resp_trends.json()
    assert trends_data["metric"] == "risk"
    assert "trend_direction" in trends_data

    # 2. Gaps
    resp_gaps = await api_client.get("/api/v1/intelligence/gaps")
    assert resp_gaps.status_code == 200
    gaps_data = resp_gaps.json()
    assert isinstance(gaps_data, list)

    # 3. Portfolio Summary
    resp_summary = await api_client.get("/api/v1/intelligence/summary")
    assert resp_summary.status_code == 200
    summary_data = resp_summary.json()
    assert "total_contracts" in summary_data
    assert "avg_risk_score" in summary_data
    assert "compliance_score" in summary_data
    assert len(summary_data["top_risks"]) >= 1
