"""Unit tests for TriageResult and TriageRule ORM models."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.db.models import Document, TriageResult, TriageRule


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_triage_result_with_all_fields(test_db_session: AsyncSession):
    """Verify creating a TriageResult persists classification, urgency, and tags."""
    doc = Document(filename="master_subscription_agreement_2026.pdf", file_type="pdf")
    test_db_session.add(doc)
    await test_db_session.flush()

    triage = TriageResult(
        document_id=doc.id,
        contract_type_detected="msa",
        type_confidence=0.95,
        urgency_score=85,
        urgency_factors={
            "deadline_proximity": 20,
            "contract_value": 25,
            "risk_signals": 25,
            "contract_type_weight": 15,
        },
        summary_bullets=[
            "3-year enterprise SaaS agreement with Acme Corp",
            "Annual contract value of $1,200,000 with net 30 payment terms",
            "Uncapped indemnity on data protection breaches under Section 9",
        ],
        action_required="Legal Review required before CFO signature",
        suggested_assignee="Sarah Chen (Lead Counsel)",
        auto_tags=["high-value", "uncapped-liability", "urgent"],
        inbox_status="unreviewed",
        assigned_to="Sarah Chen",
    )
    test_db_session.add(triage)
    await test_db_session.commit()
    await test_db_session.refresh(triage)

    assert triage.id is not None
    assert triage.contract_type_detected == "msa"
    assert triage.urgency_score == 85
    assert len(triage.summary_bullets) == 3
    assert "high-value" in triage.auto_tags
    assert triage.document.filename == "master_subscription_agreement_2026.pdf"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_triage_result_unique_per_document(test_db_session: AsyncSession):
    """Verify database enforces unique triage result per document."""
    doc = Document(filename="mutual_nda.pdf", file_type="pdf")
    test_db_session.add(doc)
    await test_db_session.flush()

    t1 = TriageResult(
        document_id=doc.id,
        contract_type_detected="nda",
        type_confidence=0.9,
        urgency_score=10,
        summary_bullets=["Standard mutual confidentiality agreement"],
    )
    test_db_session.add(t1)
    await test_db_session.commit()

    # Attempt second triage on same doc
    t2 = TriageResult(
        document_id=doc.id,
        contract_type_detected="nda",
        type_confidence=0.9,
        urgency_score=15,
        summary_bullets=["Duplicate triage attempt"],
    )
    test_db_session.add(t2)
    with pytest.raises(IntegrityError):
        await test_db_session.commit()
    await test_db_session.rollback()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_triage_rule_priority_ordering(test_db_session: AsyncSession):
    """Verify creating TriageRules and querying in priority ordering."""
    rule_low_prio = TriageRule(
        name="Catch-all NDA Assignment",
        condition={"contract_type": "nda"},
        action={"assign_to": "Junior Counsel", "set_status": "assigned"},
        priority=100,
        is_active=True,
    )
    rule_high_prio = TriageRule(
        name="Urgent High-Value Escalation",
        condition={"urgency_min": 80, "tags_include": ["high-value"]},
        action={"assign_to": "VP Legal", "add_tags": ["executive-review"]},
        priority=10,
        is_active=True,
    )
    test_db_session.add_all([rule_low_prio, rule_high_prio])
    await test_db_session.commit()

    stmt = (
        select(TriageRule)
        .where(TriageRule.id.in_([rule_low_prio.id, rule_high_prio.id]))
        .order_by(TriageRule.priority.asc())
    )
    rules = list((await test_db_session.execute(stmt)).scalars().all())

    assert len(rules) == 2
    assert rules[0].priority == 10
    assert rules[0].name == "Urgent High-Value Escalation"
    assert rules[1].priority == 100
