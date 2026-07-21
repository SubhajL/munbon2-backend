import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from core.authority_grant import ExecutionAuthorityError
from core.canonical_json import canonicalize
from core.command_intent import command_intent_content_hash
from repositories.control_plan_repository import OutboxRow
from schemas.machine_boundary import CommandIntent
from schemas.machine_execution import ExecutionReceipt
from services.clients.scada_execution_client import ExecutionDispatchResult
from services.operator_approved_dispatch_service import OperatorApprovedDispatchService

NOW = datetime(2026, 7, 20, 3, 0, tzinfo=timezone.utc)
PLAN_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
GRANT_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
AUTHORITY_NOT_AFTER = NOW + timedelta(seconds=90)


def fixture_intent():
    for parent in Path(__file__).resolve().parents:
        path = (
            parent
            / "contracts/machine-boundary/v1/fixtures/valid/command-intent.shadow.valid.json"
        )
        if path.is_file():
            data = json.loads(path.read_text())
            data["lineage"]["plan_id"] = str(PLAN_ID)
            data["lineage"]["plan_version"] = 1
            return CommandIntent.model_validate(data)
    raise AssertionError("fixture missing")


def outbox_row(intent):
    text = canonicalize(intent.model_dump())
    return OutboxRow(
        intent_id=UUID(intent.intent_id),
        correlation_id=UUID(intent.correlation_id),
        request_id=intent.request_id,
        idempotency_key=intent.idempotency_key,
        canonical_gate_id=intent.canonical_gate_id,
        event_kind=intent.event_kind,
        event_sequence=intent.event_sequence,
        gate_event_sequence=intent.gate_event_sequence,
        device_id=intent.device_id,
        adapter_gate_id=intent.adapter_gate_id,
        capability_release_id=intent.capability_release_id,
        capability_hash=intent.capability_hash,
        target_position_m=intent.target_position_m,
        target_level=intent.target_level,
        not_before=datetime.fromisoformat(intent.not_before.replace("Z", "+00:00")),
        deadline=datetime.fromisoformat(intent.deadline.replace("Z", "+00:00")),
        mode="shadow",
        intent_document_text=text,
        intent_content_hash=command_intent_content_hash(intent),
        activation_transition_sequence=1,
    )


class FakeRepository:
    def __init__(self, row):
        self.rows = [row]
        self.calls = []
        self.persisted = []
        self.open_loop_events = []
        self.grant_events = (
            SimpleNamespace(
                event_sequence=1,
                event_type="granted",
                effective_expires_at=AUTHORITY_NOT_AFTER,
                occurred_at=NOW - timedelta(minutes=1),
            ),
        )

    async def load_authority_grant_for_plan(self, session, plan_id, version):
        self.calls.append("load_grant")
        return (
            SimpleNamespace(grant_id=GRANT_ID, plan_id=PLAN_ID, plan_version=1),
            self.grant_events,
        )

    async def acquire_authority_execution_lock(self, session, grant_id):
        self.calls.append("lock")

    async def load_draft_plan(self, session, plan_id, version):
        self.calls.append("load_plan")
        return SimpleNamespace(
            plan_id=PLAN_ID,
            plan_version=1,
            model_release_id="model",
            model_release_content_hash="d" * 64,
            engine_descriptor_content_hash="e" * 64,
            transitions=[
                SimpleNamespace(
                    transition_sequence=1,
                    transition_type="draft_created",
                    from_state=None,
                    to_state="draft",
                ),
                SimpleNamespace(
                    transition_sequence=2,
                    transition_type="review_requested",
                    from_state="draft",
                    to_state="under_review",
                ),
                SimpleNamespace(
                    transition_sequence=3,
                    transition_type="shadow_approved",
                    from_state="under_review",
                    to_state="approved_for_shadow",
                ),
                SimpleNamespace(
                    transition_sequence=4,
                    transition_type="shadow_activated",
                    from_state="approved_for_shadow",
                    to_state="shadow_active",
                ),
            ],
        )

    async def load_command_outbox(self, session, plan_id, version):
        self.calls.append("load_outbox")
        return self.rows

    async def load_executed_intent_ids(self, session, plan_id, version):
        return set()

    async def record_execution_receipt(self, session, row, *, hold_event=None):
        self.persisted.append((row, hold_event))
        return True

    async def append_execution_events(self, session, plan_id, version, rows):
        self.persisted.append((None, rows[0]))

    async def load_open_loop_context(self, session, plan_id, version):
        return SimpleNamespace(events=self.open_loop_events)


class FakeClient:
    def __init__(self, status="execution_succeeded"):
        self.status = status
        self.requests = []

    async def execute_intent(self, request, **kwargs):
        self.requests.append((request, kwargs))
        intent = request["intent"]
        reason = None if self.status == "execution_succeeded" else "readback_mismatch"
        body = {
            "schema_version": 1,
            "receipt_id": "99999999-9999-4999-8999-999999999999",
            "intent_id": intent["intent_id"],
            "idempotency_key": intent["idempotency_key"],
            "grant_id": request["grant_id"],
            "authority_not_after": request["authority_not_after"],
            "original_intent_content_hash": request["original_intent_content_hash"],
            "execution_intent_content_hash": request["execution_intent_content_hash"],
            "capability_hash": intent["capability_hash"],
            "purpose": request["purpose"],
            "status": self.status,
            "reason_code": reason,
            "target_level": intent["target_level"],
            "observed_level": intent["target_level"] if reason is None else 2,
            "readback_quality": "ok",
            "writes": [],
            "executed_at": NOW.isoformat().replace("+00:00", "Z"),
        }
        return ExecutionDispatchResult(
            ExecutionReceipt.model_validate(body), json.dumps(body)
        )


def service(mode="operator_approved_open_loop", status="execution_succeeded"):
    intent = fixture_intent()
    repo = FakeRepository(outbox_row(intent))
    client = FakeClient(status)
    verifier_calls = []

    def verify(grant, events, context, *, now):
        verifier_calls.append(repo.calls.copy())

    svc = OperatorApprovedDispatchService(
        repo,
        client,
        snapshot=SimpleNamespace(
            capability_release_id=intent.capability_release_id,
            capability_hash=intent.capability_hash,
        ),
        execution_mode=mode,
        clock=lambda: NOW,
        authority_verifier=verify,
        token_minter=lambda **kwargs: "bound-token",
    )
    return svc, repo, client, verifier_calls


@pytest.mark.asyncio
async def test_execute_requires_the_scheduler_operator_approved_flag():
    svc, repo, client, _ = service(mode="disabled")
    report = await svc.run_execute_dispatch_once(object(), PLAN_ID, 1)
    assert report.action == "disabled"
    assert repo.calls == []
    assert client.requests == []


@pytest.mark.asyncio
async def test_execute_revalidates_authority_after_taking_the_execution_lock():
    svc, _, _, verifier_calls = service()
    await svc.run_execute_dispatch_once(object(), PLAN_ID, 1)
    assert verifier_calls == [
        ["load_grant", "lock", "load_grant", "load_plan", "load_outbox"]
    ]


@pytest.mark.asyncio
async def test_success_persists_one_receipt_without_holding_the_plan():
    svc, repo, client, _ = service()
    report = await svc.run_execute_dispatch_once(object(), PLAN_ID, 1)
    row, hold = repo.persisted[0]
    assert report.action == "executed"
    assert row.status == "execution_succeeded"
    assert hold is None
    assert client.requests[0][0]["intent"]["mode"] == "operator_approved"


@pytest.mark.asyncio
async def test_execute_binds_grant_and_effective_expiry_into_request_and_capped_token():
    svc, _, client, _ = service()
    token_claims = {}

    def mint_token(**claims):
        token_claims.update(claims)
        return "grant-bound-token"

    svc._token_minter = mint_token
    await svc.run_execute_dispatch_once(object(), PLAN_ID, 1)
    request = client.requests[0][0]
    expected_not_after = AUTHORITY_NOT_AFTER.isoformat().replace("+00:00", "Z")
    assert {
        "request_grant_id": request["grant_id"],
        "request_not_after": request["authority_not_after"],
        "token_grant_id": token_claims["grant_id"],
        "token_not_after": token_claims["authority_not_after"],
        "token_max_age": token_claims["max_age_seconds"],
    } == {
        "request_grant_id": str(GRANT_ID),
        "request_not_after": expected_not_after,
        "token_grant_id": str(GRANT_ID),
        "token_not_after": expected_not_after,
        "token_max_age": 90,
    }


@pytest.mark.asyncio
async def test_mismatch_persists_receipt_and_holds_all_remaining_intents_atomically():
    svc, repo, _, _ = service(status="readback_mismatch")
    report = await svc.run_execute_dispatch_once(object(), PLAN_ID, 1)
    row, hold = repo.persisted[0]
    assert report.action == "held"
    assert row.status == "readback_mismatch"
    assert hold.event_type == "held"


@pytest.mark.asyncio
async def test_operator_hold_blocks_active_authority_before_scada_execution():
    svc, repo, client, _ = service()
    repo.open_loop_events = [
        SimpleNamespace(event_type="held", occurred_at=NOW, created_at=NOW)
    ]

    report = await svc.run_execute_dispatch_once(object(), PLAN_ID, 1)

    assert (report.action, client.requests, repo.persisted) == ("held", [], [])


@pytest.mark.asyncio
@pytest.mark.parametrize("reason_code", ["grant_not_active", "capability_mismatch"])
async def test_authority_failure_holds_an_unheld_plan_before_any_scada_execution(
    reason_code,
):
    svc, repo, client, _ = service()

    def reject_authority(grant, events, context, *, now):
        raise ExecutionAuthorityError(reason_code, "authority is not executable")

    svc._verify = reject_authority
    report = await svc.run_execute_dispatch_once(object(), PLAN_ID, 1)

    assert report.action == "held"
    assert client.requests == []
    assert repo.persisted[0][1].event_type == "held"


@pytest.mark.asyncio
async def test_expired_authority_dispatches_only_a_held_fail_safe_close_with_scoped_token():
    open_intent = fixture_intent()
    close_document = fixture_intent().model_dump()
    close_document.update(
        {
            "intent_id": "33333333-3333-4333-8333-333333333333",
            "idempotency_key": "campaign-gate-close-seq-2",
            "event_kind": "close",
            "event_sequence": 2,
            "gate_event_sequence": 2,
            "target_position_m": 0,
            "target_level": 0,
        }
    )
    close_intent = CommandIntent.model_validate(close_document)
    repo = FakeRepository(outbox_row(open_intent))
    repo.rows.append(outbox_row(close_intent))
    repo.open_loop_events = [
        SimpleNamespace(event_type="held", occurred_at=NOW, created_at=NOW)
    ]
    client = FakeClient()
    fail_safe_calls = []
    token_claims = {}

    def verify_expired(grant, events, context, *, now):
        raise ExecutionAuthorityError("grant_not_active", "expired")

    def verify_fail_safe(grant, events, context, *, selected_intent_id, is_held, now):
        fail_safe_calls.append((selected_intent_id, is_held, now))

    def mint_token(**claims):
        token_claims.update(claims)
        return "fail-safe-bound-token"

    svc = OperatorApprovedDispatchService(
        repo,
        client,
        snapshot=SimpleNamespace(
            capability_release_id=close_intent.capability_release_id,
            capability_hash=close_intent.capability_hash,
        ),
        execution_mode="operator_approved_open_loop",
        clock=lambda: NOW,
        authority_verifier=verify_expired,
        fail_safe_verifier=verify_fail_safe,
        token_minter=mint_token,
    )

    report = await svc.run_execute_dispatch_once(object(), PLAN_ID, 1)
    receipt, hold = repo.persisted[0]

    assert (
        report.action,
        fail_safe_calls,
        client.requests[0][0]["purpose"],
        client.requests[0][0]["intent"]["intent_id"],
        token_claims["scope"],
        receipt.purpose,
        hold,
    ) == (
        "executed",
        [(UUID(close_intent.intent_id), True, NOW)],
        "fail_safe_close",
        close_intent.intent_id,
        "command_intents.fail_safe_close",
        "fail_safe_close",
        None,
    )
