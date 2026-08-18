"""Unit tests for WorkspaceService business operations and member management."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.workspace.service import WorkspaceService


@pytest.mark.unit
@pytest.mark.asyncio
async def test_workspace_service_create_and_list(test_db_session: AsyncSession):
    """Verify creating a workspace automatically registers creator as owner."""
    service = WorkspaceService(test_db_session)
    ws = await service.create_workspace(
        name="Tech Licensing Deal",
        document_scope=[],
        created_by="Sarah Chen",
        description="Scrutinizing IP indemnities",
    )

    assert ws.id is not None
    assert ws.name == "Tech Licensing Deal"
    assert ws.created_by == "Sarah Chen"

    members = await service.get_members(ws.id)
    assert len(members) == 1
    assert members[0].user_name == "Sarah Chen"
    assert members[0].role == "owner"

    items = await service.list_workspaces()
    assert any(item["workspace"].id == ws.id for item in items)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_workspace_member_addition_and_removal(test_db_session: AsyncSession):
    """Verify adding/removing members and preventing removal of sole owner."""
    service = WorkspaceService(test_db_session)
    ws = await service.create_workspace(name="Finance Audit", created_by="Alice")

    # Add editor
    member_bob = await service.add_member(ws.id, user_name="Bob", role="editor")
    assert member_bob.role == "editor"

    # Remove editor
    ok = await service.remove_member(ws.id, user_name="Bob")
    assert ok is True

    # Try removing sole owner -> should raise ValueError
    with pytest.raises(ValueError, match="Cannot remove the only workspace owner"):
        await service.remove_member(ws.id, user_name="Alice")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_workspace_message_pins_and_reactions(test_db_session: AsyncSession):
    """Verify pinning messages and toggling emoji reactions."""
    service = WorkspaceService(test_db_session)
    ws = await service.create_workspace(name="Legal Review", created_by="Alice")

    msg = await service.add_message(
        workspace_id=ws.id,
        content="Important warranty clause noted here.",
        user_name="Alice",
    )
    assert msg.is_pinned is False

    # Pin message
    pinned_msg = await service.toggle_pin_message(msg.id, is_pinned=True)
    assert pinned_msg.is_pinned is True

    pinned_list = await service.get_pinned_messages(ws.id)
    assert len(pinned_list) == 1
    assert pinned_list[0].id == msg.id

    # Toggle reaction
    updated = await service.toggle_reaction(msg.id, reaction="👍", user_name="Bob")
    assert "Bob" in updated.reactions["👍"]

    # Toggle again to remove
    updated_again = await service.toggle_reaction(msg.id, reaction="👍", user_name="Bob")
    assert "👍" not in updated_again.reactions or "Bob" not in updated_again.reactions.get("👍", [])
