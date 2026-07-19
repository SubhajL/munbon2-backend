"""Compile an approved v2 control plan into 6.0 CommandIntents (PR 4.3c-1).

Pure and I/O-free: one ``CommandIntent`` per ``gate_plan_event``, binding the
device/level/capability_hash from the 6.1a snapshot (exact membership) and the v2
lineage from the immutable record. Ids are CONTENT-ADDRESSED and DETERMINISTIC
(uuid5) so re-activation replays identically; they are keyed on the GLOBAL
``event_sequence`` — never the per-gate ``gate_event_sequence`` (which restarts at
1 for each gate and would collide across gates). ``mode`` is always ``shadow``:
nothing here dispatches or actuates.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import timezone
from typing import List

from pydantic import ValidationError

from core.canonical_json import canonicalize
from core.device_capabilities import capability_member
from schemas.machine_boundary import CommandIntent, CommandLineage

# Deterministic namespace (uuid5 is content-derived, not random) so intent ids are
# stable across processes and replays.
_INTENT_NS = uuid.uuid5(uuid.NAMESPACE_URL, "munbon:machine-boundary:command-intent:v1")


class NonActivatablePlanError(Exception):
    """The plan lacks the v2 provenance a CommandIntent lineage requires."""


def _utc_instant(dt) -> str:
    """Format a datetime as a contract UtcInstant (RFC-3339 UTC, trailing ``Z``).

    ``datetime.isoformat()`` on a UTC-aware value yields ``+00:00`` which fails the
    contract regex; the boundary requires ``Z``.
    """
    aware = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(
        timezone.utc
    )
    return aware.replace(tzinfo=None).isoformat() + "Z"


def _require_v2(record) -> None:
    if (
        getattr(record, "prediction_identity_version", None) != 2
        or getattr(record, "prediction_run_id", None) is None
        or getattr(record, "engine_descriptor_content_hash", None) is None
        or getattr(record, "artifact_sha256", None) is None
    ):
        raise NonActivatablePlanError(
            "only a v2 (artifact-reference) plan carries an activatable lineage"
        )


def _lineage(record, requirement_set_sha256: str) -> CommandLineage:
    return CommandLineage(
        campaign_id=str(record.campaign_id),
        plan_id=str(record.plan_id),
        plan_version=record.plan_version,
        input_content_hash=record.input_content_hash,
        draft_content_hash=record.draft_content_hash,
        requirement_run_id=str(record.requirement_run_id),
        requirement_version=record.requirement_version,
        requirement_set_sha256=requirement_set_sha256,
        model_snapshot_id=record.model_snapshot_id,
        model_release_id=record.model_release_id,
        model_release_content_hash=record.model_release_content_hash,
        prediction_run_id=record.prediction_run_id,
        prediction_identity_version=record.prediction_identity_version,
        engine_descriptor_content_hash=record.engine_descriptor_content_hash,
        artifact_sha256=record.artifact_sha256,
    )


def compile_command_intents(
    record,
    snapshot,
    *,
    activation_sequence: int,
    request_id: str,
    requirement_set_sha256: str,
) -> List[CommandIntent]:
    """One CommandIntent per gate event, in event_sequence order. Fails closed on a
    non-v2 plan (NonActivatablePlanError) or a non-member position/gate
    (CapabilityMembershipError) — never emits an unachievable command."""
    _require_v2(record)
    try:
        lineage = _lineage(record, requirement_set_sha256)
    except ValidationError as error:
        # A stored lineage field that violates the machine-boundary contract (a
        # non-hex hash, an id with a space) is a fail-closed 409, never a 500.
        raise NonActivatablePlanError(
            f"the plan lineage is not a valid CommandLineage: {error}"
        ) from error
    correlation_id = str(
        uuid.uuid5(
            _INTENT_NS,
            f"{record.plan_id}:{record.plan_version}:activation:{activation_sequence}",
        )
    )
    deadline = _utc_instant(record.horizon_end)
    intents: List[CommandIntent] = []
    for event in sorted(record.events, key=lambda e: e.event_sequence):
        binding = capability_member(snapshot, event.gate_id, event.target_position_m)
        try:
            intent = CommandIntent(
                schema_version=1,
                intent_id=str(
                    uuid.uuid5(
                        _INTENT_NS,
                        f"{record.plan_id}:{record.plan_version}:{event.event_sequence}",
                    )
                ),
                correlation_id=correlation_id,
                request_id=request_id,
                idempotency_key=(
                    f"cmd.{record.plan_id}.{record.plan_version}.{event.event_sequence}"
                ),
                canonical_gate_id=event.gate_id,
                event_kind=event.event_kind,
                event_sequence=event.event_sequence,
                gate_event_sequence=event.gate_event_sequence,
                device_id=binding.device_id,
                adapter_gate_id=binding.adapter_gate_id,
                capability_release_id=binding.capability_release_id,
                capability_hash=binding.capability_hash,
                target_position_m=event.target_position_m,
                target_level=binding.target_level,
                not_before=_utc_instant(event.planned_at),
                deadline=deadline,
                mode="shadow",
                lineage=lineage,
            )
        except ValidationError as error:
            raise NonActivatablePlanError(
                f"gate event {event.event_sequence} does not form a valid "
                f"CommandIntent: {error}"
            ) from error
        intents.append(intent)
    return intents


def command_intent_content_hash(intent: CommandIntent) -> str:
    """Stable content hash over the canonical JSON of the intent (drives the outbox
    ``intent_content_hash`` + the 6.2 ValidationReceipt)."""
    return hashlib.sha256(
        canonicalize(intent.model_dump()).encode("utf-8")
    ).hexdigest()
