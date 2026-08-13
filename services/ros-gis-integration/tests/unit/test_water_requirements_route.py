from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.routes.water_requirements import (
    ManualRequirementRunRequest,
    trigger_daily_requirement_run,
)
from db.daily_requirement_run_store import SupersededRequirementRunError
from services.daily_requirement_producer import RequirementInputError
from services.daily_requirement_job import operational_date
from services.requirement_source_loader import RequirementSourceError

AS_OF = date(2026, 8, 12)
NOW = datetime(2026, 8, 11, 23, 59, 16, tzinfo=timezone.utc)


class _SuccessfulJob:
    def __init__(self, status: str, as_of_date: date = AS_OF):
        self.cron = "0 2 * * *"
        self.timezone_name = "Asia/Bangkok"
        self.calls = []
        self.result = SimpleNamespace(
            status=status,
            run_id=uuid4(),
            as_of_date=as_of_date,
            requirement_count=287,
        )

    async def run_once(self, as_of_date: date, now: datetime):
        self.calls.append((as_of_date, now))
        return self.result


class _FailingJob:
    def __init__(self, error: Exception):
        self.error = error
        self.calls = []
        self.cron = "0 2 * * *"
        self.timezone_name = "Asia/Bangkok"

    async def run_once(self, as_of_date: date, now: datetime):
        self.calls.append((as_of_date, now))
        raise self.error


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["published", "deduplicated"])
async def test_trigger_daily_requirement_run_returns_declared_success(status):
    job = _SuccessfulJob(status)

    response = await trigger_daily_requirement_run(
        ManualRequirementRunRequest(asOfDate=AS_OF),
        job=job,
        now=NOW,
    )

    assert response.model_dump() == {
        "status": status,
        "runId": job.result.run_id,
        "asOfDate": AS_OF,
        "requirementCount": 287,
    }
    assert job.calls == [(AS_OF, NOW)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("now", "expected_date"),
    [
        (datetime(2026, 8, 11, 16, 59, 59, tzinfo=timezone.utc), date(2026, 8, 11)),
        (datetime(2026, 8, 11, 17, 0, tzinfo=timezone.utc), date(2026, 8, 11)),
        (datetime(2026, 8, 11, 23, 59, 16, tzinfo=timezone.utc), date(2026, 8, 12)),
        (datetime(2026, 8, 12, 0, 0, tzinfo=timezone.utc), date(2026, 8, 12)),
    ],
)
async def test_trigger_daily_requirement_run_accepts_only_current_bangkok_operational_date(
    now,
    expected_date,
):
    job = _SuccessfulJob("published", expected_date)

    accepted = await trigger_daily_requirement_run(
        ManualRequirementRunRequest(asOfDate=expected_date),
        job=job,
        now=now,
    )

    assert accepted.asOfDate == expected_date
    assert job.calls == [(expected_date, now)]

    rejected_date = expected_date + timedelta(days=1)
    with pytest.raises(HTTPException) as exc_info:
        await trigger_daily_requirement_run(
            ManualRequirementRunRequest(asOfDate=rejected_date),
            job=job,
            now=now,
        )

    assert (exc_info.value.status_code, exc_info.value.detail) == (
        409,
        {
            "status": "rejected",
            "reason": "operational_date_mismatch",
            "asOfDate": rejected_date.isoformat(),
            "expectedAsOfDate": expected_date.isoformat(),
        },
    )
    assert job.calls == [(expected_date, now)]
    assert expected_date == operational_date(now, job.cron, job.timezone_name)


@pytest.mark.asyncio
async def test_trigger_daily_requirement_run_does_not_misclassify_unexpected_failure():
    job = _FailingJob(RuntimeError("unexpected"))

    with pytest.raises(RuntimeError, match="unexpected"):
        await trigger_daily_requirement_run(
            ManualRequirementRunRequest(asOfDate=AS_OF),
            job=job,
            now=NOW,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_reason"),
    [
        (
            RequirementSourceError("sensitive source details"),
            "requirement_source_invalid",
        ),
        (
            RequirementInputError("sensitive section details"),
            "requirement_inputs_incomplete",
        ),
    ],
)
async def test_trigger_daily_requirement_run_returns_sanitized_typed_incomplete_source_failure(
    error,
    expected_reason,
):
    job = _FailingJob(error)

    with pytest.raises(HTTPException) as exc_info:
        await trigger_daily_requirement_run(
            ManualRequirementRunRequest(asOfDate=AS_OF),
            job=job,
            now=NOW,
        )

    assert job.calls == [(AS_OF, NOW)]
    assert (exc_info.value.status_code, exc_info.value.detail) == (
        409,
        {
            "status": "failed_incomplete_source",
            "reason": expected_reason,
            "asOfDate": AS_OF.isoformat(),
        },
    )


@pytest.mark.asyncio
async def test_trigger_daily_requirement_run_returns_superseded_lineage_conflict():
    job = _FailingJob(SupersededRequirementRunError(AS_OF))

    with pytest.raises(HTTPException) as exc_info:
        await trigger_daily_requirement_run(
            ManualRequirementRunRequest(asOfDate=AS_OF), job=job, now=NOW
        )

    assert (exc_info.value.status_code, exc_info.value.detail) == (
        409,
        {
            "status": "rejected",
            "reason": "superseded_lineage",
            "asOfDate": AS_OF.isoformat(),
        },
    )
