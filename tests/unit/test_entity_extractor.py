"""Unit tests for entity extraction, normalization, and fuzzy matching."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.config import Settings
from termnova.db.models import Document, DocumentEntity, EntityNode
from termnova.graph.entity_extractor import EntityExtractor
from termnova.graph.schemas import ExtractedEntities, ExtractedParty


@pytest.mark.unit
def test_normalize_entity_name():
    """Verify corporate suffix removal and string normalization."""
    assert EntityExtractor.normalize_name("Acme Corporation") == "acme"
    assert EntityExtractor.normalize_name("Acme Corp.") == "acme"
    assert EntityExtractor.normalize_name("Acme, Inc.") == "acme"
    assert EntityExtractor.normalize_name("Wayne Enterprises LLC") == "wayne enterprises"
    assert EntityExtractor.normalize_name("Stark Industries Ltd.") == "stark industries"


@pytest.mark.unit
def test_fuzzy_match():
    """Verify fuzzy matching between company variations."""
    assert EntityExtractor.is_fuzzy_match("Acme Corporation", "Acme Corp")
    assert EntityExtractor.is_fuzzy_match("Wayne Enterprises LLC", "Wayne Enterprises")
    assert EntityExtractor.is_fuzzy_match("CloudTech Solutions Inc", "CloudTech Solutions")
    assert not EntityExtractor.is_fuzzy_match("Google LLC", "Microsoft Corp")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_heuristic_extraction(test_settings: Settings):
    """Verify rule-based heuristic extraction on mock contract text."""
    extractor = EntityExtractor(test_settings)
    contract_text = """MASTER SERVICES AGREEMENT
    This Agreement is entered into by and between Acme Corp (Party A) and CloudTech Solutions Inc (Party B).
    ARTICLE 1: GOVERNING LAW
    This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware.
    ARTICLE 2: EFFECTIVE DATE
    Made as of January 15, 2024.
    ARTICLE 3: PRIOR AGREEMENTS
    Executed pursuant to the terms of the Master Vendor Agreement.
    """
    extracted = await extractor.extract(contract_text, "acme_cloudtech_msa.pdf")
    assert extracted.contract_type == "msa"
    assert len(extracted.parties) >= 2
    party_names = [p.name for p in extracted.parties]
    assert any("Acme" in p for p in party_names)
    assert any("CloudTech" in p for p in party_names)
    assert extracted.governing_law is not None
    assert "Delaware" in extracted.governing_law
    assert extracted.effective_date is not None
    assert len(extracted.referenced_contracts) >= 1
    assert extracted.referenced_contracts[0].target_title != ""


@pytest.mark.unit
@pytest.mark.asyncio
async def test_persist_entities_in_database(test_session: AsyncSession, test_settings: Settings):
    """Verify persisting entities creates EntityNode and DocumentEntity links."""
    extractor = EntityExtractor(test_settings)
    doc = Document(
        id=uuid.uuid4(),
        filename="test_contract.pdf",
        file_type="pdf",
        processing_status="completed",
        metadata_={},
    )
    test_session.add(doc)
    await test_session.flush()

    extracted = ExtractedEntities(
        contract_type="msa",
        title="Master Services Agreement",
        parties=[
            ExtractedParty(name="Acme Corp", role="party_a", entity_type="company"),
            ExtractedParty(name="Beta LLC", role="party_b", entity_type="company"),
        ],
        governing_law="State of New York",
    )

    persisted = await extractor.persist_entities(test_session, doc.id, extracted)
    assert len(persisted) >= 3  # 2 parties + 1 governing law jurisdiction

    # Check entities in DB
    ent_stmt = select(EntityNode)
    res = await test_session.execute(ent_stmt)
    entities = res.scalars().all()
    assert len(entities) >= 3

    # Check links
    link_stmt = select(DocumentEntity).where(DocumentEntity.document_id == doc.id)
    links_res = await test_session.execute(link_stmt)
    links = links_res.scalars().all()
    assert len(links) >= 3
