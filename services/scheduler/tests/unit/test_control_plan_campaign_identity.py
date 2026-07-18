"""Campaign identity: monotonic immutable plan_version per campaign (PR 4.4b-4).

The advisory-lock concurrency + real backfill live in the env-gated Postgres
suite; here the ALLOCATION LOGIC + response wiring are proven against the
in-memory fake: a fresh campaign starts at version 1, a present campaign gets the
next version, an unknown campaign fails closed, an idempotent replay consumes no
version (no gap), campaign_id enters the content identity, and every response
carries the campaign.
"""

import json
from datetime import datetime, timezone
from functools import partial
from uuid import uuid4

import pytest

from algorithms.hydraulic_schedule_optimizer import (
    optimize_limited_adjustment_plan,
)
from api.v1.endpoints.control_plans import _response_from_record
from repositories.control_plan_projection_repository import (
    build_prediction_coverage,
)
from repositories.control_plan_repository import UnknownCampaignError
from schemas.control_plan import DraftControlPlanRequest
from services.control_plan_service import ControlPlanDraftService
from tests.control_plan_test_support import (
    FakeControlFlowClient,
    FakeRepository,
    FakeRosGisClient,
    draft_payload,
    requirement_item,
    snapshot_mirror,
)


async def _run_blocking(func, *args, **kwargs):
    return func(*args, **kwargs)


def _service(repository, *, volume=6000.0, clock=None):
    return ControlPlanDraftService(
        ros_client=FakeRosGisClient([requirement_item(volume=volume)]),
        flow_client=FakeControlFlowClient(snapshot_mirror()),
        repository=repository,
        optimizer=partial(
            optimize_limited_adjustment_plan,
            model_step_seconds=3600,
            max_intermediate_trims=1,
            solver_timeout_seconds=60,
        ),
        run_blocking=_run_blocking,
        model_step_seconds=3600,
        max_intermediate_trims=1,
        solver_timeout_seconds=60,
        clock=clock,
    )


def _request(**overrides):
    return DraftControlPlanRequest.model_validate(draft_payload(**overrides))


@pytest.mark.asyncio
async def test_first_draft_creates_campaign_version_one():
    repo = FakeRepository()
    record, replayed = await _service(repo).create_draft(
        None, _request(), "operator-1"
    )
    assert not replayed
    assert record.plan_version == 1
    assert record.campaign_id is not None
    # A brand-new campaign is NOT a legacy singleton: its id is a fresh uuid
    # distinct from the per-version plan_id.
    assert record.campaign_id != record.plan_id


@pytest.mark.asyncio
async def test_second_draft_same_campaign_allocates_version_two():
    repo = FakeRepository()
    first, _ = await _service(repo, volume=6000.0).create_draft(
        None, _request(), "operator-1"
    )
    campaign = first.campaign_id
    # A genuinely different input (distinct volume -> distinct content hash) pinned
    # to the SAME campaign gets the next immutable version.
    second, replayed = await _service(repo, volume=6050.0).create_draft(
        None, _request(campaign_id=str(campaign)), "operator-1"
    )
    assert not replayed
    assert second.campaign_id == campaign
    assert second.plan_version == 2
    assert second.plan_id != first.plan_id


@pytest.mark.asyncio
async def test_present_but_unknown_campaign_id_is_rejected():
    repo = FakeRepository()
    with pytest.raises(UnknownCampaignError):
        await _service(repo).create_draft(
            None, _request(campaign_id=str(uuid4())), "operator-1"
        )
    # Fail closed: nothing persisted, no version minted under a caller-chosen id.
    assert repo.store_calls == 0
    assert repo.campaign_versions == {}


@pytest.mark.asyncio
async def test_idempotent_replay_does_not_consume_a_campaign_version():
    repo = FakeRepository()
    first, _ = await _service(repo).create_draft(None, _request(), "operator-1")
    campaign = first.campaign_id

    # A byte-identical request replays the stored draft and allocates NOTHING.
    replay, replayed = await _service(repo).create_draft(
        None, _request(), "operator-2"
    )
    assert replayed
    assert replay.plan_id == first.plan_id
    assert replay.campaign_id == campaign
    assert repo.store_calls == 1

    # The next GENUINE new version is 2 (not 3): the replay left no gap.
    second, replayed2 = await _service(repo, volume=6050.0).create_draft(
        None, _request(campaign_id=str(campaign)), "operator-1"
    )
    assert not replayed2
    assert second.plan_version == 2


# The EXACT pre-4.4b-4 input_content_hash for the no-campaign draft_payload()
# fixture (computed from the identical serialization a legacy request produced,
# which carried NO campaign_id field). A byte-identical legacy request MUST keep
# this hash so it replays its stored draft instead of forking a new one.
_GOLDEN_PRE_PR_INPUT_HASH = (
    "9fbc794604fe7e954faef94fd86b11225ddd540875f9e06f94edec3dcf649d03"
)


@pytest.mark.asyncio
async def test_absent_campaign_id_keeps_the_pre_pr_input_hash_golden():
    repo = FakeRepository()
    record, _ = await _service(repo).create_draft(None, _request(), "operator-1")
    # (1) Byte-exact golden: the new-campaign path serializes identically to a
    # pre-4.4b-4 request, so its content hash is unchanged and a legacy request
    # still finds + replays this draft (rather than creating a duplicate).
    assert record.input_content_hash == _GOLDEN_PRE_PR_INPUT_HASH
    # (2) The structural reason: a NULL campaign_id is excluded from the hashed
    # request document. Present-as-null (the pre-fix behaviour) would add a key and
    # change the hash, so this assertion also fails without the fix.
    stored_request = json.loads(record.canonical_input_document_text)["request"]
    assert "campaign_id" not in stored_request


@pytest.mark.asyncio
async def test_campaign_id_enters_the_content_identity():
    repo = FakeRepository()
    absent, _ = await _service(repo).create_draft(None, _request(), "operator-1")
    # Same requirement content, differing ONLY by the request's campaign_id, is a
    # DISTINCT content-addressed draft (campaign_id is part of the hashed input),
    # so it is a genuine new version rather than a replay.
    pinned, replayed = await _service(repo).create_draft(
        None, _request(campaign_id=str(absent.campaign_id)), "operator-1"
    )
    assert not replayed
    assert pinned.input_content_hash != absent.input_content_hash
    assert pinned.campaign_id == absent.campaign_id
    assert pinned.plan_version == 2


@pytest.mark.asyncio
async def test_midnight_rollover_does_not_create_an_automatic_version():
    repo = FakeRepository()
    before = datetime(2026, 7, 20, 23, 59, tzinfo=timezone.utc)
    after = datetime(2026, 7, 21, 0, 1, tzinfo=timezone.utc)

    first, _ = await _service(repo, clock=lambda: before).create_draft(
        None, _request(), "operator-1"
    )
    assert first.plan_version == 1
    # The clock crossing midnight is used only for timestamps — it never allocates
    # a version. A byte-identical request AFTER the rollover still replays version
    # 1; the campaign holds exactly one version.
    rolled, replayed = await _service(repo, clock=lambda: after).create_draft(
        None, _request(), "operator-2"
    )
    assert replayed
    assert rolled.plan_id == first.plan_id
    assert rolled.plan_version == 1
    assert rolled.campaign_id == first.campaign_id
    assert repo.store_calls == 1
    assert repo.campaign_versions[first.campaign_id] == 1


@pytest.mark.asyncio
async def test_response_and_coverage_carry_campaign_id():
    repo = FakeRepository()
    record, _ = await _service(repo).create_draft(None, _request(), "operator-1")
    response = _response_from_record(record)
    coverage = build_prediction_coverage(record)
    assert response.campaign_id == record.campaign_id
    assert coverage.campaign_id == record.campaign_id
