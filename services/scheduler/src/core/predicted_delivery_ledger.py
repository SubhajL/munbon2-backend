"""Pure predicted-fulfillment ledger projection (PR 5.1).

Projects a feasible draft's already-persisted flow prediction response into
per-requirement, per-checkpoint delivery-ledger entries. No hydraulics are
recomputed here — every value is copied or summed from the persisted artifact,
and the horizon-end totals are reconciled back to it. Flow deliberately
attributes NO in-transit volume to requirements (delivery accounting is
delivered-only; the transit picture lives in the reach series), so per-
requirement transit is the sum of the requirement's own path reaches' persisted
`in_transit_volume_m3` — path occupancy CONTEXT, never additive across
requirements. Member labels (lower/nominal/upper) are parameter-distribution
positions, not a delivery ordering, so bounds are min/max across members.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

LEDGER_HASH_PREFIX = "scheduler:section-delivery-ledger:v1\n"
LEDGER_SET_HASH_PREFIX = "scheduler:section-delivery-ledger-set:v1\n"

_MEMBERS = ("lower", "nominal", "upper")
_LEDGER_STATUSES = frozenset(
    {
        "not_started",
        "predicted_in_progress",
        "predicted_fulfilled",
        "predicted_excess_risk",
        "invalidated",
        "manual_review",
    }
)
# Numeric reconciliation tolerance: absolute floor plus a relative term.
_ABS_TOL = 1e-8
_REL_TOL = 1e-12


class LedgerProjectionError(ValueError):
    """The persisted prediction artifact cannot be projected into a ledger."""


@dataclass(frozen=True)
class ScheduledRequirement:
    requirement_id: str
    section_id: str
    gate_id: str
    required_volume_m3: float
    approved_excess_m3: float
    path_reach_ids: tuple[str, ...]
    window_start: datetime
    window_end: datetime


@dataclass(frozen=True)
class GateEvent:
    gate_id: str
    kind: str
    planned_at: datetime
    target_position_m: float


@dataclass(frozen=True)
class LedgerEntry:
    requirement_id: str
    section_id: str
    checkpoint_index: int
    checkpoint_at: datetime
    status: str
    required_volume_m3: float
    approved_excess_m3: float
    lower_delivered_m3: Optional[float]
    nominal_delivered_m3: Optional[float]
    upper_delivered_m3: Optional[float]
    lower_path_in_transit_m3: Optional[float]
    nominal_path_in_transit_m3: Optional[float]
    upper_path_in_transit_m3: Optional[float]
    checkpoint_reasons: tuple[str, ...]
    prediction_run_id: str
    prediction_response_sha256: str
    projection_sha256: str
    projection_document_text: str


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise LedgerProjectionError(message)


def _canonical(payload: Any) -> str:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    )


def ledger_row_sha256(projection_document_text: str) -> str:
    return hashlib.sha256(
        (LEDGER_HASH_PREFIX + projection_document_text).encode("utf-8")
    ).hexdigest()


def verify_ledger_entry_columns(entry: "LedgerEntry") -> None:
    """Fail closed if any queryable/served ledger column drifts from the
    hash-bound projection document. Columns — not just the document — are what
    the API and handover math read, so a column edited independently of the
    document (and its hash) must be rejected."""
    if ledger_row_sha256(entry.projection_document_text) != (
        entry.projection_sha256
    ):
        raise LedgerProjectionError("ledger row does not match its content hash")
    document = json.loads(entry.projection_document_text)
    checks = {
        "requirement_id": entry.requirement_id,
        "section_id": entry.section_id,
        "checkpoint_index": entry.checkpoint_index,
        "status": entry.status,
        "required_volume_m3": entry.required_volume_m3,
        "approved_excess_m3": entry.approved_excess_m3,
        "prediction_run_id": entry.prediction_run_id,
        "prediction_response_sha256": entry.prediction_response_sha256,
    }
    for key, value in checks.items():
        if document.get(key) != value:
            raise LedgerProjectionError(
                f"ledger column {key!r} does not match the hashed document"
            )
    if document.get("checkpoint_at") != entry.checkpoint_at.astimezone(
        timezone.utc
    ).isoformat():
        raise LedgerProjectionError(
            "ledger column checkpoint_at does not match the hashed document"
        )
    delivered = document.get("delivered", {})
    transit = document.get("path_in_transit", {})
    envelope = {
        ("delivered", "lower"): entry.lower_delivered_m3,
        ("delivered", "nominal"): entry.nominal_delivered_m3,
        ("delivered", "upper"): entry.upper_delivered_m3,
        ("path_in_transit", "lower"): entry.lower_path_in_transit_m3,
        ("path_in_transit", "nominal"): entry.nominal_path_in_transit_m3,
        ("path_in_transit", "upper"): entry.upper_path_in_transit_m3,
    }
    for (group, member), value in envelope.items():
        source = delivered if group == "delivered" else transit
        if source.get(member) != value:
            raise LedgerProjectionError(
                f"ledger column {group}.{member} does not match the hashed "
                "document"
            )
    if list(document.get("checkpoint_reasons", [])) != list(
        entry.checkpoint_reasons
    ):
        raise LedgerProjectionError(
            "ledger column checkpoint_reasons does not match the hashed document"
        )


def coalesce_equal_gate_events(
    events: Sequence[GateEvent],
) -> list[dict[str, Any]]:
    """Classify a gate's ordered events as physical moves vs no-write
    checkpoints. An equal adjacent target position (e.g. holding a level across
    midnight) is a checkpoint that must NOT create a new gate command."""
    ordered = sorted(events, key=lambda event: event.planned_at)
    classified: list[dict[str, Any]] = []
    previous_position: Optional[float] = None
    for event in ordered:
        movement_required = (
            previous_position is None
            or event.target_position_m != previous_position
        )
        classified.append(
            {
                "gate_id": event.gate_id,
                "planned_at": event.planned_at,
                "kind": event.kind,
                "target_position_m": event.target_position_m,
                "movement_required": movement_required,
            }
        )
        previous_position = event.target_position_m
    return classified


def _completed_members(
    prediction_response: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    members = prediction_response.get("members")
    _require(
        isinstance(members, list) and len(members) == 3,
        "prediction response must carry exactly three members",
    )
    by_name: dict[str, Mapping[str, Any]] = {}
    completed: dict[str, Mapping[str, Any]] = {}
    for member in members:
        name = member.get("member")
        status = member.get("status")
        timeline = member.get("timeline")
        _require(name in _MEMBERS, f"unknown member label {name!r}")
        _require(name not in by_name, f"duplicate member {name!r}")
        by_name[name] = member
        if status == "completed":
            _require(
                timeline is not None,
                f"member {name!r} is completed but carries no timeline",
            )
            completed[name] = timeline
        elif status == "infeasible":
            _require(
                timeline is None,
                f"member {name!r} is infeasible but carries a timeline",
            )
        else:
            raise LedgerProjectionError(
                f"member {name!r} carries unknown status {status!r}"
            )
    _require(set(by_name) == set(_MEMBERS), "members must be lower/nominal/upper")
    return completed


def _requirement_series(
    timeline: Mapping[str, Any], requirement_id: str, sample_count: int
) -> Mapping[str, Any]:
    for series in timeline["requirements"]:
        if series["requirement_id"] == requirement_id:
            _require(
                len(series["predicted_delivered_m3"]) == sample_count
                and len(series["status"]) == sample_count,
                f"requirement {requirement_id!r} series length mismatch",
            )
            return series
    raise LedgerProjectionError(
        f"requirement {requirement_id!r} absent from a completed timeline"
    )


def _reach_series(
    timeline: Mapping[str, Any], sample_count: int
) -> dict[str, Sequence[float]]:
    by_reach: dict[str, Sequence[float]] = {}
    for series in timeline["reaches"]:
        _require(
            len(series["in_transit_volume_m3"]) == sample_count,
            f"reach {series['reach_id']!r} series length mismatch",
        )
        by_reach[series["reach_id"]] = series["in_transit_volume_m3"]
    return by_reach


def _path_in_transit(
    reach_by_id: Mapping[str, Sequence[float]],
    path_reach_ids: Sequence[str],
    index: int,
) -> float:
    total = 0.0
    for reach_id in path_reach_ids:
        series = reach_by_id.get(reach_id)
        _require(
            series is not None,
            f"path reach {reach_id!r} absent from the prediction timeline",
        )
        total += float(series[index])
    return total


def _aggregate_status(
    member_statuses: Sequence[str], any_infeasible: bool
) -> str:
    if any_infeasible:
        return "manual_review"
    if any(status == "predicted_excess" for status in member_statuses):
        return "predicted_excess_risk"
    if all(status == "predicted_fulfilled" for status in member_statuses):
        return "predicted_fulfilled"
    if all(status == "pending" for status in member_statuses):
        return "not_started"
    return "predicted_in_progress"


def _checkpoint_indices(
    requirement: ScheduledRequirement,
    sampled_at: Sequence[datetime],
    completed: Mapping[str, Mapping[str, Any]],
    gate_events: Sequence[GateEvent],
) -> dict[int, list[str]]:
    sample_count = len(sampled_at)
    step_seconds = None
    if sample_count >= 2:
        step_seconds = (sampled_at[1] - sampled_at[0]).total_seconds()
    reasons: dict[int, list[str]] = {}

    def add(index: int, reason: str) -> None:
        clamped = max(0, min(index, sample_count - 1))
        reasons.setdefault(clamped, [])
        if reason not in reasons[clamped]:
            reasons[clamped].append(reason)

    def index_of(instant: datetime) -> int:
        if step_seconds is None or step_seconds == 0:
            return 0
        return round((instant - sampled_at[0]).total_seconds() / step_seconds)

    # Flow's sampled_at are step-END times, so index 0 is the first step's end
    # (there is no sample at the horizon start) and the last is the horizon end.
    add(0, "first_sample")
    add(sample_count - 1, "horizon_end")
    add(index_of(requirement.window_start), "window_start")
    add(index_of(requirement.window_end), "window_end")
    for i in range(1, sample_count):
        if sampled_at[i].date() != sampled_at[i - 1].date():
            add(i, "date_rollover")
    for classified in coalesce_equal_gate_events(
        [e for e in gate_events if e.gate_id == requirement.gate_id]
    ):
        reason = (
            "gate_move" if classified["movement_required"] else "gate_checkpoint"
        )
        add(index_of(classified["planned_at"]), reason)
    for timeline in completed.values():
        series = _requirement_series(
            timeline, requirement.requirement_id, sample_count
        )["status"]
        for i in range(1, sample_count):
            if series[i] != series[i - 1]:
                add(i, "status_transition")
    return reasons


def project_predicted_delivery_ledger(
    scheduled_requirements: Sequence[ScheduledRequirement],
    prediction_response: Mapping[str, Any],
    gate_events: Sequence[GateEvent],
    *,
    prediction_run_id: str,
    prediction_response_sha256: str,
) -> list[LedgerEntry]:
    """Project the persisted prediction into immutable ledger entries.

    Returns entries for every scheduled requirement. Fails closed on any array
    misalignment, missing requirement/reach, or horizon-end total that does not
    reconcile to the persisted member totals.
    """
    completed = _completed_members(prediction_response)
    entries: list[LedgerEntry] = []

    if not completed:
        # All three members infeasible: one honest manual_review row.
        for requirement in scheduled_requirements:
            entries.append(
                _build_entry(
                    requirement=requirement,
                    checkpoint_index=1,
                    checkpoint_at=_first_sampled_at(prediction_response),
                    status="manual_review",
                    delivered={},
                    transit={},
                    reasons=("all_members_infeasible",),
                    prediction_run_id=prediction_run_id,
                    prediction_response_sha256=prediction_response_sha256,
                )
            )
        return entries

    any_reference_timeline = next(iter(completed.values()))
    sampled_at = _parse_sampled_at(any_reference_timeline)
    _validate_sampled_at(sampled_at)
    sample_count = len(sampled_at)
    reference_utc = [instant.astimezone(timezone.utc) for instant in sampled_at]
    for name, timeline in completed.items():
        member_samples = _parse_sampled_at(timeline)
        # Every completed member must share the EXACT timeline, else a row would
        # splice one member's value at t with another's at t±step.
        _require(
            len(member_samples) == sample_count
            and [i.astimezone(timezone.utc) for i in member_samples]
            == reference_utc,
            f"member {name!r} sample timestamps do not match the reference "
            "member",
        )
    any_infeasible = len(completed) < 3

    reach_by_member = {
        name: _reach_series(timeline, sample_count)
        for name, timeline in completed.items()
    }
    series_by_member = {
        name: {
            requirement.requirement_id: _requirement_series(
                timeline, requirement.requirement_id, sample_count
            )
            for requirement in scheduled_requirements
        }
        for name, timeline in completed.items()
    }

    for requirement in scheduled_requirements:
        reasons_by_index = _checkpoint_indices(
            requirement, sampled_at, completed, gate_events
        )
        sequence = 0
        for index in sorted(reasons_by_index):
            sequence += 1
            delivered = {
                name: float(
                    series_by_member[name][requirement.requirement_id][
                        "predicted_delivered_m3"
                    ][index]
                )
                for name in completed
            }
            transit = {
                name: _path_in_transit(
                    reach_by_member[name], requirement.path_reach_ids, index
                )
                for name in completed
            }
            member_statuses = [
                series_by_member[name][requirement.requirement_id]["status"][
                    index
                ]
                for name in completed
            ]
            status = _aggregate_status(member_statuses, any_infeasible)
            entries.append(
                _build_entry(
                    requirement=requirement,
                    checkpoint_index=sequence,
                    checkpoint_at=sampled_at[index],
                    status=status,
                    delivered=delivered,
                    transit=transit,
                    reasons=tuple(reasons_by_index[index]),
                    prediction_run_id=prediction_run_id,
                    prediction_response_sha256=prediction_response_sha256,
                )
            )

    _reconcile_terminal_totals(
        prediction_response, completed, scheduled_requirements, sampled_at
    )
    return entries


def _build_entry(
    *,
    requirement: ScheduledRequirement,
    checkpoint_index: int,
    checkpoint_at: datetime,
    status: str,
    delivered: Mapping[str, float],
    transit: Mapping[str, float],
    reasons: tuple[str, ...],
    prediction_run_id: str,
    prediction_response_sha256: str,
) -> LedgerEntry:
    _require(status in _LEDGER_STATUSES, f"illegal ledger status {status!r}")
    document = {
        "requirement_id": requirement.requirement_id,
        "section_id": requirement.section_id,
        "checkpoint_index": checkpoint_index,
        # UTC-normalized so the content hash is machine-independent.
        "checkpoint_at": checkpoint_at.astimezone(timezone.utc).isoformat(),
        "status": status,
        "required_volume_m3": requirement.required_volume_m3,
        "approved_excess_m3": requirement.approved_excess_m3,
        "delivered": {name: delivered[name] for name in sorted(delivered)},
        "path_in_transit": {name: transit[name] for name in sorted(transit)},
        "path_reach_ids": list(requirement.path_reach_ids),
        "checkpoint_reasons": list(reasons),
        "prediction_run_id": prediction_run_id,
        "prediction_response_sha256": prediction_response_sha256,
    }
    text = _canonical(document)
    digest = ledger_row_sha256(text)
    return LedgerEntry(
        requirement_id=requirement.requirement_id,
        section_id=requirement.section_id,
        checkpoint_index=checkpoint_index,
        checkpoint_at=checkpoint_at,
        status=status,
        required_volume_m3=requirement.required_volume_m3,
        approved_excess_m3=requirement.approved_excess_m3,
        lower_delivered_m3=delivered.get("lower"),
        nominal_delivered_m3=delivered.get("nominal"),
        upper_delivered_m3=delivered.get("upper"),
        lower_path_in_transit_m3=transit.get("lower"),
        nominal_path_in_transit_m3=transit.get("nominal"),
        upper_path_in_transit_m3=transit.get("upper"),
        checkpoint_reasons=reasons,
        prediction_run_id=prediction_run_id,
        prediction_response_sha256=prediction_response_sha256,
        projection_sha256=digest,
        projection_document_text=text,
    )


def _parse_sampled_at(timeline: Mapping[str, Any]) -> list[datetime]:
    return [_parse_instant(value) for value in timeline["sampled_at"]]


def _validate_sampled_at(sampled_at: Sequence[datetime]) -> None:
    _require(len(sampled_at) >= 1, "timeline has no samples")
    utc = [instant.astimezone(timezone.utc) for instant in sampled_at]
    if len(utc) >= 2:
        step = (utc[1] - utc[0]).total_seconds()
        _require(step > 0, "timeline samples are not strictly increasing")
        for earlier, later in zip(utc, utc[1:]):
            gap = (later - earlier).total_seconds()
            _require(
                gap > 0,
                "timeline samples are not strictly increasing",
            )
            _require(
                abs(gap - step) <= 1e-6,
                "timeline samples are not uniformly spaced",
            )


def _first_sampled_at(prediction_response: Mapping[str, Any]) -> datetime:
    return _parse_instant(prediction_response["starts_at"])


def _parse_instant(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def _reconcile_terminal_totals(
    prediction_response: Mapping[str, Any],
    completed: Mapping[str, Mapping[str, Any]],
    scheduled_requirements: Sequence[ScheduledRequirement],
    sampled_at: Sequence[datetime],
) -> None:
    last = len(sampled_at) - 1
    members = {m["member"]: m for m in prediction_response["members"]}
    scheduled_ids = {r.requirement_id for r in scheduled_requirements}
    for name, timeline in completed.items():
        total = 0.0
        terminal_by_id: dict[str, float] = {}
        for requirement in scheduled_requirements:
            series = _requirement_series(
                timeline, requirement.requirement_id, len(sampled_at)
            )
            value = float(series["predicted_delivered_m3"][last])
            terminal_by_id[requirement.requirement_id] = value
            total += value
        member_total = members[name].get("predicted_delivered_total_m3")
        mass_balance = timeline["mass_balance"]["delivered_m3"]
        tolerance = max(_ABS_TOL, abs(member_total or 0.0) * _REL_TOL)
        _require(
            member_total is not None
            and abs(total - member_total) <= tolerance
            and abs(total - float(mass_balance)) <= tolerance,
            f"member {name!r} terminal delivered totals do not reconcile "
            f"(rows={total}, member={member_total}, mass_balance={mass_balance})",
        )
        # final_fulfillment must cover exactly the scheduled requirements and
        # agree with the terminal series — a summary that names another
        # requirement or a different volume is a malformed artifact.
        final = {
            row["requirement_id"]: float(row["predicted_delivered_m3"])
            for row in timeline["final_fulfillment"]
        }
        _require(
            scheduled_ids <= set(final),
            f"member {name!r} final_fulfillment does not cover every "
            "scheduled requirement",
        )
        for requirement_id, terminal_value in terminal_by_id.items():
            _require(
                abs(final[requirement_id] - terminal_value) <= tolerance,
                f"member {name!r} final_fulfillment for {requirement_id!r} "
                "disagrees with the terminal series",
            )


def predicted_delivery_ledger_sha256(entries: Sequence[LedgerEntry]) -> str:
    """Stable hash over the ordered per-row hashes, for 4.3b lineage pinning."""
    joined = "\n".join(entry.projection_sha256 for entry in entries)
    return hashlib.sha256(
        (LEDGER_SET_HASH_PREFIX + joined).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class HandoverVerdict:
    is_safe: bool
    reasons: tuple[str, ...]


def evaluate_safe_handover(
    gate_requirements: Sequence[ScheduledRequirement],
    entries: Sequence[LedgerEntry],
    gate_events: Sequence[GateEvent],
    *,
    all_members_completed: bool,
) -> HandoverVerdict:
    """Pure GATE-level predicate: is it modeled-safe to hand this physical gate
    over? EVERY requirement bound to the gate must terminally satisfy — a shared
    gate cannot be handed over while any of its obligations is short or undrained.

    Does NOT approve, supersede, or write any transition (4.3b owns lifecycle).
    Deliberately narrower than flow's earliest_safe_closure — 5.1 has no
    requirement-attributed transit commitments, so it only certifies a fully
    drained, envelope-satisfying terminal state.
    """
    reasons: list[str] = []
    _require(len(gate_requirements) >= 1, "no requirements for the gate")
    gate = gate_requirements[0].gate_id
    _require(
        all(r.gate_id == gate for r in gate_requirements),
        "evaluate_safe_handover requires one gate's requirements",
    )
    ordered = sorted(
        [e for e in gate_events if e.gate_id == gate],
        key=lambda e: e.planned_at,
    )
    if not ordered or ordered[-1].kind != "close":
        reasons.append("no_terminal_close_event")
    if not all_members_completed:
        reasons.append("incomplete_member_coverage")
    for requirement in gate_requirements:
        prefix = requirement.requirement_id
        requirement_rows = [
            e
            for e in entries
            if e.requirement_id == requirement.requirement_id
        ]
        if not requirement_rows:
            reasons.append(f"{prefix}:no_ledger_rows")
            continue
        terminal = max(requirement_rows, key=lambda e: e.checkpoint_index)
        if terminal.status in ("manual_review", "invalidated"):
            reasons.append(f"{prefix}:terminal_status_{terminal.status}")
        delivered_values = [
            v
            for v in (
                terminal.lower_delivered_m3,
                terminal.nominal_delivered_m3,
                terminal.upper_delivered_m3,
            )
            if v is not None
        ]
        transit_values = [
            v
            for v in (
                terminal.lower_path_in_transit_m3,
                terminal.nominal_path_in_transit_m3,
                terminal.upper_path_in_transit_m3,
            )
            if v is not None
        ]
        if len(delivered_values) < 3 or len(transit_values) < 3:
            reasons.append(f"{prefix}:missing_member_envelope")
            continue
        if min(delivered_values) < requirement.required_volume_m3:
            reasons.append(f"{prefix}:terminal_shortfall")
        if max(delivered_values) > (
            requirement.required_volume_m3 + requirement.approved_excess_m3
        ):
            reasons.append(f"{prefix}:terminal_excess_risk")
        if max(transit_values) > _ABS_TOL:
            reasons.append(f"{prefix}:undrained_path_transit")
    return HandoverVerdict(not reasons, tuple(reasons))
