import re
import uuid
from typing import Any

import structlog

from termnova.intelligence.schemas import HeatmapCell

logger = structlog.get_logger(__name__)

# Standard 15-category clause taxonomy
CLAUSE_TAXONOMY: list[dict[str, str]] = [
    {"key": "liability", "label": "Limitation of Liability"},
    {"key": "indemnification", "label": "Indemnification"},
    {"key": "termination", "label": "Termination & Cure"},
    {"key": "payment", "label": "Payment Terms & Fees"},
    {"key": "confidentiality", "label": "Confidentiality & NDA"},
    {"key": "ip_ownership", "label": "IP & Deliverables"},
    {"key": "data_protection", "label": "Data Privacy & GDPR"},
    {"key": "insurance", "label": "Insurance Requirements"},
    {"key": "force_majeure", "label": "Force Majeure"},
    {"key": "dispute_resolution", "label": "Dispute Resolution & Law"},
    {"key": "warranty", "label": "Warranties & Disclaimers"},
    {"key": "non_compete", "label": "Non-Compete & Solicitation"},
    {"key": "assignment", "label": "Assignment & Change of Control"},
    {"key": "audit_rights", "label": "Audit & Inspection Rights"},
    {"key": "representations", "label": "Representations & Authority"},
]

CLAUSE_KEYS: list[str] = [cat["key"] for cat in CLAUSE_TAXONOMY]


class ClausePresenceAnalyzer:
    """Determines presence, risk level, and excerpt snippets for standard clause taxonomy."""

    # Weighted regex patterns per category
    CATEGORY_PATTERNS: dict[str, list[tuple[re.Pattern[str], float]]] = {
        "liability": [
            (
                re.compile(
                    r"\b(limitation\s+of\s+liability|liability\s*[:\w\s]*cap|aggregate\s+liability|consequential\s+damages|indirect\s+damages|uncapped\s+liability|liability\s*(?:is\s+)?capped)\b",
                    re.I,
                ),
                1.0,
            ),
            (
                re.compile(
                    r"\b(maximum\s+cumulative\s+liability|in\s+no\s+event\s+shall.*liability|liability\s+exceed)\b",
                    re.I,
                ),
                0.9,
            ),
            (re.compile(r"\b(liability|damages|loss)\b", re.I), 0.5),
        ],
        "indemnification": [
            (
                re.compile(
                    r"\b(indemnif\w*|hold\s+harmless|defend\w*\s+and\s+hold\s+harmless|third-party\s+claims?)\b",
                    re.I,
                ),
                1.0,
            ),
            (re.compile(r"\b(defense\s+of\s+claims?|indemnitee|indemnitor)\b", re.I), 0.9),
        ],
        "termination": [
            (
                re.compile(
                    r"\b(terminat\w*|term\s+and\s+termination|cure\s+period|termination\s+for\s+convenience|material\s+breach)\b",
                    re.I,
                ),
                1.0,
            ),
            (
                re.compile(
                    r"\b(immediate\s+termination|notice\s+of\s+termination|expiration\s+date)\b",
                    re.I,
                ),
                0.9,
            ),
        ],
        "payment": [
            (
                re.compile(
                    r"\b(payment\s+terms?|invoic\w*|net\s+\d+|billing\s+schedule|remittance|late\s+fee\w*)\b",
                    re.I,
                ),
                1.0,
            ),
            (re.compile(r"\b(compensation|pricing|rates|taxes|due\s+and\s+payable)\b", re.I), 0.8),
        ],
        "confidentiality": [
            (
                re.compile(
                    r"\b(confidential\w*|non-disclosure|proprietary\s+information|trade\s+secrets?|duty\s+of\s+confidentiality)\b",
                    re.I,
                ),
                1.0,
            ),
            (re.compile(r"\b(receiving\s+party|disclosing\s+party|nda)\b", re.I), 0.8),
        ],
        "ip_ownership": [
            (
                re.compile(
                    r"\b(intellectual\s+property|proprietary\s+rights|work\s+for\s+hire|patent\w*|copyright\w*|license\s+grant|ownership\s+of\s+deliverables)\b",
                    re.I,
                ),
                1.0,
            ),
            (re.compile(r"\b(ip\s+rights|trademarks?|inventions?|author's\s+rights)\b", re.I), 0.9),
        ],
        "data_protection": [
            (
                re.compile(
                    r"\b(data\s+privacy|data\s+protection|gdpr|ccpa|personal\s+data|security\s+breach|security\s+incident|dpa)\b",
                    re.I,
                ),
                1.0,
            ),
            (
                re.compile(r"\b(processing\s+of\s+data|data\s+subject|encryption|hipaa)\b", re.I),
                0.9,
            ),
        ],
        "insurance": [
            (
                re.compile(
                    r"\b(insurance\s+requirements?|commercial\s+general\s+liability|errors\s+and\s+omissions|cyber\s+insurance|workers'?\s+compensation|certificate\s+of\s+insurance)\b",
                    re.I,
                ),
                1.0,
            ),
            (re.compile(r"\b(policy\s+limits?|insured|coverage\s+minimums?)\b", re.I), 0.8),
        ],
        "force_majeure": [
            (
                re.compile(
                    r"\b(force\s+majeure|acts?\s+of\s+god|war|riot|strike|pandemic|epidemic|natural\s+disaster)\b",
                    re.I,
                ),
                1.0,
            ),
            (
                re.compile(
                    r"\b(unforeseeable\s+circumstances?|beyond\s+reasonable\s+control)\b", re.I
                ),
                0.8,
            ),
        ],
        "dispute_resolution": [
            (
                re.compile(
                    r"\b(governing\s+law|jurisdiction|venue|arbitrat\w*|dispute\s+resolution|choice\s+of\s+law|governed\s+by\s+(?:the\s+)?laws?)\b",
                    re.I,
                ),
                1.0,
            ),
            (re.compile(r"\b(court\s+of\s+competent\s+jurisdiction|mediation)\b", re.I), 0.8),
        ],
        "warranty": [
            (
                re.compile(
                    r"\b(warrant\w*|disclaimer\s+of\s+warranties?|as\s+is|merchantability|fitness\s+for\s+a\s+particular\s+purpose)\b",
                    re.I,
                ),
                1.0,
            ),
            (re.compile(r"\b(express\s+warranty|implied\s+warranty|guarantee)\b", re.I), 0.8),
        ],
        "non_compete": [
            (
                re.compile(
                    r"\b(non-compete|non-solicitation|restrictive\s+covenants?|non-interference|non-hire)\b",
                    re.I,
                ),
                1.0,
            ),
            (re.compile(r"\b(solicit\s+customers?|solicit\s+employees?)\b", re.I), 0.9),
        ],
        "assignment": [
            (
                re.compile(
                    r"\b(assignment|successors\s+and\s+assigns|change\s+of\s+control|merger\s+or\s+acquisition|assignability)\b",
                    re.I,
                ),
                1.0,
            ),
            (
                re.compile(
                    r"\b(prior\s+written\s+consent\s+to\s+assign|transfer\s+of\s+rights)\b", re.I
                ),
                0.8,
            ),
        ],
        "audit_rights": [
            (
                re.compile(
                    r"\b(audit\s+rights?|right\s+to\s+audit|inspection\s+of\s+records|books\s+and\s+records|examination\s+of\s+books)\b",
                    re.I,
                ),
                1.0,
            ),
            (
                re.compile(r"\b(accounting\s+records|reasonable\s+notice\s+for\s+audit)\b", re.I),
                0.8,
            ),
        ],
        "representations": [
            (
                re.compile(
                    r"\b(representations?\s+and\s+warranties|authority\s+to\s+execute|validly\s+existing|good\s+standing|power\s+and\s+authority)\b",
                    re.I,
                ),
                1.0,
            ),
            (re.compile(r"\b(corporate\s+power|duly\s+authorized)\b", re.I), 0.8),
        ],
    }

    def analyze_chunks(
        self,
        chunks: list[dict[str, Any] | str | Any],
    ) -> dict[str, HeatmapCell]:
        """
        Scan chunks to detect presence of all 15 standard clause categories.
        Returns a dictionary mapping category key -> HeatmapCell.
        """
        results: dict[str, HeatmapCell] = {}

        # Initialize all categories as absent
        for cat in CLAUSE_KEYS:
            results[cat] = HeatmapCell(
                category=cat,
                present=False,
                risk_level=None,
                excerpt=None,
                confidence=0.0,
                chunk_id=None,
            )

        # Normalize chunk inputs
        normalized_chunks: list[tuple[str, uuid.UUID | None]] = []
        for c in chunks:
            if isinstance(c, str):
                normalized_chunks.append((c, None))
            elif isinstance(c, dict):
                content = c.get("content", "")
                cid = c.get("id")
                normalized_chunks.append((content, cid if isinstance(cid, uuid.UUID) else None))
            elif hasattr(c, "content"):
                cid = getattr(c, "id", None)
                normalized_chunks.append((c.content, cid if isinstance(cid, uuid.UUID) else None))

        # Check each category against chunks
        for cat_key, patterns in self.CATEGORY_PATTERNS.items():
            best_confidence = 0.0
            best_excerpt = None
            best_chunk_id = None
            matched_text = ""

            for content, cid in normalized_chunks:
                if not content:
                    continue

                for pattern, weight in patterns:
                    match = pattern.search(content)
                    if match and weight > best_confidence:
                        best_confidence = weight
                        best_chunk_id = cid
                        matched_text = content
                        best_excerpt = self._extract_clean_excerpt(
                            content, match.start(), match.end()
                        )

            # Threshold for presence
            if best_confidence >= 0.7:
                risk = self._classify_clause_risk(cat_key, matched_text)
                results[cat_key] = HeatmapCell(
                    category=cat_key,
                    present=True,
                    risk_level=risk,
                    excerpt=best_excerpt,
                    confidence=best_confidence,
                    chunk_id=best_chunk_id,
                )

        return results

    def _extract_clean_excerpt(
        self, text: str, match_start: int, match_end: int, max_len: int = 180
    ) -> str:
        """Extract surrounding text snippet centered around the match."""
        snippet_start = max(0, match_start - 40)
        snippet_end = min(len(text), match_end + 120)
        excerpt = text[snippet_start:snippet_end].replace("\n", " ").strip()
        if snippet_start > 0:
            excerpt = "..." + excerpt
        if snippet_end < len(text):
            excerpt = excerpt + "..."
        return excerpt[:max_len]

    def _classify_clause_risk(self, category: str, text: str) -> str:
        """Heuristic risk classification for detected clauses."""
        text_lower = text.lower()

        if category == "liability":
            if any(
                term in text_lower
                for term in ["uncapped", "unlimited", "no limitation", "gross negligence"]
            ):
                return "critical"
            if any(term in text_lower for term in ["$5,000,000", "$10,000,000", "5x", "10x"]):
                return "high"
            if any(term in text_lower for term in ["$1,000,000", "$2,000,000", "12 months"]):
                return "medium"
            return "low"

        if category == "indemnification":
            if any(
                term in text_lower
                for term in ["sole and exclusive", "solely responsible", "unilateral"]
            ):
                return "high"
            if "mutual" in text_lower or "each party" in text_lower:
                return "low"
            return "medium"

        if category == "termination":
            if "immediate" in text_lower and "without notice" in text_lower:
                return "high"
            if "convenience" in text_lower and ("penalty" in text_lower or "fee" in text_lower):
                return "medium"
            return "low"

        if category == "data_protection":
            if any(
                term in text_lower for term in ["no liability", "as is", "no breach notification"]
            ):
                return "critical"
            if any(term in text_lower for term in ["24 hours", "immediate notification"]):
                return "low"
            return "medium"

        if category == "ip_ownership":
            if "exclusive ownership" in text_lower or "work for hire" in text_lower:
                return "medium"
            return "low"

        if category == "non_compete":
            if any(term in text_lower for term in ["3 years", "5 years", "worldwide"]):
                return "high"
            return "medium"

        if category == "warranty":
            if "disclaims all warranties" in text_lower or "as is" in text_lower:
                return "medium"
            return "low"

        # Default fallback
        return "low"
