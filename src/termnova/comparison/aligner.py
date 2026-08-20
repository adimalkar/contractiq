"""Semantic clause aligner pairing relevant sections between two contracts."""

import numpy as np
import structlog

from termnova.comparison import ClauseAlignment
from termnova.comparison.differ import ClauseDiffer
from termnova.db.models import Chunk
from termnova.pipeline.embedder import EmbeddingService

logger = structlog.get_logger(__name__)


class ClauseAligner:
    """Matches corresponding clauses across two contracts using embedding similarity."""

    def __init__(
        self,
        embedder: EmbeddingService | None = None,
        similarity_threshold: float = 0.65,
    ):
        self.embedder = embedder
        self.similarity_threshold = similarity_threshold

    def align_clauses(
        self,
        chunks_a: list[Chunk],
        chunks_b: list[Chunk],
    ) -> list[ClauseAlignment]:
        """Align chunks between Doc A and Doc B, classifying similarity and generating diffs."""
        if not chunks_a and not chunks_b:
            return []

        # If one document has no chunks
        if not chunks_a:
            return [
                ClauseAlignment(
                    section_a=None,
                    section_b=c.section_header,
                    text_a="",
                    text_b=c.content,
                    similarity_score=0.0,
                    diff_type="added",
                    diff_html=ClauseDiffer.generate_html_diff("", c.content),
                )
                for c in chunks_b
            ]

        if not chunks_b:
            return [
                ClauseAlignment(
                    section_a=c.section_header,
                    section_b=None,
                    text_a=c.content,
                    text_b="",
                    similarity_score=0.0,
                    diff_type="removed",
                    diff_html=ClauseDiffer.generate_html_diff(c.content, ""),
                )
                for c in chunks_a
            ]

        # Calculate cosine similarities between chunks
        def get_vec(c: Chunk) -> np.ndarray:
            if c.embedding:
                vec = np.array(c.embedding, dtype=np.float32)
                norm = np.linalg.norm(vec) or 1.0
                return vec / norm
            # Deterministic hash fallback if chunk embedding is None
            if self.embedder:
                v = np.array(self.embedder.embed_query(c.content), dtype=np.float32)
                return v / (np.linalg.norm(v) or 1.0)

            import hashlib

            vec = np.zeros(256, dtype=np.float32)
            words = c.content.lower().split()
            for w in words:
                idx = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16) % 256
                vec[idx] += 1.0
            norm = float(np.linalg.norm(vec)) or 1.0
            return vec / norm

        vecs_a = [get_vec(c) for c in chunks_a]
        vecs_b = [get_vec(c) for c in chunks_b]

        # Similarity matrix: len(chunks_a) x len(chunks_b)
        sim_matrix = np.zeros((len(chunks_a), len(chunks_b)), dtype=np.float32)
        for i, va in enumerate(vecs_a):
            for j, vb in enumerate(vecs_b):
                sim_matrix[i, j] = float(np.dot(va, vb))

        matched_b_indices = set()
        alignments: list[ClauseAlignment] = []

        # Match each chunk in A with its highest similarity candidate in B
        for i, chunk_a in enumerate(chunks_a):
            best_j = int(np.argmax(sim_matrix[i]))
            best_score = float(sim_matrix[i, best_j])

            if best_score >= self.similarity_threshold:
                chunk_b = chunks_b[best_j]
                matched_b_indices.add(best_j)

                if best_score >= 0.98 and chunk_a.content.strip() == chunk_b.content.strip():
                    diff_type = "identical"
                else:
                    diff_type = "modified"

                alignments.append(
                    ClauseAlignment(
                        section_a=chunk_a.section_header,
                        section_b=chunk_b.section_header,
                        text_a=chunk_a.content,
                        text_b=chunk_b.content,
                        similarity_score=round(best_score, 3),
                        diff_type=diff_type,
                        diff_html=ClauseDiffer.generate_html_diff(chunk_a.content, chunk_b.content),
                    )
                )
            else:
                # No good match in B -> removed clause
                alignments.append(
                    ClauseAlignment(
                        section_a=chunk_a.section_header,
                        section_b=None,
                        text_a=chunk_a.content,
                        text_b="",
                        similarity_score=0.0,
                        diff_type="removed",
                        diff_html=ClauseDiffer.generate_html_diff(chunk_a.content, ""),
                    )
                )

        # Unmatched chunks in B -> newly added clauses
        for j, chunk_b in enumerate(chunks_b):
            if j not in matched_b_indices:
                alignments.append(
                    ClauseAlignment(
                        section_a=None,
                        section_b=chunk_b.section_header,
                        text_a="",
                        text_b=chunk_b.content,
                        similarity_score=0.0,
                        diff_type="added",
                        diff_html=ClauseDiffer.generate_html_diff("", chunk_b.content),
                    )
                )

        logger.info(
            "Clause alignment completed",
            doc_a_chunks=len(chunks_a),
            doc_b_chunks=len(chunks_b),
            total_alignments=len(alignments),
        )
        return alignments
