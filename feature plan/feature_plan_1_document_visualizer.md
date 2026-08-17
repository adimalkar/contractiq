# Feature Plan 1: Document Visualizer & Contract Knowledge Graph

## What We're Building

An interactive visual map of how contracts relate to each other within an organization. Instead of contracts being flat, isolated files, users see an interactive **force-directed graph** where:

- **Nodes** = contracts (colored by type: MSA, SOW, NDA, Amendment, Lease)
- **Edges** = relationships (amends, supersedes, references, parent SOW, renewal)
- **Entity nodes** = parties, jurisdictions, products that appear across contracts
- Clicking any node opens a side panel with contract summary, risk score, key dates

Additionally, a **Document Stack View** provides a hierarchical card layout (MSA at top → SOWs nested below → amendments inline) for users who prefer structured lists over graphs.

## Why It Matters

Legal teams manage webs of related contracts. An MSA might have 5 SOWs, 3 amendments, and a renewal. Today these relationships live only in people's heads. When someone leaves the team, institutional knowledge disappears. This feature externalizes that knowledge into a queryable, visual structure.

---

## Architecture & Approach

### Data Flow
```
Document Upload → Ingestion Pipeline → Entity Extraction (LLM)
                                          ↓
                                   entity_nodes table
                                   document_entities table
                                   document_relationships table
                                          ↓
                              /api/v1/graph/visualize → D3.js Frontend
```

### Key Design Decisions
- **No Neo4j**: Use PostgreSQL adjacency list tables. Keeps infrastructure simple (no new service). Contract graphs are small enough (hundreds, not millions of nodes) that PostgreSQL handles this efficiently.
- **D3.js via CDN**: No npm/build step. Load D3.js v7 from CDN in the HTML template. Keeps the existing static file serving architecture.
- **LLM-powered entity extraction**: Use structured output / function calling to extract parties, dates, and cross-references from contract text during ingestion.

---

## Sub-Phase 1: Database Models & Entity Extraction

### 1A. Database Models

#### [NEW] `src/termnova/db/models/graph.py`

```python
"""SQLAlchemy models for contract knowledge graph — entities, relationships, and cross-references."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from termnova.db.models import Base


class EntityNode(Base):
    """Named entity extracted from contracts (companies, people, jurisdictions)."""

    __tablename__ = "entity_nodes"
    __table_args__ = (
        UniqueConstraint("organization_id", "normalized_name", "entity_type", name="uq_org_entity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Values: "company", "person", "jurisdiction", "product", "department"
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list, server_default="{}", nullable=False
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document_links: Mapped[list["DocumentEntity"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )


class DocumentEntity(Base):
    """Junction: which entities appear in which documents, with what role."""

    __tablename__ = "document_entities"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entity_nodes.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    # Values: "party_a", "party_b", "guarantor", "beneficiary", "governing_jurisdiction"
    first_mention_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    entity: Mapped["EntityNode"] = relationship(back_populates="document_links")


class DocumentRelationship(Base):
    """Directed edge between two documents."""

    __tablename__ = "document_relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_document_id", "target_document_id", "relationship_type", name="uq_doc_rel"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Values: "amends", "supersedes", "references", "parent_sow", "renewal_of", "addendum_to"
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, server_default="{}"
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # FK to users.id once Phase 1 auth is done; nullable for AI-detected relationships
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### 1B. Entity Extraction Service

#### [NEW] `src/termnova/graph/entity_extractor.py`

**Approach:** After document chunking, pass the first ~3000 tokens of the contract through the LLM with a structured output schema to extract entities and metadata.

```python
"""Extract named entities and contract metadata using LLM structured output."""


# Key functions:
async def extract_entities(document_text: str, llm_provider: str) -> ExtractedEntities:
    """
    Uses LLM function calling to extract:
    - parties: list of {name, role, entity_type}
    - governing_law: jurisdiction string
    - referenced_contracts: list of {title, relationship_type}
    - contract_type: enum string
    - key_dates: {effective, expiration, renewal_deadline}
    """


async def normalize_entity(name: str, existing_entities: list[EntityNode]) -> EntityNode | None:
    """
    Fuzzy match against existing entities to avoid duplicates.
    Uses Levenshtein distance + token overlap.
    "Acme Corporation" should match "Acme Corp" and "ACME Inc."
    Returns existing entity if match found, None if new.
    """


async def persist_entities(
    session: AsyncSession,
    document_id: uuid.UUID,
    org_id: uuid.UUID,
    extracted: ExtractedEntities,
) -> list[EntityNode]:
    """Upsert entities into entity_nodes and create document_entities links."""
```

**LLM Prompt Strategy:**
```
You are a legal document analyst. Extract the following from this contract:
1. All parties (company names, people, with their roles)
2. The governing law jurisdiction
3. Any contracts referenced by name or number
4. The contract type (MSA, NDA, SOW, Amendment, Lease, Employment, Other)
5. Key dates (effective date, expiration, renewal deadline)

Return as JSON matching this schema: {schema}
```

### 1C. Alembic Migration

#### [NEW] `src/termnova/db/alembic/versions/XXX_knowledge_graph_tables.py`
- Creates `entity_nodes`, `document_entities`, `document_relationships`
- Adds indexes on `organization_id`, `normalized_name`, `entity_type`
- Adds composite unique constraints

### Tests for Sub-Phase 1
```
tests/unit/test_entity_extractor.py
  - test_extract_parties_from_msa_text
  - test_extract_governing_law
  - test_normalize_entity_fuzzy_match
  - test_normalize_entity_exact_match
  - test_normalize_entity_no_match_creates_new
  - test_persist_entities_creates_document_links
```

---

## Sub-Phase 2: Graph Builder & Relationship Detection

### 2A. Graph Builder

#### [NEW] `src/termnova/graph/builder.py`

```python
"""Build and maintain the contract knowledge graph from extracted entities."""


class GraphBuilder:
    """Constructs and queries the contract relationship graph."""

    def __init__(self, session: AsyncSession, org_id: uuid.UUID):
        self.session = session
        self.org_id = org_id

    async def build_graph_for_document(self, document_id: uuid.UUID) -> GraphSummary:
        """
        Full pipeline for a single document:
        1. Extract entities via LLM
        2. Normalize against existing entities (deduplicate)
        3. Detect relationships to other documents
        4. Persist all nodes and edges
        Returns summary of what was created/linked.
        """

    async def detect_relationships(self, document_id: uuid.UUID) -> list[DocumentRelationship]:
        """
        AI-powered relationship detection:
        1. Check extracted text for references like "pursuant to MSA dated..."
        2. Match referenced contract titles against existing documents (fuzzy)
        3. Detect amendment patterns (filename: "Amendment_3_to_MSA.pdf")
        4. Detect SOW patterns (mentions parent MSA number)
        Returns list of detected relationships for user confirmation.
        """

    async def get_graph_data(
        self,
        root_document_id: uuid.UUID | None = None,
        depth: int = 3,
    ) -> GraphData:
        """
        Return D3.js-compatible graph data.
        If root_document_id given, returns subgraph within N hops.
        If None, returns full org graph.

        Returns:
            GraphData with:
            - nodes: [{id, label, type, risk_score, status, metadata}]
            - edges: [{source, target, relationship_type, label}]
            - entities: [{id, name, type, document_count}]
        """

    async def get_document_stack(self, root_document_id: uuid.UUID) -> DocumentStack:
        """
        Return hierarchical tree structure for Document Stack View.
        MSA at root → SOWs as children → Amendments as sub-children.
        """
```

### 2B. Pydantic Schemas

#### [NEW] `src/termnova/graph/schemas.py`

```python
class GraphNode(BaseModel):
    id: uuid.UUID
    label: str  # filename or contract title
    node_type: str  # "msa", "sow", "nda", "amendment", "entity"
    risk_score: float | None = None
    status: str | None = None  # processing_status from Document
    metadata: dict[str, Any] = {}


class GraphEdge(BaseModel):
    source: uuid.UUID
    target: uuid.UUID
    relationship_type: str
    label: str  # human-readable: "amends", "references"


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    entity_nodes: list[GraphNode]  # Separate list for entity overlay


class DocumentStackItem(BaseModel):
    document_id: uuid.UUID
    filename: str
    contract_type: str
    risk_score: float | None
    effective_date: str | None
    children: list["DocumentStackItem"] = []


class DocumentStack(BaseModel):
    root: DocumentStackItem
    total_documents: int
    total_value: float | None
```

### Tests for Sub-Phase 2
```
tests/unit/test_graph_builder.py
  - test_build_graph_creates_entities_and_links
  - test_detect_relationships_finds_amendment_reference
  - test_detect_relationships_matches_parent_msa
  - test_get_graph_data_returns_d3_format
  - test_get_graph_data_respects_depth_limit
  - test_get_document_stack_builds_hierarchy
  - test_get_document_stack_single_document_no_children
```

---

## Sub-Phase 3: API Endpoints

#### [NEW] `src/termnova/api/routes/graph.py`

```python
router = APIRouter(prefix="/api/v1/graph", tags=["Knowledge Graph"])

# Document relationships
GET  /documents/{doc_id}/relationships
    → Returns all documents linked to this one (direct + transitive up to depth=N)
    → Response: {relationships: [{document, relationship_type, direction}]}

GET  /visualize
    → Query params: root={doc_id} (optional), depth=3, include_entities=true
    → Returns D3.js-compatible {nodes: [...], edges: [...]}
    → If no root, returns full org graph

GET  /stack/{doc_id}
    → Returns hierarchical DocumentStack for tree/card view

# Entity management
GET  /entities
    → Query params: type={company|person|jurisdiction}, search={text}
    → Returns paginated entity list with document counts

GET  /entities/{entity_id}/documents
    → All contracts involving this entity

# Relationship management
POST /relationships
    → Body: {source_id, target_id, relationship_type, metadata}
    → Manually link two documents

DELETE /relationships/{rel_id}
    → Remove a relationship

POST /auto-detect/{doc_id}
    → Trigger AI-powered relationship detection
    → Returns detected relationships (user can confirm/reject)
```

### Tests for Sub-Phase 3
```
tests/integration/test_graph_api.py
  - test_get_relationships_for_document
  - test_visualize_returns_d3_format
  - test_visualize_with_root_filters_subgraph
  - test_stack_view_returns_hierarchy
  - test_entities_list_with_type_filter
  - test_entities_search_fuzzy
  - test_create_relationship_manual
  - test_delete_relationship
  - test_auto_detect_triggers_extraction
  - test_graph_respects_org_isolation (tenant A can't see tenant B's graph)
```

---

## Sub-Phase 4: Frontend — D3.js Visualization

#### [NEW] `src/termnova/static/js/graph.js`

**Implementation approach:**
1. Load D3.js v7 from CDN: `<script src="https://d3js.org/d3.v7.min.js"></script>`
2. Fetch graph data from `/api/v1/graph/visualize`
3. Render force-directed simulation with:
   - **Node colors by type**: MSA=#3b82f6, SOW=#22c55e, NDA=#a855f7, Amendment=#f59e0b, Lease=#ef4444
   - **Node size**: proportional to contract value or linked document count
   - **Edge labels**: relationship type text along the edge
   - **Click handler**: clicking a node opens a side panel with document details
   - **Drag**: nodes are draggable to rearrange layout
   - **Zoom/Pan**: d3.zoom() for navigation
   - **Filter panel**: checkboxes to show/hide document types, date range slider

```javascript
// Key functions to implement:

function initializeGraph(containerId) { ... }
// Sets up SVG, zoom behavior, force simulation

function renderGraph(graphData) { ... }
// Takes {nodes, edges} from API, creates D3 force layout

function updateFilters(filters) { ... }
// Re-renders graph with filtered nodes/edges

function openNodeDetail(nodeId) { ... }
// Fetches document details, shows in side panel

function renderDocumentStack(stackData, containerId) { ... }
// Alternative view: nested card layout from /api/v1/graph/stack/{id}

function exportGraphAsSVG() { ... }
// Downloads current graph view as SVG file
```

#### [MODIFY] `src/termnova/static/index.html`
- Add new navigation tab: "Document Map"
- Add `<div id="graph-container">` with D3 canvas
- Add `<div id="stack-container">` for Document Stack View
- Toggle button: "Graph View" / "Stack View"

#### [NEW] `src/termnova/static/css/graph.css`
- Styles for graph nodes, edges, labels, side panel
- Dark mode compatible with existing obsidian slate palette
- Responsive: graph fills available space

### Tests for Sub-Phase 4
```
tests/e2e/test_graph_ui.py (browser-based)
  - test_graph_page_loads_d3_library
  - test_graph_renders_nodes_for_uploaded_documents
  - test_graph_click_node_opens_detail_panel
  - test_graph_filter_by_document_type
  - test_stack_view_toggle_renders_hierarchy
```

---

## Integration with Existing Pipeline

#### [MODIFY] `src/termnova/pipeline/ingestion.py`
After successful chunking and embedding, trigger entity extraction:
```python
# At end of ingest_file():
from termnova.graph.builder import GraphBuilder

graph_builder = GraphBuilder(session, org_id)
await graph_builder.build_graph_for_document(document.id)
```

This makes graph building **automatic** — every uploaded document is immediately added to the knowledge graph.

---

## Verification Checklist

- [ ] `entity_nodes` table created via Alembic migration
- [ ] `document_entities` table created with composite PK
- [ ] `document_relationships` table created with unique constraint
- [ ] Entity extraction returns structured data from sample contract
- [ ] Entity normalization deduplicates "Acme Corp" / "Acme Corporation"
- [ ] Graph builder creates nodes and edges after document upload
- [ ] `/api/v1/graph/visualize` returns valid D3.js JSON
- [ ] `/api/v1/graph/stack/{id}` returns hierarchical tree
- [ ] D3.js graph renders in browser with nodes and edges
- [ ] Clicking a node shows document details in side panel
- [ ] Filter panel hides/shows document types
- [ ] Graph respects organization isolation (multi-tenant)
- [ ] `ruff check` and `ruff format --check` pass
- [ ] All unit and integration tests pass
