"""REST API Router for Contract Negotiation Tracking, Version Diffing, and Concession Ledgers."""

import uuid
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.api.dependencies import get_db, get_settings
from termnova.comparison.concession_analyzer import ConcessionAnalyzer
from termnova.comparison.negotiation_differ import NegotiationDiffer
from termnova.comparison.version_processor import VersionProcessor
from termnova.config import Settings
from termnova.db.models import (
    Chunk,
    Document,
    NegotiationChange,
    NegotiationTrack,
    NegotiationVersion,
)
from termnova.schemas.negotiation import (
    ConcessionItem,
    ConcessionLedgerResponse,
    NegotiationChangeResponse,
    NegotiationDiffResponse,
    NegotiationSummaryResponse,
    NegotiationTimelineResponse,
    NegotiationTrackCreate,
    NegotiationTrackDetailResponse,
    NegotiationTrackListItem,
    NegotiationTrackUpdate,
    NegotiationVersionResponse,
    RiskTrajectoryPoint,
    RiskTrajectoryResponse,
    TimelineEvent,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/negotiations", tags=["Negotiation Tracker"])

# Shared processors
differ = NegotiationDiffer()
analyzer = ConcessionAnalyzer()
version_processor = VersionProcessor(differ=differ, analyzer=analyzer)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. Negotiation Tracks CRUD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.post(
    "/",
    response_model=NegotiationTrackDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new negotiation track",
)
async def create_negotiation_track(
    payload: NegotiationTrackCreate,
    db: AsyncSession = Depends(get_db),
) -> NegotiationTrackDetailResponse:
    """Create a new contract negotiation track for tracking redline versions."""
    track = NegotiationTrack(
        name=payload.name,
        counterparty=payload.counterparty,
        contract_type=payload.contract_type,
        notes=payload.notes,
        started_by=payload.started_by,
    )
    db.add(track)
    await db.commit()
    await db.refresh(track)

    logger.info("Negotiation track created", track_id=str(track.id), name=track.name)
    return NegotiationTrackDetailResponse(
        id=track.id,
        name=track.name,
        counterparty=track.counterparty,
        contract_type=track.contract_type,
        status=track.status,
        notes=track.notes,
        started_by=track.started_by,
        started_at=track.started_at,
        completed_at=track.completed_at,
        created_at=track.created_at,
        updated_at=track.updated_at,
        versions=[],
        changes=[],
    )


@router.get(
    "/",
    response_model=list[NegotiationTrackListItem],
    summary="List all negotiation tracks with status filters",
)
async def list_negotiation_tracks(
    status_filter: str | None = Query(
        None, alias="status", description="Filter by status: active, agreed, abandoned, paused"
    ),
    counterparty: str | None = Query(None, description="Search by counterparty name"),
    contract_type: str | None = Query(None, description="Filter by contract type"),
    db: AsyncSession = Depends(get_db),
) -> list[NegotiationTrackListItem]:
    """Retrieve all negotiation tracks with calculated version counts and latest risk scores."""
    stmt = select(NegotiationTrack).order_by(NegotiationTrack.updated_at.desc())

    if status_filter and status_filter.lower() != "all":
        stmt = stmt.where(NegotiationTrack.status == status_filter.lower())
    if counterparty:
        stmt = stmt.where(NegotiationTrack.counterparty.ilike(f"%{counterparty.strip()}%"))
    if contract_type and contract_type.lower() != "all":
        stmt = stmt.where(NegotiationTrack.contract_type == contract_type.lower())

    res = await db.execute(stmt)
    tracks = list(res.scalars().all())

    items: list[NegotiationTrackListItem] = []
    for t in tracks:
        # Fetch versions count and latest risk score
        v_res = await db.execute(
            select(NegotiationVersion)
            .where(NegotiationVersion.track_id == t.id)
            .order_by(NegotiationVersion.version_number.desc())
        )
        versions = list(v_res.scalars().all())
        v_count = len(versions)
        latest_risk = versions[0].risk_score if versions else None

        items.append(
            NegotiationTrackListItem(
                id=t.id,
                name=t.name,
                counterparty=t.counterparty,
                contract_type=t.contract_type,
                status=t.status,
                version_count=v_count,
                latest_risk_score=latest_risk,
                started_by=t.started_by,
                started_at=t.started_at,
                updated_at=t.updated_at,
            )
        )

    return items


@router.get(
    "/{track_id}",
    response_model=NegotiationTrackDetailResponse,
    summary="Get full negotiation track details",
)
async def get_negotiation_track(
    track_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> NegotiationTrackDetailResponse:
    """Retrieve full detail for a negotiation track including version list and changes."""
    track_res = await db.execute(select(NegotiationTrack).where(NegotiationTrack.id == track_id))
    track = track_res.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=404, detail="Negotiation track not found.")

    # Load versions
    v_res = await db.execute(
        select(NegotiationVersion)
        .where(NegotiationVersion.track_id == track_id)
        .order_by(NegotiationVersion.version_number.asc())
    )
    versions = list(v_res.scalars().all())

    # Load changes
    c_res = await db.execute(
        select(NegotiationChange)
        .where(NegotiationChange.track_id == track_id)
        .order_by(NegotiationChange.created_at.asc())
    )
    changes = list(c_res.scalars().all())

    v_responses: list[NegotiationVersionResponse] = []
    for v in versions:
        doc_filename = v.document.filename if v.document else "Contract Document"
        v_responses.append(
            NegotiationVersionResponse(
                id=v.id,
                track_id=v.track_id,
                document_id=v.document_id,
                filename=doc_filename,
                version_number=v.version_number,
                source=v.source,
                notes=v.notes,
                risk_score=v.risk_score,
                risk_delta=v.risk_delta,
                uploaded_by=v.uploaded_by,
                uploaded_at=v.uploaded_at,
            )
        )

    c_responses = [
        NegotiationChangeResponse(
            id=c.id,
            track_id=c.track_id,
            from_version=c.from_version,
            to_version=c.to_version,
            clause_category=c.clause_category,
            change_type=c.change_type,
            original_text=c.original_text,
            modified_text=c.modified_text,
            diff_html=c.diff_html,
            risk_impact=c.risk_impact,
            concession_party=c.concession_party,
            concession_summary=c.concession_summary,
            significance=c.significance,
            created_at=c.created_at,
        )
        for c in changes
    ]

    return NegotiationTrackDetailResponse(
        id=track.id,
        name=track.name,
        counterparty=track.counterparty,
        contract_type=track.contract_type,
        status=track.status,
        notes=track.notes,
        started_by=track.started_by,
        started_at=track.started_at,
        completed_at=track.completed_at,
        created_at=track.created_at,
        updated_at=track.updated_at,
        versions=v_responses,
        changes=c_responses,
    )


@router.patch(
    "/{track_id}",
    response_model=NegotiationTrackDetailResponse,
    summary="Update negotiation track status or metadata",
)
async def update_negotiation_track(
    track_id: uuid.UUID,
    payload: NegotiationTrackUpdate,
    db: AsyncSession = Depends(get_db),
) -> NegotiationTrackDetailResponse:
    """Update negotiation status (active, agreed, abandoned, paused) or notes."""
    track_res = await db.execute(select(NegotiationTrack).where(NegotiationTrack.id == track_id))
    track = track_res.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=404, detail="Negotiation track not found.")

    if payload.name is not None:
        track.name = payload.name
    if payload.counterparty is not None:
        track.counterparty = payload.counterparty
    if payload.contract_type is not None:
        track.contract_type = payload.contract_type
    if payload.status is not None:
        track.status = payload.status
        if payload.status in ("agreed", "abandoned") and not track.completed_at:
            track.completed_at = func.now()
    if payload.notes is not None:
        track.notes = payload.notes

    await db.commit()
    await db.refresh(track)
    return await get_negotiation_track(track_id=track_id, db=db)


@router.delete(
    "/{track_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a negotiation track",
)
async def delete_negotiation_track(
    track_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a negotiation track and cascade delete versions and tracked changes."""
    track_res = await db.execute(select(NegotiationTrack).where(NegotiationTrack.id == track_id))
    track = track_res.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=404, detail="Negotiation track not found.")

    await db.delete(track)
    await db.commit()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. Version Management & File Upload
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.post(
    "/{track_id}/versions",
    response_model=NegotiationVersionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload or link a new contract version round",
)
async def upload_negotiation_version(
    track_id: uuid.UUID,
    file: UploadFile | None = File(None),
    document_id: uuid.UUID | None = Form(None),
    source: Literal["internal", "counterparty"] = Form("internal"),
    notes: str | None = Form(None),
    uploaded_by: str = Form("Legal Counsel"),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> NegotiationVersionResponse:
    """
    Add a new version round to a negotiation track.
    Accepts either an uploaded contract file (parsed on the fly) or an existing document UUID.
    """
    # 1. Verify track exists
    track_res = await db.execute(select(NegotiationTrack).where(NegotiationTrack.id == track_id))
    track = track_res.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=404, detail="Negotiation track not found.")

    target_doc_id = document_id

    # 2. If file uploaded, run through ingestion pipeline
    if file and file.filename:
        import re
        from pathlib import Path

        from termnova.pipeline.embedder import EmbeddingService
        from termnova.pipeline.ingestion import IngestionPipeline

        file_bytes = await file.read()
        raw_filename = Path(file.filename).name
        safe_filename = re.sub(r"[^a-zA-Z0-9._-]", "_", raw_filename)
        dest_path = settings.upload_path / f"{uuid.uuid4().hex[:8]}_{safe_filename}"
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(file_bytes)

        embedder = EmbeddingService(settings)
        pipeline = IngestionPipeline(session=db, embedder=embedder, settings=settings)
        doc = await pipeline.ingest_file(dest_path, force_reindex=True)
        target_doc_id = doc.id

    if not target_doc_id:
        raise HTTPException(
            status_code=400,
            detail="Either a contract file or an existing document_id must be provided.",
        )

    # 3. Process new version through VersionProcessor
    try:
        new_version, _ = await version_processor.process_new_version(
            db=db,
            track_id=track_id,
            document_id=target_doc_id,
            source=source,
            uploaded_by=uploaded_by,
            notes=notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    doc_res = await db.execute(select(Document).where(Document.id == target_doc_id))
    doc = doc_res.scalar_one_or_none()
    filename = doc.filename if doc else "Contract Document"

    return NegotiationVersionResponse(
        id=new_version.id,
        track_id=new_version.track_id,
        document_id=new_version.document_id,
        filename=filename,
        version_number=new_version.version_number,
        source=new_version.source,
        notes=new_version.notes,
        risk_score=new_version.risk_score,
        risk_delta=new_version.risk_delta,
        uploaded_by=new_version.uploaded_by,
        uploaded_at=new_version.uploaded_at,
    )


@router.get(
    "/{track_id}/versions",
    response_model=list[NegotiationVersionResponse],
    summary="List all versions in a negotiation track",
)
async def list_negotiation_versions(
    track_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[NegotiationVersionResponse]:
    """Retrieve all versions in sequence with risk scores and source indicators."""
    v_res = await db.execute(
        select(NegotiationVersion)
        .where(NegotiationVersion.track_id == track_id)
        .order_by(NegotiationVersion.version_number.asc())
    )
    versions = list(v_res.scalars().all())

    responses: list[NegotiationVersionResponse] = []
    for v in versions:
        responses.append(
            NegotiationVersionResponse(
                id=v.id,
                track_id=v.track_id,
                document_id=v.document_id,
                filename=v.document.filename if v.document else "Contract Document",
                version_number=v.version_number,
                source=v.source,
                notes=v.notes,
                risk_score=v.risk_score,
                risk_delta=v.risk_delta,
                uploaded_by=v.uploaded_by,
                uploaded_at=v.uploaded_at,
            )
        )
    return responses


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. Diff, Concession Ledger, Timeline & AI Summary
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get(
    "/{track_id}/diff",
    response_model=NegotiationDiffResponse,
    summary="Diff between any two versions in a track",
)
async def get_version_diff(
    track_id: uuid.UUID,
    from_version: int = Query(1, description="Base version number"),
    to_version: int = Query(2, description="Target version number"),
    db: AsyncSession = Depends(get_db),
) -> NegotiationDiffResponse:
    """Compare any two versions (e.g. v1 vs v4) and return clause-by-clause changes and diff HTML."""
    if from_version == to_version:
        raise HTTPException(status_code=400, detail="from_version and to_version must be distinct.")

    # Check if direct consecutive changes already recorded
    if to_version == from_version + 1:
        c_res = await db.execute(
            select(NegotiationChange)
            .where(
                NegotiationChange.track_id == track_id,
                NegotiationChange.from_version == from_version,
                NegotiationChange.to_version == to_version,
            )
            .order_by(NegotiationChange.created_at.asc())
        )
        changes = list(c_res.scalars().all())
        c_responses = [
            NegotiationChangeResponse(
                id=c.id,
                track_id=c.track_id,
                from_version=c.from_version,
                to_version=c.to_version,
                clause_category=c.clause_category,
                change_type=c.change_type,
                original_text=c.original_text,
                modified_text=c.modified_text,
                diff_html=c.diff_html,
                risk_impact=c.risk_impact,
                concession_party=c.concession_party,
                concession_summary=c.concession_summary,
                significance=c.significance,
                created_at=c.created_at,
            )
            for c in changes
        ]
        return NegotiationDiffResponse(
            track_id=track_id,
            from_version=from_version,
            to_version=to_version,
            total_changes=len(c_responses),
            changes=c_responses,
            summary=f"Found {len(c_responses)} clause changes between Version {from_version} and Version {to_version}.",
        )

    # For non-consecutive versions (e.g. v1 vs v4), load chunks and compute on the fly
    v_a_res = await db.execute(
        select(NegotiationVersion).where(
            NegotiationVersion.track_id == track_id,
            NegotiationVersion.version_number == from_version,
        )
    )
    v_a = v_a_res.scalar_one_or_none()

    v_b_res = await db.execute(
        select(NegotiationVersion).where(
            NegotiationVersion.track_id == track_id,
            NegotiationVersion.version_number == to_version,
        )
    )
    v_b = v_b_res.scalar_one_or_none()

    if not v_a or not v_b:
        raise HTTPException(status_code=404, detail="One or both requested versions not found.")

    chunks_a_res = await db.execute(
        select(Chunk).where(Chunk.document_id == v_a.document_id).order_by(Chunk.chunk_index.asc())
    )
    chunks_a = list(chunks_a_res.scalars().all())

    chunks_b_res = await db.execute(
        select(Chunk).where(Chunk.document_id == v_b.document_id).order_by(Chunk.chunk_index.asc())
    )
    chunks_b = list(chunks_b_res.scalars().all())

    clause_changes = differ.diff_versions(chunks_a, chunks_b)
    dynamic_changes: list[NegotiationChangeResponse] = []

    for c in clause_changes:
        concession = analyzer.analyze_concession(
            original_text=c.original_text,
            modified_text=c.modified_text,
            source=v_b.source,
            clause_category=c.clause_category,
        )
        dynamic_changes.append(
            NegotiationChangeResponse(
                id=uuid.uuid4(),
                track_id=track_id,
                from_version=from_version,
                to_version=to_version,
                clause_category=c.clause_category,
                change_type=c.change_type,
                original_text=c.original_text,
                modified_text=c.modified_text,
                diff_html=c.diff_html,
                risk_impact=concession.risk_impact,
                concession_party=concession.concession_party,
                concession_summary=concession.concession_summary,
                significance=concession.significance,
                created_at=func.now(),
            )
        )

    return NegotiationDiffResponse(
        track_id=track_id,
        from_version=from_version,
        to_version=to_version,
        total_changes=len(dynamic_changes),
        changes=dynamic_changes,
        summary=f"Found {len(dynamic_changes)} clause discrepancies between Version {from_version} and Version {to_version}.",
    )


@router.get(
    "/{track_id}/concessions",
    response_model=ConcessionLedgerResponse,
    summary="Get two-column concession ledger",
)
async def get_concession_ledger(
    track_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ConcessionLedgerResponse:
    """Return categorized concession balance sheet ('We Gave' vs 'They Gave') across all rounds."""
    c_res = await db.execute(
        select(NegotiationChange)
        .where(NegotiationChange.track_id == track_id)
        .order_by(NegotiationChange.created_at.asc())
    )
    changes = list(c_res.scalars().all())

    our_concessions: list[ConcessionItem] = []
    their_concessions: list[ConcessionItem] = []
    mutual_trades: list[ConcessionItem] = []
    neutral_changes: list[ConcessionItem] = []

    for c in changes:
        item = ConcessionItem(
            change_id=c.id,
            clause_category=c.clause_category,
            from_version=c.from_version,
            to_version=c.to_version,
            summary=c.concession_summary or f"Modified {c.clause_category} clause",
            significance=c.significance,
            risk_impact=c.risk_impact,
            original_snippet=c.original_text[:120] + "..."
            if len(c.original_text) > 120
            else c.original_text,
            modified_snippet=c.modified_text[:120] + "..."
            if len(c.modified_text) > 120
            else c.modified_text,
        )

        if c.concession_party == "us":
            our_concessions.append(item)
        elif c.concession_party == "counterparty":
            their_concessions.append(item)
        elif c.concession_party == "mutual":
            mutual_trades.append(item)
        else:
            neutral_changes.append(item)

    diff = len(their_concessions) - len(our_concessions)
    if diff >= 2:
        balance: Literal["favorable", "balanced", "unfavorable"] = "favorable"
    elif diff <= -2:
        balance = "unfavorable"
    else:
        balance = "balanced"

    return ConcessionLedgerResponse(
        track_id=track_id,
        our_concessions=our_concessions,
        their_concessions=their_concessions,
        mutual_trades=mutual_trades,
        neutral_changes=neutral_changes,
        balance=balance,
        total_changes=len(changes),
    )


@router.get(
    "/{track_id}/risk-trajectory",
    response_model=RiskTrajectoryResponse,
    summary="Get risk score trajectory data for visualization",
)
async def get_risk_trajectory(
    track_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RiskTrajectoryResponse:
    """Retrieve version-by-version risk scores for plotting SVG trendlines."""
    v_res = await db.execute(
        select(NegotiationVersion)
        .where(NegotiationVersion.track_id == track_id)
        .order_by(NegotiationVersion.version_number.asc())
    )
    versions = list(v_res.scalars().all())

    points: list[RiskTrajectoryPoint] = []
    for v in versions:
        points.append(
            RiskTrajectoryPoint(
                version_number=v.version_number,
                source=v.source,
                risk_score=v.risk_score or 0.25,
                risk_delta=v.risk_delta or 0.0,
                date=v.uploaded_at.strftime("%b %d, %Y"),
                notes=v.notes,
            )
        )

    trend: Literal["improving", "deteriorating", "stable"] = "stable"
    if len(points) >= 2:
        delta = points[-1].risk_score - points[0].risk_score
        if delta <= -0.1:
            trend = "improving"
        elif delta >= 0.1:
            trend = "deteriorating"

    return RiskTrajectoryResponse(
        track_id=track_id,
        versions=points,
        overall_trend=trend,
    )


@router.get(
    "/{track_id}/timeline",
    response_model=NegotiationTimelineResponse,
    summary="Get formatted vertical timeline data",
)
async def get_negotiation_timeline(
    track_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> NegotiationTimelineResponse:
    """Retrieve sequential timeline event cards for UI rendering."""
    track_res = await db.execute(select(NegotiationTrack).where(NegotiationTrack.id == track_id))
    track = track_res.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=404, detail="Negotiation track not found.")

    v_res = await db.execute(
        select(NegotiationVersion)
        .where(NegotiationVersion.track_id == track_id)
        .order_by(NegotiationVersion.version_number.asc())
    )
    versions = list(v_res.scalars().all())

    events: list[TimelineEvent] = []
    for v in versions:
        c_res = await db.execute(
            select(NegotiationChange).where(
                NegotiationChange.track_id == track_id,
                NegotiationChange.to_version == v.version_number,
            )
        )
        changes = list(c_res.scalars().all())
        key_changes = [
            c.concession_summary or f"{c.clause_category.capitalize()} adjusted"
            for c in changes[:3]
        ]

        doc_filename = v.document.filename if v.document else f"v{v.version_number}.pdf"

        events.append(
            TimelineEvent(
                version_number=v.version_number,
                source=v.source,
                date=v.uploaded_at.strftime("%b %d, %Y • %H:%M"),
                uploaded_by=v.uploaded_by,
                document_filename=doc_filename,
                change_count=len(changes),
                risk_score=v.risk_score,
                risk_delta=v.risk_delta,
                notes=v.notes,
                key_changes=key_changes,
            )
        )

    return NegotiationTimelineResponse(
        track_id=track.id,
        track_name=track.name,
        counterparty=track.counterparty,
        status=track.status,
        events=events,
    )


@router.get(
    "/{track_id}/summary",
    response_model=NegotiationSummaryResponse,
    summary="Get AI negotiation executive summary",
)
async def get_negotiation_summary(
    track_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> NegotiationSummaryResponse:
    """Generate executive negotiation overview with key concessions and gap analysis."""
    track_res = await db.execute(select(NegotiationTrack).where(NegotiationTrack.id == track_id))
    track = track_res.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=404, detail="Negotiation track not found.")

    v_res = await db.execute(
        select(NegotiationVersion)
        .where(NegotiationVersion.track_id == track_id)
        .order_by(NegotiationVersion.version_number.asc())
    )
    versions = list(v_res.scalars().all())

    c_res = await db.execute(
        select(NegotiationChange).where(NegotiationChange.track_id == track_id)
    )
    changes = list(c_res.scalars().all())

    return analyzer.generate_negotiation_summary(changes, track, versions)
