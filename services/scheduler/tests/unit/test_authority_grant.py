"""PR 7.1a: pure execution-authority grant logic (core/authority_grant.py).

Covers the append-only ledger fold (derive_authority_grant_status), grant-time
evidence validation (validate_authority_evidence), and the 7.2-consumable
execution predicate (verify_execution_authority). Everything fails closed;
nothing here can actuate.
"""

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Optional
from uuid import uuid4

import pytest

from tests.control_plan_test_support import (
    authority_commandability_evidence,
    authority_model_snapshot,
    authority_outbox_rows,
)

from core.authority_grant import (
    EVENT_GRANTED,
    EVENT_RENEWED,
    EVENT_REVOKED,
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_REVOKED,
    AuthorityEvidenceCorruptError,
    AuthorityEvidenceError,
    AuthorityGrantCandidate,
    AuthorityHistoryCorruptError,
    ExecutionAuthorityError,
    build_grant_document,
    derive_authority_grant_status,
    grant_content_sha256,
    intent_set_sha256,
    parse_scope_document,
    validate_authority_evidence,
    verify_fail_safe_close_authority,
    verify_execution_authority,
)
from core.canonical_json import canonicalize

NOW = datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
SHA_E = "e" * 64
SHA_F = "f" * 64

INTENT_HASH_1 = "1" * 64
INTENT_HASH_2 = "2" * 64
RELEASE_ID = "hydraulic-model-2026.06"
CAPABILITY_RELEASE_ID = "field-registry-2026.06"
GATE = "MC-01"
SECTION = "S-1"
PATH = ["R-1", "R-2"]


def _event(
    sequence: int,
    event_type: str,
    *,
    expires_at: Optional[datetime] = None,
    occurred_at: Optional[datetime] = None,
):
    return SimpleNamespace(
        event_sequence=sequence,
        event_type=event_type,
        effective_expires_at=expires_at,
        occurred_at=occurred_at or (NOW - 2 * HOUR + sequence * timedelta(minutes=1)),
    )


def _granted(expires_at: Optional[datetime] = None):
    return _event(1, EVENT_GRANTED, expires_at=expires_at or (NOW + 12 * HOUR))


class TestDeriveAuthorityGrantStatus:
    def test_granted_history_is_active_before_expiry(self):
        derived = derive_authority_grant_status([_granted()], NOW)
        assert derived.status == STATUS_ACTIVE
        assert derived.effective_expires_at == NOW + 12 * HOUR

    def test_grant_status_expires_at_exact_boundary(self):
        # Exclusive-active boundary matching 5.2 deadline semantics: at exactly
        # expires_at the grant is EXPIRED, not active.
        expiry = NOW + 12 * HOUR
        derived = derive_authority_grant_status([_granted(expiry)], expiry)
        assert derived.status == STATUS_EXPIRED

    def test_renewal_extends_effective_expiry(self):
        events = [
            _granted(NOW + 1 * HOUR),
            _event(2, EVENT_RENEWED, expires_at=NOW + 20 * HOUR),
        ]
        derived = derive_authority_grant_status(events, NOW + 2 * HOUR)
        assert derived.status == STATUS_ACTIVE
        assert derived.effective_expires_at == NOW + 20 * HOUR

    def test_revoked_wins_over_unexpired_renewal(self):
        events = [
            _granted(NOW + 12 * HOUR),
            _event(2, EVENT_RENEWED, expires_at=NOW + 20 * HOUR),
            _event(3, EVENT_REVOKED),
        ]
        assert derive_authority_grant_status(events, NOW).status == STATUS_REVOKED

    def test_revoked_is_terminal_even_after_expiry_passes(self):
        events = [_granted(NOW + 1 * HOUR), _event(2, EVENT_REVOKED)]
        derived = derive_authority_grant_status(events, NOW + 5 * HOUR)
        assert derived.status == STATUS_REVOKED

    @pytest.mark.parametrize(
        "events",
        [
            [],  # no history at all
            [_event(2, EVENT_RENEWED, expires_at=NOW + HOUR)],  # no granted birth
            [_granted(), _event(3, EVENT_RENEWED, expires_at=NOW + 20 * HOUR)],  # gap
            [_granted(), _granted()],  # two births (duplicate sequence 1)
            [  # event after terminal revocation
                _granted(),
                _event(2, EVENT_REVOKED),
                _event(3, EVENT_RENEWED, expires_at=NOW + 20 * HOUR),
            ],
            [  # two revocations
                _granted(),
                _event(2, EVENT_REVOKED),
                _event(3, EVENT_REVOKED),
            ],
            [_event(1, EVENT_GRANTED, expires_at=None)],  # birth without expiry
            [  # renewal that does not extend (equal expiry)
                _granted(NOW + 12 * HOUR),
                _event(2, EVENT_RENEWED, expires_at=NOW + 12 * HOUR),
            ],
            [
                _granted(),
                _event(2, EVENT_REVOKED, expires_at=NOW + HOUR),
            ],  # revoke w/ expiry
        ],
    )
    def test_corrupt_history_fails_closed(self, events):
        with pytest.raises(AuthorityHistoryCorruptError):
            derive_authority_grant_status(events, NOW)

    def test_naive_stored_timestamp_is_corruption(self):
        naive = _event(1, EVENT_GRANTED, expires_at=datetime(2026, 7, 21, 0, 0, 0))
        with pytest.raises(AuthorityHistoryCorruptError):
            derive_authority_grant_status([naive], NOW)

    @pytest.mark.parametrize(
        "events",
        [
            (
                _event(
                    1,
                    EVENT_GRANTED,
                    expires_at=NOW,
                    occurred_at=NOW,
                ),
            ),
            (
                _event(
                    1,
                    EVENT_GRANTED,
                    expires_at=NOW,
                    occurred_at=NOW - HOUR,
                ),
                _event(
                    2,
                    EVENT_RENEWED,
                    expires_at=NOW + 2 * HOUR,
                    occurred_at=NOW,
                ),
            ),
        ],
    )
    def test_expired_birth_or_post_expiry_renewal_is_corruption(self, events):
        with pytest.raises(AuthorityHistoryCorruptError):
            derive_authority_grant_status(events, NOW + HOUR)


def _commandability_evidence(**overrides):
    doc = authority_commandability_evidence(
        authority_model_snapshot(
            model_release_id=RELEASE_ID,
            model_release_content_hash=SHA_A,
            engine_descriptor_content_hash=SHA_B,
            capability_release_id=CAPABILITY_RELEASE_ID,
            capability_hash=SHA_C,
            approved_gate_ids=(GATE,),
        )
    )
    doc.update(overrides)
    return doc


def _scope(**overrides):
    doc = {
        "schema_version": 1,
        "gate_paths": [
            {
                "section_id": SECTION,
                "canonical_gate_id": GATE,
                "path_reach_ids": list(PATH),
            }
        ],
    }
    doc.update(overrides)
    return doc


def _candidate(**overrides) -> AuthorityGrantCandidate:
    base = dict(
        plan_id=PLAN_ID,
        plan_version=3,
        model_release_id=RELEASE_ID,
        model_release_content_hash=SHA_A,
        engine_descriptor_content_hash=SHA_B,
        commandability_evidence=_commandability_evidence(),
        capability_release_id=CAPABILITY_RELEASE_ID,
        capability_hash=SHA_C,
        scope=_scope(),
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


PLAN_ID = uuid4()


def _requirement(section=SECTION, gate=GATE, path=PATH):
    import json

    return SimpleNamespace(
        section_id=section,
        gate_id=gate,
        path_reach_ids_document_text=json.dumps(list(path)),
    )


def _gate_event(flow, planned_at, position=0.5, gate=GATE):
    return SimpleNamespace(
        gate_id=gate,
        source_flow_m3s=flow,
        target_position_m=position,
        planned_at=planned_at,
    )


def _record(**overrides):
    snapshot = authority_model_snapshot(
        model_release_id=RELEASE_ID,
        model_release_content_hash=SHA_A,
        engine_descriptor_content_hash=SHA_B,
    )
    base = dict(
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
            _gate_event(5.0, NOW + 1 * HOUR, position=0.5),
            _gate_event(0.0, NOW + 4 * HOUR, position=0.0),
        ),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _snapshot(release_id=CAPABILITY_RELEASE_ID, cap_hash=SHA_C, gates=(GATE,)):
    return SimpleNamespace(
        capability_release_id=release_id,
        capability_hash=cap_hash,
        capabilities={gate: object() for gate in gates},
    )


def _context(**overrides):
    base = dict(
        record=_record(),
        derived_lifecycle_state="shadow_active",
        snapshot=_snapshot(),
        outbox_intent_count=2,
        accepted_receipt_intent_count=2,
        matching_receipt_intent_count=2,
        outbox_intents=(),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _validate(candidate=None, context=None, now=NOW, lease_hours=24):
    return validate_authority_evidence(
        candidate or _candidate(),
        context or _context(),
        now=now,
        lease_hours=lease_hours,
    )


class TestValidateAuthorityEvidence:
    def test_complete_candidate_validates(self):
        _validate()  # must not raise

    def test_grant_rejects_noncommandable_model_release(self):
        candidate = _candidate(
            commandability_evidence=_commandability_evidence(
                commandability_approval_content_hash=SHA_F
            )
        )
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(candidate)
        assert excinfo.value.reason == "noncommandable_release"

    def test_commandability_evidence_must_bind_the_same_release(self):
        candidate = _candidate(
            commandability_evidence=_commandability_evidence(
                approval_refs=["different-approval"]
            )
        )
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(candidate)
        assert excinfo.value.reason == "noncommandable_release"

    def test_grant_scope_rejects_unapproved_gate_or_flow(self):
        # A scope gate with no approved device capability fails closed...
        with pytest.raises(AuthorityEvidenceError) as unapproved:
            _validate(context=_context(snapshot=_snapshot(gates=("OTHER-GATE",))))
        assert unapproved.value.reason == "scope_unapproved_gate"
        # ...and a plan flow outside the approved envelope fails closed.
        with pytest.raises(AuthorityEvidenceError) as out_of_envelope:
            _validate(_candidate(flow_upper_inclusive_m3s=4.0))
        assert out_of_envelope.value.reason == "envelope_violation"

    def test_v1_provenance_plan_is_never_grantable(self):
        record = _record(provenance_version=None, engine_descriptor_content_hash=None)
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(context=_context(record=record))
        assert excinfo.value.reason == "plan_not_v2"

    def test_release_triple_must_match_the_stored_plan(self):
        record = _record(engine_descriptor_content_hash=SHA_F)
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(context=_context(record=record))
        assert excinfo.value.reason == "release_mismatch"

    def test_plan_must_hold_shadow_authority(self):
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(context=_context(derived_lifecycle_state="approved_for_shadow"))
        assert excinfo.value.reason == "plan_not_shadow_active"

    def test_capability_pair_must_match_the_configured_snapshot(self):
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(context=_context(snapshot=_snapshot(cap_hash=SHA_F)))
        assert excinfo.value.reason == "capability_mismatch"

    def test_outbox_capability_pair_must_match_the_grant(self):
        context = _context(
            outbox_intents=(
                SimpleNamespace(
                    capability_release_id="superseded-capability",
                    capability_hash=SHA_F,
                ),
            )
        )
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(context=context)
        assert excinfo.value.reason == "capability_mismatch"

    def test_scope_must_exactly_equal_the_plan_scope(self):
        extra_gate = _scope()
        extra_gate["gate_paths"] = extra_gate["gate_paths"] + [
            {
                "section_id": "S-2",
                "canonical_gate_id": "MC-02",
                "path_reach_ids": ["R-9"],
            }
        ]
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(
                _candidate(scope=extra_gate),
                # MC-02 exists in the registry, so the failure is scope
                # inequality with the PLAN — not an unapproved gate.
                _context(snapshot=_snapshot(gates=(GATE, "MC-02"))),
            )
        assert excinfo.value.reason == "scope_mismatch"

    def test_scope_path_must_match_the_plan_path_order(self):
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(
                _candidate(
                    scope=_scope(
                        gate_paths=[
                            {
                                "section_id": SECTION,
                                "canonical_gate_id": GATE,
                                "path_reach_ids": list(reversed(PATH)),
                            }
                        ]
                    )
                )
            )
        assert excinfo.value.reason == "scope_mismatch"

    def test_receipt_coverage_must_be_complete(self):
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(context=_context(accepted_receipt_intent_count=1))
        assert excinfo.value.reason == "receipt_coverage_incomplete"

    def test_plan_with_no_intents_has_no_shadow_evidence(self):
        context = _context(outbox_intent_count=0, accepted_receipt_intent_count=0)
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(context=context)
        assert excinfo.value.reason == "receipt_coverage_incomplete"

    def test_continuous_open_longer_than_policy_is_rejected(self):
        # The single open interval spans 3h (open at +1h, close at +4h); a 2h
        # policy cap must reject it.
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(_candidate(maximum_continuous_open_seconds=2 * 3600))
        assert excinfo.value.reason == "envelope_violation"

    def test_open_at_horizon_end_counts_to_horizon_end(self):
        # A rolling plan whose gate never closes stays open until horizon_end
        # (NOW+10h): opening at +1h means 9h continuous open, above an 8h cap.
        record = _record(events=(_gate_event(5.0, NOW + 1 * HOUR, position=0.5),))
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(
                _candidate(maximum_continuous_open_seconds=8 * 3600),
                _context(record=record),
            )
        assert excinfo.value.reason == "envelope_violation"

    def test_trim_policy_below_plan_setting_is_rejected(self):
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(
                _candidate(maximum_intermediate_trims=0),
                _context(record=_record(max_intermediate_trims=1)),
            )
        assert excinfo.value.reason == "envelope_violation"

    def test_initialization_must_be_the_dry_contract(self):
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(_candidate(initialization={"kind": "wet"}))
        assert excinfo.value.reason == "evidence_incomplete"

    @pytest.mark.parametrize(
        "overrides",
        [
            {"shadow_evidence_sha256": ""},
            {"shadow_evidence_sha256": "not-a-sha"},
            {"hold_drill_evidence_sha256": None},
            {"rollback_drill_evidence_sha256": "ABC"},
            {"evidence_manifest": {"schema_version": 1, "refs": []}},
            {"evidence_manifest": {"schema_version": 1, "refs": ["  "]}},
        ],
    )
    def test_incomplete_drill_evidence_is_rejected(self, overrides):
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(_candidate(**overrides))
        assert excinfo.value.reason == "evidence_incomplete"

    @pytest.mark.parametrize(
        "expires_at",
        [
            NOW,  # not strictly future
            NOW - HOUR,  # past
            NOW + 25 * HOUR,  # beyond the 24h lease cap
        ],
    )
    def test_expiry_must_be_future_and_lease_capped(self, expires_at):
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(_candidate(expires_at=expires_at))
        assert excinfo.value.reason == "expiry_invalid"

    def test_expiry_exactly_at_lease_cap_is_allowed(self):
        _validate(_candidate(expires_at=NOW + 24 * HOUR))  # must not raise


def _intent_rows(
    *,
    gate=GATE,
    capability_release_id=CAPABILITY_RELEASE_ID,
    capability_hash=SHA_C,
):
    return authority_outbox_rows(
        plan_id=PLAN_ID,
        plan_version=3,
        model_release_id=RELEASE_ID,
        model_release_content_hash=SHA_A,
        engine_descriptor_content_hash=SHA_B,
        capability_release_id=capability_release_id,
        capability_hash=capability_hash,
        canonical_gate_id=gate,
        now=NOW,
    )


def _grant_row(candidate=None, granted_intent_hashes=None):
    candidate = candidate or _candidate()
    granted_intent_hashes = granted_intent_hashes or tuple(
        row.intent_content_hash for row in _intent_rows()
    )
    granted_intent_set = intent_set_sha256(granted_intent_hashes)
    document = build_grant_document(
        candidate, intent_content_hashes=granted_intent_hashes
    )
    return SimpleNamespace(
        grant_id=uuid4(),
        intent_set_sha256=granted_intent_set,
        plan_id=candidate.plan_id,
        plan_version=candidate.plan_version,
        model_release_id=candidate.model_release_id,
        model_release_content_hash=candidate.model_release_content_hash,
        engine_descriptor_content_hash=candidate.engine_descriptor_content_hash,
        capability_release_id=candidate.capability_release_id,
        capability_hash=candidate.capability_hash,
        scope_document_text=canonicalize(candidate.scope),
        flow_lower_exclusive_m3s=candidate.flow_lower_exclusive_m3s,
        flow_upper_inclusive_m3s=candidate.flow_upper_inclusive_m3s,
        grant_document_text=canonicalize(document),
        grant_content_sha256=grant_content_sha256(document),
    )


def _execution_context(**overrides):
    base = dict(
        plan_id=PLAN_ID,
        plan_version=3,
        model_release_id=RELEASE_ID,
        model_release_content_hash=SHA_A,
        engine_descriptor_content_hash=SHA_B,
        capability_release_id=CAPABILITY_RELEASE_ID,
        capability_hash=SHA_C,
        derived_lifecycle_state="shadow_active",
        intents=_intent_rows(),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestVerifyExecutionAuthority:
    def test_active_matching_grant_authorizes_the_whole_batch(self):
        verify_execution_authority(
            _grant_row(), [_granted()], _execution_context(), now=NOW
        )  # must not raise

    def test_expired_or_revoked_grant_blocks_execution(self):
        expiry = NOW + 12 * HOUR
        with pytest.raises(ExecutionAuthorityError) as expired:
            verify_execution_authority(
                _grant_row(), [_granted(expiry)], _execution_context(), now=expiry
            )
        assert expired.value.reason_code == "grant_not_active"
        with pytest.raises(ExecutionAuthorityError) as revoked:
            verify_execution_authority(
                _grant_row(),
                [_granted(), _event(2, EVENT_REVOKED)],
                _execution_context(),
                now=NOW,
            )
        assert revoked.value.reason_code == "grant_not_active"

    def test_release_identity_mismatch_blocks(self):
        context = _execution_context(engine_descriptor_content_hash=SHA_F)
        with pytest.raises(ExecutionAuthorityError) as excinfo:
            verify_execution_authority(_grant_row(), [_granted()], context, now=NOW)
        assert excinfo.value.reason_code == "release_mismatch"

    def test_capability_hash_drift_blocks(self):
        context = _execution_context(capability_hash=SHA_F)
        with pytest.raises(ExecutionAuthorityError) as excinfo:
            verify_execution_authority(_grant_row(), [_granted()], context, now=NOW)
        assert excinfo.value.reason_code == "capability_mismatch"

    def test_plan_identity_mismatch_blocks(self):
        context = _execution_context(plan_version=4)
        with pytest.raises(ExecutionAuthorityError) as excinfo:
            verify_execution_authority(_grant_row(), [_granted()], context, now=NOW)
        assert excinfo.value.reason_code == "release_mismatch"

    def test_non_active_plan_lifecycle_blocks(self):
        context = _execution_context(derived_lifecycle_state="invalidated")
        with pytest.raises(ExecutionAuthorityError) as excinfo:
            verify_execution_authority(_grant_row(), [_granted()], context, now=NOW)
        assert excinfo.value.reason_code == "plan_not_executable"

    def test_any_out_of_scope_intent_blocks_the_whole_batch(self):
        # WHOLE-BATCH preflight: intent 1 alone would pass; the out-of-scope
        # intent 2 must fail the batch BEFORE any (future) first write.
        rows = _intent_rows(gate="MC-99")
        context = _execution_context(intents=rows)
        grant = _grant_row(
            granted_intent_hashes=tuple(row.intent_content_hash for row in rows)
        )
        with pytest.raises(ExecutionAuthorityError) as excinfo:
            verify_execution_authority(grant, [_granted()], context, now=NOW)
        assert excinfo.value.reason_code == "scope_exceeded"

    def test_typed_target_drift_from_document_blocks(self):
        rows = _intent_rows()
        context = _execution_context(
            intents=(replace(rows[0], target_position_m=9.5), rows[1])
        )
        with pytest.raises(ExecutionAuthorityError) as excinfo:
            verify_execution_authority(_grant_row(), [_granted()], context, now=NOW)
        assert excinfo.value.reason_code == "intent_evidence_corrupt"

    def test_empty_intent_batch_is_refused(self):
        context = _execution_context(intents=())
        with pytest.raises(ExecutionAuthorityError) as excinfo:
            verify_execution_authority(_grant_row(), [_granted()], context, now=NOW)
        assert excinfo.value.reason_code == "scope_exceeded"

    def test_corrupt_scope_document_fails_closed(self):
        grant = _grant_row()
        grant.scope_document_text = "{not json"
        with pytest.raises(ExecutionAuthorityError) as excinfo:
            verify_execution_authority(
                grant, [_granted()], _execution_context(), now=NOW
            )
        assert excinfo.value.reason_code == "evidence_corrupt"

    def test_corrupt_history_fails_closed_as_evidence_corrupt(self):
        with pytest.raises(ExecutionAuthorityError) as excinfo:
            verify_execution_authority(_grant_row(), [], _execution_context(), now=NOW)
        assert excinfo.value.reason_code == "evidence_corrupt"


class TestGrantDocument:
    def test_document_hash_is_deterministic_and_content_bound(self):
        first = grant_content_sha256(
            build_grant_document(
                _candidate(), intent_content_hashes=(INTENT_HASH_1, INTENT_HASH_2)
            )
        )
        second = grant_content_sha256(
            build_grant_document(
                _candidate(), intent_content_hashes=(INTENT_HASH_1, INTENT_HASH_2)
            )
        )
        assert first == second
        changed = grant_content_sha256(
            build_grant_document(
                _candidate(flow_upper_inclusive_m3s=7.5),
                intent_content_hashes=(INTENT_HASH_1, INTENT_HASH_2),
            )
        )
        assert changed != first
        # A different immutable intent batch is a DIFFERENT grant.
        rebatched = grant_content_sha256(
            build_grant_document(
                _candidate(),
                intent_content_hashes=(INTENT_HASH_1,),
            )
        )
        assert rebatched != first

    def test_document_round_trips_the_scope(self):
        document = build_grant_document(
            _candidate(), intent_content_hashes=(INTENT_HASH_1, INTENT_HASH_2)
        )
        text = canonicalize(document)
        import json

        parsed = json.loads(text)
        assert parse_scope_document(canonicalize(parsed["scope"])) == {
            (SECTION, GATE): tuple(PATH)
        }


class TestStoredSnapshotCommandability:
    """QCHECK fix (Codex CRITICAL): request evidence can NEVER promote — the
    STORED model snapshot must itself declare a commandable release."""

    def test_stored_noncommandable_snapshot_rejects_even_with_true_evidence(self):
        snapshot = authority_model_snapshot(
            model_release_id=RELEASE_ID,
            model_release_content_hash=SHA_A,
            engine_descriptor_content_hash=SHA_B,
            commandable=False,
        )
        record = _record(
            model_snapshot_id=snapshot["snapshot_id"],
            model_snapshot_document_text=json.dumps(snapshot),
        )
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(context=_context(record=record))
        assert excinfo.value.reason == "noncommandable_release"

    def test_v3_true_booleans_reject_without_a_versioned_approval(self):
        snapshot = authority_model_snapshot(
            model_release_id=RELEASE_ID,
            model_release_content_hash=SHA_A,
            engine_descriptor_content_hash=SHA_B,
        )
        snapshot.pop("commandability_approval")
        snapshot["schema_version"] = 3
        payload = dict(snapshot)
        payload.pop("snapshot_id")
        snapshot["snapshot_id"] = hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        record = _record(
            model_snapshot_id=snapshot["snapshot_id"],
            model_snapshot_document_text=json.dumps(snapshot),
        )

        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(context=_context(record=record))

        assert excinfo.value.reason == "noncommandable_release"

    def test_tampered_v4_approval_after_snapshot_rehash_is_corruption(self):
        snapshot = authority_model_snapshot(
            model_release_id=RELEASE_ID,
            model_release_content_hash=SHA_A,
            engine_descriptor_content_hash=SHA_B,
        )
        snapshot["commandability_approval"]["device_capability"][
            "capability_hash"
        ] = SHA_F
        payload = dict(snapshot)
        payload.pop("snapshot_id")
        snapshot["snapshot_id"] = hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        record = _record(
            model_snapshot_id=snapshot["snapshot_id"],
            model_snapshot_document_text=json.dumps(snapshot),
        )

        with pytest.raises(AuthorityEvidenceCorruptError):
            _validate(context=_context(record=record))

    def test_full_flow_snapshot_metadata_does_not_invalidate_the_v4_approval(self):
        snapshot = authority_model_snapshot(
            model_release_id=RELEASE_ID,
            model_release_content_hash=SHA_A,
            engine_descriptor_content_hash=SHA_B,
        )
        snapshot["scada_graph"].update(
            {
                "source_workbook_sha256": SHA_D,
                "root_node_id": "S",
                "gate_count": 1,
                "edge_count": 1,
                "edges": [],
            }
        )
        snapshot["routing_topology"].update(
            {
                "schema_version": 1,
                "content_hash": SHA_E,
                "root_node_id": "S",
                "node_count": 2,
                "element_count": 1,
                "role_counts": {"transport": 1},
                "elements": [],
            }
        )
        payload = dict(snapshot)
        payload.pop("snapshot_id")
        snapshot["snapshot_id"] = hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        record = _record(
            model_snapshot_id=snapshot["snapshot_id"],
            model_snapshot_document_text=json.dumps(snapshot),
        )
        candidate = _candidate(
            commandability_evidence=authority_commandability_evidence(snapshot)
        )

        _validate(candidate, context=_context(record=record))

    def test_malformed_approval_timestamp_is_stored_evidence_corruption(self):
        snapshot = authority_model_snapshot(
            model_release_id=RELEASE_ID,
            model_release_content_hash=SHA_A,
            engine_descriptor_content_hash=SHA_B,
        )
        approval = snapshot["commandability_approval"]
        approval["approval"]["approved_at"] = "not-a-timeZ"
        approval_payload = dict(approval)
        approval_payload.pop("content_hash")
        approval["content_hash"] = hashlib.sha256(
            json.dumps(
                approval_payload,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        payload = dict(snapshot)
        payload.pop("snapshot_id")
        snapshot["snapshot_id"] = hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        record = _record(
            model_snapshot_id=snapshot["snapshot_id"],
            model_snapshot_document_text=json.dumps(snapshot),
        )

        with pytest.raises(AuthorityEvidenceCorruptError):
            _validate(context=_context(record=record))

    def test_approval_capability_pair_must_match_current_server_snapshot(self):
        snapshot = authority_model_snapshot(
            model_release_id=RELEASE_ID,
            model_release_content_hash=SHA_A,
            engine_descriptor_content_hash=SHA_B,
            capability_hash=SHA_F,
        )
        record = _record(
            model_snapshot_id=snapshot["snapshot_id"],
            model_snapshot_document_text=json.dumps(snapshot),
        )

        candidate = _candidate(
            commandability_evidence=authority_commandability_evidence(snapshot)
        )
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(candidate, context=_context(record=record))

        assert excinfo.value.reason == "capability_mismatch"

    def test_approval_gate_scope_must_equal_the_plan_physical_scope(self):
        snapshot = authority_model_snapshot(
            model_release_id=RELEASE_ID,
            model_release_content_hash=SHA_A,
            engine_descriptor_content_hash=SHA_B,
            approved_gate_ids=("OTHER-GATE",),
        )
        record = _record(
            model_snapshot_id=snapshot["snapshot_id"],
            model_snapshot_document_text=json.dumps(snapshot),
        )

        candidate = _candidate(
            commandability_evidence=authority_commandability_evidence(snapshot)
        )
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(candidate, context=_context(record=record))

        assert excinfo.value.reason == "scope_mismatch"

    def test_grant_flow_envelope_must_equal_the_approved_snapshot_envelope(self):
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(_candidate(flow_upper_inclusive_m3s=7.0))

        assert excinfo.value.reason == "envelope_violation"

    @pytest.mark.parametrize(
        "snapshot_text",
        [
            "{}",  # commandable key absent
            "{not json",  # unreadable
            "[]",  # not an object
        ],
    )
    def test_missing_or_malformed_stored_snapshot_fails_closed(self, snapshot_text):
        record = _record(model_snapshot_document_text=snapshot_text)
        with pytest.raises(AuthorityEvidenceCorruptError):
            _validate(context=_context(record=record))

    @pytest.mark.parametrize(
        "snapshot_overrides",
        [
            {"model_release_id": "different-release"},
            {"model_release_content_hash": SHA_F},
            {"engine_descriptor_content_hash": SHA_F},
        ],
    )
    def test_snapshot_release_and_engine_pins_must_match_plan(self, snapshot_overrides):
        snapshot = authority_model_snapshot(
            model_release_id=snapshot_overrides.get("model_release_id", RELEASE_ID),
            model_release_content_hash=snapshot_overrides.get(
                "model_release_content_hash", SHA_A
            ),
            engine_descriptor_content_hash=snapshot_overrides.get(
                "engine_descriptor_content_hash", SHA_B
            ),
        )
        record = _record(
            model_snapshot_id=snapshot["snapshot_id"],
            model_snapshot_document_text=json.dumps(snapshot),
        )
        with pytest.raises(AuthorityEvidenceCorruptError):
            _validate(context=_context(record=record))

    def test_snapshot_content_must_reproduce_its_pinned_identity(self):
        snapshot = authority_model_snapshot(
            model_release_id=RELEASE_ID,
            model_release_content_hash=SHA_A,
            engine_descriptor_content_hash=SHA_B,
        )
        snapshot["action_model"]["extra"] = "tampered-after-hash"
        record = _record(model_snapshot_document_text=json.dumps(snapshot))
        with pytest.raises(AuthorityEvidenceCorruptError):
            _validate(context=_context(record=record))

    @pytest.mark.parametrize(
        "snapshot_kwargs",
        [
            {"response_commandable": False},
            {"action_commandable": False},
            {"actuation_approved": False},
        ],
    )
    def test_every_stored_commandability_gate_must_be_true(self, snapshot_kwargs):
        snapshot = authority_model_snapshot(
            model_release_id=RELEASE_ID,
            model_release_content_hash=SHA_A,
            engine_descriptor_content_hash=SHA_B,
            **snapshot_kwargs,
        )
        record = _record(
            model_snapshot_id=snapshot["snapshot_id"],
            model_snapshot_document_text=json.dumps(snapshot),
        )
        with pytest.raises(AuthorityEvidenceError) as excinfo:
            _validate(context=_context(record=record))
        assert excinfo.value.reason == "noncommandable_release"


class TestIntentSetBinding:
    """QCHECK fix: the grant authorizes EXACTLY one immutable intent batch."""

    def test_altered_intent_hash_blocks_the_batch(self):
        rows = _intent_rows()
        context = _execution_context(
            intents=(replace(rows[0], intent_content_hash="9" * 64), rows[1])
        )
        with pytest.raises(ExecutionAuthorityError) as excinfo:
            verify_execution_authority(_grant_row(), [_granted()], context, now=NOW)
        assert excinfo.value.reason_code == "intent_evidence_corrupt"

    def test_missing_or_extra_intent_blocks_the_batch(self):
        rows = _intent_rows()
        missing = _execution_context(intents=(rows[0],))
        with pytest.raises(ExecutionAuthorityError) as gone:
            verify_execution_authority(_grant_row(), [_granted()], missing, now=NOW)
        assert gone.value.reason_code == "intent_set_mismatch"
        extra = _execution_context(intents=(rows[0], rows[1], rows[1]))
        with pytest.raises(ExecutionAuthorityError) as dup:
            verify_execution_authority(_grant_row(), [_granted()], extra, now=NOW)
        assert dup.value.reason_code == "intent_set_mismatch"

    def test_intent_without_a_hash_fails_closed(self):
        rows = _intent_rows()
        context = _execution_context(
            intents=(replace(rows[0], intent_content_hash=""), rows[1])
        )
        with pytest.raises(ExecutionAuthorityError) as excinfo:
            verify_execution_authority(_grant_row(), [_granted()], context, now=NOW)
        assert excinfo.value.reason_code == "intent_evidence_corrupt"

    def test_typed_capability_drift_from_document_fails_closed(self):
        rows = _intent_rows()
        context = _execution_context(
            intents=(replace(rows[0], capability_hash=SHA_F), rows[1])
        )
        with pytest.raises(ExecutionAuthorityError) as excinfo:
            verify_execution_authority(_grant_row(), [_granted()], context, now=NOW)
        assert excinfo.value.reason_code == "intent_evidence_corrupt"

    def test_verified_outbox_batch_is_authorized(self):
        context = _execution_context()
        verify_execution_authority(_grant_row(), [_granted()], context, now=NOW)

    def test_reordered_intents_block_the_batch(self):
        context = _execution_context()
        reordered = _execution_context(intents=tuple(reversed(context.intents)))
        with pytest.raises(ExecutionAuthorityError) as excinfo:
            verify_execution_authority(_grant_row(), [_granted()], reordered, now=NOW)
        assert excinfo.value.reason_code == "intent_batch_mismatch"

    def test_altered_document_with_retained_hash_blocks_the_batch(self):
        context = _execution_context()
        altered = tuple(
            replace(
                intent,
                intent_document_text='{"target_position_m":999}',
            )
            for intent in context.intents
        )
        with pytest.raises(ExecutionAuthorityError) as excinfo:
            verify_execution_authority(
                _grant_row(),
                [_granted()],
                _execution_context(intents=altered),
                now=NOW,
            )
        assert excinfo.value.reason_code == "intent_evidence_corrupt"


class TestFailSafeCloseAuthority:
    def test_revoked_held_grant_authorizes_only_the_granted_close_at_zero(self):
        context = _execution_context()
        close = next(
            row
            for row in context.intents
            if json.loads(row.intent_document_text)["event_kind"] == "close"
        )
        verify_fail_safe_close_authority(
            _grant_row(),
            [_granted(), _event(2, EVENT_REVOKED)],
            context,
            selected_intent_id=close.intent_id,
            is_held=True,
            now=NOW,
        )

    def test_fail_safe_close_never_authorizes_open_or_an_unheld_plan(self):
        context = _execution_context()
        opened = next(
            row
            for row in context.intents
            if json.loads(row.intent_document_text)["event_kind"] == "open"
        )
        with pytest.raises(ExecutionAuthorityError, match="close-at-zero"):
            verify_fail_safe_close_authority(
                _grant_row(),
                [_granted(NOW)],
                context,
                selected_intent_id=opened.intent_id,
                is_held=True,
                now=NOW,
            )
        with pytest.raises(ExecutionAuthorityError, match="operator-held"):
            verify_fail_safe_close_authority(
                _grant_row(),
                [_granted(NOW)],
                context,
                selected_intent_id=opened.intent_id,
                is_held=False,
                now=NOW,
            )
