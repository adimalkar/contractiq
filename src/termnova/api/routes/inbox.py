"""Contract Inbox and Triage REST API endpoints."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.api.dependencies import get_db, get_settings_dep
from termnova.config import Settings
from termnova.db.models import Chunk, Document
from termnova.triage.orchestrator import TriageOrchestrator
from termnova.triage.schemas import (
    AcknowledgeContractRequest,
    AssignContractRequest,
    BulkArchiveRequest,
    BulkAssignRequest,
    CompleteContractRequest,
    InboxListResponse,
    InboxStatsResponse,
    ModifyTagsRequest,
    TriageResultResponse,
)
from termnova.triage.service import InboxService

router = APIRouter(prefix="/api/v1/inbox", tags=["Contract Inbox"])


@router.get("/", response_model=InboxListResponse)
async def list_inbox_items(
    status_filter: str | None = Query(
        None,
        alias="status",
        description="Filter by status (unreviewed, in_progress, assigned, completed, archived, all)",
    ),
    contract_type: str | None = Query(
        None, alias="type", description="Filter by contract type (nda, msa, sow, etc.)"
    ),
    tag: str | None = Query(None, description="Filter by auto tag (e.g. high-value, urgent)"),
    assignee: str | None = Query(None, description="Filter by assignee or 'unassigned'"),
    search: str | None = Query(None, description="Search keyword across contract filenames"),
    sort_by: str = Query(
        "urgency_desc",
        alias="sort",
        description="Sort order (urgency_desc, urgency_asc, date_desc, date_asc)",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> InboxListResponse:
    """Retrieve paginated and filterable contract inbox items."""
    service = InboxService(db)
    items, total_count, has_more = await service.get_inbox_items(
        status=status_filter,
        contract_type=contract_type,
        tag=tag,
        assignee=assignee,
        search=search,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )
    return InboxListResponse(
        items=items,
        total_count=total_count,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


@router.get("/stats", response_model=InboxStatsResponse)
async def get_inbox_stats(db: AsyncSession = Depends(get_db)) -> InboxStatsResponse:
    """Retrieve operational KPIs and category distributions for the inbox dashboard."""
    service = InboxService(db)
    return await service.get_inbox_stats()


@router.get("/{doc_id}", response_model=TriageResultResponse)
async def get_document_triage(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> TriageResultResponse:
    """Retrieve triage details for a specific contract document."""
    service = InboxService(db)
    triage = await service.get_triage_by_document(doc_id)
    if not triage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Triage result for document {doc_id} not found",
        )
    return TriageResultResponse.model_validate(triage)


@router.post("/{doc_id}/assign", response_model=TriageResultResponse)
async def assign_contract(
    doc_id: uuid.UUID,
    payload: AssignContractRequest,
    db: AsyncSession = Depends(get_db),
) -> TriageResultResponse:
    """Assign a contract to a reviewer and mark status as assigned."""
    service = InboxService(db)
    triage = await service.assign_contract(doc_id, assigned_to=payload.assigned_to)
    if not triage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found in triage inbox",
        )
    return TriageResultResponse.model_validate(triage)


@router.post("/{doc_id}/acknowledge", response_model=TriageResultResponse)
async def acknowledge_contract(
    doc_id: uuid.UUID,
    payload: AcknowledgeContractRequest,
    db: AsyncSession = Depends(get_db),
) -> TriageResultResponse:
    """Acknowledge receipt/review of a contract and move status to in_progress."""
    service = InboxService(db)
    triage = await service.acknowledge_contract(doc_id, acknowledged_by=payload.acknowledged_by)
    if not triage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found in triage inbox",
        )
    return TriageResultResponse.model_validate(triage)


@router.post("/{doc_id}/complete", response_model=TriageResultResponse)
async def complete_contract(
    doc_id: uuid.UUID,
    payload: CompleteContractRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> TriageResultResponse:
    """Mark contract review as completed."""
    service = InboxService(db)
    triage = await service.complete_contract(doc_id)
    if not triage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found in triage inbox",
        )
    return TriageResultResponse.model_validate(triage)


@router.post("/{doc_id}/archive", response_model=TriageResultResponse)
async def archive_contract(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> TriageResultResponse:
    """Archive a contract from active inbox view."""
    service = InboxService(db)
    triage = await service.archive_contract(doc_id)
    if not triage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found in triage inbox",
        )
    return TriageResultResponse.model_validate(triage)


@router.patch("/{doc_id}/tags", response_model=TriageResultResponse)
async def modify_contract_tags(
    doc_id: uuid.UUID,
    payload: ModifyTagsRequest,
    db: AsyncSession = Depends(get_db),
) -> TriageResultResponse:
    """Add or remove custom tags on a triaged contract."""
    service = InboxService(db)
    triage = await service.modify_tags(
        doc_id, add_tags=payload.add_tags, remove_tags=payload.remove_tags
    )
    if not triage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found in triage inbox",
        )
    return TriageResultResponse.model_validate(triage)


@router.post("/bulk-assign")
async def bulk_assign_contracts(
    payload: BulkAssignRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Bulk assign multiple contracts to a reviewer."""
    service = InboxService(db)
    count = await service.bulk_assign(payload.document_ids, assigned_to=payload.assigned_to)
    return {"updated_count": count, "assigned_to": payload.assigned_to}


@router.post("/bulk-archive")
async def bulk_archive_contracts(
    payload: BulkArchiveRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Bulk archive multiple contracts."""
    service = InboxService(db)
    count = await service.bulk_archive(payload.document_ids)
    return {"archived_count": count}


@router.post("/{doc_id}/retriage", response_model=TriageResultResponse)
async def retriage_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> TriageResultResponse:
    """Re-run triage classification and urgency scoring for a document."""
    # Fetch Document
    doc_stmt = select(Document).where(Document.id == doc_id)
    doc = (await db.execute(doc_stmt)).scalars().first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found",
        )

    # Fetch first few chunk texts
    chunk_stmt = (
        select(Chunk).where(Chunk.document_id == doc_id).order_by(Chunk.chunk_index.asc()).limit(10)
    )
    chunks = list((await db.execute(chunk_stmt)).scalars().all())
    full_text = " ".join([c.content for c in chunks]) if chunks else doc.filename

    orchestrator = TriageOrchestrator(session=db, settings=settings)
    triage = await orchestrator.triage_document(
        document_id=doc.id,
        document_text=full_text,
        filename=doc.filename,
    )
    return TriageResultResponse.model_validate(triage)
