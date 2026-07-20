"""PR 6.3a — the shadow dispatcher.

One bounded unit of work: drive 5.2's claim path, then for each CLAIMED, not-yet-receipted
command-intent, POST it to SCADA's validation-only endpoint and persist the durable
ValidationReceipt exactly once. It NEVER calls an execute/actuate route — the injected
``scada_client`` is a validation-only client with no execute method or URL, by construction.

Fail-closed / dark-by-default: a ``None`` ``scada_client`` (SCADA URL or service secret
unset) dispatches nothing; the 5.2 mode gate (disabled → dark, operator_approved → refused)
is delegated to ``advance_open_loop_execution``. Restart-safe: re-running the tick replays
SCADA's idempotent receipt and the ON CONFLICT persistence is a no-op.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID

from core.logger import get_logger
from repositories.control_plan_repository import ValidationReceiptRow
from services.clients.scada_client_errors import (
    ScadaClientError,
    ScadaUnavailableError,
)
from services.open_loop_execution_service import ExecutionModeNotEnabledError

logger = get_logger(__name__)


@dataclass(frozen=True)
class ReceiptOutcome:
    persisted: bool
    failure: Optional[Tuple[str, str]]  # (kind, detail) or None


@dataclass(frozen=True)
class DispatchReport:
    action: str  # dark | refused | disabled | not_active | invalidated | held | dispatched
    dispatched_intent_ids: tuple
    persisted_receipts: int
    failures: tuple


def _parse_utc_instant(instant: str) -> datetime:
    """Parse a contract UtcInstant (``…Z``) to an aware UTC datetime for a TIMESTAMPTZ."""
    return datetime.fromisoformat(instant.replace("Z", "+00:00"))


class ShadowDispatchService:
    def __init__(
        self,
        repository,
        scada_client,
        open_loop_service,
        *,
        clock=None,
        worker_id: str = "scheduler-dispatch",
    ):
        self._repository = repository
        self._scada_client = scada_client  # ScadaValidationClient | None (None => dark)
        self._open_loop = open_loop_service
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._worker_id = worker_id

    async def run_shadow_dispatch_once(
        self, session, plan_id, plan_version
    ) -> DispatchReport:
        """One dispatch tick for a plan. Dark unless a SCADA client is configured. Drives
        5.2's ``advance`` (the single claim path — never re-claims), then dispatches every
        claimed, not-yet-receipted intent. Returns a report; NEVER actuates."""
        if self._scada_client is None:
            return DispatchReport("dark", (), 0, ())
        try:
            advance = await self._open_loop.advance_open_loop_execution(
                session, plan_id, plan_version, worker_id=self._worker_id, now=self._clock()
            )
        except ExecutionModeNotEnabledError:
            # operator_approved (7.x execute path) must never dispatch in 6.3 — fail closed.
            return DispatchReport("refused", (), 0, ())
        if advance.action != "claimed":
            # disabled (dark) / not_active / invalidated / held — nothing to dispatch.
            return DispatchReport(advance.action, (), 0, ())

        dispatchable = await self._repository.load_dispatchable_intents(
            session, plan_id, plan_version
        )
        # Release the read snapshot BEFORE the per-intent SCADA round-trips (the DTOs are fully
        # materialized) so the pooled connection is not idle-in-transaction across the network.
        await session.commit()

        dispatched: list = []
        persisted = 0
        failures: list = []
        for intent in dispatchable:
            # Per-intent isolation: one poisoned intent (a malformed stored document, a DB blip)
            # must never abort the whole tick and starve the other intents/plans. A committed
            # receipt is durable; re-dispatch is idempotent, so continuing is always safe.
            try:
                outcome = await self.dispatch_validation_intent(session, intent)
            except Exception as error:  # noqa: BLE001 - deliberately isolate one intent
                logger.error(
                    "shadow dispatch of intent {} raised, isolating it: {}",
                    intent.intent_id,
                    str(error),
                )
                failures.append((intent.intent_id, ("dispatch_error", str(error))))
                continue
            dispatched.append(intent.intent_id)
            if outcome.persisted:
                persisted += 1
            if outcome.failure is not None:
                failures.append((intent.intent_id, outcome.failure))
        return DispatchReport(
            "dispatched", tuple(dispatched), persisted, tuple(failures)
        )

    async def dispatch_validation_intent(self, session, intent) -> ReceiptOutcome:
        """Validate ONE claimed intent against SCADA and persist its receipt exactly once.

        Terminal outcomes (200 accepted/rejected AND 409 idempotency_conflict) DO carry a valid
        echoed ValidationReceipt, so they are persisted (the 409 is a durable `validation_rejected`
        / idempotency_conflict — it terminates the intent so it drops out of the dispatchable set,
        NOT re-attempted forever).

        Transient / unresolvable-here outcomes persist NOTHING: 503/timeout is retried next tick
        (SCADA replays its idempotent receipt); a 401 (token/clock/config) heals when fixed. A 422
        schema_invalid or a contract/echo violation leaves NO persistable receipt — it is
        unreachable absent a Python<->Ajv schema drift or SCADA corruption (the outbox intent
        already passed the IDENTICAL frozen schema at compile time), so it is re-attempted LOUDLY
        once per tick (the tick interval is the backoff) until the source drift is fixed. A bounded
        dead-letter for those is a PR 6.4 (observability) concern."""
        document = json.loads(intent.intent_document_text)
        now = self._clock()
        try:
            result = await self._scada_client.validate_intent(
                document,
                expected_content_hash=intent.intent_content_hash,
                intent_id=str(intent.intent_id),
                idempotency_key=intent.idempotency_key,
            )
        except ScadaUnavailableError as error:
            # Retryable: persist nothing so the next tick re-dispatches.
            logger.warning(
                "shadow dispatch of intent {} deferred (SCADA unavailable): {}",
                intent.intent_id,
                str(error),
            )
            return ReceiptOutcome(False, ("unavailable", str(error)))
        except ScadaClientError as error:
            logger.error(
                "shadow dispatch of intent {} failed ({}): {}",
                intent.intent_id,
                type(error).__name__,
                str(error),
            )
            return ReceiptOutcome(False, (type(error).__name__, str(error)))

        if result.conflict:
            # 409 idempotency_conflict: NOT a success, but SCADA returned a valid echoed
            # `validation_rejected`/idempotency_conflict receipt — persist it (below) so this
            # terminal outcome drops the intent out of the dispatchable set rather than being
            # re-POSTed every tick forever. (Unreachable absent SCADA store corruption, since the
            # outbox idempotency_key is content-addressed + immutable.)
            logger.error(
                "shadow dispatch of intent {} hit an idempotency conflict at SCADA (recording it)",
                intent.intent_id,
            )

        receipt = result.receipt
        row = ValidationReceiptRow(
            intent_id=intent.intent_id,
            plan_id=intent.plan_id,
            plan_version=intent.plan_version,
            receipt_id=UUID(str(receipt.receipt_id)),
            correlation_id=intent.correlation_id,
            request_id=intent.request_id,
            idempotency_key=intent.idempotency_key,
            intent_content_hash=intent.intent_content_hash,
            capability_hash=receipt.capability_hash,
            status=result.status,
            reason_code=receipt.reason_code,
            validated_at=_parse_utc_instant(receipt.validated_at),
            receipt_document_text=result.receipt_document_text,
            receipt_content_sha256=hashlib.sha256(
                result.receipt_document_text.encode("utf-8")
            ).hexdigest(),
            dispatch_worker_id=self._worker_id,
            dispatched_at=now,
        )
        inserted = await self._repository.record_validation_receipt(session, row)
        # A 409 is persisted (terminates the intent) but is still surfaced as a failure for
        # telemetry — it is never a healthy validation.
        failure = ("idempotency_conflict", "SCADA 409") if result.conflict else None
        return ReceiptOutcome(inserted, failure)

    async def aclose(self) -> None:
        """Close the underlying SCADA HTTP client (no-op when dark)."""
        if self._scada_client is not None:
            await self._scada_client.aclose()
