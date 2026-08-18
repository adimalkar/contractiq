"""Unit tests for Workspace ORM models, relationships, pinning, and reactions."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.db.models import Workspace, WorkspaceMember, WorkspaceMessage


@pytest.mark.unit
@pytest.mark.asyncio
async def test_workspace_creation_with_document_scope(test_db_session: AsyncSession):
    """Test creating a workspace with an assigned document scope."""
    doc_1 = uuid.uuid4()
    doc_2 = uuid.uuid4()

    ws = Workspace(
        name="Q3 Vendor Review",
        description="Reviewing SaaS vendors and cloud infra agreements",
        document_scope=[str(doc_1), str(doc_2)],
        created_by="Alice",
    )
    test_db_session.add(ws)
    await test_db_session.commit()
    await test_db_session.refresh(ws)

    assert ws.id is not None
    assert ws.name == "Q3 Vendor Review"
    assert len(ws.document_scope) == 2
    assert str(doc_1) in ws.document_scope
    assert ws.is_archived is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_workspace_members_and_roles(test_db_session: AsyncSession):
    """Test adding members with different roles."""
    from sqlalchemy import select

    ws = Workspace(name="Acme Negotiation", created_by="Alice")
    test_db_session.add(ws)
    await test_db_session.flush()

    member_owner = WorkspaceMember(workspace_id=ws.id, user_name="Alice", role="owner")
    member_editor = WorkspaceMember(workspace_id=ws.id, user_name="Bob", role="editor")
    member_viewer = WorkspaceMember(workspace_id=ws.id, user_name="Charlie", role="viewer")

    test_db_session.add_all([member_owner, member_editor, member_viewer])
    await test_db_session.commit()

    stmt = select(WorkspaceMember).where(WorkspaceMember.workspace_id == ws.id)
    result = await test_db_session.execute(stmt)
    members = list(result.scalars().all())

    assert len(members) == 3
    roles = {m.user_name: m.role for m in members}
    assert roles["Alice"] == "owner"
    assert roles["Bob"] == "editor"
    assert roles["Charlie"] == "viewer"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_workspace_message_threading_pinning_and_reactions(test_db_session: AsyncSession):
    """Test human/AI messages, threading, pinning, and emoji reactions."""
    ws = Workspace(name="M&A Deal Room", created_by="Alice")
    test_db_session.add(ws)
    await test_db_session.flush()

    # Human parent message
    msg_1 = WorkspaceMessage(
        workspace_id=ws.id,
        user_name="Alice",
        message_type="human",
        content="What are the indemnity caps across all three vendor contracts?",
    )
    test_db_session.add(msg_1)
    await test_db_session.flush()

    # AI reply
    msg_ai = WorkspaceMessage(
        workspace_id=ws.id,
        user_name=None,
        message_type="ai_response",
        content="The aggregate liability cap is $5,000,000 under Section 8.1 [Source 1].",
        citations=[{"source_id": 1, "document_name": "vendor_msa.pdf", "page_number": 12}],
        parent_message_id=msg_1.id,
        is_pinned=True,
        reactions={"👍": ["Alice", "Bob"], "⚠️": ["Charlie"]},
    )
    test_db_session.add(msg_ai)
    await test_db_session.commit()
    await test_db_session.refresh(msg_ai)

    assert msg_ai.is_pinned is True
    assert msg_ai.parent_message_id == msg_1.id
    assert len(msg_ai.citations) == 1
    assert "Alice" in msg_ai.reactions["👍"]
    assert "Charlie" in msg_ai.reactions["⚠️"]
