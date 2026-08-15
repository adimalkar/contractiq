"""Comparison report generator aggregating clause alignments and calculating document similarity."""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from contractiq.comparison import ComparisonReport
from contractiq.comparison.aligner import ClauseAligner
from contractiq.comparison.differ import ClauseDiffer
from contractiq.db.repository import ContractRepository
from contractiq.pipeline.embedder import EmbeddingService

logger = structlog.get_logger(__name__)


class ComparisonReportGenerator:
    """Orchestrates document loading, clause alignment, diffing, and report assembly."""

    def __init__(self, session: AsyncSession, embedder: EmbeddingService | None = None):
        self.session = session
        self.repository = ContractRepository(session)
        self.aligner = ClauseAligner(embedder=embedder)

    async def compare_documents(
        self,
        document_a_id: uuid.UUID,
        document_b_id: uuid.UUID,
    ) -> ComparisonReport:
        """Generate comparison report between two documents by primary key."""
        doc_a = await self.repository.get_document(document_a_id)
        doc_b = await self.repository.get_document(document_b_id)

        if not doc_a or not doc_b:
            raise ValueError("One or both target documents not found in repository.")

        chunks_a = await self.repository.get_chunks_by_document(document_a_id)
        chunks_b = await self.repository.get_chunks_by_document(document_b_id)

        alignments = self.aligner.align_clauses(chunks_a, chunks_b)
        key_differences = ClauseDiffer.extract_key_differences(alignments)

        identical_count = sum(1 for a in alignments if a.diff_type == "identical")
        modified_count = sum(1 for a in alignments if a.diff_type == "modified")
        added_count = sum(1 for a in alignments if a.diff_type == "added")
        removed_count = sum(1 for a in alignments if a.diff_type == "removed")
        matched_count = identical_count + modified_count

        total_a = len(chunks_a)
        total_b = len(chunks_b)
        max_total = max(1, max(total_a, total_b))

        # Overall similarity score
        overall_sim = (identical_count * 1.0 + modified_count * 0.7) / max_total
        overall_sim = round(max(0.0, min(1.0, overall_sim)), 3)

        report = ComparisonReport(
            comparison_id=uuid.uuid4(),
            document_a_id=document_a_id,
            document_b_id=document_b_id,
            document_a_name=doc_a.filename,
            document_b_name=doc_b.filename,
            total_clauses_a=total_a,
            total_clauses_b=total_b,
            matched_clauses=matched_count,
            added_clauses=added_count,
            removed_clauses=removed_count,
            modified_clauses=modified_count,
            identical_clauses=identical_count,
            overall_similarity=overall_sim,
            alignments=alignments,
            key_differences=key_differences,
        )

        logger.info(
            "Comparison report assembled",
            doc_a=doc_a.filename,
            doc_b=doc_b.filename,
            overall_sim=overall_sim,
            alignments=len(alignments),
        )

        return report
