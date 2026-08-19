"""Deterministic urgency scoring engine based on contract signals."""

from datetime import date, datetime
from typing import Any


class UrgencyScorer:
    """Computes explainable urgency score (0-100) from contract signals."""

    @staticmethod
    def compute_urgency(
        expiration_date: str | date | datetime | None = None,
        deadline_days: int | None = None,
        estimated_value: float | None = None,
        risk_signals: list[str] | None = None,
        contract_type: str = "other",
    ) -> tuple[int, dict[str, Any]]:
        """
        Compute deterministic urgency score (0-100) based on 4 explainable pillars:
        1. Deadline proximity (0-25 pts)
        2. Contract financial value (0-25 pts)
        3. Risk signal count & severity (0-25 pts)
        4. Contract type complexity weight (0-25 pts)

        Returns:
            (urgency_score: int, factors: dict[str, Any])
        """
        risks = risk_signals or []
        factors: dict[str, Any] = {}

        # 1. Deadline proximity (0-25)
        days = deadline_days
        if days is None and expiration_date:
            days = UrgencyScorer._parse_days_until(expiration_date)

        if days is not None:
            if days <= 7:
                deadline_pts = 25
            elif days <= 14:
                deadline_pts = 20
            elif days <= 30:
                deadline_pts = 15
            elif days <= 60:
                deadline_pts = 10
            elif days <= 90:
                deadline_pts = 5
            else:
                deadline_pts = 0
            factors["deadline_proximity"] = {
                "days_remaining": days,
                "points": deadline_pts,
                "max": 25,
            }
        else:
            deadline_pts = 0
            factors["deadline_proximity"] = {
                "days_remaining": None,
                "points": 0,
                "max": 25,
            }

        # 2. Contract value (0-25)
        if estimated_value is not None:
            if estimated_value >= 1_000_000:
                val_pts = 25
            elif estimated_value >= 500_000:
                val_pts = 20
            elif estimated_value >= 100_000:
                val_pts = 15
            elif estimated_value >= 50_000:
                val_pts = 10
            else:
                val_pts = 5
            factors["contract_value"] = {
                "amount": estimated_value,
                "points": val_pts,
                "max": 25,
            }
        else:
            val_pts = 10  # Unknown value defaults to standard baseline
            factors["contract_value"] = {
                "amount": None,
                "points": val_pts,
                "max": 25,
            }

        # 3. Risk signal count & severity (0-25)
        has_critical_risk = "uncapped_liability" in risks
        risk_count = len(risks)
        if has_critical_risk or risk_count >= 4:
            risk_pts = 25
        elif risk_count == 3:
            risk_pts = 20
        elif risk_count == 2:
            risk_pts = 15
        elif risk_count == 1:
            risk_pts = 10
        else:
            risk_pts = 0

        factors["risk_signals"] = {
            "signals_detected": risks,
            "count": risk_count,
            "points": risk_pts,
            "max": 25,
        }

        # 4. Contract type complexity weight (0-25)
        type_weights = {
            "amendment": 20,
            "msa": 15,
            "sow": 15,
            "lease": 12,
            "vendor": 12,
            "employment": 10,
            "license": 10,
            "services": 10,
            "other": 8,
            "nda": 5,
        }
        type_pts = type_weights.get(contract_type.lower(), 8)
        factors["contract_type_weight"] = {
            "type": contract_type,
            "points": type_pts,
            "max": 25,
        }

        total_score = min(100, max(0, deadline_pts + val_pts + risk_pts + type_pts))
        return total_score, factors

    @staticmethod
    def _parse_days_until(target: str | date | datetime) -> int | None:
        """Calculate days from today until target date."""
        today = date.today()
        if isinstance(target, datetime):
            target_date = target.date()
        elif isinstance(target, date):
            target_date = target
        elif isinstance(target, str):
            for fmt in ["%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"]:
                try:
                    dt = datetime.strptime(target.strip(), fmt)
                    target_date = dt.date()
                    break
                except ValueError:
                    continue
            else:
                return None
        else:
            return None

        delta = (target_date - today).days
        return max(0, delta)
