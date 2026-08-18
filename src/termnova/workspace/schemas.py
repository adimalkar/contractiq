"""Pydantic v2 validation and serialization schemas for collaborative workspaces."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkspaceCreateRequest(BaseModel):
    """Payload to create a new scoped collaborative workspace."""

    name: str = Field(..., min_length=1, max_length=255, description="Workspace title")
    description: str | None = Field(
        None, max_length=2000, description="Optional description/purpose"
    )
    document_scope: list[str] = Field(
        default_factory=list,
        description="List of document UUID strings included in this workspace's RAG scope",
    )
    created_by: str = Field(default="Team Member", max_length=100)


class WorkspaceUpdateRequest(BaseModel):
    """Payload to update workspace metadata or document scope."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    document_scope: list[str] | None = None
    is_archived: bool | None = None


class WorkspaceMemberAddRequest(BaseModel):
    """Payload to add or invite a member to a workspace."""

    user_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(default="editor", pattern="^(owner|editor|viewer)$")


class WorkspaceMemberResponse(BaseModel):
    """Member detail within a workspace."""

    workspace_id: uuid.UUID
    user_name: str
    role: str
    joined_at: datetime
    last_read_at: datetime | None = None


class WorkspaceResponse(BaseModel):
    """Workspace summary for lists and navigation."""

    id: uuid.UUID
    name: str
    description: str | None
    document_scope: list[str]
    document_count: int = 0
    is_archived: bool
    created_by: str
    created_at: datetime
    updated_at: datetime
    member_count: int = 0
    message_count: int = 0
    unread_count: int = 0


class WorkspaceDetailResponse(WorkspaceResponse):
    """Detailed workspace view including full member list and recent messages."""

    members: list[WorkspaceMemberResponse] = []
    scoped_documents: list[dict[str, Any]] = []


class MessageCreateRequest(BaseModel):
    """Payload to send a human message to a workspace."""

    user_name: str = Field(default="Team Member", max_length=100)
    content: str = Field(..., min_length=1, max_length=50000)
    parent_message_id: uuid.UUID | None = None


class MessagePatchRequest(BaseModel):
    """Payload to toggle pin status or add/remove an emoji reaction."""

    is_pinned: bool | None = None
    reaction: str | None = Field(None, max_length=20)
    user_name: str | None = Field(None, max_length=100)


class WorkspaceMessageResponse(BaseModel):
    """Message item in the workspace chat feed."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    user_name: str | None
    message_type: str  # human, ai_response, system
    content: str
    citations: list[dict[str, Any]] = []
    parent_message_id: uuid.UUID | None = None
    is_pinned: bool = False
    reactions: dict[str, list[str]] = {}
    query_log_id: uuid.UUID | None = None
    created_at: datetime


class ScopedQueryRequest(BaseModel):
    """Payload to execute an AI RAG query scoped to the workspace documents."""

    query: str = Field(
        ..., min_length=2, max_length=2000, description="Natural language contract question"
    )
    user_name: str = Field(default="Team Member", max_length=100)
    parent_message_id: uuid.UUID | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class ScopedQueryResponse(BaseModel):
    """Result of an AI RAG query in a collaborative workspace."""

    human_message: WorkspaceMessageResponse
    ai_response: WorkspaceMessageResponse
