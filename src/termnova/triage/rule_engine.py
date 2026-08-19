"""Configurable routing rule engine for contract triage."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.db.models import TriageResult, TriageRule


class RuleMatchResult:
    """Outcome of rule evaluation."""

    def __init__(self, rule: TriageRule):
        self.rule_id = rule.id
        self.rule_name = rule.name
        self.action = rule.action
        self.assign_to: str | None = rule.action.get("assign_to")
        self.add_tags: list[str] = rule.action.get("add_tags", [])
        self.set_status: str | None = rule.action.get("set_status")


class TriageRuleEngine:
    """Evaluates organization routing rules against contract triage results."""

    async def evaluate_rules(
        self,
        session: AsyncSession,
        triage_result: TriageResult,
        organization_id: uuid.UUID | None = None,
    ) -> list[RuleMatchResult]:
        """
        Evaluate active rules in priority order (ASC) and return all matched rules.
        """
        stmt = (
            select(TriageRule)
            .where(TriageRule.is_active.is_(True))
            .order_by(TriageRule.priority.asc())
        )
        if organization_id is not None:
            stmt = stmt.where(
                (TriageRule.organization_id == organization_id)
                | (TriageRule.organization_id.is_(None))
            )

        rules = list((await session.execute(stmt)).scalars().all())
        matches: list[RuleMatchResult] = []

        for rule in rules:
            if self.matches_condition(rule.condition, triage_result):
                matches.append(RuleMatchResult(rule))

        return matches

    def matches_condition(self, condition: dict[str, Any], triage: TriageResult) -> bool:
        """
        Evaluate a single condition JSON object against a TriageResult.

        Supported condition keys:
        - "contract_type": str or list[str] (case-insensitive)
        - "urgency_min": int (triage.urgency_score >= min)
        - "urgency_max": int (triage.urgency_score <= max)
        - "tags_include": list[str] (all must be present in auto_tags)
        - "tags_exclude": list[str] (none can be present in auto_tags)
        - "confidence_min": float (type_confidence >= min)
        """
        if not condition:
            return True

        # 1. Contract Type
        if "contract_type" in condition:
            req_type = condition["contract_type"]
            detected = (triage.contract_type_detected or "").lower()
            if isinstance(req_type, list) and not any(t.lower() == detected for t in req_type):
                return False
            if isinstance(req_type, str) and req_type.lower() != detected:
                return False

        # 2. Urgency Min
        if "urgency_min" in condition and triage.urgency_score < int(condition["urgency_min"]):
            return False

        # 3. Urgency Max
        if "urgency_max" in condition and triage.urgency_score > int(condition["urgency_max"]):
            return False

        # 4. Tags Include (All must be present)
        if "tags_include" in condition:
            req_tags = condition["tags_include"]
            current_tags = set(triage.auto_tags or [])
            if not all(t in current_tags for t in req_tags):
                return False

        # 5. Tags Exclude (None can be present)
        if "tags_exclude" in condition:
            ex_tags = condition["tags_exclude"]
            current_tags = set(triage.auto_tags or [])
            if any(t in current_tags for t in ex_tags):
                return False

        # 6. Confidence Min
        if "confidence_min" in condition:
            return triage.type_confidence >= float(condition["confidence_min"])

        return True
