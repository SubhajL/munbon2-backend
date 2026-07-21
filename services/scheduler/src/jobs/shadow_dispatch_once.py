"""PR 6.3a — the shadow-dispatch tick entrypoint (``python -m jobs.shadow_dispatch_once``).

The "loop" is the EXTERNAL supervisor (PM2/systemd/cron) invoking this bounded tick — NOT an
in-process asyncio loop (the scheduler has no background-task/graceful-shutdown infra, and a
loop here would be the first, racing DB-pool teardown). Restart-safe: each run re-dispatches
claimed-but-unreceipted intents and SCADA replays its idempotent receipts.

DARK-by-default: unless BOTH a SCADA base URL and the dedicated service secret are configured,
``build_scada_validation_client`` returns None and the dispatcher dispatches nothing.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Callable, Optional

from core.config import Settings, settings as default_settings
from core.logger import get_logger
from core.service_token import mint_scheduler_service_token
from core.device_capabilities import load_device_capability_snapshot
from services.clients.scada_client_errors import ScadaClientError
from services.clients.scada_readback_client import ScadaReadbackClient
from services.clients.scada_validation_client import ScadaValidationClient
from services.open_loop_execution_service import OpenLoopExecutionService
from services.readback_reconciliation_service import ReadbackReconciliationService
from services.shadow_dispatch_service import ShadowDispatchService
from services.clients.scada_execution_client import ScadaExecutionClient
from services.operator_approved_dispatch_service import OperatorApprovedDispatchService

logger = get_logger(__name__)


def _service_token_provider(
    settings: Settings, clock: Callable[[], datetime], *, scope: str
):
    return lambda: mint_scheduler_service_token(
        secret=settings.scheduler_service_jwt_secret,
        issuer=settings.scheduler_service_jwt_issuer,
        audience=settings.scheduler_service_jwt_audience,
        subject=settings.scheduler_service_jwt_subject,
        now=clock(),
        max_age_seconds=settings.scheduler_service_jwt_max_age_seconds,
        scope=scope,
    )


def build_scada_validation_client(
    settings: Settings,
    *,
    clock: Callable[[], datetime],
    http_client=None,
) -> Optional[ScadaValidationClient]:
    """Build the SCADA validation client, or None (dark) when the base URL or the dedicated
    service secret is unset. The token provider mints a FRESH short-lived token per call.
    """
    base_url = settings.scheduler_scada_base_url
    if not base_url or not settings.scheduler_service_jwt_secret:
        return None
    return ScadaValidationClient(
        base_url,
        _service_token_provider(settings, clock, scope="command_intents.validate"),
        client=http_client,
    )


def build_readback_client(
    settings: Settings,
    *,
    clock: Callable[[], datetime],
    http_client=None,
) -> Optional[ScadaReadbackClient]:
    """Build the SCADA readback client, or None (dark) when the base URL/service secret is unset —
    the SAME service token the validation client uses (the scheduler holds no operator creds).
    """
    base_url = settings.scheduler_scada_base_url
    if not base_url or not settings.scheduler_service_jwt_secret:
        return None
    return ScadaReadbackClient(
        base_url,
        _service_token_provider(settings, clock, scope="gate_readback.read"),
        client=http_client,
    )


def build_scada_execution_client(
    settings: Settings, *, http_client=None
) -> Optional[ScadaExecutionClient]:
    if (
        not settings.scheduler_scada_base_url
        or not settings.scheduler_service_jwt_secret
    ):
        return None
    return ScadaExecutionClient(settings.scheduler_scada_base_url, client=http_client)


def build_operator_dispatch_service(
    settings: Settings,
    repository,
    *,
    snapshot,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    http_client=None,
) -> OperatorApprovedDispatchService:
    return OperatorApprovedDispatchService(
        repository,
        build_scada_execution_client(settings, http_client=http_client),
        snapshot=snapshot,
        execution_mode=settings.control_execution_mode,
        clock=clock,
        token_settings=settings,
    )


def build_shadow_dispatch_service(
    settings: Settings,
    repository,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    http_client=None,
) -> ShadowDispatchService:
    """Wire a dispatch service from settings. Its SCADA client is None (dark) unless configured."""
    scada_client = build_scada_validation_client(
        settings, clock=clock, http_client=http_client
    )
    # Thread the INJECTED settings' execution mode through (do not let the open-loop service
    # silently read the module-global singleton — a caller passing a distinct Settings must win).
    open_loop = OpenLoopExecutionService(
        repository, clock=clock, execution_mode=settings.control_execution_mode
    )
    return ShadowDispatchService(repository, scada_client, open_loop, clock=clock)


async def dispatch_active_plans(
    service: ShadowDispatchService, session, repository
) -> list:
    """Run one dispatch tick for every currently shadow-active plan; return the reports.
    Per-plan isolation: a plan that raises is logged and skipped so it never starves the
    other shadow-active plans (a committed receipt is durable; re-dispatch is idempotent).
    """
    reports = []
    for plan_id, plan_version in await repository.load_active_shadow_plan_keys(session):
        try:
            reports.append(
                await service.run_shadow_dispatch_once(session, plan_id, plan_version)
            )
        except Exception as error:  # noqa: BLE001 - isolate one plan from the others
            logger.error(
                "shadow dispatch tick for plan {} v{} failed, isolating it: {}",
                plan_id,
                plan_version,
                str(error),
            )
    return reports


async def dispatch_operator_active_plans(service, session, repository) -> list:
    reports = []
    for plan_id, plan_version in await repository.load_active_shadow_plan_keys(session):
        try:
            reports.append(
                await service.run_execute_dispatch_once(session, plan_id, plan_version)
            )
        except Exception as error:  # noqa: BLE001 - isolate one plan from the others
            logger.error(
                "operator execution tick for plan {} v{} failed, isolating it: {}",
                plan_id,
                plan_version,
                str(error),
            )
        finally:
            # The execution service takes transaction-scoped lifecycle/grant locks.
            # Early actions (pending/held/complete) intentionally write nothing, so
            # they have no repository commit to release those locks.
            await session.rollback()
    return reports


def build_readback_reconciliation_service(
    settings: Settings,
    repository,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> ReadbackReconciliationService:
    """Wire the readback reconciler from settings (mode = ``control_readback_reconciliation_mode``)."""
    open_loop = OpenLoopExecutionService(
        repository, clock=clock, execution_mode=settings.control_execution_mode
    )
    return ReadbackReconciliationService(
        repository,
        open_loop,
        mode=settings.control_readback_reconciliation_mode,
        clock=clock,
    )


async def reconcile_active_plans(
    service: ReadbackReconciliationService,
    readback_client,
    session,
    repository,
    *,
    baselines,
) -> list:
    """Reconcile every active plan's readback against its baseline. ``baselines`` maps
    ``(plan_id, plan_version) -> {canonical_gate_id: expected_level}``; the baseline SOURCE is
    D6-gated, so with the default empty map this is a no-op even in observe/enforce. Per-plan
    isolation so one plan's reconcile error never starves the others."""
    # Dark when no client; and — critically — DON'T touch SCADA when there is nothing to
    # reconcile (the baseline source is D6-gated, so `baselines` is empty today). This keeps the
    # readback endpoint un-polled until real baselines exist.
    if readback_client is None or not baselines:
        return []
    try:
        readings = await readback_client.get_gate_readback()
    except ScadaClientError as error:
        # Best-effort sidecar: a readback outage must NEVER fail the dispatch tick (which has
        # already committed) or starve the plans. Skip reconciliation this tick.
        logger.error(
            "readback fetch failed, skipping reconciliation this tick: {}", str(error)
        )
        return []
    reports = []
    for plan_id, plan_version in await repository.load_active_shadow_plan_keys(session):
        try:
            reports.append(
                await service.reconcile_plan_readback(
                    session,
                    plan_id,
                    plan_version,
                    readings=readings,
                    expected_levels=baselines.get((plan_id, plan_version), {}),
                )
            )
        except Exception as error:  # noqa: BLE001 - isolate one plan from the others
            logger.error(
                "readback reconcile for plan {} v{} failed, isolating it: {}",
                plan_id,
                plan_version,
                str(error),
            )
    return reports


async def main() -> None:  # pragma: no cover - external glue (parts are unit-tested)
    from core.database import AsyncSessionLocal
    from repositories.control_plan_repository import PostgresControlPlanRepository

    repository = PostgresControlPlanRepository()
    operator_mode = (
        default_settings.control_execution_mode == "operator_approved_open_loop"
    )
    service = (
        build_operator_dispatch_service(
            default_settings,
            repository,
            snapshot=load_device_capability_snapshot(os.environ),
        )
        if operator_mode
        else build_shadow_dispatch_service(default_settings, repository)
    )
    # Readback reconciliation is DARK unless its mode is on (default off). The baseline source is
    # D6-gated, so it is a no-op until real per-gate baselines are supplied.
    reconcile_on = default_settings.control_readback_reconciliation_mode != "off"
    readback_client = (
        build_readback_client(
            default_settings, clock=lambda: datetime.now(timezone.utc)
        )
        if reconcile_on
        else None
    )
    reconciler = (
        build_readback_reconciliation_service(default_settings, repository)
        if reconcile_on
        else None
    )
    try:
        async with AsyncSessionLocal() as session:
            reports = (
                await dispatch_operator_active_plans(service, session, repository)
                if operator_mode
                else await dispatch_active_plans(service, session, repository)
            )
            if reconciler is not None:
                # Best-effort sidecar: reconciliation must never fail the (already-committed)
                # dispatch tick. baselines is empty until the D6 baseline source lands.
                try:
                    await reconcile_active_plans(
                        reconciler, readback_client, session, repository, baselines={}
                    )
                except (
                    Exception
                ) as error:  # noqa: BLE001 - reconciliation is best-effort
                    logger.error(
                        "readback reconciliation tick failed (isolated): {}", str(error)
                    )
    finally:
        if hasattr(service, "aclose"):
            await service.aclose()
        if readback_client is not None:
            await readback_client.aclose()

    # Heartbeat: prove the tick ran so readiness (armed mode) can tell a live-but-idle worker
    # from a dead one. Best-effort, in its own connection — it can never fail the (already-
    # committed) dispatch tick above. Only written when the tick reached here (a crashed tick
    # writes no beat → readiness fails closed, which is correct). EVERYTHING (import, connect,
    # write, AND disconnect) is inside the guard — a failure in any of them, including the
    # disconnect in the finally, is swallowed so it can never fail the tick process.
    try:
        from core.redis import get_redis
        from core.worker_heartbeat import record_dispatch_heartbeat

        redis = await get_redis()
        try:
            await redis.connect()
            await record_dispatch_heartbeat(redis, now=datetime.now(timezone.utc))
        finally:
            await redis.disconnect()
    except Exception as error:  # noqa: BLE001 - heartbeat is best-effort
        logger.error("dispatch heartbeat step failed (non-fatal): {}", str(error))

    if operator_mode:
        logger.info(
            "operator execution tick complete: {} plan(s) ticked, actions={}",
            len(reports),
            [report.action for report in reports],
        )
    else:
        persisted = sum(r.persisted_receipts for r in reports)
        failures = sum(len(r.failures) for r in reports)
        logger.info(
            "shadow dispatch tick complete: {} plan(s) ticked, {} receipt(s) persisted, "
            "{} failure(s)",
            len(reports),
            persisted,
            failures,
        )


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
