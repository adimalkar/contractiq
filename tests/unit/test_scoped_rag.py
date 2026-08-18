"""Unit tests for ScopedRAGExecutor verifying document isolation and citations."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.config import Settings
from termnova.db.models import Chunk, Document, Workspace
from termnova.pipeline.embedder import EmbeddingService
from termnova.workspace.scoped_query import ScopedRAGExecutor


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scoped_rag_executor_isolation(
    test_db_session: AsyncSession, test_settings: Settings
):
    """Verify ScopedRAGExecutor strictly retrieves chunks belonging to workspace document scope."""
    # 1. Create Document A (In Scope)
    doc_a = Document(filename="scoped_msa.pdf", file_type="pdf")
    test_db_session.add(doc_a)
    await test_db_session.flush()

    embedder = EmbeddingService(test_settings)
    chunk_a_text = "The vendor provides 99.99% uptime guarantee with 24/7 support under Section 4."
    chunk_a = Chunk(
        document_id=doc_a.id,
        chunk_index=0,
        content=chunk_a_text,
        token_count=20,
        page_number=2,
        embedding=embedder.embed_query(chunk_a_text),
        section_header="Section 4 Uptime SLA",
    )

    # 2. Create Document B (Out of Scope)
    doc_b = Document(filename="unrelated_lease.pdf", file_type="pdf")
    test_db_session.add(doc_b)
    await test_db_session.flush()

    chunk_b_text = "The commercial tenant shall maintain premises in clean condition."
    chunk_b = Chunk(
        document_id=doc_b.id,
        chunk_index=0,
        content=chunk_b_text,
        token_count=15,
        page_number=1,
        embedding=embedder.embed_query(chunk_b_text),
        section_header="Premises Maintenance",
    )
    test_db_session.add_all([chunk_a, chunk_b])
    await test_db_session.commit()

    # 3. Create Workspace with ONLY doc_a in scope
    ws = Workspace(
        name="SLA Review Room",
        document_scope=[str(doc_a.id)],
        created_by="Alice",
    )
    test_db_session.add(ws)
    await test_db_session.commit()
    await test_db_session.refresh(ws)

    # 4. Execute Scoped RAG Query
    executor = ScopedRAGExecutor(
        session=test_db_session,
        settings=test_settings,
        embedder=embedder,
    )

    human_msg, ai_msg = await executor.execute_workspace_query(
        workspace=ws,
        query="What is the uptime guarantee?",
        user_name="Alice",
    )

    assert human_msg.content == "What is the uptime guarantee?"
    assert human_msg.user_name == "Alice"
    assert ai_msg.message_type == "ai_response"
    assert len(ai_msg.citations) > 0

    # Ensure all citations only originate from doc_a
    for c in ai_msg.citations:
        assert c["document_name"] == "scoped_msa.pdf"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scoped_rag_executor_empty_scope_does_not_leak(
    test_db_session: AsyncSession, test_settings: Settings
):
    """Verify that an empty workspace scope returns early and never retrieves out-of-scope documents."""
    embedder = EmbeddingService(test_settings)
    doc_unrelated = Document(filename="confidential_patent.pdf", file_type="pdf")
    test_db_session.add(doc_unrelated)
    await test_db_session.flush()

    chunk_text = "Proprietary trade secrets regarding neural quantum circuits."
    chunk = Chunk(
        document_id=doc_unrelated.id,
        chunk_index=0,
        content=chunk_text,
        token_count=10,
        page_number=1,
        embedding=embedder.embed_query(chunk_text),
        section_header="Quantum IP",
    )
    test_db_session.add(chunk)
    await test_db_session.commit()

    # Workspace with completely empty document scope
    ws_empty = Workspace(
        name="Empty Workspace",
        document_scope=[],
        created_by="Bob",
    )
    test_db_session.add(ws_empty)
    await test_db_session.commit()
    await test_db_session.refresh(ws_empty)

    executor = ScopedRAGExecutor(
        session=test_db_session,
        settings=test_settings,
        embedder=embedder,
    )

    human_msg, ai_msg = await executor.execute_workspace_query(
        workspace=ws_empty,
        query="What are the quantum trade secrets?",
        user_name="Bob",
    )

    assert human_msg.content == "What are the quantum trade secrets?"
    assert "No valid documents are attached" in ai_msg.content
    assert ai_msg.citations is None or len(ai_msg.citations) == 0
