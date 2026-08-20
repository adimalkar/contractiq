"""Multi-version contract diffing with clause-level semantic alignment and categorization."""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from termnova.comparison.aligner import ClauseAligner
from termnova.comparison.differ import ClauseDiffer
from termnova.db.models import Chunk

if TYPE_CHECKING:
    from termnova.comparison import ClauseAlignment

logger = structlog.get_logger(__name__)


@dataclass
class ClauseChange:
    """Representation of a detected change in a contractual clause."""

    clause_category: str
    change_type: str  # added, removed, modified, identical
    original_text: str
    modified_text: str
    diff_html: str
    section_name: str | None = None
    similarity_score: float = 0.0


class NegotiationDiffer:
    """Extends clause diffing for multi-version contract negotiation tracking."""

    # Pre-compiled category patterns
    CATEGORY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
        (
            "liability",
            re.compile(
                r"\b(limitation\s+of\s+liability|aggregate\s+liability|liability\s+cap|indirect\s+damages|consequential\s+damages|willful\s+misconduct)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "indemnification",
            re.compile(
                r"\b(indemnif\w*|hold\s+harmless|defense\s+of\s+claims|third-party\s+claim)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "termination",
            re.compile(
                r"\b(terminat\w*|term\s+and\s+termination|cure\s+period|convenience|material\s+breach|expiration)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "payment",
            re.compile(
                r"\b(payment\s+terms|invoic\w*|fee\w*|net\s+\d+|billing|pricing|compensation|remittance)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "ip",
            re.compile(
                r"\b(intellectual\s+property|proprietary\s+rights|patent\w*|copyright\w*|work\s+for\s+hire|license\s+grant|ip\s+ownership)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "confidentiality",
            re.compile(
                r"\b(confidential\w*|non-disclosure|proprietary\s+information|trade\s+secret\w*|duty\s+of\s+confidentiality)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "governing_law",
            re.compile(
                r"\b(governing\s+law|governed\s+by\s+(?:the\s+)?laws?|jurisdiction|venue|dispute\s+resolution|arbitrat\w*|choice\s+of\s+law)\b",
                re.IGNORECASE,
            ),
        ),
    ]

    def __init__(
        self,
        aligner: ClauseAligner | None = None,
        differ: ClauseDiffer | None = None,
    ):
        self.aligner = aligner or ClauseAligner()
        self.differ = differ or ClauseDiffer()

    def categorize_clause(self, clause_text: str) -> str:
        """
        Categorize clause text using robust regex pattern matching.
        Returns one of: liability, indemnification, termination, payment, ip, confidentiality, governing_law, other
        """
        if not clause_text or not clause_text.strip():
            return "other"

        text_lower = clause_text.strip()
        for category, pattern in self.CATEGORY_PATTERNS:
            if pattern.search(text_lower):
                return category

        return "other"

    def diff_versions(
        self,
        chunks_a: list[Chunk | str],
        chunks_b: list[Chunk | str],
    ) -> list[ClauseChange]:
        """
        Align and diff clauses between two version chunk sets.
        Returns list of ClauseChange instances excluding identical clauses.
        """
        normalized_a = self._normalize_chunks(chunks_a, prefix="vA")
        normalized_b = self._normalize_chunks(chunks_b, prefix="vB")

        alignments: list[ClauseAlignment] = self.aligner.align_clauses(normalized_a, normalized_b)

        changes: list[ClauseChange] = []
        for al in alignments:
            if al.diff_type == "identical":
                continue

            category = self.categorize_clause(al.text_a or al.text_b)
            sec = al.section_a or al.section_b or "General Section"

            changes.append(
                ClauseChange(
                    clause_category=category,
                    change_type=al.diff_type,
                    original_text=al.text_a or "",
                    modified_text=al.text_b or "",
                    diff_html=al.diff_html
                    or self.differ.generate_html_diff(al.text_a or "", al.text_b or ""),
                    section_name=sec,
                    similarity_score=al.similarity_score,
                )
            )

        logger.info(
            "Negotiation diff completed",
            chunks_a=len(chunks_a),
            chunks_b=len(chunks_b),
            total_changes=len(changes),
        )
        return changes

    @staticmethod
    def _normalize_chunks(chunks: list[Chunk | str], prefix: str = "v") -> list[Chunk]:
        """Convert string lists to Chunk objects if raw strings are passed."""
        normalized: list[Chunk] = []
        for i, c in enumerate(chunks):
            if isinstance(c, Chunk):
                normalized.append(c)
            elif isinstance(c, str) and c.strip():
                normalized.append(
                    Chunk(
                        content=c.strip(),
                        section_header=f"{prefix}_Section_{i + 1}",
                        chunk_index=i,
                    )
                )
        return normalized
