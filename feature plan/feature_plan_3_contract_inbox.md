# Feature Plan 3: Contract Inbox & Smart Triage

## What We're Building

An **email-inbox-style interface** for incoming contracts that automatically:
1. **Classifies** each uploaded contract by type (MSA, NDA, SOW, Amendment, etc.)
2. **Scores urgency** (0-100) based on deadline proximity, contract value, and risk indicators
3. **Generates a 3-5 bullet summary** so reviewers don't need to read the full document
4. **Suggests an assignee** based on configurable routing rules
5. **Tags automatically** with labels like "high-value", "expiring-soon", "new-vendor"

The inbox gives legal/procurement managers a single dashboard to see all incoming work, prioritize it, assign reviewers, and track progress — replacing the spreadsheet-and-email chaos most teams use today.

## Why It Matters

Enterprises receive dozens of contracts per week. Today, someone manually opens each one, reads it, figures out what type it is, who should review it, and how urgent it is. This creates bottlenecks (one person becomes the "contract traffic cop"), missed deadlines (urgent contracts buried under routine NDAs), and inconsistent handling (different people apply different standards).

---

## Architecture & Approach

### Data Flow
```
Document Upload (existing)
       ↓
Ingestion Pipeline (existing: parse → chunk → embed)
       ↓
Triage Classifier (NEW: runs after ingestion completes)
       ↓
  ┌────┴────────────────────────────┐
  │  1. Contract type detection     │
  │  2. Urgency score calculation   │
  │  3. Summary bullet generation   │
  │  4. Auto-tag assignment         │
  │  5. Routing rule evaluation     │
  └────┬────────────────────────────┘
       ↓
TriageResult saved to DB → Notification dispatched → Inbox UI updated
```

### Key Design Decisions
- **Runs automatically post-ingestion**: Triage is a Celery task chained after the existing ingestion task, not a separate user action
- **Lightweight LLM call**: Uses first ~2000 tokens of the document (title page + first sections) for classification — fast and cheap
- **Rule engine is simple JSON conditions**: No custom DSL. Conditions are JSON objects matched against triage results. Keeps it maintainable.
- **Urgency is computed, not LLM-generated**: Formula-based scoring using extracted dates + value + risk indicators for deterministic, explainable results

---

## Sub-Phase 1: Database Models & Migration

#### [NEW] `src/termnova/db/models/triage.py`

```python
"""SQLAlchemy models for contract triage — classification results and routing rules."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from termnova.db.models import Base


class TriageResult(Base):
    """AI-powered classification and routing result for an incoming contract."""

    __tablename__ = "triage_results"
    __table_args__ = (UniqueConstraint("document_id", name="uq_triage_per_document"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Classification
    contract_type_detected: Mapped[str] = mapped_column(String(50), nullable=False)
    # Values: "msa", "nda", "sow", "amendment", "lease", "employment", "vendor", "other"
    type_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    # 0.0-1.0 confidence in type detection

    # Urgency
    urgency_score: Mapped[int] = mapped_column(Integer, nullable=False)
    # 0-100, computed from deadline proximity + value + risk signals
    urgency_factors: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    # Explainability: {"deadline_days": 14, "estimated_value": 500000, "risk_signals": ["uncapped_liability"]}

    # Summary
    summary_bullets: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    # ["3-year MSA with Acme Corp", "Total value ~$2.4M", "Auto-renewal with 60-day notice", ...]
    action_required: Mapped[str] = mapped_column(Text, nullable=False)
    # "Review and sign by Aug 30" or "Standard NDA — auto-approve candidate"

    # Routing
    suggested_assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    auto_tags: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        default=list,
        server_default="{}",
        nullable=False,
    )
    # ["high-value", "expiring-soon", "new-vendor", "requires-legal"]

    # Status tracking
    inbox_status: Mapped[str] = mapped_column(String(20), default="unreviewed", nullable=False)
    # "unreviewed", "in_progress", "assigned", "completed", "archived"
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    acknowledged_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    triaged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class TriageRule(Base):
    """Organization-configurable routing rules evaluated against triage results."""

    __tablename__ = "triage_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # "Route NDAs to Legal Assistant", "Escalate high-value to VP"

    condition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Condition schema:
    # {
    #   "contract_type": "nda",           # exact match
    #   "urgency_min": 70,                # urgency >= 70
    #   "tags_include": ["high-value"],   # must have this tag
    #   "tags_exclude": ["auto-approve"], # must NOT have this tag
    # }

    action: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Action schema:
    # {
    #   "assign_to": "user_id_or_role",   # assign to specific user or role
    #   "add_tags": ["requires-legal"],    # add additional tags
    #   "set_status": "assigned",          # set inbox status
    #   "notify": ["email", "slack"],      # notification channels
    # }

    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    # Lower number = higher priority. First matching rule wins.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### Tests for Sub-Phase 1
```
tests/unit/test_triage_models.py
  - test_create_triage_result_with_all_fields
  - test_triage_result_unique_per_document
  - test_create_triage_rule_with_condition_and_action
  - test_triage_rule_priority_ordering
```

---

## Sub-Phase 2: Triage Classifier & Urgency Scorer

### 2A. Contract Type Classifier

#### [NEW] `src/termnova/triage/classifier.py`

```python
"""AI-powered contract classification and summary generation."""

import structlog
from termnova.config import Settings

logger = structlog.get_logger(__name__)

CONTRACT_TYPES = [
    "msa",
    "nda",
    "sow",
    "amendment",
    "lease",
    "employment",
    "vendor",
    "services",
    "license",
    "other",
]


class ContractClassifier:
    """Classifies contract type and generates summary from document text."""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def classify(self, document_text: str, filename: str) -> ClassificationResult:
        """
        Classify contract using two signals:
        1. Filename heuristics (fast, no LLM cost):
           - "NDA" or "Non-Disclosure" in filename → nda
           - "SOW" or "Statement of Work" → sow
           - "Amendment" or "Addendum" → amendment
           - "MSA" or "Master Service" → msa
        2. LLM classification (first ~2000 tokens):
           - Structured output with type + confidence + summary bullets
           - Only called if filename heuristic confidence < 0.8

        Returns:
            ClassificationResult with:
            - contract_type: str
            - confidence: float (0.0-1.0)
            - summary_bullets: list[str] (3-5 key points)
            - action_required: str
            - detected_dates: {effective, expiration, deadline}
            - detected_value: float | None
            - risk_signals: list[str]
        """

    def _classify_by_filename(self, filename: str) -> tuple[str, float]:
        """
        Fast heuristic classification from filename patterns.
        Returns (type, confidence).
        """
        filename_lower = filename.lower()
        patterns = {
            "nda": (["nda", "non-disclosure", "confidentiality"], 0.85),
            "sow": (["sow", "statement of work", "scope of work"], 0.85),
            "msa": (["msa", "master service", "master agreement"], 0.85),
            "amendment": (["amendment", "addendum", "modification"], 0.80),
            "lease": (["lease", "rental", "tenancy"], 0.80),
            "employment": (["employment", "offer letter", "employment agreement"], 0.80),
        }
        for contract_type, (keywords, confidence) in patterns.items():
            if any(kw in filename_lower for kw in keywords):
                return contract_type, confidence
        return "other", 0.3

    async def _classify_by_llm(self, text_snippet: str) -> ClassificationResult:
        """
        LLM-powered classification with structured output.
        Prompt extracts: type, summary, dates, value, risk signals.
        Uses first 2000 tokens only for speed.
        """
```

### 2B. Urgency Scorer

#### [NEW] `src/termnova/triage/urgency.py`

```python
"""Deterministic urgency scoring based on extracted contract signals."""

from datetime import date, timedelta


class UrgencyScorer:
    """Computes urgency score (0-100) from contract metadata."""

    @staticmethod
    def compute_urgency(
        expiration_date: date | None,
        deadline_date: date | None,
        estimated_value: float | None,
        risk_signals: list[str],
        contract_type: str,
    ) -> tuple[int, dict]:
        """
        Formula-based urgency scoring for explainability.

        Factors (each 0-25, summed to 0-100):
        1. Deadline proximity (25 pts):
           - < 7 days: 25
           - 7-14 days: 20
           - 14-30 days: 15
           - 30-60 days: 10
           - 60-90 days: 5
           - > 90 days or no deadline: 0

        2. Contract value (25 pts):
           - > $1M: 25
           - $500K-$1M: 20
           - $100K-$500K: 15
           - $50K-$100K: 10
           - < $50K: 5
           - Unknown: 10

        3. Risk signal count (25 pts):
           - 5+ signals: 25
           - 3-4: 20
           - 1-2: 10
           - 0: 0

        4. Contract type weight (25 pts):
           - amendment (existing obligation): 20
           - msa (high impact): 15
           - sow (deliverables): 15
           - lease (real estate): 10
           - nda (low complexity): 5
           - other: 10

        Returns: (score: int, factors: dict) for explainability.
        """
```

### 2C. Rule Engine

#### [NEW] `src/termnova/triage/rule_engine.py`

```python
"""Evaluate routing rules against triage results."""


class TriageRuleEngine:
    """Evaluates configurable routing rules in priority order."""

    async def evaluate_rules(
        self,
        session: AsyncSession,
        org_id: uuid.UUID,
        triage_result: TriageResult,
    ) -> list[RuleAction]:
        """
        1. Load all active rules for org, sorted by priority ASC
        2. For each rule, evaluate condition against triage result
        3. First matching rule wins (or accumulate all matches)
        4. Return list of actions to apply
        """

    def _matches_condition(self, condition: dict, triage: TriageResult) -> bool:
        """
        Evaluate a single condition dict against triage result.
        Supports:
        - "contract_type": exact match
        - "urgency_min": triage.urgency_score >= value
        - "urgency_max": triage.urgency_score <= value
        - "tags_include": all listed tags must be present
        - "tags_exclude": none of listed tags may be present
        - "confidence_min": type_confidence >= value
        """
```

### 2D. Triage Orchestrator

#### [NEW] `src/termnova/triage/orchestrator.py`

```python
"""Orchestrates the full triage pipeline: classify → score → route → notify."""


class TriageOrchestrator:
    """Runs the complete triage pipeline for a newly ingested document."""

    def __init__(self, session, settings, classifier, scorer, rule_engine): ...

    async def triage_document(
        self,
        document_id: uuid.UUID,
        org_id: uuid.UUID,
        document_text: str,
        filename: str,
    ) -> TriageResult:
        """
        Full pipeline:
        1. Classify contract type + generate summary
        2. Compute urgency score
        3. Generate auto-tags based on signals
        4. Evaluate routing rules → set assignee
        5. Persist TriageResult
        6. Dispatch notifications if rules specify
        """

    def _generate_auto_tags(self, classification: ClassificationResult, urgency: int) -> list[str]:
        """
        Generate tags based on signals:
        - urgency >= 80 → "urgent"
        - estimated_value > 500000 → "high-value"
        - expiration within 30 days → "expiring-soon"
        - no matching entity in DB → "new-vendor"
        - risk_signals contains liability items → "requires-legal"
        """
```

### Integration with Ingestion Pipeline

#### [MODIFY] `src/termnova/pipeline/tasks.py`

Chain triage after ingestion:
```python
@celery_app.task
def ingest_and_triage(file_path: str, org_id: str):
    """Ingest document, then run triage classification."""
    # Step 1: Existing ingestion
    document = await ingest_file(file_path)

    # Step 2: NEW — Run triage
    orchestrator = TriageOrchestrator(...)
    full_text = " ".join([chunk.content for chunk in document.chunks[:10]])  # First 10 chunks
    await orchestrator.triage_document(
        document_id=document.id,
        org_id=org_id,
        document_text=full_text,
        filename=document.filename,
    )
```

### Tests for Sub-Phase 2
```
tests/unit/test_classifier.py
  - test_classify_nda_by_filename
  - test_classify_msa_by_filename
  - test_classify_unknown_filename_falls_to_llm
  - test_classify_generates_summary_bullets
  - test_classify_extracts_dates_and_value

tests/unit/test_urgency_scorer.py
  - test_urgency_deadline_7_days_scores_25
  - test_urgency_deadline_90_days_scores_5
  - test_urgency_no_deadline_scores_0
  - test_urgency_high_value_scores_25
  - test_urgency_combined_factors_sum_correctly
  - test_urgency_returns_explainability_factors

tests/unit/test_rule_engine.py
  - test_matches_contract_type_condition
  - test_matches_urgency_min_condition
  - test_matches_tags_include_condition
  - test_matches_tags_exclude_condition
  - test_first_matching_rule_wins_by_priority
  - test_no_matching_rules_returns_empty

tests/unit/test_triage_orchestrator.py
  - test_full_pipeline_classifies_and_scores
  - test_auto_tags_generated_from_signals
  - test_routing_rule_sets_assignee
```

---

## Sub-Phase 3: API Endpoints

#### [NEW] `src/termnova/api/routes/inbox.py`

```python
router = APIRouter(prefix="/api/v1/inbox", tags=["Contract Inbox"])

# Inbox views
GET  /
    → Query params: status=unreviewed, sort=urgency_desc, type=nda, assignee={user_id}, tag=high-value
    → Paginated list of triaged contracts sorted by urgency
    → Response: {items: [InboxItem], total, page, has_more}
    → InboxItem includes: document info, triage result, assignee, status

GET  /stats
    → Inbox statistics for dashboard
    → Response: {
        unreviewed_count, in_progress_count, completed_today,
        avg_time_to_acknowledge_hours, urgency_distribution: {high: N, medium: N, low: N},
        type_distribution: {msa: N, nda: N, ...}
      }

# Actions on inbox items
POST /{doc_id}/assign
    → Body: {user_id}
    → Assign contract to a user, set status to "assigned"

POST /{doc_id}/acknowledge
    → Mark as reviewed by current user
    → Sets acknowledged_by, acknowledged_at, status to "in_progress"

POST /{doc_id}/complete
    → Mark as completed
    → Sets status to "completed"

POST /{doc_id}/archive
    → Archive (hide from default inbox view)
    → Sets status to "archived"

PATCH /{doc_id}/tags
    → Body: {add: ["tag1"], remove: ["tag2"]}
    → Modify auto_tags on triage result

# Bulk actions
POST /bulk-assign
    → Body: {document_ids: [...], user_id}
    → Assign multiple contracts at once

POST /bulk-archive
    → Body: {document_ids: [...]}
    → Archive multiple contracts

# Re-triage
POST /{doc_id}/retriage
    → Re-run triage classification (useful after document re-upload)
```

#### [NEW] `src/termnova/api/routes/triage_rules.py`

```python
router = APIRouter(prefix="/api/v1/triage/rules", tags=["Triage Rules"])

GET  /
    → List all routing rules for org, sorted by priority
    → Response: [TriageRuleResponse]

POST /
    → Body: {name, condition, action, priority}
    → Create new routing rule

PUT  /{rule_id}
    → Update rule condition, action, or priority

DELETE /{rule_id}
    → Deactivate rule (soft delete via is_active=False)

POST /test
    → Body: {document_id}
    → Dry-run: evaluate rules against a document's triage result without applying
    → Response: {matched_rules: [...], would_assign_to: ..., would_add_tags: [...]}
```

### Tests for Sub-Phase 3
```
tests/integration/test_inbox_api.py
  - test_inbox_list_sorted_by_urgency
  - test_inbox_filter_by_status
  - test_inbox_filter_by_contract_type
  - test_inbox_filter_by_tag
  - test_inbox_stats_returns_counts
  - test_assign_contract_updates_status
  - test_acknowledge_sets_timestamp
  - test_complete_sets_status
  - test_archive_hides_from_default_view
  - test_bulk_assign_multiple_documents
  - test_modify_tags_add_and_remove
  - test_retriage_reruns_classification
  - test_inbox_respects_org_isolation

tests/integration/test_triage_rules_api.py
  - test_create_routing_rule
  - test_list_rules_sorted_by_priority
  - test_update_rule_condition
  - test_delete_rule_deactivates
  - test_dry_run_shows_matched_rules
```

---

## Sub-Phase 4: Frontend — Inbox UI

#### [NEW] `src/termnova/static/js/inbox.js`

```javascript
// Key UI components:

// 1. Inbox List View
function renderInboxList(items, filters) { ... }
// Card-based list, each card shows:
// - Contract name + type badge (colored: MSA=blue, NDA=purple, etc.)
// - Urgency bar (green/yellow/red gradient)
// - Summary bullets (first 2 lines)
// - Suggested action text
// - Assignee avatar (or "Unassigned")
// - Tags as small pill badges
// - Time since upload ("2h ago", "Yesterday")

// 2. Filter Bar
function renderFilterBar(currentFilters) { ... }
// Horizontal filter bar:
// - Status dropdown: All / Unreviewed / In Progress / Completed
// - Type multi-select: MSA / NDA / SOW / Amendment / ...
// - Assignee dropdown: Me / Unassigned / [team members]
// - Tag filter: text input with autocomplete
// - Sort: Urgency (High→Low) / Date (Newest) / Value (Highest)

// 3. Quick Actions
function renderQuickActions(selectedItems) { ... }
// When items are checkbox-selected:
// - "Assign to..." button
// - "Archive" button
// - "Add tag..." button

// 4. Inbox Stats Bar
function renderInboxStats(stats) { ... }
// Top bar: "12 unreviewed | 5 in progress | 3 completed today | Avg response: 4.2h"
// Mini donut chart: type distribution
// Mini bar chart: urgency distribution

// 5. Detail Slide-Over
function openInboxDetail(docId) { ... }
// Slide-over panel from right side showing:
// - Full summary bullets
// - Urgency score with factor breakdown
// - Detected dates timeline
// - Risk signals list
// - Assign / Acknowledge / Complete buttons
// - Link to full document analysis
```

#### [MODIFY] `src/termnova/static/index.html`
- Add "Inbox" navigation tab (with unread badge counter)
- Badge shows count of unreviewed items

#### [NEW] `src/termnova/static/css/inbox.css`
- Card styles with urgency gradient border
- Type badge colors matching document visualizer node colors
- Tag pill styles
- Filter bar horizontal layout
- Stats bar with mini charts
- Slide-over animation

### Tests for Sub-Phase 4
```
tests/e2e/test_inbox_ui.py
  - test_inbox_page_loads_with_triaged_documents
  - test_inbox_filter_by_type_updates_list
  - test_inbox_click_card_opens_detail
  - test_inbox_assign_updates_card
  - test_inbox_badge_shows_unreviewed_count
```

---

## Verification Checklist

- [ ] `triage_results` table created with unique constraint on document_id
- [ ] `triage_rules` table created with priority ordering
- [ ] Classifier correctly identifies NDA/MSA/SOW from filename
- [ ] Classifier falls back to LLM for unknown filenames
- [ ] Summary bullets are 3-5 concise points
- [ ] Urgency score is deterministic and explainable (factors dict)
- [ ] Auto-tags generated correctly from signals
- [ ] Routing rules evaluate in priority order
- [ ] First matching rule assigns document correctly
- [ ] Triage runs automatically after ingestion pipeline
- [ ] Inbox API returns paginated, filterable results
- [ ] Bulk actions work on multiple documents
- [ ] Stats endpoint returns accurate counts
- [ ] Inbox respects org isolation
- [ ] UI renders inbox cards with urgency indicators
- [ ] `ruff check` and `ruff format --check` pass
- [ ] All tests pass
