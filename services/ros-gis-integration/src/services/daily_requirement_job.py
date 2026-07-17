"""Scheduled orchestration for canonical daily requirement publication."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from services.daily_requirement_producer import (
    calculate_daily_water_requirements,
    requirement_run_content_hash,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DailyRequirementJobResult:
    status: Literal["published", "deduplicated"]
    run_id: UUID
    as_of_date: date
    requirement_count: int


class DailyRequirementJob:
    def __init__(
        self,
        *,
        run_store,
        source_loader,
        publisher,
        cron: str,
        timezone_name: str,
        horizon_days: int,
    ):
        self.run_store = run_store
        self.source_loader = source_loader
        self.publisher = publisher
        self.cron = cron
        self.timezone_name = timezone_name
        self.horizon_days = horizon_days
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    async def run_once(
        self,
        as_of_date: date,
        now: datetime | None = None,
    ) -> DailyRequirementJobResult:
        computed_at = datetime.now(timezone.utc) if now is None else now
        if computed_at.tzinfo is None or computed_at.utcoffset() is None:
            raise ValueError("daily requirement job time must be timezone-aware")
        async with self.run_store.locked_connection() as conn:
            snapshot = await self.source_loader.load(conn, as_of_date, computed_at)
            content_hash = requirement_run_content_hash(
                snapshot, as_of_date, self.horizon_days
            )
            existing = await self.run_store.find_published(
                conn, as_of_date, content_hash
            )
            if existing is not None:
                records = await self.run_store.flow_records(conn, existing["run_id"])
                await self.publisher.publish(records)
                return DailyRequirementJobResult(
                    status="deduplicated",
                    run_id=existing["run_id"],
                    as_of_date=as_of_date,
                    requirement_count=len(records),
                )
            run = await self.run_store.start(
                conn,
                snapshot,
                as_of_date,
                as_of_date + timedelta(days=self.horizon_days - 1),
                content_hash,
                computed_at,
            )
            try:
                batch = calculate_daily_water_requirements(
                    snapshot, as_of_date, self.horizon_days
                )
                await self.run_store.publish(conn, run, batch, computed_at)
            except Exception as exc:
                await self.run_store.fail(conn, run["run_id"], str(exc))
                raise
            records = await self.run_store.flow_records(conn, run["run_id"])
            await self.publisher.publish(records)
            return DailyRequirementJobResult(
                status="published",
                run_id=run["run_id"],
                as_of_date=as_of_date,
                requirement_count=len(records),
            )

    async def catch_up(self, now: datetime | None = None) -> DailyRequirementJobResult:
        current = datetime.now(timezone.utc) if now is None else now
        return await self.run_once(
            operational_date(current, self.cron, self.timezone_name), current
        )

    @property
    def schedule_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start_schedule(self) -> None:
        if self._task is not None:
            raise RuntimeError("daily requirement schedule is already running")
        # Validate cron/timezone before spawning: a config error must fail
        # startup loudly, not die later inside the unobserved loop task.
        _daily_cron(self.cron)
        ZoneInfo(self.timezone_name)
        self._stopping.clear()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception:
                # A loop task that already died must not abort shutdown
                # cleanup (db close) — surface it in the log instead.
                logger.exception(
                    "daily requirement schedule task had failed before shutdown"
                )
            self._task = None

    async def _run_loop(self) -> None:
        while not self._stopping.is_set():
            now = datetime.now(timezone.utc)
            next_run = _next_scheduled_time(now, self.cron, self.timezone_name)
            await asyncio.sleep((next_run - now).total_seconds())
            try:
                await self.run_once(
                    operational_date(next_run, self.cron, self.timezone_name), next_run
                )
            except Exception:
                logger.exception("scheduled daily requirement publication failed")


def operational_date(now: datetime, cron: str, timezone_name: str) -> date:
    minute, hour = _daily_cron(cron)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("job time must be timezone-aware")
    local_now = now.astimezone(ZoneInfo(timezone_name))
    cutoff = datetime.combine(
        local_now.date(), time(hour=hour, minute=minute), tzinfo=local_now.tzinfo
    )
    if local_now < cutoff:
        return local_now.date() - timedelta(days=1)
    return local_now.date()


def _daily_cron(cron: str) -> tuple[int, int]:
    parts = cron.split()
    try:
        minute = int(parts[0])
        hour = int(parts[1])
    except (IndexError, ValueError) as exc:
        raise ValueError(
            "DAILY_REQUIREMENT_CRON must be '<minute> <hour> * * *'"
        ) from exc
    if len(parts) != 5 or parts[2:] != ["*", "*", "*"]:
        raise ValueError("DAILY_REQUIREMENT_CRON must be '<minute> <hour> * * *'")
    if not 0 <= minute <= 59 or not 0 <= hour <= 23:
        raise ValueError("DAILY_REQUIREMENT_CRON minute/hour is out of range")
    return minute, hour


def _next_scheduled_time(now: datetime, cron: str, timezone_name: str) -> datetime:
    minute, hour = _daily_cron(cron)
    zone = ZoneInfo(timezone_name)
    local_now = now.astimezone(zone)
    candidate = datetime.combine(
        local_now.date(), time(hour=hour, minute=minute), tzinfo=zone
    )
    if candidate <= local_now:
        candidate += timedelta(days=1)
    return candidate.astimezone(timezone.utc)
