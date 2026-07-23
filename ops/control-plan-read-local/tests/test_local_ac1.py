from datetime import datetime, timezone
import importlib.util
from pathlib import Path
from uuid import UUID

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "local-ac1.py"
SPEC = importlib.util.spec_from_file_location("local_ac1", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
local_ac1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(local_ac1)

UTC = timezone.utc
RUN_ID = UUID("11111111-1111-4111-8111-111111111111")
REQUIREMENT_ID = UUID("22222222-2222-4222-8222-222222222222")


def test_build_branch_allocations_covers_each_nonwithdrawal_branch_equally():
    elements = [
        {
            "upstream_node_id": "S",
            "downstream_node_id": "A",
            "role": "transport",
        },
        {
            "upstream_node_id": "S",
            "downstream_node_id": "B",
            "role": "branch_structure",
        },
        {
            "upstream_node_id": "S",
            "downstream_node_id": "W",
            "role": "withdrawal_structure",
        },
        {
            "upstream_node_id": "B",
            "downstream_node_id": "C",
            "role": "transport",
        },
    ]

    assert local_ac1.build_branch_allocations(elements) == [
        {"upstream_node_id": "S", "downstream_node_id": "A", "fraction": 0.5},
        {"upstream_node_id": "S", "downstream_node_id": "B", "fraction": 0.5},
    ]


def test_build_branch_allocations_keeps_unavailable_transport_reach_dry():
    elements = [
        {
            "element_id": "C_S_A",
            "upstream_node_id": "S",
            "downstream_node_id": "A",
            "role": "transport",
        },
        {
            "element_id": "B_S_B",
            "upstream_node_id": "S",
            "downstream_node_id": "B",
            "role": "branch_structure",
        },
    ]

    assert local_ac1.build_branch_allocations(elements, {"C_S_A"}) == [
        {"upstream_node_id": "S", "downstream_node_id": "A", "fraction": 0.0},
        {"upstream_node_id": "S", "downstream_node_id": "B", "fraction": 1.0},
    ]


def test_build_control_plan_draft_uses_actual_requirements_and_dark_snapshot():
    window_start = datetime(2026, 7, 22, 19, tzinfo=UTC)
    window_end = datetime(2026, 7, 23, 19, tzinfo=UTC)
    requirements = [
        {
            "requirementId": str(REQUIREMENT_ID),
            "runId": str(RUN_ID),
            "version": 1,
            "serviceDate": "2026-07-23",
            "sectionId": "01-06-01-35",
            "zone": 6,
            "requiredVolumeM3": 9000.0,
            "deliveryWindow": {
                "start": window_start.isoformat(),
                "end": window_end.isoformat(),
            },
            "dataStatus": "published",
        }
    ]
    snapshot = {
        "commandable": False,
        "action_model": {
            "commandable": False,
            "actuation_approved": False,
            "operating_envelope": {
                "minimum_flow_m3s": 0.0,
                "maximum_flow_m3s": 11.2,
                "minimum_timestep_seconds": 60.0,
                "maximum_timestep_seconds": 300.0,
                "maximum_horizon_seconds": 604800.0,
            },
        },
        "response_model": {
            "commandable": False,
            "reach_parameters": [
                {
                    "reach_id": "C_M(0,0)_M(0,0;2,0)",
                    "capacity_m3s": {
                        "lower": 0.25,
                        "nominal": 0.3,
                        "upper": 0.35,
                    },
                }
            ],
        },
        "unavailable_transport_reaches": [],
        "routing_topology": {
            "elements": [
                {
                    "upstream_node_id": "S",
                    "downstream_node_id": "M(0,0)",
                    "role": "boundary",
                },
                {
                    "upstream_node_id": "M(0,0)",
                    "downstream_node_id": "M(0,0;2,0)",
                    "role": "transport",
                    "element_id": "C_M(0,0)_M(0,0;2,0)",
                },
            ]
        },
    }

    draft = local_ac1.build_control_plan_draft(
        requirements,
        snapshot,
        {"01-06-01-35": "M(0,0;2,0)"},
    )

    assert draft == {
        "requirement_run_id": str(RUN_ID),
        "requirement_version": 1,
        "requirement_scopes": [{"service_date": "2026-07-23", "zone": 6}],
        "starts_at": window_start.isoformat(),
        "ends_at": window_end.isoformat(),
        "section_bindings": [
            {
                "section_id": "01-06-01-35",
                "delivery_node_id": "M(0,0;2,0)",
                "gate_id": "M(0,0;2,0)",
                "maximum_delivery_m3s": 0.1,
            }
        ],
        "requirement_policies": [
            {
                "requirement_id": str(REQUIREMENT_ID),
                "approved_excess_m3": 4500.0,
                "rotation_windows": [
                    {
                        "starts_at": window_start.isoformat(),
                        "ends_at": window_end.isoformat(),
                    }
                ],
            }
        ],
        "flow_candidates": [
            {
                "gate_id": "M(0,0;2,0)",
                "target_position_m": 0.5,
                "source_flow_m3s": 0.1,
            }
        ],
        "pulse_duties": [
            {
                "gate_id": "M(0,0;2,0)",
                "minimum_open_seconds": 300,
                "maximum_open_seconds": 86400,
            }
        ],
        "operator_withdrawals": [],
        "branch_allocations": [],
    }


def test_build_control_plan_draft_omits_zero_volume_boundary_only_requirement():
    window_start = datetime(2026, 7, 22, 19, tzinfo=UTC)
    window_end = datetime(2026, 7, 23, 19, tzinfo=UTC)
    requirements = [
        {
            "requirementId": str(REQUIREMENT_ID),
            "runId": str(RUN_ID),
            "version": 1,
            "serviceDate": "2026-07-23",
            "sectionId": "01-06-01-35",
            "zone": 6,
            "requiredVolumeM3": 0,
            "deliveryWindow": {
                "start": window_start.isoformat(),
                "end": window_end.isoformat(),
            },
            "dataStatus": "published",
        },
        {
            "requirementId": "33333333-3333-4333-8333-333333333333",
            "runId": str(RUN_ID),
            "version": 1,
            "serviceDate": "2026-07-23",
            "sectionId": "01-06-01-36",
            "zone": 6,
            "requiredVolumeM3": 9000.0,
            "deliveryWindow": {
                "start": window_start.isoformat(),
                "end": window_end.isoformat(),
            },
            "dataStatus": "published",
        },
    ]
    snapshot = {
        "commandable": False,
        "action_model": {
            "commandable": False,
            "actuation_approved": False,
            "operating_envelope": {"maximum_flow_m3s": 11.2},
        },
        "response_model": {
            "commandable": False,
            "reach_parameters": [
                {
                    "reach_id": "C_M(0,0;2,0)_M(0,0;2,1)",
                    "capacity_m3s": {
                        "lower": 0.5,
                        "nominal": 0.6,
                        "upper": 0.7,
                    },
                }
            ],
        },
        "unavailable_transport_reaches": [],
        "routing_topology": {
            "elements": [
                {
                    "upstream_node_id": "S",
                    "downstream_node_id": "M(0,0;2,0)",
                    "role": "branch_structure",
                },
                {
                    "upstream_node_id": "M(0,0;2,0)",
                    "downstream_node_id": "M(0,0;2,1)",
                    "role": "transport",
                    "element_id": "C_M(0,0;2,0)_M(0,0;2,1)",
                },
            ]
        },
    }

    draft = local_ac1.build_control_plan_draft(
        requirements,
        snapshot,
        {
            "01-06-01-35": "M(0,0;2,0)",
            "01-06-01-36": "M(0,0;2,1)",
        },
    )

    assert draft["section_bindings"] == [
        {
            "section_id": "01-06-01-36",
            "delivery_node_id": "M(0,0;2,1)",
            "gate_id": "M(0,0;2,1)",
            "maximum_delivery_m3s": 0.1,
        }
    ]
    assert [item["requirement_id"] for item in draft["requirement_policies"]] == [
        "33333333-3333-4333-8333-333333333333"
    ]


@pytest.mark.parametrize(
    ("requirements", "snapshot", "gates", "error"),
    [
        ([], {}, {}, "requirements_not_accepted"),
        (
            [
                {
                    "requirementId": str(REQUIREMENT_ID),
                    "runId": str(RUN_ID),
                    "version": 1,
                    "serviceDate": "2026-07-23",
                    "sectionId": "01-06-01-35",
                    "zone": 6,
                    "requiredVolumeM3": 1.0,
                    "deliveryWindow": {
                        "start": "2026-07-22T19:00:00+00:00",
                        "end": "2026-07-23T19:00:00+00:00",
                    },
                    "dataStatus": "published",
                }
            ],
            {
                "commandable": True,
                "action_model": {
                    "commandable": False,
                    "actuation_approved": False,
                    "operating_envelope": {"maximum_flow_m3s": 11.2},
                },
                "routing_topology": {"elements": []},
            },
            {"01-06-01-35": "M(0,0;2,0)"},
            "snapshot_not_dark",
        ),
    ],
)
def test_build_control_plan_draft_fails_closed_on_invalid_inputs(
    requirements, snapshot, gates, error
):
    with pytest.raises(local_ac1.LocalAcceptanceError, match=error):
        local_ac1.build_control_plan_draft(requirements, snapshot, gates)


def test_projection_paths_covers_every_local_ac1_bff_read():
    assert local_ac1.projection_paths("33333333-3333-4333-8333-333333333333", 1) == (
        "/api/v1/control-plans",
        ("/api/v1/control-plans/" "33333333-3333-4333-8333-333333333333/versions/1"),
        (
            "/api/v1/control-plans/"
            "33333333-3333-4333-8333-333333333333/versions/1/"
            "prediction-coverage"
        ),
        (
            "/api/v1/control-plans/"
            "33333333-3333-4333-8333-333333333333/versions/1/ledger"
        ),
        (
            "/api/v1/control-plans/"
            "33333333-3333-4333-8333-333333333333/versions/1/"
            "lifecycle-history"
        ),
        (
            "/api/v1/control-plans/"
            "33333333-3333-4333-8333-333333333333/versions/1/intent-timeline"
        ),
        (
            "/api/v1/control-plans/"
            "33333333-3333-4333-8333-333333333333/versions/1/"
            "readback-observations"
        ),
        (
            "/api/v1/control-plans/"
            "33333333-3333-4333-8333-333333333333/versions/1/execution-state"
        ),
    )
