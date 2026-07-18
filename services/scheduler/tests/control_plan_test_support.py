"""Shared fakes and fixture builders for the PR 4.3a control-plan tests.

Non-test filename: never collected. The fakes pin the real client/repository
interfaces — tests/unit/test_control_service_clients.py asserts their method
signatures match the production classes exactly.
"""

import json
from dataclasses import replace
from datetime import date, datetime, timezone
from uuid import UUID

from core.control_plan import canonical_json_text
from repositories.control_plan_repository import (
    PlanContentConflictError,
    TransitionConflictError,
)

RUN_ID = UUID("8e0b0e6a-6c1e-5f5e-9d5c-2f6a8b1c2d3e")
REQ_ID = "7c8a4c62-4b0e-5efd-9c3a-111111111111"


def requirement_item(volume=6000.0, run_id=None, requirement_id=None, version=3):
    return {
        "requirement_id": requirement_id or REQ_ID,
        "run_id": str(run_id or RUN_ID),
        "version": version,
        "service_date": date(2026, 7, 20),
        "section_id": "SEC-1",
        "zone": 1,
        "required_volume_m3": volume,
        "window_start": datetime(2026, 7, 20, 6, 0, tzinfo=timezone.utc),
        "window_end": datetime(2026, 7, 20, 18, 0, tzinfo=timezone.utc),
        "quality": "estimated",
        "published_at": datetime(2026, 7, 19, 19, 5, tzinfo=timezone.utc),
        "as_of_date": date(2026, 7, 19),
        "data_status": "published",
    }


def snapshot_mirror():
    return {
        "snapshot_id": "a" * 64,
        "data_status": "complete",
        "routing_topology": {
            # N1 is a genuine branching node (children N2, N3), matching flow's
            # network-wide allocation contract. Delivery for SEC-1 is at N4 via
            # the N2 branch; N3 is the sibling branch, NW the withdrawal.
            "elements": [
                {
                    "element_id": "R1",
                    "upstream_node_id": "S",
                    "downstream_node_id": "N1",
                    "role": "transport",
                },
                {
                    "element_id": "B1",
                    "upstream_node_id": "N1",
                    "downstream_node_id": "N2",
                    "role": "branch_structure",
                },
                {
                    "element_id": "B2",
                    "upstream_node_id": "N1",
                    "downstream_node_id": "N3",
                    "role": "branch_structure",
                },
                {
                    "element_id": "R2",
                    "upstream_node_id": "N2",
                    "downstream_node_id": "N4",
                    "role": "transport",
                },
                {
                    "element_id": "W1",
                    "upstream_node_id": "N1",
                    "downstream_node_id": "NW",
                    "role": "withdrawal_structure",
                },
            ]
        },
        "action_model": {
            "operating_envelope": {
                "minimum_flow_m3s": 0.0,
                "maximum_flow_m3s": 10.0,
                "minimum_timestep_seconds": 300.0,
                "maximum_timestep_seconds": 3600.0,
                "maximum_horizon_seconds": 604800.0,
            }
        },
        "response_model_release": {
            "release_id": "release-2026-07",
            "content_hash": "b" * 64,
            "response_members": [
                {
                    "reach_id": reach_id,
                    "member": member,
                    "delay_seconds": delay,
                    "loss_fraction": loss,
                    "capacity_m3s": capacity,
                }
                for reach_id, rows in {
                    "R1": [
                        ("lower", 500.0, 0.10, 5.0),
                        ("nominal", 600.0, 0.05, 5.5),
                        ("upper", 700.0, 0.02, 6.0),
                    ],
                    "R2": [
                        ("lower", 1000.0, 0.05, 3.2),
                        ("nominal", 1100.0, 0.04, 3.0),
                        ("upper", 1150.0, 0.02, 3.1),
                    ],
                }.items()
                for member, delay, loss, capacity in rows
            ],
        },
        "unavailable_transport_reaches": [],
    }


def draft_payload(**overrides):
    payload = {
        "requirement_run_id": str(RUN_ID),
        "requirement_version": 3,
        "requirement_scopes": [{"service_date": "2026-07-20", "zone": 1}],
        "starts_at": "2026-07-20T00:00:00+00:00",
        "ends_at": "2026-07-21T00:00:00+00:00",
        "section_bindings": [
            {
                "section_id": "SEC-1",
                "delivery_node_id": "N4",
                "gate_id": "G1",
                "maximum_delivery_m3s": 2.5,
            }
        ],
        "requirement_policies": [
            {
                "requirement_id": REQ_ID,
                "approved_excess_m3": 1000.0,
                "rotation_windows": [
                    {
                        "starts_at": "2026-07-20T06:00:00+00:00",
                        "ends_at": "2026-07-20T18:00:00+00:00",
                    }
                ],
            }
        ],
        "flow_candidates": [
            {"gate_id": "G1", "target_position_m": 0.5, "source_flow_m3s": 2.0}
        ],
        "pulse_duties": [
            {
                "gate_id": "G1",
                "minimum_open_seconds": 3600,
                "maximum_open_seconds": 86400,
            }
        ],
        "operator_withdrawals": [],
        "branch_allocations": [
            {"upstream_node_id": "N1", "downstream_node_id": "N2",
             "fraction": 0.6},
            {"upstream_node_id": "N1", "downstream_node_id": "N3",
             "fraction": 0.4},
        ],
    }
    payload.update(overrides)
    return payload


class FakeRosGisClient:
    def __init__(self, items):
        self.items = items
        self.calls = 0

    async def get_exact_requirements(
        self, requirement_run_id, requirement_version, scopes
    ):
        self.calls += 1
        return [dict(item) for item in self.items]


def _build_member_timeline(request_document, member_name):
    """A realistic, aligned, reconciling three-member timeline for the SEC-1
    delivery at N4 over reaches R1, R2. All members deliver exactly the required
    volume (degenerate bounds) so the projector's reconciliation holds."""
    from datetime import datetime, timedelta

    starts_at = datetime.fromisoformat(request_document["starts_at"])
    ends_at = datetime.fromisoformat(request_document["ends_at"])
    step = int(request_document["timestep_seconds"])
    count = int((ends_at - starts_at).total_seconds() // step)
    # Match flow: sampled_at are step-END times, so the last sample == ends_at.
    sampled = [
        (starts_at + timedelta(seconds=(i + 1) * step)).isoformat()
        for i in range(count)
    ]
    reach_ids = ["R1", "R2"]
    reaches = [
        {
            "reach_id": rid,
            "inflow_m3s": [0.0] * count,
            "outflow_m3s": [0.0] * count,
            "in_transit_volume_m3": [
                (2.0 if 0 < i < count - 1 else 0.0) for i in range(count)
            ],
            "cumulative_declared_loss_m3": [0.0] * count,
        }
        for rid in reach_ids
    ]
    requirements = []
    final = []
    total = 0.0
    for section in request_document["section_requirements"]:
        required = float(section["required_volume_m3"])
        total += required
        delivered = [
            required * min(1.0, (i + 1) / max(1, count - 1))
            for i in range(count)
        ]
        delivered[-1] = required
        status = [
            "pending" if i == 0
            else ("predicted_fulfilled" if i == count - 1
                  else "delivery_predicted_active")
            for i in range(count)
        ]
        requirements.append(
            {
                "requirement_id": section["requirement_id"],
                "predicted_delivered_m3": delivered,
                "status": status,
            }
        )
        final.append(
            {
                "requirement_id": section["requirement_id"],
                "section_id": section["section_id"],
                "required_volume_m3": required,
                "approved_excess_m3": float(section["approved_excess_m3"]),
                "predicted_delivered_m3": required,
                "status": "predicted_fulfilled",
            }
        )
    return total, {
        "sampled_at": sampled,
        "reaches": reaches,
        "withdrawals": [],
        "requirements": requirements,
        "terminal_outflow_m3": [0.0] * count,
        "mass_balance": {
            "initial_in_transit_m3": 0.0,
            "boundary_inflow_m3": total,
            "delivered_m3": total,
            "withdrawn_m3": 0.0,
            "declared_loss_m3": 0.0,
            "terminal_outflow_m3": 0.0,
            "final_in_transit_m3": 0.0,
            "balance_error_m3": 0.0,
        },
        "final_fulfillment": final,
    }


class FakeControlFlowClient:
    def __init__(
        self,
        snapshot,
        prediction_members=None,
        prediction_error=None,
        snapshot_error=None,
        with_timeline=True,
        infeasible_members=None,
    ):
        self.snapshot = snapshot
        # When prediction_members is given, the caller controls the members
        # verbatim (used to exercise malformed responses). Otherwise a realistic
        # reconciling three-member timeline is built per request; members named
        # in infeasible_members are emitted as timeline-less infeasible members.
        self.prediction_members = prediction_members
        self.prediction_error = prediction_error
        self.snapshot_error = snapshot_error
        self.with_timeline = with_timeline
        self.infeasible_members = set(infeasible_members or ())
        self.prediction_requests = []

    async def create_model_snapshot(self):
        if self.snapshot_error is not None:
            raise self.snapshot_error
        return (
            canonical_json_text({"snapshot": self.snapshot["snapshot_id"]}),
            json.loads(json.dumps(self.snapshot)),
        )

    async def create_prediction(self, request_document):
        if self.prediction_error is not None:
            raise self.prediction_error
        self.prediction_requests.append(request_document)
        if self.prediction_members is not None:
            members = self.prediction_members
        elif self.with_timeline:
            members = []
            for name in ("lower", "nominal", "upper"):
                if name in self.infeasible_members:
                    members.append(
                        {
                            "member": name,
                            "status": "infeasible",
                            "predicted_delivered_total_m3": None,
                            "timeline": None,
                        }
                    )
                    continue
                total, timeline = _build_member_timeline(request_document, name)
                members.append(
                    {
                        "member": name,
                        "status": "completed",
                        "predicted_delivered_total_m3": total,
                        "timeline": timeline,
                    }
                )
        else:
            members = [
                {"member": "lower", "status": "completed"},
                {"member": "nominal", "status": "completed"},
                {"member": "upper", "status": "completed"},
            ]
        body = {
            "prediction_run_id": "c" * 64,
            "model_snapshot_id": request_document["model_snapshot_id"],
            "model_release_id": request_document["model_release_id"],
            "model_release_content_hash": request_document[
                "model_release_content_hash"
            ],
            "starts_at": request_document["starts_at"],
            "ends_at": request_document["ends_at"],
            "members": members,
        }
        return canonical_json_text(body), body


class FakeRepository:
    def __init__(self):
        self.by_input_hash = {}
        self.by_key = {}
        self.store_calls = 0

    async def find_by_input_hash(self, session, input_content_hash):
        return self.by_input_hash.get(input_content_hash)

    async def store_draft_plan(self, session, record):
        self.store_calls += 1
        # Mirror production exactly: the race-loser replays on canonical INPUT
        # only (solver nondeterminism must not 409), and the winning writer
        # returns its own in-memory record (with the service's injected-clock
        # timestamps) rather than a post-commit reload.
        existing = self.by_input_hash.get(record.input_content_hash)
        if existing is not None:
            if (
                existing.canonical_input_document_text
                != record.canonical_input_document_text
            ):
                raise PlanContentConflictError(
                    "an identical input hash is stored with different content"
                )
            return existing, True
        self.by_input_hash[record.input_content_hash] = record
        self.by_key[(record.plan_id, record.plan_version)] = record
        return record, False

    async def load_draft_plan(self, session, plan_id, plan_version):
        return self.by_key.get((plan_id, plan_version))

    async def append_state_transition(
        self, session, plan_id, plan_version, transition
    ):
        record = self.by_key.get((plan_id, plan_version))
        if record is None:
            raise KeyError((plan_id, plan_version))
        # The real repository's (plan, version, sequence) PK is the concurrency
        # backstop: a second append at the same sequence conflicts.
        if any(
            t.transition_sequence == transition.transition_sequence
            for t in record.transitions
        ):
            raise TransitionConflictError(
                "a concurrent lifecycle action already advanced this plan"
            )
        updated = replace(
            record, transitions=record.transitions + (transition,)
        )
        self.by_key[(plan_id, plan_version)] = updated
        self.by_input_hash[record.input_content_hash] = updated
