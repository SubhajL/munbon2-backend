import asyncio
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from services.daily_requirement_job import DailyRequirementJob, operational_date
from services.daily_requirement_producer import RequirementSnapshot, SectionCropInput

UTC = timezone.utc
AS_OF = date(2026, 7, 16)
NOW = datetime(2026, 7, 16, 2, tzinfo=UTC)


def _snapshot(crop_type="rice") -> RequirementSnapshot:
    return RequirementSnapshot(
        sections=(
            SectionCropInput(
                section_id="01-01-01-03",
                zone=1,
                area_rai=Decimal("10"),
                crop_type=crop_type,
                planting_date=date(2026, 7, 9),
                expected_harvest_date=date(2026, 12, 31),
                delivery_gate="M(0,2)",
                source="operator-fe",
                as_of_date=AS_OF,
            ),
        ),
        eto_monthly_mm={7: Decimal("93")},
        kc_weekly={
            ("rice", 2): Decimal("1.2"),
            ("rice", 3): Decimal("1.2"),
        },
        effective_rainfall_monthly_mm={("rice", 7): Decimal("31")},
        section_dataset_version_id=11,
        gate_mapping_dataset_version_id=12,
        crop_register_version="crop-v1",
        weather_version="weather-v1",
        annual_plan_version="annual-plan-v1",
        input_cutoff_at=datetime(2026, 7, 16, 1, tzinfo=UTC),
    )


class _SourceLoader:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = []

    async def load(self, conn, as_of_date, now):
        self.calls.append((conn, as_of_date, now))
        return self.snapshot


class _RunStore:
    def __init__(self):
        self.connection = object()
        self.lock = asyncio.Lock()
        self.runs = {}
        self.published_by_key = {}
        self.failed = []
        self.events = []

    @asynccontextmanager
    async def locked_connection(self):
        async with self.lock:
            yield self.connection

    async def find_published(self, conn, as_of_date, content_hash):
        return self.published_by_key.get((as_of_date, content_hash))

    async def start(self, conn, snapshot, as_of_date, horizon_end, content_hash, now):
        await asyncio.sleep(0)
        run = {
            "run_id": uuid4(),
            "as_of_date": as_of_date,
            "content_hash": content_hash,
        }
        self.runs[run["run_id"]] = run
        self.events.append("started")
        return run

    async def publish(self, conn, run, batch, now):
        self.events.append("local-published")
        self.runs[run["run_id"]]["batch"] = batch
        self.published_by_key[(run["as_of_date"], run["content_hash"])] = run

    async def fail(self, conn, run_id, reason):
        self.events.append("failed")
        self.failed.append((run_id, reason))

    async def flow_records(self, conn, run_id):
        batch = self.runs[run_id]["batch"]
        return [
            {
                "requirement_id": item.requirement_id,
                "run_id": run_id,
                "service_date": item.service_date,
                "section_id": item.section_id,
                "required_net_volume_m3": item.required_net_volume_m3,
                "delivery_window_start": item.delivery_window_start,
                "delivery_window_end": item.delivery_window_end,
                "quality": item.quality,
                "input_versions": item.input_versions,
                "computed_at": NOW,
                "downstream_version": 1,
            }
            for item in batch.requirements
        ]


class _Publisher:
    def __init__(self, store, failures=0):
        self.store = store
        self.failures = failures
        self.calls = []

    async def publish(self, records):
        self.store.events.append("downstream-post")
        self.calls.append(records)
        if self.failures:
            self.failures -= 1
            raise RuntimeError("flow-monitoring unavailable")


def _job(store=None, snapshot=None, publisher=None):
    store = store or _RunStore()
    return DailyRequirementJob(
        run_store=store,
        source_loader=_SourceLoader(snapshot or _snapshot()),
        publisher=publisher or _Publisher(store),
        cron="0 2 * * *",
        timezone_name="Asia/Bangkok",
        horizon_days=7,
    )


@pytest.mark.asyncio
async def test_job_publishes_exactly_one_run_per_identical_input_set_concurrently():
    store = _RunStore()
    publisher = _Publisher(store)
    job = _job(store=store, publisher=publisher)

    results = await asyncio.gather(
        job.run_once(AS_OF, NOW),
        job.run_once(AS_OF, NOW),
    )

    assert {result.status for result in results} == {"published", "deduplicated"}
    assert len(store.runs) == 1
    assert len(store.published_by_key) == 1
    assert store.events[:2] == ["started", "local-published"]
    assert all(
        store.events.index("local-published") < index
        for index, event in enumerate(store.events)
        if event == "downstream-post"
    )


@pytest.mark.asyncio
async def test_dependency_failure_marks_run_failed_and_never_publishes_zero_requirements():
    store = _RunStore()
    job = _job(store=store, snapshot=_snapshot(crop_type=None))

    with pytest.raises(ValueError, match="has no crop type"):
        await job.run_once(AS_OF, NOW)

    assert len(store.runs) == 1
    assert len(store.failed) == 1
    assert store.published_by_key == {}
    assert "downstream-post" not in store.events


@pytest.mark.asyncio
async def test_restart_catchup_publishes_missing_operational_day_once():
    store = _RunStore()
    job = _job(store=store)
    after_cutoff = datetime(2026, 7, 16, 3, tzinfo=UTC)

    first = await job.catch_up(after_cutoff)
    second = await job.catch_up(after_cutoff)

    assert (first.as_of_date, first.status) == (AS_OF, "published")
    assert (second.as_of_date, second.status) == (AS_OF, "deduplicated")
    assert len(store.runs) == 1


@pytest.mark.asyncio
async def test_transport_retry_reuses_the_published_run_and_idempotent_records():
    store = _RunStore()
    publisher = _Publisher(store, failures=1)
    job = _job(store=store, publisher=publisher)

    with pytest.raises(RuntimeError, match="flow-monitoring unavailable"):
        await job.run_once(AS_OF, NOW)
    result = await job.run_once(AS_OF, NOW)

    assert result.status == "deduplicated"
    assert len(store.runs) == 1
    assert publisher.calls[0] == publisher.calls[1]


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 7, 15, 18, 59, tzinfo=UTC), date(2026, 7, 15)),
        (datetime(2026, 7, 15, 19, 0, tzinfo=UTC), date(2026, 7, 16)),
    ],
)
def test_operational_date_uses_configured_bangkok_cron_cutoff(now, expected):
    assert operational_date(now, "0 2 * * *", "Asia/Bangkok") == expected


@pytest.mark.parametrize("cron", ["bad", "0 2 * * 1", "60 2 * * *", "0 24 * * *"])
def test_operational_date_rejects_unsupported_or_invalid_cron(cron):
    with pytest.raises(ValueError, match="DAILY_REQUIREMENT_CRON"):
        operational_date(NOW, cron, "Asia/Bangkok")


@pytest.mark.asyncio
async def test_start_schedule_never_invokes_catch_up():
    store = _RunStore()
    job = _job(store=store)

    await job.start_schedule()
    try:
        await asyncio.sleep(0)
        assert job.source_loader.calls == []
        assert store.events == []
        assert store.runs == {}
    finally:
        await job.stop()


@pytest.mark.asyncio
async def test_start_schedule_rejects_double_start():
    job = _job()

    await job.start_schedule()
    try:
        with pytest.raises(RuntimeError, match="already running"):
            await job.start_schedule()
    finally:
        await job.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cron", "timezone_name", "match"),
    [
        ("0 24 * * *", "Asia/Bangkok", "DAILY_REQUIREMENT_CRON"),
        ("0 2 * * *", "Not/AZone", "Not/AZone"),
    ],
)
async def test_start_schedule_validates_cron_and_timezone_synchronously(
    cron, timezone_name, match
):
    store = _RunStore()
    job = DailyRequirementJob(
        run_store=store,
        source_loader=_SourceLoader(_snapshot()),
        publisher=_Publisher(store),
        cron=cron,
        timezone_name=timezone_name,
        horizon_days=7,
    )

    with pytest.raises((ValueError, KeyError), match=match):
        await job.start_schedule()

    assert job.schedule_running is False


@pytest.mark.asyncio
async def test_schedule_running_is_false_after_the_loop_task_dies():
    job = _job()

    async def dead_loop():
        return None

    job._task = asyncio.create_task(dead_loop())
    await asyncio.sleep(0)

    assert job.schedule_running is False
    await job.stop()


@pytest.mark.asyncio
async def test_stop_swallows_a_dead_loop_task_failure_so_shutdown_continues():
    job = _job()

    async def crashed_loop():
        raise ValueError("unexpected scheduler failure")

    job._task = asyncio.create_task(crashed_loop())
    await asyncio.sleep(0)

    await job.stop()

    assert job.schedule_running is False


@pytest.mark.asyncio
async def test_shutdown_stops_only_a_started_scheduler():
    never_started = _job()
    assert never_started.schedule_running is False
    await never_started.stop()
    assert never_started.schedule_running is False

    started = _job()
    await started.start_schedule()
    assert started.schedule_running is True
    await started.stop()
    assert started.schedule_running is False
    await started.stop()
    assert started.schedule_running is False
