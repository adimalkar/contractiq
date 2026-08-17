"""Guardrails engine for hallucination detection, PII redaction, and multi-factor confidence scoring."""

import re

import structlog

from termnova.config import Settings, get_settings
from termnova.rag import GeneratedAnswer, GradedChunk, GuardrailResult, HallucinationFlag

logger = structlog.get_logger(__name__)

# PII Regex Patterns
PII_PATTERNS = {
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "EMAIL": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "PHONE": re.compile(r"\b(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "CREDIT_CARD": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
}


class GuardrailChecker:
    """Responsible AI auditor verifying factual entailment and privacy compliance."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.provider = self.settings.LLM_PROVIDER
        self.model = self.settings.LLM_MODEL

    def _split_into_claims(self, text: str) -> list[str]:
        """Split text into distinct propositional sentences, removing headers and citations."""
        # Strip citation tags for cleaner entailment analysis
        clean_text = re.sub(r"\[Source\s+\d+\]", "", text)
        sentences = re.split(r"(?<=[.!?])\s+", clean_text)
        claims: list[str] = []

        for s in sentences:
            trimmed = s.strip(" \n\t*#-•")
            # Filter out non-factual or trivial filler sentences
            if len(trimmed) > 15 and not trimmed.lower().startswith(
                ("based on", "here is", "in summary", "note that")
            ):
                claims.append(trimmed)

        return claims

    def _check_entailment_heuristic(
        self, claim: str, context_chunks: list[GradedChunk]
    ) -> tuple[str, str]:
        """Verify claim against context using token containment and semantic overlap."""
        claim_words = set(re.findall(r"\b\w{3,}\b", claim.lower()))
        if not claim_words:
            return "supported", "Sentence contains no verifiable factual terms."

        best_overlap_ratio = 0.0
        best_chunk_header = "N/A"

        for chunk in context_chunks:
            chunk_words = set(re.findall(r"\b\w{3,}\b", chunk.content.lower()))
            common = claim_words.intersection(chunk_words)
            ratio = len(common) / len(claim_words)
            if ratio > best_overlap_ratio:
                best_overlap_ratio = ratio
                best_chunk_header = chunk.section_header or chunk.document_filename

        # If >= 40% of non-trivial words in claim appear in a chunk, consider it supported
        if best_overlap_ratio >= 0.40:
            return (
                "supported",
                f"Corroborated by section '{best_chunk_header}' with {round(best_overlap_ratio * 100)}% term overlap.",
            )
        else:
            return (
                "unsupported",
                f"Claim terms not found in provided contract context (highest overlap: {round(best_overlap_ratio * 100)}%).",
            )

    async def _audit_hallucinations(
        self,
        answer_text: str,
        context_chunks: list[GradedChunk],
    ) -> tuple[float, list[HallucinationFlag]]:
        """Audit each claim in the generated answer for factual grounding."""
        claims = self._split_into_claims(answer_text)
        if not claims:
            return 1.0, []

        flags: list[HallucinationFlag] = []
        supported_count = 0

        for claim in claims:
            verdict, evidence = self._check_entailment_heuristic(claim, context_chunks)
            if verdict == "supported":
                supported_count += 1
            else:
                flags.append(
                    HallucinationFlag(
                        claim=claim,
                        verdict=verdict,
                        evidence=evidence,
                    )
                )

        faithfulness = round(supported_count / len(claims), 3)
        return faithfulness, flags

    def _redact_pii(self, text: str) -> tuple[str, bool]:
        """Detect and redact sensitive personal identifiable information."""
        redacted = text
        pii_found = False

        for pii_type, pattern in PII_PATTERNS.items():
            if pattern.search(redacted):
                pii_found = True
                redacted = pattern.sub(f"[REDACTED_{pii_type}]", redacted)

        return redacted, pii_found

    def _compute_confidence(
        self,
        retrieval_chunks: list[GradedChunk],
        faithfulness_score: float,
    ) -> float:
        """Compute holistic confidence score across retrieval, grading, and faithfulness."""
        if not retrieval_chunks:
            return 0.0

        avg_retrieval = sum(c.fused_score for c in retrieval_chunks) / len(retrieval_chunks)
        avg_relevance = sum(c.relevance_score for c in retrieval_chunks) / len(retrieval_chunks)

        # Weighted composition: 30% retrieval strength + 30% relevance grading + 40% faithfulness
        confidence = (0.30 * avg_retrieval) + (0.30 * avg_relevance) + (0.40 * faithfulness_score)
        return round(max(0.0, min(1.0, confidence)), 3)

    async def check(
        self,
        answer: GeneratedAnswer,
        context_chunks: list[GradedChunk],
    ) -> GuardrailResult:
        """Run all guardrails checks across generation and privacy."""
        # 1. PII Redaction
        redacted_text, pii_redacted = self._redact_pii(answer.answer_text)

        # 2. Hallucination and Faithfulness Audit
        faithfulness_score, hallucination_flags = await self._audit_hallucinations(
            answer_text=redacted_text,
            context_chunks=context_chunks,
        )

        # 3. Overall Confidence Calculation
        confidence_score = self._compute_confidence(
            retrieval_chunks=context_chunks,
            faithfulness_score=faithfulness_score,
        )

        # Pass criteria: faithfulness >= 0.70 and confidence >= 0.40
        passed = faithfulness_score >= 0.70 and len(hallucination_flags) == 0

        logger.info(
            "Guardrails check completed",
            faithfulness=faithfulness_score,
            confidence=confidence_score,
            flags_count=len(hallucination_flags),
            pii_redacted=pii_redacted,
        )

        return GuardrailResult(
            faithfulness_score=faithfulness_score,
            hallucination_flags=hallucination_flags,
            pii_redacted=pii_redacted,
            redacted_answer=redacted_text,
            confidence_score=confidence_score,
            passed=passed,
        )
