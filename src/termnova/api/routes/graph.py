"""Contract Knowledge Graph & Interactive Topology API endpoints."""

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.api.dependencies import get_db, get_settings
from termnova.config import Settings
from termnova.db.models import Document
from termnova.graph.builder import GraphBuilder
from termnova.graph.schemas import (
    CreateRelationshipRequest,
    DocumentRelationshipResponse,
    DocumentStack,
    EntityListResponse,
    GraphData,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/graph", tags=["Knowledge Graph"])


@router.get("/visualize", response_model=GraphData)
async def visualize_graph(
    root: uuid.UUID | None = Query(
        None, description="Optional root document ID to center subgraph"
    ),
    depth: int = Query(3, ge=1, le=10, description="Maximum traversal depth from root"),
    include_entities: bool = Query(
        True, description="Include extracted parties and jurisdictions as graph nodes"
    ),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> GraphData:
    """Fetch D3.js force-directed graph dataset (nodes and relationship edges)."""
    builder = GraphBuilder(session, settings)
    return await builder.get_graph_data(
        root_document_id=root,
        depth=depth,
        include_entities=include_entities,
    )


@router.get("/stack/{doc_id}", response_model=DocumentStack)
async def get_document_stack_view(
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DocumentStack:
    """Fetch hierarchical contract stack tree (e.g. MSA -> SOWs -> Amendments)."""
    builder = GraphBuilder(session, settings)
    try:
        return await builder.get_document_stack(doc_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/documents/{doc_id}/relationships", response_model=list[DocumentRelationshipResponse])
async def get_document_relationships(
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[DocumentRelationshipResponse]:
    """Retrieve all direct cross-contract relationships connected to a document."""
    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Document {doc_id} not found"
        )

    builder = GraphBuilder(session, settings)
    return await builder.get_document_relationships(doc_id)


@router.get("/entities", response_model=EntityListResponse)
async def list_graph_entities(
    entity_type: str | None = Query(
        None, description="Filter by entity type (company, person, jurisdiction)"
    ),
    search: str | None = Query(None, description="Fuzzy search entity name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> EntityListResponse:
    """List extracted legal entities with associated contract counts."""
    builder = GraphBuilder(session, settings)
    return await builder.get_entities(
        entity_type=entity_type,
        search_query=search,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/relationships",
    response_model=DocumentRelationshipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_contract_relationship(
    request: CreateRelationshipRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DocumentRelationshipResponse:
    """Manually link two contracts with a directed relationship."""
    src = await session.get(Document, request.source_document_id)
    tgt = await session.get(Document, request.target_document_id)

    if not src or not tgt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both contract documents could not be found.",
        )

    builder = GraphBuilder(session, settings)
    rel = await builder.create_relationship(
        source_id=request.source_document_id,
        target_id=request.target_document_id,
        rel_type=request.relationship_type,
        metadata=request.metadata,
    )
    await session.commit()

    return DocumentRelationshipResponse(
        id=rel.id,
        source_document_id=rel.source_document_id,
        target_document_id=rel.target_document_id,
        source_filename=src.filename,
        target_filename=tgt.filename,
        relationship_type=rel.relationship_type,
        metadata=rel.metadata_ or {},
    )


@router.delete("/relationships/{rel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contract_relationship(
    rel_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    """Delete a contract relationship edge."""
    builder = GraphBuilder(session, settings)
    deleted = await builder.delete_relationship(rel_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found")
    await session.commit()


@router.post("/auto-detect/{doc_id}")
async def auto_detect_document_graph(
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Trigger AI extraction and relationship detection scan on a document."""
    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Document {doc_id} not found"
        )

    builder = GraphBuilder(session, settings)
    summary = await builder.build_graph_for_document(doc_id)
    await session.commit()
    return summary
