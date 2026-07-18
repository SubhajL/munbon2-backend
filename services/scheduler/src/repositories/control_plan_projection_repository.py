"""Bounded read-model for the control-plan list projection (PR 4.4a-3).

This repository is DELIBERATELY separate from ``PostgresControlPlanRepository``:
the detail path (`_assemble`) loads the full aggregate (requirements, events,
ALL transitions, ledger, the prediction response and optimizer documents) and
re-verifies every content hash — far too much for a page of headers. The list
projection selects ONLY ``control_plan_runs`` header columns, plus a bounded
read of the small transition rows (sequence/type/from/to + the small lifecycle
document) to derive each plan's current lifecycle state and approval-trust flag.

It NEVER selects the large documents (optimizer_result, prediction response,
model snapshot, canonical input) and never touches the requirements / events /
ledger tables — so a list page can never leak a plan's heavy payload. The
per-row lifecycle state and approval-trust flag are derived in the SAME snapshot
as the header/filter query (two correlated scalar subqueries), so the state a row
is filtered on and the state it is returned with can never disagree under a
concurrent transition, and only the single ``shadow_approved`` transition document
is loaded (never the whole transition history's documents).

Keyset pagination is ordered ``created_at DESC, plan_id DESC, plan_version DESC``
with a row-value ``(created_at, plan_id, plan_version) < (cursor)`` predicate over
the row's TOTAL identity ``(plan_id, plan_version)`` and a ``limit + 1`` fetch to
decide ``next_cursor`` without a second COUNT query.
"""

from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import is_trusted_shadow_approval
from core.control_plan_cursor import (
    decode_plan_cursor,
    encode_plan_cursor,
)
from core.control_plan_lifecycle import (
    LifecycleHistoryCorruptError,
)
from models.control_plan import ControlPlanRun, ControlStateTransition
from schemas.control_plan import (
    PROJECTION_SCHEMA_VERSION,
    ControlPlanListFilters,
    ControlPlanListPage,
    ControlPlanSummaryOut,
)

# The queryable per-plan prediction CONTENT hash: the v1 full-response sha for a
# v1 row, the artifact sha for a v2 (artifact-reference) row whose response sha is
# NULL. Exposing it as one COALESCE keeps the BFF 4.4 content-hash filter and the
# served ``prediction_response_sha256`` non-null and consistent across BOTH storage
# versions. Both operands are small CHAR(64) scalars, so the projection stays
# bounded.
_PREDICTION_CONTENT_SHA256 = func.coalesce(
    ControlPlanRun.prediction_response_sha256,
    ControlPlanRun.artifact_sha256,
)

# The exact header columns a summary row is built from — small scalars only.
# Adding the large *_document_text / model_snapshot_document_text columns here
# would defeat the whole point of a bounded projection, so they are absent by
# construction (the omission is asserted by a unit test over the compiled SQL).
_SUMMARY_COLUMNS = (
    ControlPlanRun.plan_id,
    ControlPlanRun.plan_version,
    ControlPlanRun.horizon_start,
    ControlPlanRun.horizon_end,
    ControlPlanRun.requirement_run_id,
    ControlPlanRun.requirement_version,
    ControlPlanRun.input_content_hash,
    ControlPlanRun.model_snapshot_id,
    ControlPlanRun.model_release_content_hash,
    ControlPlanRun.optimizer_status,
    ControlPlanRun.prediction_status,
    ControlPlanRun.prediction_run_id,
    _PREDICTION_CONTENT_SHA256.label("prediction_response_sha256"),
    ControlPlanRun.created_by_subject,
    ControlPlanRun.created_at,
)


def _latest_state_subquery():
    """The DERIVED current lifecycle state as a correlated scalar subquery.

    A validated linear history's current state IS the terminal transition's
    ``to_state`` (exactly what ``derive_control_plan_state`` returns), so both the
    ``lifecycle_state`` filter AND the returned ``lifecycle_state`` select on the
    max-sequence ``to_state`` — from ONE statement/snapshot, so a concurrent
    transition can never leave a row filtered on one state but returned with
    another. It selects ONLY ``to_state`` (never the transition document), so the
    projection stays bounded."""
    return (
        select(ControlStateTransition.to_state)
        .where(
            ControlStateTransition.plan_id == ControlPlanRun.plan_id,
            ControlStateTransition.plan_version == ControlPlanRun.plan_version,
        )
        .order_by(ControlStateTransition.transition_sequence.desc())
        .limit(1)
        .scalar_subquery()
    )


def _shadow_approval_document_subquery():
    """The single ``shadow_approved`` transition document as a correlated scalar
    subquery.

    Restricted to ``transition_type = 'shadow_approved'`` (there is at most one
    per plan version), so a page of N plans loads at most N small approval
    documents — NEVER every transition's document. Any non-approval transition
    document stays unread."""
    return (
        select(ControlStateTransition.transition_document_text)
        .where(
            ControlStateTransition.plan_id == ControlPlanRun.plan_id,
            ControlStateTransition.plan_version == ControlPlanRun.plan_version,
            ControlStateTransition.transition_type == "shadow_approved",
        )
        .order_by(ControlStateTransition.transition_sequence.desc())
        .limit(1)
        .scalar_subquery()
    )


def _apply_filters(stmt, filters: ControlPlanListFilters):
    if filters.lifecycle_state is not None:
        stmt = stmt.where(_latest_state_subquery() == filters.lifecycle_state)
    if filters.horizon_start_gte is not None:
        stmt = stmt.where(ControlPlanRun.horizon_start >= filters.horizon_start_gte)
    if filters.horizon_end_lte is not None:
        stmt = stmt.where(ControlPlanRun.horizon_end <= filters.horizon_end_lte)
    if filters.requirement_run_id is not None:
        stmt = stmt.where(
            ControlPlanRun.requirement_run_id == filters.requirement_run_id
        )
    if filters.requirement_version is not None:
        stmt = stmt.where(
            ControlPlanRun.requirement_version == filters.requirement_version
        )
    if filters.input_content_hash is not None:
        stmt = stmt.where(
            ControlPlanRun.input_content_hash == filters.input_content_hash
        )
    if filters.model_snapshot_id is not None:
        stmt = stmt.where(
            ControlPlanRun.model_snapshot_id == filters.model_snapshot_id
        )
    if filters.model_release_content_hash is not None:
        stmt = stmt.where(
            ControlPlanRun.model_release_content_hash
            == filters.model_release_content_hash
        )
    if filters.prediction_run_id is not None:
        stmt = stmt.where(
            ControlPlanRun.prediction_run_id == filters.prediction_run_id
        )
    if filters.prediction_content_sha256 is not None:
        stmt = stmt.where(
            _PREDICTION_CONTENT_SHA256 == filters.prediction_content_sha256
        )
    return stmt


def build_summary_query(
    filters: ControlPlanListFilters,
    keyset: Optional[tuple],
    limit: int,
):
    """The bounded keyset SELECT: header columns + the derived lifecycle state and
    the single shadow-approval document (both correlated scalar subqueries from the
    SAME snapshot), filtered, keyset-bounded, ordered ``created_at DESC, plan_id
    DESC, plan_version DESC``, fetching ``limit + 1``."""
    stmt = select(
        *_SUMMARY_COLUMNS,
        _latest_state_subquery().label("derived_state"),
        _shadow_approval_document_subquery().label(
            "shadow_approval_document_text"
        ),
    )
    stmt = _apply_filters(stmt, filters)
    if keyset is not None:
        cursor_created_at, cursor_plan_id, cursor_plan_version = keyset
        stmt = stmt.where(
            tuple_(
                ControlPlanRun.created_at,
                ControlPlanRun.plan_id,
                ControlPlanRun.plan_version,
            )
            < tuple_(cursor_created_at, cursor_plan_id, cursor_plan_version)
        )
    return stmt.order_by(
        ControlPlanRun.created_at.desc(),
        ControlPlanRun.plan_id.desc(),
        ControlPlanRun.plan_version.desc(),
    ).limit(limit + 1)


def _approval_trust_from_document(document_text: Optional[str]) -> bool:
    """True iff the single loaded ``shadow_approved`` document is a TRUSTED
    (strict-policy v2) approval.

    No shadow_approved transition (``document_text`` is None/empty), a legacy v1
    freeze, a compat-mode v2 document, or an unparseable document all read as
    untrusted — the projection never upgrades an unverifiable approval to
    trusted."""
    if not document_text:
        return False
    try:
        document = json.loads(document_text)
    except ValueError:
        return False
    return is_trusted_shadow_approval(document)


class PostgresControlPlanProjectionRepository:
    """Header-only list read model. Twin-checked against the in-memory fake by
    ``test_control_plan_projection`` (both expose the same ``list_plan_summaries``
    signature and pagination semantics)."""

    async def list_plan_summaries(
        self,
        session: AsyncSession,
        *,
        filters: ControlPlanListFilters,
        cursor: Optional[str],
        limit: int,
    ) -> ControlPlanListPage:
        identity = filters.cursor_identity()
        keyset = (
            decode_plan_cursor(cursor, identity) if cursor is not None else None
        )
        rows = (
            await session.execute(build_summary_query(filters, keyset, limit))
        ).all()
        has_more = len(rows) > limit
        page_rows = rows[:limit]

        items = []
        for row in page_rows:
            if row.derived_state is None:
                # A run with no transition history at all is impossible under the
                # atomic store (draft_created lands with the run) — treat a null
                # derived state as fail-closed corruption (503), never a 500.
                raise LifecycleHistoryCorruptError(
                    f"control plan {row.plan_id} v{row.plan_version} has no "
                    "transition history"
                )
            items.append(
                ControlPlanSummaryOut(
                    plan_id=row.plan_id,
                    plan_version=row.plan_version,
                    lifecycle_state=row.derived_state,
                    approval_trust=_approval_trust_from_document(
                        row.shadow_approval_document_text
                    ),
                    horizon_start=row.horizon_start,
                    horizon_end=row.horizon_end,
                    requirement_run_id=row.requirement_run_id,
                    requirement_version=row.requirement_version,
                    input_content_hash=row.input_content_hash,
                    model_snapshot_id=row.model_snapshot_id,
                    model_release_content_hash=row.model_release_content_hash,
                    optimizer_status=row.optimizer_status,
                    prediction_status=row.prediction_status,
                    prediction_run_id=row.prediction_run_id,
                    prediction_response_sha256=row.prediction_response_sha256,
                    created_by_subject=row.created_by_subject,
                    created_at=row.created_at,
                )
            )

        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = encode_plan_cursor(
                last.created_at, last.plan_id, last.plan_version, identity
            )
        return ControlPlanListPage(
            items=items,
            next_cursor=next_cursor,
            projection_schema_version=PROJECTION_SCHEMA_VERSION,
        )
