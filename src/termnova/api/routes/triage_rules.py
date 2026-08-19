"""Contract Triage Routing Rules REST API endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.api.dependencies import get_db
from termnova.triage.schemas import (
    RuleDryRunRequest,
    RuleDryRunResponse,
    TriageRuleCreate,
    TriageRuleResponse,
    TriageRuleUpdate,
)
from termnova.triage.service import InboxService

router = APIRouter(prefix="/api/v1/triage/rules", tags=["Triage Rules"])


@router.get("/", response_model=list[TriageRuleResponse])
async def list_rules(
    active_only: bool = Query(False, description="Filter to active rules only"),
    db: AsyncSession = Depends(get_db),
) -> list[TriageRuleResponse]:
    """List all triage routing rules sorted by priority."""
    service = InboxService(db)
    rules = await service.list_rules(is_active_only=active_only)
    return [TriageRuleResponse.model_validate(r) for r in rules]


@router.post("/", response_model=TriageRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    payload: TriageRuleCreate,
    db: AsyncSession = Depends(get_db),
) -> TriageRuleResponse:
    """Create a new automated contract routing rule."""
    service = InboxService(db)
    rule = await service.create_rule(payload)
    return TriageRuleResponse.model_validate(rule)


@router.put("/{rule_id}", response_model=TriageRuleResponse)
async def update_rule(
    rule_id: uuid.UUID,
    payload: TriageRuleUpdate,
    db: AsyncSession = Depends(get_db),
) -> TriageRuleResponse:
    """Update condition, action, priority, or active status of a routing rule."""
    service = InboxService(db)
    rule = await service.update_rule(rule_id, payload)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule {rule_id} not found",
        )
    return TriageRuleResponse.model_validate(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft delete / deactivate a routing rule."""
    service = InboxService(db)
    success = await service.delete_rule(rule_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule {rule_id} not found",
        )


@router.post("/test", response_model=RuleDryRunResponse)
async def test_rules(
    payload: RuleDryRunRequest,
    db: AsyncSession = Depends(get_db),
) -> RuleDryRunResponse:
    """Simulate rule evaluation on a contract document without persisting changes."""
    service = InboxService(db)
    result = await service.dry_run_rules(payload.document_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {payload.document_id} not found in triage database",
        )
    return result
