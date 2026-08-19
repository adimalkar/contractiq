"""Unit tests for TriageOrchestrator."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.config import Settings
from termnova.db.models import Document, TriageRule
from termnova.triage.orchestrator import TriageOrchestrator


@pytest.mark.unit
@pytest.mark.asyncio
async def test_triage_orchestrator_end_to_end(
    test_db_session: AsyncSession, test_settings: Settings
):
    """Verify full triage orchestrator pipeline classifies, scores, and persists TriageResult."""
    # 1. Create Routing Rule
    rule = TriageRule(
        name="Auto-Route NDAs to Contracts Specialist",
        condition={"contract_type": "nda"},
        action={"assign_to": "Sarah Chen", "set_status": "assigned"},
        priority=50,
        is_active=True,
    )
    test_db_session.add(rule)
    await test_db_session.commit()

    # 2. Create Document
    doc = Document(filename="mutual_nda_bilateral_2026.pdf", file_type="pdf")
    test_db_session.add(doc)
    await test_db_session.commit()
    await test_db_session.refresh(doc)

    # 3. Execute Triage
    orchestrator = TriageOrchestrator(session=test_db_session, settings=test_settings)
    sample_text = """
    MUTUAL NON-DISCLOSURE AGREEMENT
    Effective Date: April 1, 2026.
    Both parties desire to exchange confidential business information.
    Term of confidentiality shall be 2 years.
    """
    triage = await orchestrator.triage_document(
        document_id=doc.id,
        document_text=sample_text,
        filename=doc.filename,
    )

    assert triage.id is not None
    assert triage.document_id == doc.id
    assert triage.contract_type_detected == "nda"
    assert triage.urgency_score >= 0
    assert len(triage.summary_bullets) >= 1
    assert "standard-nda" in triage.auto_tags
    assert triage.assigned_to == "Sarah Chen"
    assert triage.inbox_status == "assigned"
