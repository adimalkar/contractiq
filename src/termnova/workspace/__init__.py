"""Collaborative Workspace package for multi-user scoped RAG team chat."""

from termnova.workspace.schemas import (
    MessageCreateRequest,
    MessagePatchRequest,
    ScopedQueryRequest,
    ScopedQueryResponse,
    WorkspaceCreateRequest,
    WorkspaceDetailResponse,
    WorkspaceMemberAddRequest,
    WorkspaceMemberResponse,
    WorkspaceMessageResponse,
    WorkspaceResponse,
    WorkspaceUpdateRequest,
)
from termnova.workspace.scoped_query import ScopedRAGExecutor
from termnova.workspace.service import WorkspaceService

__all__ = [
    "WorkspaceService",
    "ScopedRAGExecutor",
    "WorkspaceCreateRequest",
    "WorkspaceUpdateRequest",
    "WorkspaceResponse",
    "WorkspaceDetailResponse",
    "WorkspaceMemberAddRequest",
    "WorkspaceMemberResponse",
    "MessageCreateRequest",
    "MessagePatchRequest",
    "WorkspaceMessageResponse",
    "ScopedQueryRequest",
    "ScopedQueryResponse",
]
