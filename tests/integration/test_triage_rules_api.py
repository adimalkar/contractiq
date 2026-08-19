"""Integration tests for Triage Rules REST API."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.db.models import Document, TriageResult


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_list_and_update_rules(api_client: AsyncClient):
    """Verify creating, listing, updating, and deactivating routing rules."""
    # 1. Create Rule
    create_payload = {
        "name": "Auto-Assign NDAs to Tier 1 Reviewer",
        "condition": {"contract_type": "nda", "urgency_max": 40},
        "action": {"assign_to": "Tier 1 Specialist", "set_status": "assigned"},
        "priority": 25,
        "is_active": True,
    }
    res_create = await api_client.post("/api/v1/triage/rules/", json=create_payload)
    assert res_create.status_code == 201
    rule_data = res_create.json()
    rule_id = rule_data["id"]
    assert rule_data["name"] == create_payload["name"]
    assert rule_data["priority"] == 25

    # 2. List Rules
    res_list = await api_client.get("/api/v1/triage/rules/")
    assert res_list.status_code == 200
    rules = res_list.json()
    assert any(r["id"] == rule_id for r in rules)

    # 3. Update Rule
    res_update = await api_client.put(
        f"/api/v1/triage/rules/{rule_id}",
        json={"priority": 15, "name": "Urgent Auto-Assign NDAs"},
    )
    assert res_update.status_code == 200
    assert res_update.json()["priority"] == 15
    assert res_update.json()["name"] == "Urgent Auto-Assign NDAs"

    # 4. Soft Delete Rule
    res_del = await api_client.delete(f"/api/v1/triage/rules/{rule_id}")
    assert res_del.status_code == 204

    # 5. Verify active_only filter
    res_active = await api_client.get("/api/v1/triage/rules/?active_only=true")
    assert res_active.status_code == 200
    active_rules = res_active.json()
    assert not any(r["id"] == rule_id for r in active_rules)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dry_run_rule_test(api_client: AsyncClient, test_db_session: AsyncSession):
    """Verify simulating rule matching on a contract document without committing state."""
    # 1. Create a matching active rule
    rule_payload = {
        "name": "High Urgency Escalation Rule",
        "condition": {"urgency_min": 70},
        "action": {"assign_to": "Senior Legal Officer", "add_tags": ["high-priority-escalation"]},
        "priority": 5,
        "is_active": True,
    }
    await api_client.post("/api/v1/triage/rules/", json=rule_payload)

    # 2. Create document and triage record
    doc = Document(filename="critical_amendment_deal.pdf", file_type="pdf")
    test_db_session.add(doc)
    await test_db_session.flush()

    triage = TriageResult(
        document_id=doc.id,
        contract_type_detected="amendment",
        urgency_score=88,
        inbox_status="unreviewed",
    )
    test_db_session.add(triage)
    await test_db_session.commit()

    # 3. POST /api/v1/triage/rules/test
    res_test = await api_client.post(
        "/api/v1/triage/rules/test",
        json={"document_id": str(doc.id)},
    )
    assert res_test.status_code == 200
    data = res_test.json()
    assert "High Urgency Escalation Rule" in data["matched_rules"]
    assert data["would_assign_to"] == "Senior Legal Officer"
    assert "high-priority-escalation" in data["would_add_tags"]
