"""RAGAS-inspired evaluation metrics for quantitative RAG benchmark assessment."""

import re

import numpy as np
import structlog

from contractiq.pipeline.embedder import EmbeddingService

logger = structlog.get_logger(__name__)


def compute_faithfulness(
    answer: str,
    retrieved_contexts: list[str],
) -> float:
    """Measure factual consistency of the generated answer against retrieved context.

    Returns score between 0.0 and 1.0.
    """
    if not answer:
        return 0.0
    if "insufficient information" in answer.lower():
        return 1.0
    if not retrieved_contexts:
        return 0.0

    # Extract sentences/claims
    clean_text = re.sub(r"\[Source\s+\d+\]", "", answer)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean_text) if len(s.strip()) > 15]

    if not sentences:
        return 1.0

    combined_context = " ".join(retrieved_contexts).lower()
    context_words = set(re.findall(r"\b\w{3,}\b", combined_context))

    supported_count = 0
    for s in sentences:
        s_words = set(re.findall(r"\b\w{3,}\b", s.lower()))
        if not s_words:
            supported_count += 1
            continue

        overlap = len(s_words.intersection(context_words)) / len(s_words)
        if overlap >= 0.35:
            supported_count += 1

    return round(supported_count / len(sentences), 3)


def compute_answer_relevance(
    query: str,
    answer: str,
    embedder: EmbeddingService | None = None,
) -> float:
    """Evaluate semantic alignment between question and generated answer.

    Returns score between 0.0 and 1.0.
    """
    if not query or not answer:
        return 0.0

    # Negative question handling: correctly stating insufficient info is 100% relevant
    if "insufficient information" in answer.lower() and "none" in query.lower():
        return 1.0

    query_tokens = set(re.findall(r"\b\w{3,}\b", query.lower()))
    answer_tokens = set(re.findall(r"\b\w{3,}\b", answer.lower()))

    if not query_tokens:
        return 1.0

    overlap = len(query_tokens.intersection(answer_tokens)) / len(query_tokens)

    # Embedding cosine similarity if embedder available
    cos_sim = 0.5
    if embedder is not None:
        try:
            q_vec = np.array(embedder.embed_query(query), dtype=np.float32)
            a_vec = np.array(embedder.embed_query(answer[:500]), dtype=np.float32)
            q_norm = np.linalg.norm(q_vec) or 1.0
            a_norm = np.linalg.norm(a_vec) or 1.0
            cos_sim = float(np.dot(q_vec, a_vec) / (q_norm * a_norm))
            cos_sim = max(0.0, min(1.0, (cos_sim + 1.0) / 2.0))
        except Exception:
            cos_sim = 0.5

    relevance = (0.5 * overlap) + (0.5 * cos_sim)
    return round(min(1.0, max(0.0, relevance)), 3)


def compute_context_precision(
    ground_truth_contexts: list[str],
    retrieved_contexts: list[str],
) -> float:
    """Evaluate whether relevant chunks are prioritized at the top of retrieval results (Precision@K)."""
    if not ground_truth_contexts:
        return 1.0  # For negative queries with no ground truth context

    if not retrieved_contexts:
        return 0.0

    hits: list[int] = []
    for _idx, r_ctx in enumerate(retrieved_contexts):
        r_text = r_ctx.lower()
        is_hit = any(
            gt.lower() in r_text
            or len(set(gt.lower().split()).intersection(set(r_text.split()))) >= 2
            for gt in ground_truth_contexts
        )
        hits.append(1 if is_hit else 0)

    # Calculate Average Precision (AP)
    num_hits = sum(hits)
    if num_hits == 0:
        return 0.0

    precisions = []
    cumulative_hits = 0
    for k, hit in enumerate(hits):
        if hit == 1:
            cumulative_hits += 1
            precisions.append(cumulative_hits / (k + 1))

    return round(sum(precisions) / len(precisions), 3) if precisions else 0.0


def compute_context_recall(
    ground_truth_contexts: list[str],
    retrieved_contexts: list[str],
) -> float:
    """Measure the fraction of ground truth context facts recalled by retrieved chunks."""
    if not ground_truth_contexts:
        return 1.0

    if not retrieved_contexts:
        return 0.0

    combined_retrieval = " ".join(retrieved_contexts).lower()
    covered = 0

    for gt in ground_truth_contexts:
        gt_terms = set(re.findall(r"\b\w{3,}\b", gt.lower()))
        if not gt_terms:
            covered += 1
            continue

        retrieval_terms = set(re.findall(r"\b\w{3,}\b", combined_retrieval))
        overlap = len(gt_terms.intersection(retrieval_terms)) / len(gt_terms)
        if overlap >= 0.40:
            covered += 1

    return round(covered / len(ground_truth_contexts), 3)
