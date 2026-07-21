from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Callable, Optional
from uuid import UUID, uuid4

from core.authority_grant import (
    ExecutionAuthorityError,
    derive_authority_grant_status,
    verify_command_intent_row,
    verify_execution_authority,
    verify_fail_safe_close_authority,
)
from core.canonical_json import canonicalize, sha256_hex
from core.config import settings as default_settings
from core.control_plan_lifecycle import derive_control_plan_state
from core.operator_approved_execution import promote_command_intent
from core.open_loop_execution import is_plan_held
from core.service_token import mint_scheduler_service_token
from repositories.control_plan_repository import ExecutionEventRow, ExecutionReceiptRow
from services.clients.scada_client_errors import ScadaClientError

EXECUTION_MODE_OPERATOR_APPROVED = "operator_approved_open_loop"


@dataclass(frozen=True)
class ExecuteDispatchReport:
    action: str
    intent_id: Optional[UUID] = None


class OperatorApprovedDispatchService:
    def __init__(
        self,
        repository,
        scada_client,
        *,
        snapshot,
        execution_mode: str,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        authority_verifier=verify_execution_authority,
        fail_safe_verifier=verify_fail_safe_close_authority,
        token_minter=mint_scheduler_service_token,
        token_settings=default_settings,
        worker_id: str = "scheduler-operator-approved-dispatcher",
    ):
        self._repository = repository
        self._scada = scada_client
        self._snapshot = snapshot
        self._mode = execution_mode
        self._clock = clock
        self._verify = authority_verifier
        self._verify_fail_safe = fail_safe_verifier
        self._token_minter = token_minter
        self._token_settings = token_settings
        self._worker_id = worker_id

    async def aclose(self) -> None:
        if self._scada is not None:
            await self._scada.aclose()

    async def run_execute_dispatch_once(
        self, session, plan_id: UUID, plan_version: int
    ) -> ExecuteDispatchReport:
        if self._mode != EXECUTION_MODE_OPERATOR_APPROVED:
            return ExecuteDispatchReport("disabled")
        loaded = await self._repository.load_authority_grant_for_plan(
            session, plan_id, plan_version
        )
        if loaded is None:
            return ExecuteDispatchReport("no_authority")
        grant, _ = loaded
        await self._repository.acquire_authority_execution_lock(session, grant.grant_id)

        # Reload every authority input after both locks. The locks are deliberately held
        # across the bounded SCADA request so revoke/supersede cannot race the write.
        grant, events = await self._repository.load_authority_grant_for_plan(
            session, plan_id, plan_version
        )
        record = await self._repository.load_draft_plan(session, plan_id, plan_version)
        outbox = tuple(
            await self._repository.load_command_outbox(session, plan_id, plan_version)
        )
        now = self._clock()
        context = SimpleNamespace(
            plan_id=record.plan_id,
            plan_version=record.plan_version,
            model_release_id=record.model_release_id,
            model_release_content_hash=record.model_release_content_hash,
            engine_descriptor_content_hash=record.engine_descriptor_content_hash,
            capability_release_id=self._snapshot.capability_release_id,
            capability_hash=self._snapshot.capability_hash,
            derived_lifecycle_state=derive_control_plan_state(record.transitions),
            intents=outbox,
        )
        executed = await self._repository.load_executed_intent_ids(
            session, plan_id, plan_version
        )
        remaining = tuple(row for row in outbox if row.intent_id not in executed)
        if not remaining:
            return ExecuteDispatchReport("complete")
        pending = remaining[0]
        open_loop = await self._repository.load_open_loop_context(
            session, plan_id, plan_version
        )
        held = is_plan_held(open_loop.events)

        purpose = "operator_approved"
        authority_not_after = None
        try:
            self._verify(grant, events, context, now=now)
            authority_not_after = derive_authority_grant_status(
                events, now
            ).effective_expires_at
        except ExecutionAuthorityError as error:
            if not held:
                await self._hold_without_receipt(
                    session,
                    plan_id,
                    plan_version,
                    f"execution authority refused: {error}",
                    now,
                )
                return ExecuteDispatchReport("held", pending.intent_id)
            if error.reason_code != "grant_not_active":
                return ExecuteDispatchReport("held", pending.intent_id)
            pending = next(
                (
                    row
                    for row in remaining
                    if row.event_kind == "close" and row.target_position_m == 0
                ),
                pending,
            )
            try:
                self._verify_fail_safe(
                    grant,
                    events,
                    context,
                    selected_intent_id=pending.intent_id,
                    is_held=held,
                    now=now,
                )
            except ExecutionAuthorityError:
                return ExecuteDispatchReport("held", pending.intent_id)
            purpose = "fail_safe_close"
            authority_not_after = now + timedelta(
                seconds=self._token_settings.scheduler_service_jwt_max_age_seconds
            )
        if purpose == "operator_approved" and held:
            return ExecuteDispatchReport("held", pending.intent_id)

        if purpose == "operator_approved" and now < pending.not_before:
            return ExecuteDispatchReport("pending", pending.intent_id)
        if purpose == "operator_approved" and now >= pending.deadline:
            await self._hold_without_receipt(
                session,
                plan_id,
                plan_version,
                "operator execution deadline expired",
                now,
            )
            return ExecuteDispatchReport("held", pending.intent_id)

        original = verify_command_intent_row(pending)
        promotion = promote_command_intent(original)
        assert authority_not_after is not None
        token_lifetime_seconds = min(
            self._token_settings.scheduler_service_jwt_max_age_seconds,
            int((authority_not_after - now).total_seconds()),
        )
        if token_lifetime_seconds <= 0:
            await self._hold_without_receipt(
                session,
                plan_id,
                plan_version,
                "execution authority expired before dispatch",
                now,
            )
            return ExecuteDispatchReport("held", pending.intent_id)
        authority_not_after_text = (
            authority_not_after.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
        request_document = {
            "intent": promotion.intent.model_dump(),
            "grant_id": str(grant.grant_id),
            "authority_not_after": authority_not_after_text,
            "original_intent_content_hash": promotion.original_intent_content_hash,
            "execution_intent_content_hash": promotion.execution_intent_content_hash,
            "purpose": purpose,
        }
        token = self._token_minter(
            secret=self._token_settings.scheduler_service_jwt_secret or "",
            issuer=self._token_settings.scheduler_service_jwt_issuer,
            audience=self._token_settings.scheduler_service_jwt_audience,
            subject=self._token_settings.scheduler_service_jwt_subject,
            now=now,
            max_age_seconds=token_lifetime_seconds,
            scope=(
                "command_intents.execute"
                if purpose == "operator_approved"
                else "command_intents.fail_safe_close"
            ),
            jti=str(uuid4()),
            grant_id=str(grant.grant_id),
            authority_not_after=authority_not_after_text,
            intent_id=str(pending.intent_id),
            original_intent_content_hash=promotion.original_intent_content_hash,
            execution_intent_content_hash=promotion.execution_intent_content_hash,
            purpose=purpose,
        )
        if self._scada is None:
            await self._hold_without_receipt(
                session, plan_id, plan_version, "SCADA execution client is dark", now
            )
            return ExecuteDispatchReport("held", pending.intent_id)
        try:
            result = await self._scada.execute_intent(
                request_document,
                token=token,
                intent_id=str(pending.intent_id),
                idempotency_key=pending.idempotency_key,
                grant_id=str(grant.grant_id),
                authority_not_after=authority_not_after_text,
                original_intent_content_hash=promotion.original_intent_content_hash,
                execution_intent_content_hash=promotion.execution_intent_content_hash,
            )
        except ScadaClientError as error:
            await self._hold_without_receipt(
                session,
                plan_id,
                plan_version,
                f"SCADA execution uncertainty: {error}",
                now,
            )
            return ExecuteDispatchReport("held", pending.intent_id)

        receipt = result.receipt
        row = ExecutionReceiptRow(
            intent_id=UUID(receipt.intent_id),
            plan_id=plan_id,
            plan_version=plan_version,
            grant_id=grant.grant_id,
            authority_not_after=datetime.fromisoformat(
                receipt.authority_not_after.replace("Z", "+00:00")
            ),
            receipt_id=UUID(receipt.receipt_id),
            idempotency_key=receipt.idempotency_key,
            original_intent_content_hash=receipt.original_intent_content_hash,
            execution_intent_content_hash=receipt.execution_intent_content_hash,
            capability_hash=receipt.capability_hash,
            purpose=receipt.purpose,
            status=receipt.status,
            reason_code=receipt.reason_code,
            target_level=receipt.target_level,
            observed_level=receipt.observed_level,
            readback_quality=receipt.readback_quality,
            writes_document_text=canonicalize(
                [write.model_dump() for write in receipt.writes]
            ),
            executed_at=datetime.fromisoformat(
                receipt.executed_at.replace("Z", "+00:00")
            ),
            receipt_document_text=result.receipt_document_text,
            receipt_content_sha256=sha256_hex(result.receipt_document_text),
            dispatch_worker_id=self._worker_id,
            dispatched_at=self._clock(),
        )
        hold = None
        if receipt.status != "execution_succeeded":
            hold = self._hold_event(
                f"machine execution stopped: {receipt.status}/{receipt.reason_code}",
                self._clock(),
            )
        await self._repository.record_execution_receipt(session, row, hold_event=hold)
        return ExecuteDispatchReport(
            "executed" if hold is None else "held", pending.intent_id
        )

    def _hold_event(self, reason: str, now: datetime) -> ExecutionEventRow:
        return ExecutionEventRow(
            event_id=uuid4(),
            intent_id=None,
            event_type="held",
            worker_id=self._worker_id,
            detail_document_text=reason,
            occurred_at=now,
        )

    async def _hold_without_receipt(self, session, plan_id, plan_version, reason, now):
        await self._repository.append_execution_events(
            session, plan_id, plan_version, [self._hold_event(reason, now)]
        )
