# Feature Plan 2: Collaborative RAG Workspace (Shared Team Chat)

## What We're Building

A **shared team workspace** where multiple users can collaboratively query contracts using the RAG engine, see each other's questions and AI answers in real-time, pin important findings, and build shared understanding. Think of it as a Slack channel where the AI is a permanent team member that answers legal questions grounded in your documents.

### Key Capabilities
- **Workspace creation**: Scope a workspace to specific documents (e.g., "Q3 Vendor Review" scoped to 5 vendor contracts)
- **Shared RAG queries**: When Alice asks a question, Bob sees the question AND the AI answer appear in real-time
- **Threaded discussions**: Reply to any message (human or AI) in a thread
- **Pinned findings**: Pin key discoveries so the team doesn't lose critical insights
- **@mentions**: Tag team members to draw attention to specific findings
- **Reactions**: Quick emoji reactions (👍, ⚠️, ✅) for lightweight feedback

## Why It Matters

Contract review is inherently collaborative. Legal, procurement, finance, and ops teams all analyze the same documents but currently do so in isolation. One person asks the AI a question, gets an answer, then copy-pastes it into Slack or email — losing the source citations and context. This feature makes the AI a shared team resource with a persistent memory of all questions asked.

---

## Architecture & Approach

### Real-Time Architecture
```
User A (Browser)  ──WebSocket──→  FastAPI WS Handler  ←──WebSocket──  User B (Browser)
       │                                │                                    │
       │  POST /workspaces/{id}/query   │                                    │
       └────────────────────────────────→│                                    │
                                        │  1. Save human message to DB       │
                                        │  2. Broadcast "user_message" event │
                                        │──────────────────────────────────→ │
                                        │  3. Run RAG query (scoped docs)    │
                                        │  4. Save AI response to DB         │
                                        │  5. Broadcast "ai_response" event  │
                                        │──────────────────────────────────→ │
```

### Key Design Decisions
- **WebSocket channels per workspace**: Extend existing `WebSocketManager` to support channel-based broadcasting (workspace_id as channel key)
- **Document scoping**: Workspace has a `document_scope: ARRAY(UUID)` — RAG retriever is filtered to only search chunks from these documents
- **Hybrid REST + WebSocket**: REST for CRUD operations (create workspace, load history), WebSocket for real-time message push
- **No external dependencies**: Uses existing WebSocket, RAG engine, and PostgreSQL — no Redis pub/sub or message queue needed for MVP

---

## Sub-Phase 1: Database Models

#### [NEW] `src/termnova/db/models/workspace.py`

```python
"""SQLAlchemy models for collaborative workspaces — rooms, members, messages."""

class Workspace(Base):
    """Shared collaborative workspace scoped to specific documents."""

    __tablename__ = "workspaces"

    id: UUID (PK, default=uuid4)
    organization_id: FK → organizations.id (CASCADE, indexed)
    name: str(500)  # "Q3 Vendor Review", "Acme MSA Negotiation"
    description: str | None (Text)
    document_scope: ARRAY(UUID)  # Which document IDs are in scope for RAG
    is_archived: bool (default=False)
    created_by: FK → users.id
    created_at, updated_at

    # Relationships
    members → WorkspaceMember (cascade)
    messages → WorkspaceMessage (cascade, order_by created_at)


class WorkspaceMember(Base):
    """Users who have access to a workspace."""

    __tablename__ = "workspace_members"

    workspace_id: FK → workspaces.id (PK, CASCADE)
    user_id: FK → users.id (PK, CASCADE)
    role: str(20)  # "owner", "editor", "viewer"
    last_read_at: datetime | None  # Track unread messages
    joined_at: datetime (server_default=now())


class WorkspaceMessage(Base):
    """Messages in workspace — human messages, AI responses, and system events."""

    __tablename__ = "workspace_messages"

    id: UUID (PK, default=uuid4)
    workspace_id: FK → workspaces.id (CASCADE, indexed)
    user_id: FK → users.id (nullable — None for AI responses)
    message_type: str(20)  # "human", "ai_response", "system"
    content: Text
    citations: JSONB (default=[])  # Same format as QueryLog.citations
    parent_message_id: FK → workspace_messages.id (nullable, for threading)
    is_pinned: bool (default=False)
    reactions: JSONB (default={})
    # Format: {"👍": ["user_id_1", "user_id_2"], "⚠️": ["user_id_3"]}
    query_log_id: FK → query_log.id (nullable)
    # Links AI response to the underlying QueryLog for audit trail
    created_at: datetime (server_default=now())
```

### Alembic Migration
#### [NEW] `src/termnova/db/alembic/versions/XXX_collaborative_workspaces.py`
- Creates `workspaces`, `workspace_members`, `workspace_messages`
- Indexes: `workspace_id` on messages, `(workspace_id, user_id)` on members
- Foreign key from `workspace_messages.query_log_id` → `query_log.id`

### Tests for Sub-Phase 1
```
tests/unit/test_workspace_models.py
  - test_create_workspace_with_document_scope
  - test_add_member_with_role
  - test_create_human_message
  - test_create_ai_response_message_with_citations
  - test_threaded_message_links_to_parent
  - test_pin_message_updates_is_pinned
  - test_add_reaction_to_message
```

---

## Sub-Phase 2: Workspace Service & Scoped RAG

### 2A. Workspace Service

#### [NEW] `src/termnova/workspace/service.py`

```python
"""Business logic for workspace CRUD and member management."""

class WorkspaceService:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID):
        self.session = session
        self.org_id = org_id

    async def create_workspace(
        self,
        name: str,
        document_ids: list[uuid.UUID],
        created_by: uuid.UUID,
        description: str | None = None,
    ) -> Workspace:
        """
        Create workspace and add creator as owner.
        Validates that all document_ids belong to this org.
        """

    async def add_member(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str = "editor",
        added_by: uuid.UUID,
    ) -> WorkspaceMember:
        """
        Add user to workspace. Only owner/admin can add members.
        Raises 403 if added_by lacks permission.
        """

    async def remove_member(self, workspace_id: uuid.UUID, user_id: uuid.UUID, removed_by: uuid.UUID):
        """Remove user. Owner cannot be removed. Only owner/admin can remove others."""

    async def get_user_workspaces(self, user_id: uuid.UUID) -> list[Workspace]:
        """List all workspaces where this user is a member."""

    async def verify_membership(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> WorkspaceMember:
        """Check user is a member. Raises 403 if not."""

    async def update_document_scope(
        self,
        workspace_id: uuid.UUID,
        document_ids: list[uuid.UUID],
        updated_by: uuid.UUID,
    ) -> Workspace:
        """Update which documents are in scope. Only owner/editor can update."""
```

### 2B. Scoped RAG Query

#### [NEW] `src/termnova/workspace/scoped_query.py`

```python
"""Execute RAG queries scoped to a workspace's document set."""


class ScopedRAGExecutor:
    """Runs RAG queries filtered to workspace document scope."""

    def __init__(self, session: AsyncSession, embedder: EmbeddingService, settings: Settings):
        self.session = session
        self.embedder = embedder
        self.settings = settings

    async def execute_workspace_query(
        self,
        workspace: Workspace,
        query_text: str,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID | None = None,
    ) -> tuple[WorkspaceMessage, QueryLog]:
        """
        1. Filter chunk retrieval to only chunks from workspace.document_scope
        2. Run normal RAG pipeline (retrieve → grade → generate)
        3. Save both QueryLog (for audit) and WorkspaceMessage (for chat)
        4. Return both for API response and WebSocket broadcast
        """
```

**Key implementation detail — document scoping:**
```python
# In retriever, add WHERE clause:
chunks = await session.execute(
    select(Chunk).where(Chunk.document_id.in_(workspace.document_scope)).order_by(...)
)
```

This is the **critical differentiator** — the RAG query only searches documents in the workspace's scope, so different teams analyzing different deals get relevant answers from their own document set.

### Tests for Sub-Phase 2
```
tests/unit/test_workspace_service.py
  - test_create_workspace_adds_creator_as_owner
  - test_create_workspace_validates_document_ownership
  - test_add_member_requires_owner_permission
  - test_remove_member_prevents_owner_removal
  - test_verify_membership_raises_403_for_non_member
  - test_update_document_scope_validates_org_ownership

tests/unit/test_scoped_rag.py
  - test_scoped_query_only_retrieves_from_workspace_documents
  - test_scoped_query_ignores_documents_outside_scope
  - test_scoped_query_creates_query_log_and_workspace_message
  - test_scoped_query_with_empty_scope_returns_no_results
```

---

## Sub-Phase 3: API Endpoints & WebSocket Channels

### 3A. REST API

#### [NEW] `src/termnova/api/routes/workspaces.py`

```python
router = APIRouter(prefix="/api/v1/workspaces", tags=["Collaborative Workspaces"])

# Workspace CRUD
POST   /
    → Body: {name, description?, document_ids}
    → Creates workspace, adds current user as owner
    → Response: WorkspaceResponse

GET    /
    → Lists current user's workspaces with unread message counts
    → Response: [WorkspaceListItem]

GET    /{workspace_id}
    → Workspace details + members + document scope
    → Response: WorkspaceDetailResponse

PATCH  /{workspace_id}
    → Body: {name?, description?, document_ids?}
    → Update workspace metadata or document scope

DELETE /{workspace_id}
    → Archives workspace (soft delete)

# Members
POST   /{workspace_id}/members
    → Body: {user_id, role}
    → Invite user to workspace

DELETE /{workspace_id}/members/{user_id}
    → Remove member

# Messages
GET    /{workspace_id}/messages
    → Query params: limit=50, before={message_id}, thread={parent_id}
    → Paginated message history (newest first)
    → Response: [WorkspaceMessageResponse]

POST   /{workspace_id}/messages
    → Body: {content, parent_message_id?}
    → Send human message to workspace
    → Broadcasts via WebSocket to all connected members

PATCH  /{workspace_id}/messages/{message_id}
    → Body: {is_pinned?, reaction?}
    → Pin/unpin message or add/remove reaction

# Scoped RAG Query
POST   /{workspace_id}/query
    → Body: {query, parent_message_id?}
    → Executes RAG scoped to workspace documents
    → Saves human message + AI response
    → Broadcasts both via WebSocket
    → Response: {human_message, ai_response}

# Pinned Findings
GET    /{workspace_id}/pinned
    → All pinned messages for quick reference
```

### 3B. WebSocket Channel Extension

#### [MODIFY] `src/termnova/api/ws_manager.py`

Extend the existing `WebSocketManager` to support channel-based broadcasting:

```python
class WebSocketManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.channel_members: dict[str, set[str]] = {}
        # channel_id (workspace_id) → set of client_ids

    async def join_channel(self, client_id: str, channel_id: str) -> None:
        """Subscribe client to a workspace channel."""
        if channel_id not in self.channel_members:
            self.channel_members[channel_id] = set()
        self.channel_members[channel_id].add(client_id)

    async def leave_channel(self, client_id: str, channel_id: str) -> None:
        """Unsubscribe client from channel."""
        if channel_id in self.channel_members:
            self.channel_members[channel_id].discard(client_id)

    async def broadcast_to_channel(self, channel_id: str, message: dict[str, Any]) -> None:
        """Send message to all clients subscribed to a channel."""
        members = self.channel_members.get(channel_id, set())
        payload = json.dumps(message)
        dead_clients = []
        for cid in members:
            ws = self.active_connections.get(cid)
            if ws:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead_clients.append(cid)
        for cid in dead_clients:
            self.disconnect(cid)
```

**WebSocket message types:**
```json
// Incoming from client:
{"action": "join_workspace", "workspace_id": "..."}
{"action": "leave_workspace", "workspace_id": "..."}
{"action": "typing", "workspace_id": "..."}

// Outgoing to clients:
{"event": "workspace_message", "data": {message_object}}
{"event": "workspace_ai_thinking", "data": {"workspace_id": "...", "query": "..."}}
{"event": "workspace_ai_response", "data": {message_object_with_citations}}
{"event": "user_typing", "data": {"workspace_id": "...", "user_name": "Alice"}}
{"event": "message_pinned", "data": {"message_id": "...", "pinned_by": "..."}}
{"event": "reaction_added", "data": {"message_id": "...", "reaction": "👍", "user": "..."}}
```

### Tests for Sub-Phase 3
```
tests/integration/test_workspace_api.py
  - test_create_workspace_with_documents
  - test_list_user_workspaces_shows_only_member_workspaces
  - test_get_workspace_detail_includes_members
  - test_add_member_to_workspace
  - test_remove_member_from_workspace
  - test_send_message_to_workspace
  - test_load_message_history_paginated
  - test_pin_message
  - test_add_reaction
  - test_workspace_query_scoped_to_documents
  - test_workspace_query_returns_citations
  - test_workspace_isolation_across_orgs

tests/integration/test_workspace_websocket.py
  - test_websocket_join_workspace_channel
  - test_websocket_receives_broadcast_on_new_message
  - test_websocket_receives_ai_response_broadcast
  - test_websocket_typing_indicator
  - test_websocket_disconnect_cleans_up_channel
```

---

## Sub-Phase 4: Frontend UI

#### [NEW] `src/termnova/static/js/workspace.js`

**Key UI components to implement:**

```javascript
// 1. Workspace List (Left Sidebar)
function renderWorkspaceList(workspaces) { ... }
// Shows workspace name, unread badge, document count
// Click → loads that workspace's messages

// 2. Message Feed (Center Panel)
function renderMessageFeed(messages) { ... }
// Chat-style feed: human messages left-aligned, AI responses right-aligned
// AI responses have citation chips that expand on click
// Pinned messages have a 📌 indicator
// Threaded replies shown as indented sub-messages

// 3. Message Input
function renderMessageInput(workspaceId) { ... }
// Textarea with "Ask AI" button (triggers /query) and "Send" button (human message)
// @mention autocomplete when typing "@"
// Shift+Enter for newline, Enter to send

// 4. WebSocket Connection
function connectWorkspaceWebSocket(workspaceId) { ... }
// Connects to WS, joins workspace channel
// Handles incoming events: new messages, typing indicators, reactions
// Auto-reconnect on disconnect

// 5. Pinned Findings Sidebar (Right Panel)
function renderPinnedFindings(pinnedMessages) { ... }
// Collapsible panel showing all pinned messages
// Quick-jump: click a pinned finding → scrolls to it in the feed

// 6. Document Scope Badge Bar
function renderDocumentScope(documents) { ... }
// Horizontal bar showing which documents are in scope
// Click a badge → opens document detail
// "+ Add Document" button to expand scope
```

#### [MODIFY] `src/termnova/static/index.html`
- Add "Workspaces" navigation tab
- Add workspace layout: 3-column (sidebar | feed | pinned)

#### [NEW] `src/termnova/static/css/workspace.css`
- Chat bubble styles (human vs AI, with avatar placeholders)
- Citation chip styles (expandable inline references)
- Typing indicator animation
- Pinned message highlight
- Unread badge counter
- Dark mode compatible with existing obsidian slate palette

### Tests for Sub-Phase 4
```
tests/e2e/test_workspace_ui.py
  - test_workspace_page_loads
  - test_create_workspace_from_ui
  - test_send_message_appears_in_feed
  - test_ai_query_shows_thinking_then_response
  - test_pin_message_shows_in_sidebar
```

---

## Verification Checklist

- [ ] `workspaces` table created via migration
- [ ] `workspace_members` table with composite PK
- [ ] `workspace_messages` table with threading support
- [ ] Create workspace → adds creator as owner
- [ ] Add/remove members with role validation
- [ ] Send human message → stored in DB → broadcast to WS channel
- [ ] RAG query → scoped to workspace documents only
- [ ] AI response appears for all connected workspace members
- [ ] Pin/unpin messages persisted and broadcast
- [ ] Reactions stored in JSONB and broadcast
- [ ] Message history paginated (newest-first with cursor)
- [ ] Threaded replies link to parent message
- [ ] Workspace isolation: Org A members can't access Org B workspaces
- [ ] Member isolation: Non-members can't access workspace messages
- [ ] WebSocket cleanup on disconnect
- [ ] `ruff check` and `ruff format --check` pass
- [ ] All unit and integration tests pass
