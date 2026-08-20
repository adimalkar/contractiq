"""Integration tests for Contract Inbox REST API."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.db.models import Document, TriageResult


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inbox_list_and_stats(api_client: AsyncClient, test_db_session: AsyncSession):
    """Verify listing contracts in inbox and fetching summary KPI stats."""
    # Seed 2 contracts with triage results
    doc1 = Document(filename="acme_saas_msa_2026.pdf", file_type="pdf")
    doc2 = Document(filename="nda_bilateral_vendor.pdf", file_type="pdf")
    test_db_session.add_all([doc1, doc2])
    await test_db_session.flush()

    t1 = TriageResult(
        document_id=doc1.id,
        contract_type_detected="msa",
        type_confidence=0.92,
        urgency_score=85,
        summary_bullets=["3-year SaaS agreement", "Value $1.2M"],
        auto_tags=["high-value", "urgent"],
        inbox_status="unreviewed",
    )
    t2 = TriageResult(
        document_id=doc2.id,
        contract_type_detected="nda",
        type_confidence=0.95,
        urgency_score=15,
        summary_bullets=["Standard mutual confidentiality"],
        auto_tags=["standard-nda"],
        inbox_status="in_progress",
        assigned_to="Sarah Chen",
    )
    test_db_session.add_all([t1, t2])
    await test_db_session.commit()

    # 1. GET /api/v1/inbox/
    res = await api_client.get("/api/v1/inbox/")
    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] >= 2
    assert len(data["items"]) >= 2
    assert data["items"][0]["urgency_score"] >= data["items"][1]["urgency_score"]

    # 2. Filter by status
    res_status = await api_client.get("/api/v1/inbox/?status=unreviewed")
    assert res_status.status_code == 200
    unreviewed_items = res_status.json()["items"]
    assert all(item["inbox_status"] == "unreviewed" for item in unreviewed_items)

    # 3. Filter by tag
    res_tag = await api_client.get("/api/v1/inbox/?tag=urgent")
    assert res_tag.status_code == 200
    tag_data = res_tag.json()
    assert tag_data["total_count"] == 1
    assert tag_data["items"][0]["contract_type"] == "msa"

    # 4. GET /api/v1/inbox/stats
    res_stats = await api_client.get("/api/v1/inbox/stats")
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert stats["total_count"] >= 2
    assert stats["high_urgency_count"] >= 1
    assert "msa" in stats["type_distribution"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inbox_status_transitions(api_client: AsyncClient, test_db_session: AsyncSession):
    """Verify assign, acknowledge, complete, and archive mutations."""
    doc = Document(filename="hardware_lease_agreement.pdf", file_type="pdf")
    test_db_session.add(doc)
    await test_db_session.flush()

    triage = TriageResult(
        document_id=doc.id,
        contract_type_detected="lease",
        type_confidence=0.88,
        urgency_score=50,
        summary_bullets=["Equipment lease for datacenter servers"],
        inbox_status="unreviewed",
    )
    test_db_session.add(triage)
    await test_db_session.commit()

    # 1. Assign
    res_assign = await api_client.post(
        f"/api/v1/inbox/{doc.id}/assign",
        json={"assigned_to": "Alex Mercer (Procurement Lead)"},
    )
    assert res_assign.status_code == 200
    assert res_assign.json()["inbox_status"] == "assigned"
    assert res_assign.json()["assigned_to"] == "Alex Mercer (Procurement Lead)"

    # 2. Acknowledge
    res_ack = await api_client.post(
        f"/api/v1/inbox/{doc.id}/acknowledge",
        json={"acknowledged_by": "Alex Mercer"},
    )
    assert res_ack.status_code == 200
    assert res_ack.json()["inbox_status"] == "in_progress"
    assert res_ack.json()["acknowledged_by"] == "Alex Mercer"
    assert res_ack.json()["acknowledged_at"] is not None

    # 3. Modify Tags
    res_tags = await api_client.patch(
        f"/api/v1/inbox/{doc.id}/tags",
        json={"add_tags": ["capex", "reviewed"], "remove_tags": ["temporary"]},
    )
    assert res_tags.status_code == 200
    assert "capex" in res_tags.json()["auto_tags"]

    # 4. Complete
    res_comp = await api_client.post(f"/api/v1/inbox/{doc.id}/complete")
    assert res_comp.status_code == 200
    assert res_comp.json()["inbox_status"] == "completed"

    # 5. Archive
    res_arch = await api_client.post(f"/api/v1/inbox/{doc.id}/archive")
    assert res_arch.status_code == 200
    assert res_arch.json()["inbox_status"] == "archived"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inbox_bulk_assign_and_archive(
    api_client: AsyncClient, test_db_session: AsyncSession
):
    """Verify bulk assign and bulk archive operations."""
    doc1 = Document(filename="sow_backend_refactor.pdf", file_type="pdf")
    doc2 = Document(filename="sow_frontend_redesign.pdf", file_type="pdf")
    test_db_session.add_all([doc1, doc2])
    await test_db_session.flush()

    t1 = TriageResult(document_id=doc1.id, contract_type_detected="sow", urgency_score=40)
    t2 = TriageResult(document_id=doc2.id, contract_type_detected="sow", urgency_score=45)
    test_db_session.add_all([t1, t2])
    await test_db_session.commit()

    # Bulk Assign
    res_bulk_assign = await api_client.post(
        "/api/v1/inbox/bulk-assign",
        json={
            "document_ids": [str(doc1.id), str(doc2.id)],
            "assigned_to": "Engineering Legal Counsel",
        },
    )
    assert res_bulk_assign.status_code == 200
    assert res_bulk_assign.json()["updated_count"] == 2

    # Bulk Archive
    res_bulk_arch = await api_client.post(
        "/api/v1/inbox/bulk-archive",
        json={"document_ids": [str(doc1.id), str(doc2.id)]},
    )
    assert res_bulk_arch.status_code == 200
    assert res_bulk_arch.json()["archived_count"] == 2
