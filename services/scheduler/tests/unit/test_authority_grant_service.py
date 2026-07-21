"""PR 7.1a: authority-grant service orchestration over the interface-pinned fake.

Grant/renew/revoke lifecycle, replay idempotency, conflict taxonomy, trusted-
actor enforcement (grant/renew strict-complete; revoke deliberately NOT), and
the fake<->Postgres signature pin. Nothing here executes anything.
"""

import inspect
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from tests.control_plan_test_support import (
    FakeRepository,
    _transition_chain,
    authority_model_snapshot,
    authority_outbox_rows,
)

from core.authority_grant import (
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_REVOKED,
    AuthorityEvidenceError,
    AuthorityGrantCandidate,
    AuthorityHistoryCorruptError,
)
from repositories.control_plan_repository import (
    AuthorityEvidenceCounts,
    AuthorityGrantConflictError,
    PostgresControlPlanRepository,
)
from services.authority_grant_service import (
    AuthorityGrantService,
    RenewalNotAllowedError,
    UnknownAuthorityGrantError,
    UnknownPlanForGrantError,
)

NOW = datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
SHA_E = "e" * 64
SHA_F = "f" * 64
PLAN_ID = uuid4()
RELEASE_ID = "hydraulic-model-2026.06"
CAPABILITY_RELEASE_ID = "field-registry-2026.06"
GATE = "MC-01"
SECTION = "S-1"
PATH = ["R-1", "R-2"]


def _requirement():
    import json

    return SimpleNamespace(
        section_id=SECTION,
        gate_id=GATE,
        path_reach_ids_document_text=json.dumps(PATH),
    )


INTENT_HASH_1 = "1" * 64
INTENT_HASH_2 = "2" * 64


def _record():
    import json

    snapshot = authority_model_snapshot(
        model_release_id=RELEASE_ID,
        model_release_content_hash=SHA_A,
        engine_descriptor_content_hash=SHA_B,
    )
    return SimpleNamespace(
        plan_id=PLAN_ID,
        plan_version=3,
        provenance_version=2,
        model_snapshot_id=snapshot["snapshot_id"],
        model_snapshot_document_text=json.dumps(snapshot),
        model_release_id=RELEASE_ID,
        model_release_content_hash=SHA_A,
        engine_descriptor_content_hash=SHA_B,
        max_intermediate_trims=1,
        horizon_end=NOW + 10 * HOUR,
        requirements=(_requirement(),),
        events=(
            SimpleNamespace(
                gate_id=GATE,
                source_flow_m3s=5.0,
                target_position_m=0.5,
                planned_at=NOW + 1 * HOUR,
            ),
            SimpleNamespace(
                gate_id=GATE,
                source_flow_m3s=0.0,
                target_position_m=0.0,
                planned_at=NOW + 4 * HOUR,
            ),
        ),
        transitions=_transition_chain("shadow_active", None),
    )


def _snapshot():
    return SimpleNamespace(
        capability_release_id=CAPABILITY_RELEASE_ID,
        capability_hash=SHA_C,
        capabilities={GATE: object()},
    )


def _candidate(**overrides):
    base = dict(
        plan_id=PLAN_ID,
        plan_version=3,
        model_release_id=RELEASE_ID,
        model_release_content_hash=SHA_A,
        engine_descriptor_content_hash=SHA_B,
        commandability_evidence={
            "schema_version": 1,
            "model_release_id": RELEASE_ID,
            "model_release_content_hash": SHA_A,
            "engine_descriptor_content_hash": SHA_B,
            "commandable": True,
            "approval_refs": ["RID-approval-2026-118"],
        },
        capability_release_id=CAPABILITY_RELEASE_ID,
        capability_hash=SHA_C,
        scope={
            "schema_version": 1,
            "gate_paths": [
                {
                    "section_id": SECTION,
                    "canonical_gate_id": GATE,
                    "path_reach_ids": list(PATH),
                }
            ],
        },
        flow_lower_exclusive_m3s=0.0,
        flow_upper_inclusive_m3s=8.0,
        initialization={"kind": "dry"},
        maximum_continuous_open_seconds=6 * 3600,
        maximum_intermediate_trims=1,
        shadow_evidence_sha256=SHA_D,
        hold_drill_evidence_sha256=SHA_E,
        rollback_drill_evidence_sha256=SHA_F,
        evidence_manifest={"schema_version": 1, "refs": ["drill-log-2026-07-18"]},
        expires_at=NOW + 12 * HOUR,
    )
    base.update(overrides)
    return AuthorityGrantCandidate(**base)


def _strict_evidence(**overrides):
    base = {
        "authorization_policy_version": "control-plan-rbac-v1",
        "claim_policy_mode": "strict",
        "subject": "supervisor-1",
        "roles": ["supervisor"],
        "token_identity_sha256": "9" * 64,
        "request_id": "req-1",
        "evidence_refs": ["ticket-118"],
    }
    base.update(overrides)
    return base


def _compat_evidence(**overrides):
    return _strict_evidence(claim_policy_mode="compat", **overrides)


def _service(repository, *, now=NOW, lease_hours=24, snapshot=None):
    return AuthorityGrantService(
        repository,
        snapshot=snapshot or _snapshot(),
        lease_hours=lease_hours,
        clock=lambda: now,
    )


def _seeded_repository():
    repository = FakeRepository()
    record = _record()
    repository.by_key[(PLAN_ID, 3)] = record
    repository.authority_evidence_counts[(PLAN_ID, 3)] = AuthorityEvidenceCounts(
        outbox_intent_count=2,
        accepted_receipt_intent_count=2,
        matching_receipt_intent_count=2,
    )
    repository.outbox[(PLAN_ID, 3)] = list(
        authority_outbox_rows(
            plan_id=PLAN_ID,
            plan_version=3,
            model_release_id=RELEASE_ID,
            model_release_content_hash=SHA_A,
            engine_descriptor_content_hash=SHA_B,
            capability_release_id=CAPABILITY_RELEASE_ID,
            capability_hash=SHA_C,
            canonical_gate_id=GATE,
            now=NOW,
        )
    )
    return repository


async def _grant(service, repository, **overrides):
    return await service.grant_execution_authority(
        None,
        _candidate(**overrides),
        actor_subject="supervisor-1",
        reason="pilot authority",
        authorization_evidence=_strict_evidence(),
    )


class TestGrantExecutionAuthority:
    @pytest.mark.asyncio
    async def test_grant_persists_grant_and_birth_event(self):
        repository = _seeded_repository()
        view = await _grant(_service(repository), repository)
        assert view.status == STATUS_ACTIVE
        assert view.effective_expires_at == NOW + 12 * HOUR
        assert len(repository.authority_grants) == 1
        events = repository.authority_grant_events[view.grant.grant_id]
        assert [event.event_type for event in events] == ["granted"]
        assert events[0].event_sequence == 1
        assert view.grant.model_release_commandable is True

    @pytest.mark.asyncio
    async def test_grant_replay_returns_the_same_grant_without_new_events(self):
        repository = _seeded_repository()
        service = _service(repository)
        first = await _grant(service, repository)
        second = await _grant(service, repository)
        assert second.grant.grant_id == first.grant.grant_id
        assert len(repository.authority_grants) == 1
        assert len(repository.authority_grant_events[first.grant.grant_id]) == 1

    @pytest.mark.asyncio
    async def test_conflicting_regrant_for_the_plan_raises(self):
        repository = _seeded_repository()
        service = _service(repository)
        await _grant(service, repository)
        with pytest.raises(AuthorityGrantConflictError):
            await _grant(service, repository, expires_at=NOW + 6 * HOUR)

    @pytest.mark.asyncio
    async def test_unknown_plan_fails_closed(self):
        repository = FakeRepository()
        with pytest.raises(UnknownPlanForGrantError):
            await _grant(_service(repository), repository)

    @pytest.mark.asyncio
    async def test_evidence_validation_failure_propagates(self):
        repository = _seeded_repository()
        repository.authority_evidence_counts[(PLAN_ID, 3)] = AuthorityEvidenceCounts(
            outbox_intent_count=2,
            accepted_receipt_intent_count=1,
            matching_receipt_intent_count=1,
        )
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            await _grant(_service(repository), repository)
        assert excinfo.value.reason == "receipt_coverage_incomplete"
        assert repository.authority_grants == {}

    @pytest.mark.asyncio
    async def test_grant_requires_strict_complete_actor_evidence(self):
        repository = _seeded_repository()
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            await _service(repository).grant_execution_authority(
                None,
                _candidate(),
                actor_subject="supervisor-1",
                reason="pilot authority",
                authorization_evidence=_compat_evidence(),
            )
        assert excinfo.value.reason == "evidence_incomplete"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "actor_subject, evidence",
        [
            ("different-supervisor", _strict_evidence()),
            (
                "supervisor-1",
                _strict_evidence(authorization_policy_version="obsolete-policy"),
            ),
        ],
    )
    async def test_grant_binds_actor_and_current_policy(self, actor_subject, evidence):
        repository = _seeded_repository()
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            await _service(repository).grant_execution_authority(
                None,
                _candidate(),
                actor_subject=actor_subject,
                reason="pilot authority",
                authorization_evidence=evidence,
            )
        assert excinfo.value.reason == "evidence_incomplete"
        assert repository.authority_grants == {}


class TestReviewAuthorityGrant:
    @pytest.mark.asyncio
    async def test_review_validates_without_persisting(self):
        repository = _seeded_repository()
        digest = await _service(repository).review_authority_grant(None, _candidate())
        assert len(digest) == 64
        assert repository.authority_grants == {}
        assert repository.authority_grant_events == {}

    @pytest.mark.asyncio
    async def test_review_rejects_what_grant_would_reject(self):
        repository = _seeded_repository()
        with pytest.raises(AuthorityEvidenceError):
            await _service(repository).review_authority_grant(
                None, _candidate(capability_hash=SHA_F)
            )


class TestRenewAuthorityGrant:
    @pytest.mark.asyncio
    async def test_renewal_appends_an_extending_event(self):
        repository = _seeded_repository()
        service = _service(repository)
        view = await _grant(service, repository)
        renewed = await service.renew_authority_grant(
            None,
            view.grant.grant_id,
            new_expires_at=NOW + 20 * HOUR,
            shadow_evidence_sha256=SHA_D,
            hold_drill_evidence_sha256=SHA_E,
            rollback_drill_evidence_sha256=SHA_F,
            evidence_manifest={"schema_version": 1, "refs": ["drill-log-2"]},
            reason="lease checkpoint",
            actor_subject="supervisor-1",
            authorization_evidence=_strict_evidence(),
        )
        assert renewed.status == STATUS_ACTIVE
        assert renewed.effective_expires_at == NOW + 20 * HOUR
        events = repository.authority_grant_events[view.grant.grant_id]
        assert [event.event_type for event in events] == ["granted", "renewed"]
        assert events[1].event_sequence == 2

    @pytest.mark.asyncio
    async def test_renewal_must_strictly_extend(self):
        repository = _seeded_repository()
        service = _service(repository)
        view = await _grant(service, repository)
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            await service.renew_authority_grant(
                None,
                view.grant.grant_id,
                new_expires_at=NOW + 12 * HOUR,  # equal, not extending
                shadow_evidence_sha256=SHA_D,
                hold_drill_evidence_sha256=SHA_E,
                rollback_drill_evidence_sha256=SHA_F,
                evidence_manifest={"schema_version": 1, "refs": ["drill-log-2"]},
                reason="lease checkpoint",
                actor_subject="supervisor-1",
                authorization_evidence=_strict_evidence(),
            )
        assert excinfo.value.reason == "expiry_invalid"

    @pytest.mark.asyncio
    async def test_expired_or_revoked_grant_cannot_be_renewed(self):
        repository = _seeded_repository()
        service = _service(repository)
        view = await _grant(service, repository)
        late = _service(repository, now=NOW + 13 * HOUR)  # past the 12h expiry
        with pytest.raises(RenewalNotAllowedError):
            await late.renew_authority_grant(
                None,
                view.grant.grant_id,
                new_expires_at=NOW + 20 * HOUR,
                shadow_evidence_sha256=SHA_D,
                hold_drill_evidence_sha256=SHA_E,
                rollback_drill_evidence_sha256=SHA_F,
                evidence_manifest={"schema_version": 1, "refs": ["drill-log-2"]},
                reason="too late",
                actor_subject="supervisor-1",
                authorization_evidence=_strict_evidence(),
            )
        await service.revoke_authority_grant(
            None,
            view.grant.grant_id,
            reason="stand down",
            actor_subject="supervisor-1",
            authorization_evidence=_strict_evidence(),
        )
        with pytest.raises(RenewalNotAllowedError):
            await service.renew_authority_grant(
                None,
                view.grant.grant_id,
                new_expires_at=NOW + 20 * HOUR,
                shadow_evidence_sha256=SHA_D,
                hold_drill_evidence_sha256=SHA_E,
                rollback_drill_evidence_sha256=SHA_F,
                evidence_manifest={"schema_version": 1, "refs": ["drill-log-2"]},
                reason="after revoke",
                actor_subject="supervisor-1",
                authorization_evidence=_strict_evidence(),
            )

    @pytest.mark.asyncio
    async def test_renewal_requires_current_capability_and_coverage(self):
        repository = _seeded_repository()
        service = _service(repository)
        view = await _grant(service, repository)
        drifted = _service(
            repository,
            snapshot=SimpleNamespace(
                capability_release_id=CAPABILITY_RELEASE_ID,
                capability_hash=SHA_F,
                capabilities={GATE: object()},
            ),
        )
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            await drifted.renew_authority_grant(
                None,
                view.grant.grant_id,
                new_expires_at=NOW + 20 * HOUR,
                shadow_evidence_sha256=SHA_D,
                hold_drill_evidence_sha256=SHA_E,
                rollback_drill_evidence_sha256=SHA_F,
                evidence_manifest={"schema_version": 1, "refs": ["drill-log-2"]},
                reason="drifted registry",
                actor_subject="supervisor-1",
                authorization_evidence=_strict_evidence(),
            )
        assert excinfo.value.reason == "capability_mismatch"

    @pytest.mark.asyncio
    async def test_unknown_grant_fails_closed(self):
        repository = _seeded_repository()
        with pytest.raises(UnknownAuthorityGrantError):
            await _service(repository).renew_authority_grant(
                None,
                uuid4(),
                new_expires_at=NOW + 20 * HOUR,
                shadow_evidence_sha256=SHA_D,
                hold_drill_evidence_sha256=SHA_E,
                rollback_drill_evidence_sha256=SHA_F,
                evidence_manifest={"schema_version": 1, "refs": ["drill-log-2"]},
                reason="nothing there",
                actor_subject="supervisor-1",
                authorization_evidence=_strict_evidence(),
            )


class TestRevokeAuthorityGrant:
    @pytest.mark.asyncio
    async def test_revocation_is_terminal_and_idempotent(self):
        repository = _seeded_repository()
        service = _service(repository)
        view = await _grant(service, repository)
        first = await service.revoke_authority_grant(
            None,
            view.grant.grant_id,
            reason="drill finding",
            actor_subject="supervisor-1",
            authorization_evidence=_strict_evidence(),
        )
        second = await service.revoke_authority_grant(
            None,
            view.grant.grant_id,
            reason="repeat click",
            actor_subject="supervisor-1",
            authorization_evidence=_strict_evidence(),
        )
        assert first.status == STATUS_REVOKED
        assert second.status == STATUS_REVOKED
        events = repository.authority_grant_events[view.grant.grant_id]
        assert [event.event_type for event in events] == ["granted", "revoked"]

    @pytest.mark.asyncio
    async def test_revoke_accepts_compat_actor_evidence(self):
        # The safety brake must work BEFORE the external strict flip.
        repository = _seeded_repository()
        service = _service(repository)
        view = await _grant(service, repository)
        revoked = await service.revoke_authority_grant(
            None,
            view.grant.grant_id,
            reason="compat emergency",
            actor_subject="supervisor-1",
            authorization_evidence=_compat_evidence(),
        )
        assert revoked.status == STATUS_REVOKED

    @pytest.mark.asyncio
    async def test_revoke_rejects_evidence_for_a_different_actor(self):
        repository = _seeded_repository()
        service = _service(repository)
        view = await _grant(service, repository)

        with pytest.raises(AuthorityEvidenceError):
            await service.revoke_authority_grant(
                None,
                view.grant.grant_id,
                reason="mismatched audit identity",
                actor_subject="supervisor-1",
                authorization_evidence=_compat_evidence(subject="different-supervisor"),
            )

        assert [
            event.event_type
            for event in repository.authority_grant_events[view.grant.grant_id]
        ] == ["granted"]

    @pytest.mark.asyncio
    async def test_expired_grant_can_still_be_revoked_for_audit(self):
        repository = _seeded_repository()
        service = _service(repository)
        view = await _grant(service, repository)
        late = _service(repository, now=NOW + 13 * HOUR)
        revoked = await late.revoke_authority_grant(
            None,
            view.grant.grant_id,
            reason="post-expiry audit",
            actor_subject="supervisor-1",
            authorization_evidence=_strict_evidence(),
        )
        assert revoked.status == STATUS_REVOKED


class TestGrantViews:
    @pytest.mark.asyncio
    async def test_get_views_derive_status(self):
        repository = _seeded_repository()
        service = _service(repository)
        view = await _grant(service, repository)
        by_id = await service.get_authority_grant(None, view.grant.grant_id)
        by_plan = await service.get_authority_grant_for_plan(None, PLAN_ID, 3)
        assert by_id.grant.grant_id == by_plan.grant.grant_id
        assert by_id.status == STATUS_ACTIVE
        late = _service(repository, now=NOW + 13 * HOUR)
        assert (
            await late.get_authority_grant(None, view.grant.grant_id)
        ).status == STATUS_EXPIRED

    @pytest.mark.asyncio
    async def test_unknown_grant_views_return_none(self):
        repository = _seeded_repository()
        service = _service(repository)
        assert await service.get_authority_grant(None, uuid4()) is None
        assert await service.get_authority_grant_for_plan(None, PLAN_ID, 9) is None

    @pytest.mark.asyncio
    async def test_corrupt_ledger_fails_closed_on_view(self):
        repository = _seeded_repository()
        service = _service(repository)
        view = await _grant(service, repository)
        repository.authority_grant_events[view.grant.grant_id].clear()
        with pytest.raises(AuthorityHistoryCorruptError):
            await service.get_authority_grant(None, view.grant.grant_id)


def test_fake_pins_the_postgres_authority_interface():
    """The fake twin must present EXACTLY the production signatures — a fake
    encoding a wrong interface makes the whole suite false assurance."""
    for method in (
        "insert_authority_grant",
        "append_authority_grant_event",
        "load_authority_grant",
        "load_authority_grant_for_plan",
        "load_authority_evidence_counts",
    ):
        fake_signature = inspect.signature(getattr(FakeRepository, method))
        real_signature = inspect.signature(
            getattr(PostgresControlPlanRepository, method)
        )
        assert list(fake_signature.parameters) == list(
            real_signature.parameters
        ), f"{method}: fake {fake_signature} != real {real_signature}"


class TestModeGateIndependence:
    @pytest.mark.asyncio
    async def test_active_grant_cannot_enable_operator_approved_mode(self):
        """The execution-mode gate and the authority grant are INDEPENDENT dark
        gates: an active grant must not unlock the refused operator_approved
        mode (only PR 7.2 may lift that refusal, behind its own dual flags)."""
        from services.open_loop_execution_service import (
            ExecutionModeNotEnabledError,
            OpenLoopExecutionService,
        )

        repository = _seeded_repository()
        view = await _grant(_service(repository), repository)
        assert view.status == STATUS_ACTIVE  # the grant really is active
        worker = OpenLoopExecutionService(
            repository=repository, execution_mode="operator_approved"
        )
        with pytest.raises(ExecutionModeNotEnabledError):
            await worker.advance_open_loop_execution(None, PLAN_ID, 3)


class TestUnderLockRechecks:
    """QCHECK fixes: the repository re-derives plan lifecycle UNDER the shared
    authority lock, and stored events are typed-column-bound to their docs."""

    @pytest.mark.asyncio
    async def test_insert_refuses_a_plan_that_lost_shadow_active(self):
        from repositories.control_plan_repository import (
            PlanNotShadowActiveForAuthorityError,
        )

        repository = _seeded_repository()
        service = _service(repository)
        # The service-level validation is bypassed here to exercise the REPO
        # recheck (the TOCTOU backstop): retire the plan, then insert directly.
        record = repository.by_key[(PLAN_ID, 3)]
        repository.by_key[(PLAN_ID, 3)] = SimpleNamespace(
            **{**record.__dict__, "transitions": _transition_chain("invalidated", None)}
        )
        from core.authority_grant import build_grant_document, intent_set_sha256
        from repositories.control_plan_repository import AuthorityGrantRow

        candidate = _candidate()
        digest = intent_set_sha256([INTENT_HASH_1, INTENT_HASH_2])
        from core.canonical_json import canonicalize, sha256_hex

        document = build_grant_document(
            candidate, intent_content_hashes=(INTENT_HASH_1, INTENT_HASH_2)
        )
        grant = AuthorityGrantRow(
            grant_id=uuid4(),
            authority_schema_version=1,
            plan_id=PLAN_ID,
            plan_version=3,
            model_release_id=RELEASE_ID,
            model_release_content_hash=SHA_A,
            engine_descriptor_content_hash=SHA_B,
            model_release_commandable=True,
            commandability_evidence_document_text=canonicalize(
                dict(candidate.commandability_evidence)
            ),
            commandability_evidence_sha256=sha256_hex(
                canonicalize(dict(candidate.commandability_evidence))
            ),
            capability_release_id=CAPABILITY_RELEASE_ID,
            capability_hash=SHA_C,
            scope_document_text=canonicalize(dict(candidate.scope)),
            scope_sha256=sha256_hex(canonicalize(dict(candidate.scope))),
            intent_set_sha256=digest,
            flow_lower_exclusive_m3s=0.0,
            flow_upper_inclusive_m3s=8.0,
            initialization_document_text=canonicalize({"kind": "dry"}),
            initialization_sha256=sha256_hex(canonicalize({"kind": "dry"})),
            maximum_continuous_open_seconds=6 * 3600,
            maximum_intermediate_trims=1,
            grant_document_text=canonicalize(document),
            grant_content_sha256=sha256_hex(canonicalize(document)),
            created_by_subject="supervisor-1",
            request_id="req-1",
        )
        birth = service._build_event(
            grant.grant_id,
            1,
            "granted",
            effective_expires_at=_candidate().expires_at,
            shadow_evidence_sha256=SHA_D,
            hold_drill_evidence_sha256=SHA_E,
            rollback_drill_evidence_sha256=SHA_F,
            evidence_manifest={"schema_version": 1, "refs": ["drill-log-1"]},
            actor_subject="supervisor-1",
            reason="pilot authority",
            authorization_evidence=_strict_evidence(),
            occurred_at=NOW,
        )
        with pytest.raises(PlanNotShadowActiveForAuthorityError):
            await repository.insert_authority_grant(None, grant, lambda: birth)

    @pytest.mark.asyncio
    async def test_renewal_refused_when_the_plan_retired_meanwhile(self):
        from repositories.control_plan_repository import (
            PlanNotShadowActiveForAuthorityError,
        )

        repository = _seeded_repository()
        service = _service(repository)
        view = await _grant(service, repository)
        # Retire the plan AFTER issuance; the unlocked service pre-check would
        # already refuse, so drive the repo append directly to prove the
        # UNDER-LOCK recheck (the race backstop) also refuses.
        record = repository.by_key[(PLAN_ID, 3)]
        repository.by_key[(PLAN_ID, 3)] = SimpleNamespace(
            **{**record.__dict__, "transitions": _transition_chain("invalidated", None)}
        )
        with pytest.raises(PlanNotShadowActiveForAuthorityError):
            await repository.append_authority_grant_event(
                None,
                view.grant.grant_id,
                lambda sequence, existing: None,
                require_shadow_active_plan=(PLAN_ID, 3),
            )

    @pytest.mark.asyncio
    async def test_tampered_event_typed_column_is_corruption(self):
        from dataclasses import replace

        from repositories.control_plan_repository import (
            AuthorityGrantCorruptError,
        )

        repository = _seeded_repository()
        service = _service(repository)
        view = await _grant(service, repository)
        events = repository.authority_grant_events[view.grant.grant_id]
        # Tamper the TYPED expiry replica; the canonical document + its hash
        # stay untouched — the fold consumes typed columns, so the verifier
        # must catch exactly this.
        events[0] = replace(events[0], effective_expires_at=NOW + 365 * 24 * HOUR)
        with pytest.raises(AuthorityGrantCorruptError):
            await service.get_authority_grant(None, view.grant.grant_id)

    @pytest.mark.asyncio
    async def test_self_consistent_false_commandability_evidence_is_corruption(self):
        from dataclasses import replace

        from core.canonical_json import canonicalize, sha256_hex
        from repositories.control_plan_repository import AuthorityGrantCorruptError

        repository = _seeded_repository()
        view = await _grant(_service(repository), repository)
        document = json.loads(view.grant.grant_document_text)
        document["commandability_evidence"]["commandable"] = False
        evidence_text = canonicalize(document["commandability_evidence"])
        document_text = canonicalize(document)
        repository.authority_grants[view.grant.grant_id] = replace(
            view.grant,
            commandability_evidence_document_text=evidence_text,
            commandability_evidence_sha256=sha256_hex(evidence_text),
            grant_document_text=document_text,
            grant_content_sha256=sha256_hex(document_text),
        )

        with pytest.raises(AuthorityGrantCorruptError):
            await repository.load_authority_grant(None, view.grant.grant_id)

    @pytest.mark.asyncio
    async def test_self_consistent_event_actor_evidence_mismatch_is_corruption(self):
        from dataclasses import replace

        from core.canonical_json import canonicalize, sha256_hex
        from repositories.control_plan_repository import AuthorityGrantCorruptError

        repository = _seeded_repository()
        service = _service(repository)
        view = await _grant(service, repository)
        await service.revoke_authority_grant(
            None,
            view.grant.grant_id,
            reason="stand down",
            actor_subject="supervisor-1",
            authorization_evidence=_compat_evidence(),
        )
        revoked = repository.authority_grant_events[view.grant.grant_id][-1]
        evidence = json.loads(revoked.authorization_evidence_document_text)
        evidence["subject"] = "different-supervisor"
        evidence_text = canonicalize(evidence)
        event_document = json.loads(revoked.event_document_text)
        event_document["authorization_evidence_sha256"] = sha256_hex(evidence_text)
        event_text = canonicalize(event_document)
        repository.authority_grant_events[view.grant.grant_id][-1] = replace(
            revoked,
            authorization_evidence_document_text=evidence_text,
            authorization_evidence_sha256=sha256_hex(evidence_text),
            event_document_text=event_text,
            event_content_sha256=sha256_hex(event_text),
        )

        with pytest.raises(AuthorityGrantCorruptError):
            await repository.load_authority_grant(None, view.grant.grant_id)

    @pytest.mark.asyncio
    async def test_grant_expiring_while_waiting_for_insert_is_not_persisted(self):
        class DelayedInsertRepository(type(_seeded_repository())):
            async def insert_authority_grant(self, session, grant, build_granted_event):
                clock[0] = grant_deadline
                return await super().insert_authority_grant(
                    session, grant, build_granted_event
                )

        grant_deadline = NOW + HOUR
        clock = [NOW]
        repository = DelayedInsertRepository()
        seeded = _seeded_repository()
        repository.__dict__.update(seeded.__dict__)
        service = AuthorityGrantService(
            repository,
            snapshot=_snapshot(),
            lease_hours=24,
            clock=lambda: clock[0],
        )

        with pytest.raises(AuthorityEvidenceError) as caught:
            await _grant(
                service,
                repository,
                expires_at=grant_deadline,
            )

        assert caught.value.reason == "expiry_invalid"
        assert repository.authority_grants == {}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "document_text",
        [
            "[]",
            '{"schema_version":2}',
            '{ "schema_version" : 1 }',
        ],
    )
    async def test_non_object_unsupported_or_noncanonical_grant_is_corruption(
        self, document_text
    ):
        from dataclasses import replace

        from core.canonical_json import sha256_hex
        from repositories.control_plan_repository import AuthorityGrantCorruptError

        repository = _seeded_repository()
        view = await _grant(_service(repository), repository)
        repository.authority_grants[view.grant.grant_id] = replace(
            view.grant,
            grant_document_text=document_text,
            grant_content_sha256=sha256_hex(document_text),
        )
        with pytest.raises(AuthorityGrantCorruptError):
            await repository.load_authority_grant(None, view.grant.grant_id)

    @pytest.mark.asyncio
    async def test_grant_and_birth_evidence_must_match(self):
        repository = _seeded_repository()
        service = _service(repository)
        view = await _grant(service, repository)
        birth = service._build_event(
            view.grant.grant_id,
            1,
            "granted",
            effective_expires_at=view.effective_expires_at,
            shadow_evidence_sha256="0" * 64,
            hold_drill_evidence_sha256=SHA_E,
            rollback_drill_evidence_sha256=SHA_F,
            evidence_manifest={"schema_version": 1, "refs": ["drill-log-2026-07-18"]},
            actor_subject="supervisor-1",
            reason="pilot authority",
            authorization_evidence=_strict_evidence(),
            occurred_at=NOW,
        )
        repository.authority_grant_events[view.grant.grant_id] = [birth]
        from repositories.control_plan_repository import AuthorityGrantCorruptError

        with pytest.raises(AuthorityGrantCorruptError):
            await repository.load_authority_grant(None, view.grant.grant_id)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "grant_overrides",
        [
            {"created_by_subject": "different-supervisor"},
            {"request_id": "different-request"},
        ],
    )
    async def test_grant_creator_and_request_must_match_birth_authorization(
        self, grant_overrides
    ):
        from dataclasses import replace

        from repositories.control_plan_repository import AuthorityGrantCorruptError

        repository = _seeded_repository()
        view = await _grant(_service(repository), repository)
        repository.authority_grants[view.grant.grant_id] = replace(
            view.grant, **grant_overrides
        )
        with pytest.raises(AuthorityGrantCorruptError):
            await repository.load_authority_grant(None, view.grant.grant_id)


def test_corrupt_validation_receipt_is_not_authority_evidence():
    from core.canonical_json import canonicalize
    from schemas.machine_boundary import ValidationReceipt
    from repositories.control_plan_repository import (
        AuthorityEvidenceStoreCorruptError,
        verify_stored_validation_receipt,
    )

    receipt_id = uuid4()
    intent_id = uuid4()
    correlation_id = uuid4()
    receipt = ValidationReceipt(
        schema_version=1,
        receipt_id=str(receipt_id),
        intent_id=str(intent_id),
        correlation_id=str(correlation_id),
        request_id="req-1",
        idempotency_key="idem-1",
        intent_content_hash=INTENT_HASH_1,
        capability_hash=SHA_C,
        status="validation_accepted",
        validated_at=NOW.isoformat().replace("+00:00", "Z"),
        reason_code=None,
    )
    row = SimpleNamespace(
        intent_id=intent_id,
        receipt_id=receipt_id,
        correlation_id=correlation_id,
        request_id="req-1",
        idempotency_key="idem-1",
        intent_content_hash=INTENT_HASH_1,
        capability_hash=SHA_C,
        status="validation_accepted",
        reason_code=None,
        validated_at=NOW,
        receipt_document_text=canonicalize(receipt.model_dump()),
        receipt_content_sha256="0" * 64,
    )
    with pytest.raises(AuthorityEvidenceStoreCorruptError):
        verify_stored_validation_receipt(row)
