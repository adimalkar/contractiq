"""Unit tests for negotiation tracking SQLAlchemy ORM models."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.db.models import (
    Document,
    NegotiationChange,
    NegotiationTrack,
    NegotiationVersion,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_track_with_counterparty(test_session: AsyncSession):
    """Verify creating a negotiation track persists with correct defaults."""
    track = NegotiationTrack(
        name="Acme Corp MSA Q3 2026",
        counterparty="Acme Corporation",
        contract_type="msa",
        status="active",
        notes="Key priorities: 12-month liability cap, mutual IP ownership.",
        started_by="Sarah Legal",
    )
    test_session.add(track)
    await test_session.commit()
    await test_session.refresh(track)

    assert track.id is not None
    assert track.name == "Acme Corp MSA Q3 2026"
    assert track.counterparty == "Acme Corporation"
    assert track.contract_type == "msa"
    assert track.status == "active"
    assert track.started_by == "Sarah Legal"
    assert track.started_at is not None
    assert repr(track).startswith("<NegotiationTrack")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_add_version_to_track(test_session: AsyncSession):
    """Verify linking document versions to a negotiation track."""
    doc = Document(
        filename="acme_msa_v1.pdf",
        file_type="pdf",
        processing_status="completed",
    )
    test_session.add(doc)
    await test_session.flush()

    track = NegotiationTrack(
        name="Acme Master Agreement",
        counterparty="Acme Corp",
        contract_type="msa",
    )
    test_session.add(track)
    await test_session.flush()

    v1 = NegotiationVersion(
        track_id=track.id,
        document_id=doc.id,
        version_number=1,
        source="internal",
        notes="Initial draft sent to counterparty.",
        risk_score=0.25,
        risk_delta=0.0,
        uploaded_by="Sarah Legal",
    )
    test_session.add(v1)
    await test_session.commit()
    await test_session.refresh(v1)

    assert v1.id is not None
    assert v1.version_number == 1
    assert v1.source == "internal"
    assert v1.risk_score == 0.25
    assert repr(v1).startswith("<NegotiationVersion")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_version_number_unique_within_track(test_session: AsyncSession):
    """Verify unique constraint prevents duplicate version numbers within a track."""
    doc1 = Document(filename="v1.pdf", file_type="pdf")
    doc2 = Document(filename="v1_dup.pdf", file_type="pdf")
    test_session.add_all([doc1, doc2])
    await test_session.flush()

    track = NegotiationTrack(
        name="Unique Test Track",
        counterparty="Beta LLC",
        contract_type="nda",
    )
    test_session.add(track)
    await test_session.flush()

    v1_a = NegotiationVersion(
        track_id=track.id,
        document_id=doc1.id,
        version_number=1,
        source="internal",
    )
    v1_b = NegotiationVersion(
        track_id=track.id,
        document_id=doc2.id,
        version_number=1,
        source="counterparty",
    )
    test_session.add(v1_a)
    await test_session.flush()

    test_session.add(v1_b)
    with pytest.raises(IntegrityError):
        await test_session.flush()
    await test_session.rollback()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_change_between_versions(test_session: AsyncSession):
    """Verify persisting a clause change with concession and risk impact metadata."""
    track = NegotiationTrack(
        name="Change Test Track",
        counterparty="Gamma Tech",
        contract_type="sow",
    )
    test_session.add(track)
    await test_session.flush()

    change = NegotiationChange(
        track_id=track.id,
        from_version=1,
        to_version=2,
        clause_category="liability",
        change_type="modified",
        original_text="Total liability is capped at $500,000.",
        modified_text="Total liability is capped at $2,000,000.",
        diff_html="<del>500,000</del> <ins>2,000,000</ins>",
        risk_impact="increased_risk",
        concession_party="us",
        concession_summary="We agreed to increase aggregate liability cap from $500k to $2M.",
        significance="high",
    )
    test_session.add(change)
    await test_session.commit()
    await test_session.refresh(change)

    assert change.id is not None
    assert change.from_version == 1
    assert change.to_version == 2
    assert change.clause_category == "liability"
    assert change.risk_impact == "increased_risk"
    assert change.concession_party == "us"
    assert change.significance == "high"
    assert repr(change).startswith("<NegotiationChange")
