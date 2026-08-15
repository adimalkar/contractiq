"""Cross-Encoder secondary re-ranking stage for high-precision two-stage retrieval."""

from typing import Any

import numpy as np
import structlog

from contractiq.config import Settings, get_settings
from contractiq.rag import RetrievedChunk

logger = structlog.get_logger(__name__)


class CrossEncoderReranker:
    """Two-stage retrieval re-ranker scoring query-document pairs with cross-attention."""

    def __init__(
        self,
        model_name: str | None = None,
        settings: Settings | None = None,
    ):
        self.settings = settings or get_settings()
        self.model_name = model_name or self.settings.RERANKER_MODEL
        self._model: Any = None
        self._is_loaded = False

    def _load_model(self) -> Any:
        """Lazy load sentence_transformers CrossEncoder."""
        if self._is_loaded:
            return self._model

        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)
            self._is_loaded = True
            logger.info("CrossEncoder re-ranker model loaded", model=self.model_name)
        except Exception as e:
            logger.warning(
                "Could not load CrossEncoder model, fallback to score ranking", error=str(e)
            )
            self._model = None
            self._is_loaded = True

        return self._model

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """Score (query, chunk) pairs with CrossEncoder and reorder descending."""
        if not chunks:
            return []

        k = top_k or self.settings.RERANKER_TOP_K
        model = self._load_model()

        if model is None:
            # Deterministic heuristic re-ranking fallback
            return chunks[:k]

        try:
            pairs = [[query, c.content] for c in chunks]
            scores = model.predict(pairs)

            # Sigmoid normalization for scores
            def sigmoid(x: float) -> float:
                return float(1 / (1 + np.exp(-x)))

            scored_pairs = []
            for chunk, raw_score in zip(chunks, scores, strict=False):
                norm_score = sigmoid(float(raw_score))
                chunk.fused_score = round(norm_score, 4)
                scored_pairs.append(chunk)

            scored_pairs.sort(key=lambda c: c.fused_score, reverse=True)
            logger.info("CrossEncoder re-ranking complete", count=len(scored_pairs), top_k=k)
            return scored_pairs[:k]

        except Exception as e:
            logger.warning(
                "CrossEncoder prediction failed, returning original chunks", error=str(e)
            )
            return chunks[:k]

    def rerank_with_diversity(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int | None = None,
        diversity_weight: float = 0.3,
    ) -> list[RetrievedChunk]:
        """Maximal Marginal Relevance (MMR) re-ranking preventing redundant chunk clustering."""
        if not chunks:
            return []

        k = top_k or self.settings.RERANKER_TOP_K
        ranked = self.rerank(query, chunks, top_k=len(chunks))

        selected: list[RetrievedChunk] = []
        candidates = list(ranked)

        while candidates and len(selected) < k:
            if not selected:
                selected.append(candidates.pop(0))
                continue

            best_idx = 0
            best_mmr_score = -999.0

            for idx, cand in enumerate(candidates):
                rel_score = cand.fused_score

                # Compute maximum similarity with already selected chunks (simple word overlap penalty)
                cand_words = set(cand.content.lower().split())
                max_sim = 0.0
                for sel in selected:
                    sel_words = set(sel.content.lower().split())
                    sim = len(cand_words.intersection(sel_words)) / max(1, len(cand_words))
                    if sim > max_sim:
                        max_sim = sim

                mmr_score = (1.0 - diversity_weight) * rel_score - (diversity_weight * max_sim)
                if mmr_score > best_mmr_score:
                    best_mmr_score = mmr_score
                    best_idx = idx

            selected.append(candidates.pop(best_idx))

        return selected
