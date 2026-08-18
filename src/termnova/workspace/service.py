"""Business logic and database operations for collaborative workspaces and team chat."""

import uuid
from typing import Any

import structlog
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.db.models import Document, Workspace, WorkspaceMember, WorkspaceMessage

logger = structlog.get_logger(__name__)


class WorkspaceService:
    """Service handling multi-user workspace management, membership, and message feeds."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_workspace(
        self,
        name: str,
        document_scope: list[str] | None = None,
        created_by: str = "Team Member",
        description: str | None = None,
    ) -> Workspace:
        """Create a new workspace and automatically register creator as the owner."""
        scope = document_scope or []
        ws = Workspace(
            name=name.strip(),
            description=description.strip() if description else None,
            document_scope=scope,
            created_by=created_by,
        )
        self.session.add(ws)
        await self.session.flush()

        # Add creator as owner
        owner_member = WorkspaceMember(
            workspace_id=ws.id,
            user_name=created_by,
            role="owner",
        )
        self.session.add(owner_member)
        await self.session.commit()
        await self.session.refresh(ws)

        logger.info(
            "Created collaborative workspace",
            workspace_id=str(ws.id),
            name=ws.name,
            scope_count=len(scope),
            created_by=created_by,
        )
        return ws

    async def get_workspace(self, workspace_id: uuid.UUID) -> Workspace | None:
        """Fetch workspace by ID."""
        stmt = select(Workspace).where(Workspace.id == workspace_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_workspaces(
        self, user_name: str | None = None, include_archived: bool = False
    ) -> list[dict[str, Any]]:
        """List all active workspaces with member counts, document counts, and message counts."""
        stmt = select(Workspace)
        if not include_archived:
            stmt = stmt.where(Workspace.is_archived.is_(False))

        stmt = stmt.order_by(desc(Workspace.updated_at))
        result = await self.session.execute(stmt)
        workspaces = result.scalars().all()

        output = []
        for ws in workspaces:
            # Query counts
            m_count_stmt = select(func.count(WorkspaceMember.user_name)).where(
                WorkspaceMember.workspace_id == ws.id
            )
            msg_count_stmt = select(func.count(WorkspaceMessage.id)).where(
                WorkspaceMessage.workspace_id == ws.id
            )
            member_count = (await self.session.execute(m_count_stmt)).scalar() or 0
            message_count = (await self.session.execute(msg_count_stmt)).scalar() or 0

            output.append(
                {
                    "workspace": ws,
                    "member_count": member_count,
                    "message_count": message_count,
                    "document_count": len(ws.document_scope or []),
                }
            )
        return output

    async def update_workspace(
        self,
        workspace_id: uuid.UUID,
        name: str | None = None,
        description: str | None = None,
        document_scope: list[str] | None = None,
        is_archived: bool | None = None,
    ) -> Workspace | None:
        """Update workspace title, description, document scope, or archive status."""
        ws = await self.get_workspace(workspace_id)
        if not ws:
            return None

        if name is not None:
            ws.name = name.strip()
        if description is not None:
            ws.description = description.strip() if description else None
        if document_scope is not None:
            ws.document_scope = document_scope
        if is_archived is not None:
            ws.is_archived = is_archived

        await self.session.commit()
        await self.session.refresh(ws)
        return ws

    async def archive_workspace(self, workspace_id: uuid.UUID) -> bool:
        """Soft-delete / archive a workspace."""
        ws = await self.get_workspace(workspace_id)
        if not ws:
            return False
        ws.is_archived = True
        await self.session.commit()
        return True

    # ──── Members Management ────

    async def add_member(
        self, workspace_id: uuid.UUID, user_name: str, role: str = "editor"
    ) -> WorkspaceMember:
        """Add or update member role in workspace."""
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_name == user_name,
        )
        existing = (await self.session.execute(stmt)).scalars().first()
        if existing:
            existing.role = role
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_name=user_name,
            role=role,
        )
        self.session.add(member)
        await self.session.commit()
        await self.session.refresh(member)
        return member

    async def remove_member(self, workspace_id: uuid.UUID, user_name: str) -> bool:
        """Remove member from workspace. Prevents removing the last owner."""
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_name == user_name,
        )
        member = (await self.session.execute(stmt)).scalars().first()
        if not member:
            return False

        if member.role == "owner":
            owner_count_stmt = select(func.count(WorkspaceMember.user_name)).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == "owner",
            )
            owner_count = (await self.session.execute(owner_count_stmt)).scalar() or 0
            if owner_count <= 1:
                raise ValueError("Cannot remove the only workspace owner")

        await self.session.delete(member)
        await self.session.commit()
        return True

    async def get_members(self, workspace_id: uuid.UUID) -> list[WorkspaceMember]:
        """Fetch all members of a workspace."""
        stmt = select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_scoped_documents(self, workspace: Workspace) -> list[dict[str, Any]]:
        """Fetch summary metadata for documents scoped to this workspace."""
        if not workspace.document_scope:
            return []

        doc_uuids = []
        for d in workspace.document_scope:
            try:
                doc_uuids.append(uuid.UUID(str(d)))
            except (ValueError, TypeError):
                continue

        if not doc_uuids:
            return []

        stmt = select(Document).where(Document.id.in_(doc_uuids))
        result = await self.session.execute(stmt)
        docs = result.scalars().all()

        return [
            {
                "id": str(d.id),
                "filename": d.filename,
                "file_type": d.file_type,
                "contract_type": (d.metadata_ or {}).get("contract_type", "other"),
                "parties": (d.metadata_ or {}).get("extracted_parties", []),
                "upload_timestamp": d.upload_timestamp.isoformat() if d.upload_timestamp else None,
            }
            for d in docs
        ]

    # ──── Messages & Collaboration Feed ────

    async def add_message(
        self,
        workspace_id: uuid.UUID,
        content: str,
        user_name: str | None = None,
        message_type: str = "human",
        citations: list[dict[str, Any]] | None = None,
        parent_message_id: uuid.UUID | None = None,
        query_log_id: uuid.UUID | None = None,
    ) -> WorkspaceMessage:
        """Persist a message (human, AI response, or system) into the workspace history."""
        msg = WorkspaceMessage(
            workspace_id=workspace_id,
            user_name=user_name,
            message_type=message_type,
            content=content,
            citations=citations or [],
            parent_message_id=parent_message_id,
            query_log_id=query_log_id,
        )
        self.session.add(msg)

        # Touch workspace updated_at
        await self.session.execute(
            update(Workspace).where(Workspace.id == workspace_id).values(updated_at=func.now())
        )

        await self.session.commit()
        await self.session.refresh(msg)
        return msg

    async def get_messages(
        self,
        workspace_id: uuid.UUID,
        limit: int = 50,
        parent_id: uuid.UUID | None = None,
    ) -> list[WorkspaceMessage]:
        """Fetch workspace message history."""
        stmt = select(WorkspaceMessage).where(WorkspaceMessage.workspace_id == workspace_id)
        if parent_id is not None:
            stmt = stmt.where(WorkspaceMessage.parent_message_id == parent_id)
        else:
            # Main thread by default or all if parent_id is None
            pass

        stmt = stmt.order_by(WorkspaceMessage.created_at.asc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_pinned_messages(self, workspace_id: uuid.UUID) -> list[WorkspaceMessage]:
        """Fetch all pinned findings in a workspace."""
        stmt = (
            select(WorkspaceMessage)
            .where(
                WorkspaceMessage.workspace_id == workspace_id,
                WorkspaceMessage.is_pinned.is_(True),
            )
            .order_by(desc(WorkspaceMessage.created_at))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def toggle_pin_message(
        self, message_id: uuid.UUID, is_pinned: bool
    ) -> WorkspaceMessage | None:
        """Pin or unpin a message."""
        stmt = select(WorkspaceMessage).where(WorkspaceMessage.id == message_id)
        msg = (await self.session.execute(stmt)).scalars().first()
        if not msg:
            return None

        msg.is_pinned = is_pinned
        await self.session.commit()
        await self.session.refresh(msg)
        return msg

    async def toggle_reaction(
        self, message_id: uuid.UUID, reaction: str, user_name: str
    ) -> WorkspaceMessage | None:
        """Add or remove an emoji reaction on a message."""
        stmt = select(WorkspaceMessage).where(WorkspaceMessage.id == message_id)
        msg = (await self.session.execute(stmt)).scalars().first()
        if not msg:
            return None

        current_reactions = dict(msg.reactions or {})
        user_list = list(current_reactions.get(reaction, []))

        if user_name in user_list:
            user_list.remove(user_name)
            if user_list:
                current_reactions[reaction] = user_list
            else:
                current_reactions.pop(reaction, None)
        else:
            user_list.append(user_name)
            current_reactions[reaction] = user_list

        msg.reactions = current_reactions
        await self.session.commit()
        await self.session.refresh(msg)
        return msg
