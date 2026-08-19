"""Business service layer for Contract Inbox and Routing Rules."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.db.models import Document, TriageResult, TriageRule
from termnova.triage.rule_engine import TriageRuleEngine
from termnova.triage.schemas import (
    InboxItemResponse,
    InboxStatsResponse,
    RuleDryRunResponse,
    TriageRuleCreate,
    TriageRuleUpdate,
)


class InboxService:
    """Service managing contract inbox feeds, state mutations, and routing rules."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_inbox_items(
        self,
        status: str | None = None,
        contract_type: str | None = None,
        tag: str | None = None,
        assignee: str | None = None,
        search: str | None = None,
        sort_by: str = "urgency_desc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[InboxItemResponse], int, bool]:
        """Query and paginate inbox items with flexible filtering and sorting."""
        stmt = select(TriageResult).join(Document, TriageResult.document_id == Document.id)

        # Status filter
        if status and status.lower() != "all":
            stmt = stmt.where(TriageResult.inbox_status == status.lower())
        else:
            # Default: hide archived unless explicitly requested
            if status != "archived" and status != "all":
                stmt = stmt.where(TriageResult.inbox_status != "archived")

        # Contract Type filter
        if contract_type and contract_type.lower() != "all":
            stmt = stmt.where(TriageResult.contract_type_detected == contract_type.lower())

        # Assignee filter
        if assignee:
            if assignee.lower() == "unassigned":
                stmt = stmt.where(TriageResult.assigned_to.is_(None))
            else:
                stmt = stmt.where(TriageResult.assigned_to == assignee)

        # Search filter
        if search and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(Document.filename.ilike(term))

        # Count total matches
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_count = (await self.session.execute(count_stmt)).scalar() or 0

        # Sorting
        if sort_by == "urgency_asc":
            stmt = stmt.order_by(TriageResult.urgency_score.asc(), TriageResult.created_at.desc())
        elif sort_by == "date_desc":
            stmt = stmt.order_by(TriageResult.created_at.desc())
        elif sort_by == "date_asc":
            stmt = stmt.order_by(TriageResult.created_at.asc())
        else:
            # urgency_desc (default)
            stmt = stmt.order_by(TriageResult.urgency_score.desc(), TriageResult.created_at.desc())

        # Pagination
        offset = max(0, (page - 1) * page_size)
        stmt = stmt.offset(offset).limit(page_size)

        results = list((await self.session.execute(stmt)).scalars().all())

        items: list[InboxItemResponse] = []
        for t in results:
            # In-memory tag filter if requested
            if tag and tag.lower() not in [x.lower() for x in (t.auto_tags or [])]:
                continue

            doc = t.document
            items.append(
                InboxItemResponse(
                    id=t.id,
                    document_id=t.document_id,
                    filename=doc.filename if doc else "Contract.pdf",
                    file_type=doc.file_type if doc else "pdf",
                    page_count=doc.page_count if doc else 1,
                    upload_timestamp=doc.upload_timestamp if doc else t.created_at,
                    contract_type=t.contract_type_detected,
                    type_confidence=t.type_confidence,
                    urgency_score=t.urgency_score,
                    urgency_factors=t.urgency_factors or {},
                    summary_bullets=t.summary_bullets or [],
                    action_required=t.action_required,
                    suggested_assignee=t.suggested_assignee,
                    auto_tags=t.auto_tags or [],
                    inbox_status=t.inbox_status,
                    assigned_to=t.assigned_to,
                    acknowledged_by=t.acknowledged_by,
                    acknowledged_at=t.acknowledged_at,
                    triaged_at=t.triaged_at,
                )
            )

        has_more = (offset + len(items)) < total_count
        return items, total_count, has_more

    async def get_inbox_stats(self) -> InboxStatsResponse:
        """Compute live metric distribution and KPI counts across the inbox."""
        stmt = select(TriageResult)
        all_triages = list((await self.session.execute(stmt)).scalars().all())

        stats = InboxStatsResponse()
        stats.total_count = len(all_triages)

        type_counts: dict[str, int] = {}
        tag_counts: dict[str, int] = {}

        for t in all_triages:
            status = t.inbox_status or "unreviewed"
            if status == "unreviewed":
                stats.unreviewed_count += 1
            elif status == "in_progress":
                stats.in_progress_count += 1
            elif status == "assigned":
                stats.assigned_count += 1
            elif status == "completed":
                stats.completed_count += 1
            elif status == "archived":
                stats.archived_count += 1

            # Urgency buckets
            if t.urgency_score >= 75:
                stats.high_urgency_count += 1
            elif t.urgency_score >= 40:
                stats.medium_urgency_count += 1
            else:
                stats.low_urgency_count += 1

            # Type distribution
            ctype = (t.contract_type_detected or "other").lower()
            type_counts[ctype] = type_counts.get(ctype, 0) + 1

            # Tag distribution
            for tag_item in t.auto_tags or []:
                tag_counts[tag_item] = tag_counts.get(tag_item, 0) + 1

        stats.type_distribution = type_counts
        stats.tag_distribution = tag_counts
        return stats

    async def get_triage_by_document(self, document_id: uuid.UUID) -> TriageResult | None:
        """Fetch triage result for a single document."""
        stmt = select(TriageResult).where(TriageResult.document_id == document_id)
        return (await self.session.execute(stmt)).scalars().first()

    async def assign_contract(
        self, document_id: uuid.UUID, assigned_to: str
    ) -> TriageResult | None:
        """Assign contract reviewer and set status to assigned."""
        triage = await self.get_triage_by_document(document_id)
        if not triage:
            return None

        triage.assigned_to = assigned_to
        triage.inbox_status = "assigned"
        await self.session.commit()
        await self.session.refresh(triage)
        return triage

    async def acknowledge_contract(
        self, document_id: uuid.UUID, acknowledged_by: str
    ) -> TriageResult | None:
        """Mark contract as acknowledged and in progress."""
        triage = await self.get_triage_by_document(document_id)
        if not triage:
            return None

        triage.acknowledged_by = acknowledged_by
        triage.acknowledged_at = datetime.now(UTC)
        if triage.inbox_status in ["unreviewed", "assigned"]:
            triage.inbox_status = "in_progress"

        await self.session.commit()
        await self.session.refresh(triage)
        return triage

    async def complete_contract(self, document_id: uuid.UUID) -> TriageResult | None:
        """Mark contract review as completed."""
        triage = await self.get_triage_by_document(document_id)
        if not triage:
            return None

        triage.inbox_status = "completed"
        await self.session.commit()
        await self.session.refresh(triage)
        return triage

    async def archive_contract(self, document_id: uuid.UUID) -> TriageResult | None:
        """Archive contract from active inbox view."""
        triage = await self.get_triage_by_document(document_id)
        if not triage:
            return None

        triage.inbox_status = "archived"
        await self.session.commit()
        await self.session.refresh(triage)
        return triage

    async def modify_tags(
        self, document_id: uuid.UUID, add_tags: list[str], remove_tags: list[str]
    ) -> TriageResult | None:
        """Add or remove tags on a triage item."""
        triage = await self.get_triage_by_document(document_id)
        if not triage:
            return None

        current = set(triage.auto_tags or [])
        current.update(add_tags)
        for r in remove_tags:
            current.discard(r)

        triage.auto_tags = sorted(list(current))
        await self.session.commit()
        await self.session.refresh(triage)
        return triage

    async def bulk_assign(self, document_ids: list[uuid.UUID], assigned_to: str) -> int:
        """Assign multiple contracts to a reviewer at once."""
        stmt = (
            update(TriageResult)
            .where(TriageResult.document_id.in_(document_ids))
            .values(assigned_to=assigned_to, inbox_status="assigned")
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.rowcount

    async def bulk_archive(self, document_ids: list[uuid.UUID]) -> int:
        """Archive multiple contracts at once."""
        stmt = (
            update(TriageResult)
            .where(TriageResult.document_id.in_(document_ids))
            .values(inbox_status="archived")
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.rowcount

    # ──── Routing Rules CRUD ────
    async def create_rule(self, payload: TriageRuleCreate) -> TriageRule:
        """Create a new automated triage rule."""
        rule = TriageRule(
            name=payload.name,
            condition=payload.condition,
            action=payload.action,
            priority=payload.priority,
            is_active=payload.is_active,
        )
        self.session.add(rule)
        await self.session.commit()
        await self.session.refresh(rule)
        return rule

    async def list_rules(self, is_active_only: bool = False) -> list[TriageRule]:
        """List all routing rules sorted by priority."""
        stmt = select(TriageRule).order_by(TriageRule.priority.asc())
        if is_active_only:
            stmt = stmt.where(TriageRule.is_active.is_(True))
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_rule(self, rule_id: uuid.UUID) -> TriageRule | None:
        """Get a routing rule by ID."""
        stmt = select(TriageRule).where(TriageRule.id == rule_id)
        return (await self.session.execute(stmt)).scalars().first()

    async def update_rule(self, rule_id: uuid.UUID, payload: TriageRuleUpdate) -> TriageRule | None:
        """Update routing rule attributes."""
        rule = await self.get_rule(rule_id)
        if not rule:
            return None

        if payload.name is not None:
            rule.name = payload.name
        if payload.condition is not None:
            rule.condition = payload.condition
        if payload.action is not None:
            rule.action = payload.action
        if payload.priority is not None:
            rule.priority = payload.priority
        if payload.is_active is not None:
            rule.is_active = payload.is_active

        await self.session.commit()
        await self.session.refresh(rule)
        return rule

    async def delete_rule(self, rule_id: uuid.UUID) -> bool:
        """Soft-deactivate a routing rule."""
        rule = await self.get_rule(rule_id)
        if not rule:
            return False

        rule.is_active = False
        await self.session.commit()
        return True

    async def dry_run_rules(self, document_id: uuid.UUID) -> RuleDryRunResponse | None:
        """Simulate rule evaluation on a contract without committing mutations."""
        triage = await self.get_triage_by_document(document_id)
        if not triage:
            return None

        engine = TriageRuleEngine()
        matches = await engine.evaluate_rules(self.session, triage_result=triage)

        matched_names = [m.rule_name for m in matches]
        assign_to = matches[0].assign_to if matches else None
        set_status = matches[0].set_status if matches else None
        add_tags: list[str] = []
        for m in matches:
            add_tags.extend(m.add_tags)

        return RuleDryRunResponse(
            matched_rules=matched_names,
            would_assign_to=assign_to,
            would_add_tags=list(set(add_tags)),
            would_set_status=set_status,
        )
