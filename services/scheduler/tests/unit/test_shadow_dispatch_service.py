"""PR 6.3a — the ShadowDispatchService orchestration: dark-by-default, mode gating,
exactly-once persistence over at-least-once dispatch, status mapping, and the structural
no-execute guarantee."""

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest

from repositories.control_plan_repository import DispatchableIntent
from services.clients.scada_validation_client import ScadaValidationClient
from services.open_loop_execution_service import (
    AdvanceResult,
    ExecutionModeNotEnabledError,
)
from services.shadow_dispatch_service import ShadowDispatchService

NOW = datetime(2026, 7, 20, 3, 0, 0, tzinfo=timezone.utc)
INTENT_ID = UUID("11111111-1111-4111-8111-111111111111")
PLAN_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CORR_ID = UUID("22222222-2222-4222-8222-222222222222")
IDEM = "campaign-eeee-week37-gate-M00-seq-1"
CONTENT_HASH = "a" * 64


def _intent(intent_id=INTENT_ID, idem=IDEM, content_hash=CONTENT_HASH):
    return DispatchableIntent(
        intent_id=intent_id,
        plan_id=PLAN_ID,
        plan_version=1,
        correlation_id=CORR_ID,
        request_id="req-01HZY.machine-boundary_001",
        idempotency_key=idem,
        intent_content_hash=content_hash,
        intent_document_text='{"schema_version": 1, "intent_id": "' + str(intent_id) + '"}',
    )


def _receipt_json(status="validation_accepted", reason_code=None, *, intent=None):
    intent = intent or _intent()
    return {
        "schema_version": 1,
        "receipt_id": "99999999-9999-4999-8999-999999999999",
        "intent_id": str(intent.intent_id),
        "correlation_id": str(CORR_ID),
        "request_id": intent.request_id,
        "idempotency_key": intent.idempotency_key,
        "intent_content_hash": intent.intent_content_hash,
        "capability_hash": "b" * 64,
        "status": status,
        "validated_at": "2026-07-20T03:00:00.000Z",
        "reason_code": reason_code,
    }


class FakeSession:
    """Minimal stand-in: run_shadow_dispatch_once commits to release the read snapshot."""

    async def commit(self):
        pass


class FakeRepo:
    def __init__(self, dispatchable):
        self._dispatchable = list(dispatchable)
        self.receipts: dict = {}  # intent_id -> row (dedup by PK, like ON CONFLICT)

    async def load_dispatchable_intents(self, session, plan_id, plan_version):
        return [i for i in self._dispatchable if not (i.intent_id in self.receipts)]

    async def record_validation_receipt(self, session, row):
        if row.intent_id in self.receipts:
            return False
        self.receipts[row.intent_id] = row
        return True


class FakeOpenLoop:
    def __init__(self, action="claimed", raises=None):
        self._action = action
        self._raises = raises
        self.calls = 0

    async def advance_open_loop_execution(self, session, plan_id, plan_version, *, worker_id, now):
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return AdvanceResult(self._action, (), False)


def _client(handler):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ScadaValidationClient("http://scada.local", lambda: "tok", client=http)


def _respond(status_code, json_body):
    return lambda request: httpx.Response(status_code, json=json_body)


def _service(repo, open_loop, scada_client):
    return ShadowDispatchService(repo, scada_client, open_loop, clock=lambda: NOW)


class TestRunShadowDispatchOnce:
    @pytest.mark.asyncio
    async def test_dark_without_a_scada_client(self):
        repo = FakeRepo([_intent()])
        svc = _service(repo, FakeOpenLoop(), None)
        report = await svc.run_shadow_dispatch_once(FakeSession(), PLAN_ID, 1)
        assert report.action == "dark"
        assert report.dispatched_intent_ids == ()
        assert repo.receipts == {}

    @pytest.mark.asyncio
    async def test_refused_on_operator_approved_mode(self):
        repo = FakeRepo([_intent()])
        open_loop = FakeOpenLoop(raises=ExecutionModeNotEnabledError("operator_approved"))
        svc = _service(repo, open_loop, _client(_respond(200, _receipt_json())))
        report = await svc.run_shadow_dispatch_once(FakeSession(), PLAN_ID, 1)
        assert report.action == "refused"
        assert repo.receipts == {}

    @pytest.mark.asyncio
    async def test_non_claimed_advance_dispatches_nothing(self):
        repo = FakeRepo([_intent()])
        svc = _service(repo, FakeOpenLoop(action="held"), _client(_respond(200, _receipt_json())))
        report = await svc.run_shadow_dispatch_once(FakeSession(), PLAN_ID, 1)
        assert report.action == "held"
        assert repo.receipts == {}

    @pytest.mark.asyncio
    async def test_claimed_dispatches_and_persists_one_receipt(self):
        repo = FakeRepo([_intent()])
        svc = _service(repo, FakeOpenLoop(), _client(_respond(200, _receipt_json())))
        report = await svc.run_shadow_dispatch_once(FakeSession(), PLAN_ID, 1)
        assert report.action == "dispatched"
        assert report.persisted_receipts == 1
        assert INTENT_ID in repo.receipts

    @pytest.mark.asyncio
    async def test_a_poisoned_intent_is_isolated_and_the_others_still_dispatch(self):
        # A malformed stored document raises json.loads inside dispatch — it must NOT abort the
        # whole tick and starve the healthy intent behind it.
        good_id = UUID("33333333-3333-4333-8333-333333333333")
        poison = DispatchableIntent(
            intent_id=good_id, plan_id=PLAN_ID, plan_version=1, correlation_id=CORR_ID,
            request_id="r", idempotency_key="poison-key", intent_content_hash=CONTENT_HASH,
            intent_document_text="{not valid json",
        )
        # The healthy intent (INTENT_ID) is dispatched second; its receipt must still land.
        repo = FakeRepo([poison, _intent()])

        def handler(request):
            return httpx.Response(200, json=_receipt_json())

        svc = _service(repo, FakeOpenLoop(), _client(handler))
        report = await svc.run_shadow_dispatch_once(FakeSession(), PLAN_ID, 1)
        assert report.action == "dispatched"
        assert INTENT_ID in repo.receipts  # the healthy one persisted
        assert good_id not in repo.receipts  # the poisoned one did not
        assert any(fid == good_id for fid, _ in report.failures)


class TestDispatchValidationIntent:
    @pytest.mark.asyncio
    async def test_dispatch_retry_persists_one_receipt(self):
        # Done-gate: at-least-once dispatch -> exactly-once persisted effect.
        repo = FakeRepo([_intent()])
        svc = _service(repo, FakeOpenLoop(), _client(_respond(200, _receipt_json())))
        first = await svc.dispatch_validation_intent(None, _intent())
        second = await svc.dispatch_validation_intent(None, _intent())
        assert first.persisted is True
        assert second.persisted is False  # ON CONFLICT no-op
        assert len(repo.receipts) == 1

    @pytest.mark.asyncio
    async def test_rejected_receipt_is_persisted_as_a_successful_validation(self):
        repo = FakeRepo([_intent()])
        body = _receipt_json("validation_rejected", "capability_mismatch")
        svc = _service(repo, FakeOpenLoop(), _client(_respond(200, body)))
        outcome = await svc.dispatch_validation_intent(None, _intent())
        assert outcome.persisted is True
        assert repo.receipts[INTENT_ID].status == "validation_rejected"
        assert repo.receipts[INTENT_ID].reason_code == "capability_mismatch"

    @pytest.mark.asyncio
    async def test_409_conflict_is_persisted_as_a_terminal_rejection(self):
        # A 409 is NOT a healthy validation (failure is flagged), but SCADA returns a valid
        # echoed validation_rejected/idempotency_conflict receipt — persisting it TERMINATES the
        # intent so it drops out of the dispatchable set instead of being re-POSTed forever.
        repo = FakeRepo([_intent()])
        body = _receipt_json("validation_rejected", "idempotency_conflict")
        svc = _service(repo, FakeOpenLoop(), _client(_respond(409, body)))
        outcome = await svc.dispatch_validation_intent(None, _intent())
        assert outcome.persisted is True
        assert outcome.failure[0] == "idempotency_conflict"
        assert repo.receipts[INTENT_ID].status == "validation_rejected"
        assert repo.receipts[INTENT_ID].reason_code == "idempotency_conflict"

    @pytest.mark.asyncio
    async def test_unavailable_persists_nothing_then_a_later_200_persists_one(self):
        repo = FakeRepo([_intent()])
        svc_down = _service(repo, FakeOpenLoop(), _client(_respond(503, {"error": "dark"})))
        down = await svc_down.dispatch_validation_intent(None, _intent())
        assert down.persisted is False and repo.receipts == {}
        # Next tick reaches a healthy SCADA.
        svc_up = _service(repo, FakeOpenLoop(), _client(_respond(200, _receipt_json())))
        up = await svc_up.dispatch_validation_intent(None, _intent())
        assert up.persisted is True and len(repo.receipts) == 1

    @pytest.mark.asyncio
    async def test_contract_violation_is_not_persisted(self):
        repo = FakeRepo([_intent()])
        bad = _receipt_json(intent=_intent(content_hash="c" * 64))  # echoed hash != dispatched
        svc = _service(repo, FakeOpenLoop(), _client(_respond(200, bad)))
        outcome = await svc.dispatch_validation_intent(None, _intent())
        assert outcome.persisted is False
        assert repo.receipts == {}

    @pytest.mark.asyncio
    async def test_receipt_content_sha256_is_the_hash_of_the_verbatim_document(self):
        import hashlib

        repo = FakeRepo([_intent()])
        svc = _service(repo, FakeOpenLoop(), _client(_respond(200, _receipt_json())))
        await svc.dispatch_validation_intent(None, _intent())
        row = repo.receipts[INTENT_ID]
        assert (
            row.receipt_content_sha256
            == hashlib.sha256(row.receipt_document_text.encode("utf-8")).hexdigest()
        )


def test_shadow_dispatcher_has_no_execute_url():
    # Structural no-execute (robust against docstrings that MENTION the forbidden routes):
    # the SCADA client's only public network method is validate_intent (+ aclose), and the
    # only URL it can build is the validate path — a misconfiguration has no method or knob to
    # reach an actuation route. A future dev adding an `execute`/`command` method breaks this.
    from services.clients import scada_validation_client as mod

    public = {m for m in dir(mod.ScadaValidationClient) if not m.startswith("_")}
    assert public == {"validate_intent", "aclose"}
    assert mod._VALIDATE_PATH.endswith("/command-intents/validate")
    # Scan only executable CODE string-constants (AST) — never docstrings/comments — for an
    # actuation route literal.
    import ast

    tree = ast.parse((Path(mod.__file__)).read_text())
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                docstrings.add(doc)
    code_strings = [
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant)
        and isinstance(n.value, str)
        and n.value not in docstrings
    ]
    for s in code_strings:
        for route in ("command-level", "/horn", "/api/gates"):
            assert route not in s, f"actuation route {route!r} in a code string {s!r}"
