"""Pydantic schemas for contract knowledge graph, entities, and D3.js visualization."""

import uuid
from typing import Any

from pydantic import BaseModel, Field


class ExtractedParty(BaseModel):
    """Party extracted from contract preamble or signature block."""

    name: str = Field(description="Name of the company or individual")
    role: str = Field(
        default="counterparty",
        description="Legal role: party_a, party_b, guarantor, beneficiary, counterparty, governing_jurisdiction",
    )
    entity_type: str = Field(
        default="company",
        description="Entity category: company, person, jurisdiction, product, department",
    )


class ExtractedRelationship(BaseModel):
    """Cross-contract relationship detected in text."""

    target_title: str = Field(description="Referenced contract title, number, or filename")
    relationship_type: str = Field(
        default="references",
        description="Relationship type: amends, supersedes, references, parent_sow, renewal_of, addendum_to",
    )
    context_snippet: str | None = Field(
        default=None, description="Excerpt describing the relationship"
    )


class ExtractedEntities(BaseModel):
    """Complete structured metadata and entities extracted from a contract."""

    contract_type: str = Field(
        default="other",
        description="Classified type: msa, sow, nda, amendment, lease, employment, vendor, other",
    )
    title: str | None = Field(default=None, description="Formal agreement title")
    parties: list[ExtractedParty] = Field(default_factory=list)
    governing_law: str | None = Field(default=None, description="Governing law state/jurisdiction")
    effective_date: str | None = Field(
        default=None, description="Effective date (ISO or natural string)"
    )
    expiration_date: str | None = Field(default=None, description="Expiration or termination date")
    renewal_terms: str | None = Field(
        default=None, description="Auto-renewal clause summary or notice window"
    )
    total_value_usd: float | None = Field(
        default=None, description="Contract fee or ceiling amount in USD"
    )
    referenced_contracts: list[ExtractedRelationship] = Field(default_factory=list)


class GraphNode(BaseModel):
    """Node in D3.js force-directed graph (contract or entity)."""

    id: str = Field(description="Unique node identifier (UUID string)")
    label: str = Field(description="Display label (filename, agreement title, or entity name)")
    node_type: str = Field(
        description="Node category: msa, sow, nda, amendment, lease, vendor, entity, company, person, jurisdiction"
    )
    document_id: str | None = Field(
        default=None, description="Underlying document UUID if document node"
    )
    risk_score: float | None = Field(
        default=None, description="Composite risk or compliance score (0.0 - 1.0)"
    )
    status: str | None = Field(default=None, description="Document processing status")
    file_type: str | None = Field(default=None, description="Original file extension (pdf, docx)")
    page_count: int | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """Directed or bidirectional edge between two nodes in D3.js graph."""

    id: str = Field(description="Edge ID")
    source: str = Field(description="Source node ID")
    target: str = Field(description="Target node ID")
    relationship_type: str = Field(
        description="Relationship label: amends, supersedes, references, party_to, etc."
    )
    label: str = Field(description="Human-readable label for link")
    weight: float = Field(default=1.0, description="Link strength / weight")


class GraphData(BaseModel):
    """D3.js-compatible graph payload."""

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    entity_nodes: list[GraphNode] = Field(default_factory=list)
    total_contracts: int = 0
    total_entities: int = 0
    total_relationships: int = 0


class DocumentStackItem(BaseModel):
    """Hierarchical card item in Document Stack Tree view."""

    document_id: uuid.UUID
    filename: str
    title: str | None = None
    contract_type: str
    risk_score: float | None = None
    effective_date: str | None = None
    expiration_date: str | None = None
    parties: list[str] = Field(default_factory=list)
    children: list["DocumentStackItem"] = Field(default_factory=list)


class DocumentStack(BaseModel):
    """Root container for hierarchical document stack view."""

    root_document_id: uuid.UUID
    root_filename: str
    stack: DocumentStackItem
    total_descendants: int = 0
    total_value_usd: float | None = None


class CreateRelationshipRequest(BaseModel):
    """Payload to manually link two contracts."""

    source_document_id: uuid.UUID
    target_document_id: uuid.UUID
    relationship_type: str = Field(
        default="references",
        description="amends, supersedes, references, parent_sow, renewal_of, addendum_to, annex_to",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class EntityItemResponse(BaseModel):
    """Single entity summary with document count."""

    id: uuid.UUID
    name: str
    normalized_name: str
    entity_type: str
    aliases: list[str]
    document_count: int = 0
    created_at: str


class EntityListResponse(BaseModel):
    """Paginated list of entities."""

    entities: list[EntityItemResponse] = Field(default_factory=list)
    total: int = 0


class DocumentRelationshipResponse(BaseModel):
    """Relationship details for document inspection."""

    id: uuid.UUID
    source_document_id: uuid.UUID
    target_document_id: uuid.UUID
    source_filename: str
    target_filename: str
    relationship_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)
