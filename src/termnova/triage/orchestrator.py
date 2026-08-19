"""Triage orchestrator linking classification, scoring, routing, and notifications."""

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.api.ws_manager import ws_manager
from termnova.config import Settings
from termnova.db.models import TriageResult
from termnova.triage.classifier import ContractClassifier
from termnova.triage.rule_engine import TriageRuleEngine
from termnova.triage.schemas import ClassificationResult, TriageResultResponse
from termnova.triage.urgency import UrgencyScorer

logger = structlog.get_logger(__name__)


class TriageOrchestrator:
    """End-to-end pipeline orchestrator for incoming contract triage."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        classifier: ContractClassifier | None = None,
        scorer: UrgencyScorer | None = None,
        rule_engine: TriageRuleEngine | None = None,
    ):
        self.session = session
        self.settings = settings
        self.classifier = classifier or ContractClassifier(settings)
        self.scorer = scorer or UrgencyScorer()
        self.rule_engine = rule_engine or TriageRuleEngine()

    async def triage_document(
        self,
        document_id: uuid.UUID,
        document_text: str,
        filename: str,
        organization_id: uuid.UUID | None = None,
    ) -> TriageResult:
        """
        Execute full triage workflow:
        1. Classify contract type & generate summary bullets
        2. Compute explainable urgency score
        3. Derive contextual auto-tags
        4. Evaluate routing rules to assign reviewer & set status
        5. Persist or update TriageResult in database
        6. Broadcast real-time WebSocket alert
        """
        # 1. Classification & Summary
        classification: ClassificationResult = await self.classifier.classify(
            document_text=document_text, filename=filename
        )

        # 2. Urgency Scoring
        urgency_score, urgency_factors = self.scorer.compute_urgency(
            expiration_date=classification.detected_dates.get("expiration_date"),
            estimated_value=classification.detected_value,
            risk_signals=classification.risk_signals,
            contract_type=classification.contract_type,
        )

        # 3. Derive Auto-Tags
        auto_tags = self._generate_auto_tags(
            classification=classification,
            urgency_score=urgency_score,
        )

        # 4. Check for existing TriageResult
        stmt = select(TriageResult).where(TriageResult.document_id == document_id)
        existing = (await self.session.execute(stmt)).scalars().first()

        if existing:
            triage = existing
            triage.contract_type_detected = classification.contract_type
            triage.type_confidence = classification.confidence
            triage.urgency_score = urgency_score
            triage.urgency_factors = urgency_factors
            triage.summary_bullets = classification.summary_bullets
            triage.action_required = classification.action_required
            triage.auto_tags = list(set(auto_tags + (triage.auto_tags or [])))
        else:
            triage = TriageResult(
                document_id=document_id,
                organization_id=organization_id,
                contract_type_detected=classification.contract_type,
                type_confidence=classification.confidence,
                urgency_score=urgency_score,
                urgency_factors=urgency_factors,
                summary_bullets=classification.summary_bullets,
                action_required=classification.action_required,
                auto_tags=auto_tags,
                inbox_status="unreviewed",
            )
            self.session.add(triage)

        # 5. Evaluate Routing Rules
        matches = await self.rule_engine.evaluate_rules(
            session=self.session,
            triage_result=triage,
            organization_id=organization_id,
        )

        if matches:
            primary_match = matches[0]
            if primary_match.assign_to:
                triage.suggested_assignee = primary_match.assign_to
                triage.assigned_to = primary_match.assign_to
                triage.inbox_status = "assigned"
            if primary_match.set_status:
                triage.inbox_status = primary_match.set_status
            for m in matches:
                if m.add_tags:
                    triage.auto_tags = list(set((triage.auto_tags or []) + m.add_tags))

        await self.session.commit()
        await self.session.refresh(triage)

        logger.info(
            "Contract triaged successfully",
            document_id=str(document_id),
            type=triage.contract_type_detected,
            urgency=triage.urgency_score,
            status=triage.inbox_status,
        )

        # 6. WebSocket Notification Broadcast
        try:
            resp_dto = TriageResultResponse.model_validate(triage)
            await ws_manager.broadcast(
                {
                    "event": "contract_triaged",
                    "data": {
                        **resp_dto.model_dump(mode="json"),
                        "filename": filename,
                    },
                }
            )
        except Exception as e:
            logger.debug("Triage WebSocket broadcast deferred", error=str(e))

        return triage

    def _generate_auto_tags(
        self, classification: ClassificationResult, urgency_score: int
    ) -> list[str]:
        """Generate tags based on deterministic contract signals."""
        tags: set[str] = set()

        if urgency_score >= 75:
            tags.add("urgent")
        if classification.detected_value and classification.detected_value >= 500_000:
            tags.add("high-value")
        if "uncapped_liability" in classification.risk_signals:
            tags.add("uncapped-liability")
            tags.add("requires-legal")
        if "broad_indemnity" in classification.risk_signals:
            tags.add("requires-legal")
        if "auto_renewal" in classification.risk_signals:
            tags.add("auto-renewal")
        if classification.detected_dates.get("expiration_date"):
            tags.add("fixed-term")
        if classification.contract_type == "nda":
            tags.add("standard-nda")
        elif classification.contract_type == "msa":
            tags.add("master-agreement")
        elif classification.contract_type == "amendment":
            tags.add("amendment")

        return sorted(list(tags))
