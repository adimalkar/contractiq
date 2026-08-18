"""Unit tests for GraphBuilder, D3 data formatting, and Document Stack View."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.config import Settings
from termnova.db.models import Chunk, Document
from termnova.graph.builder import GraphBuilder


@pytest.mark.unit
@pytest.mark.asyncio
async def test_build_graph_and_get_graph_data(test_session: AsyncSession, test_settings: Settings):
    """Verify building graph for document populates nodes and edges."""
    builder = GraphBuilder(test_session, test_settings)

    # 1. Create MSA document with chunk
    msa_id = uuid.uuid4()
    msa_doc = Document(
        id=msa_id,
        filename="master_services_agreement.pdf",
        file_type="pdf",
        processing_status="completed",
        metadata_={"title": "Master Services Agreement"},
    )
    test_session.add(msa_doc)
    await test_session.flush()

    chunk1 = Chunk(
        document_id=msa_id,
        chunk_index=0,
        content="MASTER SERVICES AGREEMENT between Acme Corporation and Delta Systems. Governed by State of California.",
        page_number=1,
    )
    test_session.add(chunk1)
    await test_session.flush()

    # 2. Build graph for MSA
    res = await builder.build_graph_for_document(msa_id)
    assert res["document_id"] == str(msa_id)
    assert res["entities_linked"] >= 2

    # 3. Create SOW document
    sow_id = uuid.uuid4()
    sow_doc = Document(
        id=sow_id,
        filename="sow_1_delta_cloud.pdf",
        file_type="pdf",
        processing_status="completed",
        metadata_={"title": "Statement of Work 1"},
    )
    test_session.add(sow_doc)
    await test_session.flush()

    chunk2 = Chunk(
        document_id=sow_id,
        chunk_index=0,
        content="STATEMENT OF WORK between Acme Corp and Delta Systems pursuant to the Master Services Agreement.",
        page_number=1,
    )
    test_session.add(chunk2)
    await test_session.flush()

    # Build graph for SOW
    await builder.build_graph_for_document(sow_id)

    # 4. Fetch D3 Graph Data
    graph_data = await builder.get_graph_data(include_entities=True)
    assert graph_data.total_contracts >= 2
    assert graph_data.total_entities >= 2
    assert len(graph_data.nodes) >= 2
    assert len(graph_data.entity_nodes) >= 2
    assert len(graph_data.edges) >= 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_document_stack_hierarchy(test_session: AsyncSession, test_settings: Settings):
    """Verify document stack view builds tree with child SOWs."""
    builder = GraphBuilder(test_session, test_settings)

    # Create MSA
    msa_id = uuid.uuid4()
    msa = Document(
        id=msa_id,
        filename="msa_enterprise.pdf",
        file_type="pdf",
        processing_status="completed",
        metadata_={"contract_type": "msa", "title": "Enterprise MSA", "total_value_usd": 500000.0},
    )
    test_session.add(msa)

    # Create SOW
    sow_id = uuid.uuid4()
    sow = Document(
        id=sow_id,
        filename="sow_phase1.pdf",
        file_type="pdf",
        processing_status="completed",
        metadata_={"contract_type": "sow", "title": "Phase 1 SOW", "total_value_usd": 150000.0},
    )
    test_session.add(sow)
    await test_session.flush()

    # Link SOW to MSA
    await builder.create_relationship(
        source_id=sow_id,
        target_id=msa_id,
        rel_type="parent_sow",
    )

    stack = await builder.get_document_stack(msa_id)
    assert stack.root_document_id == msa_id
    assert stack.total_descendants == 1
    assert len(stack.stack.children) == 1
    assert stack.stack.children[0].document_id == sow_id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_manual_relationship_crud(test_session: AsyncSession, test_settings: Settings):
    """Verify manual creation, inspection, and deletion of contract links."""
    builder = GraphBuilder(test_session, test_settings)

    doc_a = Document(
        id=uuid.uuid4(), filename="doc_a.pdf", file_type="pdf", processing_status="completed"
    )
    doc_b = Document(
        id=uuid.uuid4(), filename="doc_b.pdf", file_type="pdf", processing_status="completed"
    )
    test_session.add_all([doc_a, doc_b])
    await test_session.flush()

    rel = await builder.create_relationship(
        source_id=doc_a.id,
        target_id=doc_b.id,
        rel_type="amends",
        metadata={"note": "Manual redline link"},
    )
    assert rel.id is not None

    rels = await builder.get_document_relationships(doc_a.id)
    assert len(rels) == 1
    assert rels[0].relationship_type == "amends"

    deleted = await builder.delete_relationship(rel.id)
    assert deleted is True

    rels_after = await builder.get_document_relationships(doc_a.id)
    assert len(rels_after) == 0
