"""Version processing pipeline linking documents, semantic clause diffs, and concession analysis."""

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.comparison.concession_analyzer import ConcessionAnalyzer
from termnova.comparison.negotiation_differ import NegotiationDiffer
from termnova.db.models import (
    Chunk,
    Document,
    NegotiationChange,
    NegotiationTrack,
    NegotiationVersion,
)

logger = structlog.get_logger(__name__)


class VersionProcessor:
    """Orchestrates multi-round contract version ingestion, diffing, and concession tracking."""

    def __init__(
        self,
        differ: NegotiationDiffer | None = None,
        analyzer: ConcessionAnalyzer | None = None,
    ):
        self.differ = differ or NegotiationDiffer()
        self.analyzer = analyzer or ConcessionAnalyzer()

    async def process_new_version(
        self,
        db: AsyncSession,
        track_id: uuid.UUID,
        document_id: uuid.UUID,
        source: str = "internal",
        uploaded_by: str = "Legal Counsel",
        notes: str | None = None,
    ) -> tuple[NegotiationVersion, list[NegotiationChange]]:
        """
        Process a newly added version in a negotiation track.
        Auto-increments version number and diffs against the immediate preceding version if N > 1.
        """
        # 1. Fetch track and existing versions
        track_res = await db.execute(
            select(NegotiationTrack).where(NegotiationTrack.id == track_id)
        )
        track = track_res.scalar_one_or_none()
        if not track:
            raise ValueError(f"Negotiation track '{track_id}' not found.")

        versions_res = await db.execute(
            select(NegotiationVersion)
            .where(NegotiationVersion.track_id == track_id)
            .order_by(NegotiationVersion.version_number.asc())
        )
        existing_versions = list(versions_res.scalars().all())

        new_version_num = len(existing_versions) + 1

        # 2. Check Document validity
        doc_res = await db.execute(select(Document).where(Document.id == document_id))
        doc = doc_res.scalar_one_or_none()
        if not doc:
            raise ValueError(f"Document '{document_id}' not found.")

        # 3. If First Version (v1) -> Base version, no preceding diff
        if new_version_num == 1:
            base_risk = 0.25
            v1 = NegotiationVersion(
                track_id=track_id,
                document_id=document_id,
                version_number=1,
                source=source,
                notes=notes,
                risk_score=base_risk,
                risk_delta=0.0,
                uploaded_by=uploaded_by,
            )
            db.add(v1)
            await db.commit()
            await db.refresh(v1)
            logger.info(
                "Initial negotiation version v1 created",
                track_id=str(track_id),
                doc_id=str(document_id),
            )
            return v1, []

        # 4. If N > 1 -> Diff against previous version (vN-1)
        prev_version = existing_versions[-1]

        # Load chunks from previous version and current version
        prev_chunks_res = await db.execute(
            select(Chunk)
            .where(Chunk.document_id == prev_version.document_id)
            .order_by(Chunk.chunk_index.asc())
        )
        prev_chunks = list(prev_chunks_res.scalars().all())

        curr_chunks_res = await db.execute(
            select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.chunk_index.asc())
        )
        curr_chunks = list(curr_chunks_res.scalars().all())

        # Run semantic diff
        clause_changes = self.differ.diff_versions(prev_chunks, curr_chunks)

        # Classify concessions and risk impacts
        persisted_changes: list[NegotiationChange] = []
        risk_increases = 0
        risk_decreases = 0

        for change in clause_changes:
            concession_res = self.analyzer.analyze_concession(
                original_text=change.original_text,
                modified_text=change.modified_text,
                source=source,
                clause_category=change.clause_category,
            )

            if concession_res.risk_impact == "increased_risk":
                risk_increases += 1
            elif concession_res.risk_impact == "decreased_risk":
                risk_decreases += 1

            n_change = NegotiationChange(
                track_id=track_id,
                from_version=prev_version.version_number,
                to_version=new_version_num,
                clause_category=change.clause_category,
                change_type=change.change_type,
                original_text=change.original_text,
                modified_text=change.modified_text,
                diff_html=change.diff_html,
                risk_impact=concession_res.risk_impact,
                concession_party=concession_res.concession_party,
                concession_summary=concession_res.concession_summary,
                significance=concession_res.significance,
            )
            db.add(n_change)
            persisted_changes.append(n_change)

        # Compute risk score and delta
        risk_delta = round((risk_increases * 0.08) - (risk_decreases * 0.08), 2)
        prev_score = prev_version.risk_score if prev_version.risk_score is not None else 0.3
        new_risk_score = round(max(0.05, min(0.95, prev_score + risk_delta)), 2)

        new_version = NegotiationVersion(
            track_id=track_id,
            document_id=document_id,
            version_number=new_version_num,
            source=source,
            notes=notes,
            risk_score=new_risk_score,
            risk_delta=risk_delta,
            uploaded_by=uploaded_by,
        )
        db.add(new_version)
        await db.commit()
        await db.refresh(new_version)

        logger.info(
            "Negotiation version created with diffs",
            track_id=str(track_id),
            version=new_version_num,
            changes_count=len(persisted_changes),
            risk_score=new_risk_score,
            risk_delta=risk_delta,
        )
        return new_version, persisted_changes
