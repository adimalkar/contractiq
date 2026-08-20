"""AI-powered concession classification and negotiation summary engine."""

import re
from dataclasses import dataclass
from typing import Literal

import structlog

from termnova.db.models import NegotiationChange, NegotiationTrack, NegotiationVersion
from termnova.schemas.negotiation import NegotiationSummaryResponse

logger = structlog.get_logger(__name__)


@dataclass
class ConcessionResult:
    """Outcome of analyzing a single clause change."""

    concession_party: Literal["us", "counterparty", "mutual", "neutral"]
    risk_impact: Literal["increased_risk", "decreased_risk", "neutral"]
    concession_summary: str
    significance: Literal["low", "medium", "high", "critical"]


class ConcessionAnalyzer:
    """Determines negotiation concessions, risk trajectory, and strategic recommendations."""

    # Financial & timeline regex patterns
    MONEY_PATTERN = re.compile(r"\$[\d,]+(?:\.\d{2})?")
    DAYS_PATTERN = re.compile(r"\b(\d+)\s*(?:calendar\s+|business\s+)?days?\b", re.IGNORECASE)
    NET_PATTERN = re.compile(r"\bnet\s+(\d+)\b", re.IGNORECASE)

    def analyze_concession(
        self,
        original_text: str,
        modified_text: str,
        source: str = "counterparty",
        clause_category: str = "other",
    ) -> ConcessionResult:
        """
        Analyze a clause change to determine who gave ground, risk impact, and summary.

        Args:
            original_text: Text in version N-1
            modified_text: Text in version N
            source: "internal" (our proposed draft) or "counterparty" (their redline)
            clause_category: liability, indemnification, termination, payment, ip, confidentiality, governing_law, other
        """
        orig_clean = (original_text or "").strip()
        mod_clean = (modified_text or "").strip()

        # Added clause
        if not orig_clean and mod_clean:
            return self._analyze_added_clause(mod_clean, source, clause_category)

        # Removed clause
        if orig_clean and not mod_clean:
            return self._analyze_removed_clause(orig_clean, source, clause_category)

        # Modified clause
        return self._analyze_modified_clause(orig_clean, mod_clean, source, clause_category)

    def _analyze_added_clause(
        self,
        text: str,
        source: str,
        category: str,
    ) -> ConcessionResult:
        """Analyze a newly inserted clause."""
        text_lower = text.lower()
        if category in ("liability", "indemnification"):
            if "sole remedy" in text_lower or "hold harmless" in text_lower:
                if source == "counterparty":
                    return ConcessionResult(
                        concession_party="us",
                        risk_impact="increased_risk",
                        concession_summary=f"Counterparty added {category} obligation on us.",
                        significance="high",
                    )
                return ConcessionResult(
                    concession_party="counterparty",
                    risk_impact="decreased_risk",
                    concession_summary=f"We added favorable {category} clause protection.",
                    significance="high",
                )
            return ConcessionResult(
                concession_party="us" if source == "counterparty" else "counterparty",
                risk_impact="increased_risk" if source == "counterparty" else "decreased_risk",
                concession_summary=f"New {category} section inserted.",
                significance="high",
            )

        if category == "termination":
            if "convenience" in text_lower:
                return ConcessionResult(
                    concession_party="mutual",
                    risk_impact="neutral",
                    concession_summary="Added termination for convenience clause.",
                    significance="medium",
                )
            return ConcessionResult(
                concession_party="neutral",
                risk_impact="neutral",
                concession_summary="Added termination clause.",
                significance="low",
            )

        return ConcessionResult(
            concession_party="neutral",
            risk_impact="neutral",
            concession_summary=f"New {category} clause inserted.",
            significance="medium" if category in ("ip", "payment") else "low",
        )

    def _analyze_removed_clause(
        self,
        text: str,
        source: str,
        category: str,
    ) -> ConcessionResult:
        """Analyze a deleted clause."""
        if category in ("liability", "indemnification", "ip"):
            if source == "counterparty":
                return ConcessionResult(
                    concession_party="us",
                    risk_impact="increased_risk",
                    concession_summary=f"Counterparty struck our {category} protection clause.",
                    significance="critical" if category == "liability" else "high",
                )
            return ConcessionResult(
                concession_party="counterparty",
                risk_impact="decreased_risk",
                concession_summary=f"We removed {category} obligation.",
                significance="high",
            )

        return ConcessionResult(
            concession_party="neutral",
            risk_impact="neutral",
            concession_summary=f"Removed {category} section.",
            significance="medium" if category in ("termination", "payment") else "low",
        )

    def _analyze_modified_clause(
        self,
        orig: str,
        mod: str,
        source: str,
        category: str,
    ) -> ConcessionResult:
        """Analyze textual modifications within an existing clause."""
        orig_lower = orig.lower()
        mod_lower = mod.lower()

        # 1. Liability changes
        if category == "liability":
            orig_money = self.MONEY_PATTERN.findall(orig)
            mod_money = self.MONEY_PATTERN.findall(mod)
            if orig_money and mod_money and orig_money != mod_money:
                orig_val = self._parse_currency(orig_money[0])
                mod_val = self._parse_currency(mod_money[0])
                if orig_val and mod_val:
                    if mod_val > orig_val:
                        # Cap increased (e.g. $500k -> $2M)
                        party = "us" if source == "counterparty" else "us"
                        return ConcessionResult(
                            concession_party=party,
                            risk_impact="increased_risk",
                            concession_summary=f"Liability cap increased from {orig_money[0]} to {mod_money[0]}.",
                            significance="critical",
                        )
                    else:
                        # Cap lowered (e.g. $2M -> $500k)
                        party = "counterparty" if source == "counterparty" else "counterparty"
                        return ConcessionResult(
                            concession_party=party,
                            risk_impact="decreased_risk",
                            concession_summary=f"Liability cap reduced from {orig_money[0]} to {mod_money[0]}.",
                            significance="high",
                        )

            if "willful misconduct" in mod_lower and "willful misconduct" not in orig_lower:
                return ConcessionResult(
                    concession_party="us" if source == "counterparty" else "counterparty",
                    risk_impact="increased_risk" if source == "counterparty" else "neutral",
                    concession_summary="Carve-out for willful misconduct and gross negligence added to liability cap.",
                    significance="high",
                )

            return ConcessionResult(
                concession_party="us" if source == "counterparty" else "neutral",
                risk_impact="increased_risk" if source == "counterparty" else "neutral",
                concession_summary="Limitation of liability terms modified.",
                significance="high",
            )

        # 2. Indemnification changes
        if category == "indemnification":
            if "mutual" in mod_lower and "mutual" not in orig_lower:
                return ConcessionResult(
                    concession_party="counterparty" if source == "counterparty" else "us",
                    risk_impact="decreased_risk",
                    concession_summary="Indemnity clause converted to mutual indemnification.",
                    significance="high",
                )
            if "sole and exclusive" in mod_lower:
                return ConcessionResult(
                    concession_party="counterparty",
                    risk_impact="decreased_risk",
                    concession_summary="Indemnification established as sole and exclusive remedy.",
                    significance="medium",
                )
            return ConcessionResult(
                concession_party="us" if source == "counterparty" else "counterparty",
                risk_impact="increased_risk" if source == "counterparty" else "decreased_risk",
                concession_summary="Indemnification coverage and defense scope adjusted.",
                significance="high",
            )

        # 3. Payment terms changes
        if category == "payment":
            orig_net = self.NET_PATTERN.findall(orig)
            mod_net = self.NET_PATTERN.findall(mod)
            if orig_net and mod_net and orig_net != mod_net:
                orig_days = int(orig_net[0])
                mod_days = int(mod_net[0])
                if mod_days > orig_days:
                    # Net 30 -> Net 60
                    return ConcessionResult(
                        concession_party="us" if source == "counterparty" else "counterparty",
                        risk_impact="neutral",
                        concession_summary=f"Payment window extended from Net {orig_days} to Net {mod_days}.",
                        significance="medium",
                    )
                else:
                    # Net 60 -> Net 30
                    return ConcessionResult(
                        concession_party="counterparty" if source == "counterparty" else "us",
                        risk_impact="decreased_risk",
                        concession_summary=f"Payment window accelerated from Net {orig_days} to Net {mod_days}.",
                        significance="medium",
                    )

            return ConcessionResult(
                concession_party="neutral",
                risk_impact="neutral",
                concession_summary="Payment and invoicing schedule updated.",
                significance="medium",
            )

        # 4. Termination notice period changes
        if category == "termination":
            orig_days_match = self.DAYS_PATTERN.findall(orig)
            mod_days_match = self.DAYS_PATTERN.findall(mod)
            if orig_days_match and mod_days_match and orig_days_match != mod_days_match:
                orig_d = int(orig_days_match[0])
                mod_d = int(mod_days_match[0])
                return ConcessionResult(
                    concession_party="mutual",
                    risk_impact="neutral",
                    concession_summary=f"Notice / cure period adjusted from {orig_d} to {mod_d} days.",
                    significance="medium",
                )

            return ConcessionResult(
                concession_party="neutral",
                risk_impact="neutral",
                concession_summary="Termination and breach cure language modified.",
                significance="medium",
            )

        # 5. IP and Ownership
        if category == "ip":
            if "exclusive" in mod_lower and "exclusive" not in orig_lower:
                return ConcessionResult(
                    concession_party="us" if source == "counterparty" else "counterparty",
                    risk_impact="increased_risk" if source == "counterparty" else "decreased_risk",
                    concession_summary="Intellectual property license exclusivity terms expanded.",
                    significance="high",
                )
            if "work for hire" in mod_lower:
                return ConcessionResult(
                    concession_party="us" if source == "counterparty" else "counterparty",
                    risk_impact="increased_risk" if source == "counterparty" else "decreased_risk",
                    concession_summary="Work-for-hire assignment obligations incorporated.",
                    significance="high",
                )
            return ConcessionResult(
                concession_party="neutral",
                risk_impact="neutral",
                concession_summary="IP license grant and ownership terms adjusted.",
                significance="medium",
            )

        # Fallback
        return ConcessionResult(
            concession_party="neutral",
            risk_impact="neutral",
            concession_summary=f"{category.capitalize()} clause terms updated.",
            significance="low",
        )

    def generate_negotiation_summary(
        self,
        changes: list[NegotiationChange],
        track: NegotiationTrack,
        versions: list[NegotiationVersion] | None = None,
    ) -> NegotiationSummaryResponse:
        """Generate comprehensive AI negotiation summary and strategic balance assessment."""
        our_concessions = [c for c in changes if c.concession_party == "us"]
        their_concessions = [c for c in changes if c.concession_party == "counterparty"]
        mutual_trades = [c for c in changes if c.concession_party == "mutual"]

        # Balance assessment
        diff = len(their_concessions) - len(our_concessions)
        if diff >= 2:
            balance: Literal["favorable", "balanced", "unfavorable"] = "favorable"
        elif diff <= -2:
            balance = "unfavorable"
        else:
            balance = "balanced"

        # Key concessions summaries
        us_summaries = [
            c.concession_summary or f"Concession in {c.clause_category}"
            for c in our_concessions[:5]
        ]
        them_summaries = [
            c.concession_summary or f"Concession in {c.clause_category}"
            for c in their_concessions[:5]
        ]

        # Remaining gaps / unresolved risk items
        unresolved_risks = [
            f"Unresolved risk in {c.clause_category}: {c.concession_summary}"
            for c in changes
            if c.risk_impact == "increased_risk"
        ][:3]

        if not unresolved_risks:
            unresolved_risks = ["No high-risk unresolved clauses detected."]

        # Executive summary narrative
        v_count = len(versions or track.versions or [])
        exec_summary = (
            f"Negotiation track '{track.name}' with {track.counterparty} has completed {v_count} version rounds. "
            f"A total of {len(changes)} clause changes were tracked ({len(our_concessions)} concessions by us, "
            f"{len(their_concessions)} concessions by counterparty, and {len(mutual_trades)} mutual adjustments). "
            f"The overall negotiation trajectory is currently {balance}."
        )

        risk_assessment = (
            f"Cumulative risk score is stable with {len([c for c in changes if c.risk_impact == 'increased_risk'])} "
            f"risk-increasing adjustments versus {len([c for c in changes if c.risk_impact == 'decreased_risk'])} risk mitigations."
        )

        return NegotiationSummaryResponse(
            track_id=track.id,
            executive_summary=exec_summary,
            key_concessions_us=us_summaries or ["No material concessions recorded."],
            key_concessions_them=them_summaries or ["No material concessions recorded."],
            remaining_gaps=unresolved_risks,
            risk_assessment=risk_assessment,
            strategic_recommendation=balance,
        )

    @staticmethod
    def _parse_currency(s: str) -> float | None:
        """Parse currency string into numeric float."""
        try:
            clean = s.replace("$", "").replace(",", "").strip()
            return float(clean)
        except (ValueError, TypeError):
            return None
