"""Unit tests for TriageRuleEngine."""

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.db.models import Document, TriageResult, TriageRule
from termnova.triage.rule_engine import TriageRuleEngine


@pytest.mark.unit
def test_rule_condition_matching():
    """Verify rule condition matching across types, urgency thresholds, and tags."""
    engine = TriageRuleEngine()
    triage = TriageResult(
        contract_type_detected="msa",
        type_confidence=0.9,
        urgency_score=80,
        auto_tags=["high-value", "requires-legal"],
    )

    # 1. Exact contract type match
    assert engine.matches_condition({"contract_type": "msa"}, triage) is True
    assert engine.matches_condition({"contract_type": "nda"}, triage) is False

    # 2. Urgency min and max
    assert engine.matches_condition({"urgency_min": 70}, triage) is True
    assert engine.matches_condition({"urgency_min": 90}, triage) is False
    assert engine.matches_condition({"urgency_max": 85}, triage) is True

    # 3. Tags include and exclude
    assert engine.matches_condition({"tags_include": ["high-value"]}, triage) is True
    assert engine.matches_condition({"tags_include": ["non-existent"]}, triage) is False
    assert engine.matches_condition({"tags_exclude": ["auto-approve"]}, triage) is True
    assert engine.matches_condition({"tags_exclude": ["high-value"]}, triage) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rule_evaluation_priority_ordering(test_db_session: AsyncSession):
    """Verify highest priority rule applies first."""
    await test_db_session.execute(delete(TriageRule))
    await test_db_session.commit()

    rule_low = TriageRule(
        name="Catch-all MSA to Legal Team",
        condition={"contract_type": "msa"},
        action={"assign_to": "Legal Team", "set_status": "assigned"},
        priority=100,
        is_active=True,
    )
    rule_high = TriageRule(
        name="Escalate High-Value MSA to General Counsel",
        condition={"contract_type": "msa", "urgency_min": 75},
        action={"assign_to": "General Counsel", "add_tags": ["executive-review"]},
        priority=10,
        is_active=True,
    )
    test_db_session.add_all([rule_low, rule_high])
    await test_db_session.commit()

    doc = Document(filename="enterprise_msa.pdf", file_type="pdf")
    test_db_session.add(doc)
    await test_db_session.flush()

    triage = TriageResult(
        document_id=doc.id,
        contract_type_detected="msa",
        type_confidence=0.95,
        urgency_score=85,
        auto_tags=["high-value"],
    )
    test_db_session.add(triage)
    await test_db_session.commit()

    engine = TriageRuleEngine()
    matches = await engine.evaluate_rules(test_db_session, triage_result=triage)

    assert len(matches) == 2
    assert matches[0].rule_name == "Escalate High-Value MSA to General Counsel"
    assert matches[0].assign_to == "General Counsel"
