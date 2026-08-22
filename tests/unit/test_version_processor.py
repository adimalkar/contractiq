"""Unit tests for VersionProcessor multi-round negotiation ingestion and diff processing."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.comparison.version_processor import VersionProcessor
from termnova.db.models import Chunk, Document, NegotiationTrack


@pytest.fixture
def processor() -> VersionProcessor:
    return VersionProcessor()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_first_version_no_diff(test_session: AsyncSession, processor: VersionProcessor):
    """Verify first version creates v1 with initial risk score and no changes."""
    track = NegotiationTrack(
        name="Track Alpha",
        counterparty="Alpha Systems",
        contract_type="msa",
    )
    doc1 = Document(filename="alpha_v1.pdf", file_type="pdf")
    test_session.add_all([track, doc1])
    await test_session.flush()

    v1, changes = await processor.process_new_version(
        db=test_session,
        track_id=track.id,
        document_id=doc1.id,
        source="internal",
        notes="Initial contract proposal.",
    )

    assert v1.version_number == 1
    assert v1.risk_score == 0.25
    assert v1.risk_delta == 0.0
    assert len(changes) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_second_version_auto_diffs_and_computes_delta(
    test_session: AsyncSession, processor: VersionProcessor
):
    """Verify second version auto-diffs against v1 and computes risk delta."""
    track = NegotiationTrack(
        name="Track Beta",
        counterparty="Beta Systems",
        contract_type="sow",
    )
    doc1 = Document(filename="beta_v1.pdf", file_type="pdf")
    doc2 = Document(filename="beta_v2.pdf", file_type="pdf")
    test_session.add_all([track, doc1, doc2])
    await test_session.flush()

    # Add chunks to doc1 and doc2
    chunk1_1 = Chunk(
        document_id=doc1.id,
        chunk_index=0,
        section_header="ARTICLE 1: LIABILITY",
        content="Total liability is capped at $500,000.",
    )
    chunk1_2 = Chunk(
        document_id=doc1.id,
        chunk_index=1,
        section_header="ARTICLE 2: PAYMENT",
        content="Payment is due Net 30 days.",
    )

    chunk2_1 = Chunk(
        document_id=doc2.id,
        chunk_index=0,
        section_header="ARTICLE 1: LIABILITY",
        content="Total liability is capped at $2,000,000.",
    )
    chunk2_2 = Chunk(
        document_id=doc2.id,
        chunk_index=1,
        section_header="ARTICLE 2: PAYMENT",
        content="Payment is due Net 60 days.",
    )
    test_session.add_all([chunk1_1, chunk1_2, chunk2_1, chunk2_2])
    await test_session.flush()

    # Process v1
    v1, changes1 = await processor.process_new_version(
        db=test_session,
        track_id=track.id,
        document_id=doc1.id,
        source="internal",
    )
    assert v1.version_number == 1

    # Process v2
    v2, changes2 = await processor.process_new_version(
        db=test_session,
        track_id=track.id,
        document_id=doc2.id,
        source="counterparty",
        notes="Counterparty redline received.",
    )

    assert v2.version_number == 2
    assert len(changes2) >= 1
    assert v2.risk_delta is not None
    assert v2.risk_score is not None
