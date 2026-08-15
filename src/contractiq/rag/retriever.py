"""Hybrid retriever combining dense pgvector semantic similarity with sparse BM25 keyword matching via Reciprocal Rank Fusion."""

import re
import uuid
from datetime import UTC, datetime
from typing import Any

import numpy as np
import structlog
from rank_bm25 import BM25Okapi
from sqlalchemy.ext.asyncio import AsyncSession

from contractiq.config import Settings, get_settings
from contractiq.db.models import Chunk
from contractiq.db.repository import ContractRepository
from contractiq.pipeline.embedder import EmbeddingService
from contractiq.rag import RetrievedChunk

logger = structlog.get_logger(__name__)


def _simple_tokenize(text: str) -> list[str]:
    """Fast, lightweight lowercase alphanumeric tokenizer."""
    return re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())


class HybridRetriever:
    """Combines vector search and BM25 using Reciprocal Rank Fusion."""

    def __init__(
        self,
        session: AsyncSession,
        embedder: EmbeddingService | None = None,
        settings: Settings | None = None,
    ):
        self.session = session
        self.settings = settings or get_settings()
        self.repository = ContractRepository(session)
        self.embedder = embedder or EmbeddingService(self.settings)

        # In-memory BM25 index cache
        self._bm25_index: BM25Okapi | None = None
        self._bm25_chunks: list[tuple[Chunk, str]] = []
        self._last_index_time: datetime | None = None

    def invalidate_bm25_cache(self) -> None:
        """Clear BM25 cache so next query reloads from database."""
        self._bm25_index = None
        self._bm25_chunks = []
        self._last_index_time = None

    async def _ensure_bm25_index(self) -> tuple[BM25Okapi | None, list[tuple[Chunk, str]]]:
        """Build or retrieve cached BM25 index over all current document chunks."""
        if self._bm25_index is not None and self._bm25_chunks:
            return self._bm25_index, self._bm25_chunks

        all_chunks = await self.repository.get_all_chunks()
        if not all_chunks:
            return None, []

        corpus = [_simple_tokenize(chunk.content) for chunk, _ in all_chunks]
        self._bm25_index = BM25Okapi(
            corpus,
            k1=self.settings.BM25_K1,
            b=self.settings.BM25_B,
        )
        self._bm25_chunks = all_chunks
        self._last_index_time = datetime.now(UTC)
        return self._bm25_index, self._bm25_chunks

    async def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        threshold: float | None = None,
    ) -> list[RetrievedChunk]:
        """Execute hybrid search and merge rankings with Reciprocal Rank Fusion."""
        k = top_k or self.settings.TOP_K_RETRIEVAL
        thresh = threshold if threshold is not None else self.settings.RELEVANCE_THRESHOLD
        rrf_k = self.settings.RRF_K

        # 1. Semantic Vector Search
        query_embedding = self.embedder.embed_query(query)
        vector_matches = await self.repository.vector_search(
            query_embedding,
            top_k=k * 2,
            threshold=-1.0,
        )

        # Build semantic ranking dictionary: chunk_id -> (rank_1_indexed, score, chunk, filename)
        semantic_ranks: dict[uuid.UUID, dict[str, Any]] = {}
        for rank_idx, (chunk, filename, score) in enumerate(vector_matches):
            norm_score = max(0.0, min(1.0, (score + 1.0) / 2.0))
            semantic_ranks[chunk.id] = {
                "rank": rank_idx + 1,
                "score": norm_score,
                "chunk": chunk,
                "filename": filename,
            }

        # 2. BM25 Keyword Search
        bm25_index, bm25_chunks = await self._ensure_bm25_index()
        bm25_ranks: dict[uuid.UUID, dict[str, Any]] = {}

        if bm25_index is not None and bm25_chunks:
            tokenized_query = _simple_tokenize(query)
            if tokenized_query:
                raw_bm25_scores = bm25_index.get_scores(tokenized_query)
                max_bm25 = (
                    float(np.max(raw_bm25_scores))
                    if len(raw_bm25_scores) > 0 and np.max(raw_bm25_scores) > 0
                    else 1.0
                )

                # Sort chunks by BM25 score descending
                scored_bm25 = sorted(
                    zip(bm25_chunks, raw_bm25_scores, strict=False),
                    key=lambda x: x[1],
                    reverse=True,
                )

                for rank_idx, ((chunk, filename), raw_score) in enumerate(scored_bm25[: k * 2]):
                    if raw_score > 0:
                        bm25_ranks[chunk.id] = {
                            "rank": rank_idx + 1,
                            "score": float(raw_score / max_bm25),
                            "chunk": chunk,
                            "filename": filename,
                        }

        # 3. Reciprocal Rank Fusion (RRF)
        all_chunk_ids = set(semantic_ranks.keys()).union(set(bm25_ranks.keys()))
        if not all_chunk_ids:
            logger.info("No chunks matched hybrid retrieval", query=query)
            return []

        fused_candidates: list[RetrievedChunk] = []

        w_semantic = 0.6
        w_bm25 = 0.4

        for cid in all_chunk_ids:
            sem_info = semantic_ranks.get(cid)
            bm25_info = bm25_ranks.get(cid)

            chunk = sem_info["chunk"] if sem_info else bm25_info["chunk"]
            filename = sem_info["filename"] if sem_info else bm25_info["filename"]

            sem_score = sem_info["score"] if sem_info else 0.0
            sem_rank = sem_info["rank"] if sem_info else 999

            bm25_score = bm25_info["score"] if bm25_info else 0.0
            bm25_rank = bm25_info["rank"] if bm25_info else 999

            # RRF calculation
            rrf_sem_component = w_semantic / (rrf_k + sem_rank) if sem_info else 0.0
            rrf_bm25_component = w_bm25 / (rrf_k + bm25_rank) if bm25_info else 0.0
            raw_fused_score = rrf_sem_component + rrf_bm25_component

            # Normalize RRF score to 0.0 - 1.0 range
            max_possible_rrf = (w_semantic / (rrf_k + 1)) + (w_bm25 / (rrf_k + 1))
            normalized_fused_score = min(1.0, raw_fused_score / max_possible_rrf)

            fused_candidates.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                    page_number=chunk.page_number,
                    section_header=chunk.section_header,
                    document_filename=filename,
                    semantic_score=round(sem_score, 4),
                    keyword_score=round(bm25_score, 4),
                    fused_score=round(normalized_fused_score, 4),
                )
            )

        # Sort by fused score descending
        fused_candidates.sort(key=lambda c: c.fused_score, reverse=True)

        # Apply threshold filtering (ensure at least top 1 is preserved if candidates exist)
        filtered = [c for c in fused_candidates if c.fused_score >= thresh]
        if not filtered and fused_candidates:
            filtered = fused_candidates[:1]

        final_results = filtered[:k]
        logger.info(
            "Hybrid retrieval completed",
            query=query,
            candidates=len(fused_candidates),
            selected=len(final_results),
        )
        return final_results
