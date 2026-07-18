"""Strict draft-request schema validation."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from schemas.control_plan import DraftControlPlanRequest


def _payload(**overrides):
    payload = {
        "requirement_run_id": "8e0b0e6a-6c1e-5f5e-9d5c-2f6a8b1c2d3e",
        "requirement_version": 3,
        "requirement_scopes": [{"service_date": "2026-07-20", "zone": 1}],
        "starts_at": "2026-07-20T00:00:00+00:00",
        "ends_at": "2026-07-21T00:00:00+00:00",
        "section_bindings": [
            {
                "section_id": "SEC-1",
                "delivery_node_id": "N3",
                "gate_id": "G1",
                "maximum_delivery_m3s": 2.5,
            }
        ],
        "requirement_policies": [
            {
                "requirement_id": "req-1",
                "approved_excess_m3": 100.0,
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
        "branch_allocations": [],
    }
    payload.update(overrides)
    return payload


class TestDraftControlPlanRequest:
    def test_valid_payload_parses_and_normalizes_to_utc(self):
        request = DraftControlPlanRequest.model_validate(
            _payload(starts_at="2026-07-20T07:00:00+07:00")
        )
        assert request.starts_at == datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc)

    def test_unknown_field_is_rejected(self):
        with pytest.raises(ValidationError):
            DraftControlPlanRequest.model_validate(_payload(surprise=1))

    def test_missing_collection_is_rejected_not_defaulted(self):
        payload = _payload()
        del payload["operator_withdrawals"]
        with pytest.raises(ValidationError):
            DraftControlPlanRequest.model_validate(payload)

    def test_naive_datetime_is_rejected(self):
        with pytest.raises(ValidationError):
            DraftControlPlanRequest.model_validate(
                _payload(starts_at="2026-07-20T00:00:00")
            )

    def test_non_finite_number_is_rejected(self):
        payload = _payload()
        payload["flow_candidates"][0]["source_flow_m3s"] = float("inf")
        with pytest.raises(ValidationError):
            DraftControlPlanRequest.model_validate(payload)

    def test_boolean_number_is_rejected(self):
        payload = _payload()
        payload["flow_candidates"][0]["source_flow_m3s"] = True
        with pytest.raises(ValidationError):
            DraftControlPlanRequest.model_validate(payload)

    def test_zero_length_horizon_is_rejected(self):
        with pytest.raises(ValidationError):
            DraftControlPlanRequest.model_validate(
                _payload(ends_at="2026-07-20T00:00:00+00:00")
            )

    def test_duplicate_scope_is_rejected(self):
        scopes = [
            {"service_date": "2026-07-20", "zone": 1},
            {"service_date": "2026-07-20", "zone": 1},
        ]
        with pytest.raises(ValidationError):
            DraftControlPlanRequest.model_validate(
                _payload(requirement_scopes=scopes)
            )

    def test_zone_out_of_range_is_rejected(self):
        with pytest.raises(ValidationError):
            DraftControlPlanRequest.model_validate(
                _payload(requirement_scopes=[{"service_date": "2026-07-20", "zone": 7}])
            )

    def test_duplicate_section_binding_is_rejected(self):
        payload = _payload()
        payload["section_bindings"].append(dict(payload["section_bindings"][0]))
        with pytest.raises(ValidationError):
            DraftControlPlanRequest.model_validate(payload)

    def test_duplicate_candidate_position_is_rejected(self):
        payload = _payload()
        payload["flow_candidates"].append(dict(payload["flow_candidates"][0]))
        with pytest.raises(ValidationError):
            DraftControlPlanRequest.model_validate(payload)

    def test_empty_rotation_windows_is_rejected(self):
        payload = _payload()
        payload["requirement_policies"][0]["rotation_windows"] = []
        with pytest.raises(ValidationError):
            DraftControlPlanRequest.model_validate(payload)

    def test_inverted_rotation_window_is_rejected(self):
        payload = _payload()
        payload["requirement_policies"][0]["rotation_windows"] = [
            {
                "starts_at": "2026-07-20T18:00:00+00:00",
                "ends_at": "2026-07-20T06:00:00+00:00",
            }
        ]
        with pytest.raises(ValidationError):
            DraftControlPlanRequest.model_validate(payload)

    def test_branch_fraction_above_one_is_rejected(self):
        with pytest.raises(ValidationError):
            DraftControlPlanRequest.model_validate(
                _payload(
                    branch_allocations=[
                        {
                            "upstream_node_id": "N1",
                            "downstream_node_id": "N2",
                            "fraction": 1.5,
                        }
                    ]
                )
            )

    def test_boundary_whitespace_gate_id_is_rejected(self):
        payload = _payload()
        payload["flow_candidates"][0]["gate_id"] = " G1 "
        with pytest.raises(ValidationError):
            DraftControlPlanRequest.model_validate(payload)

    def test_interior_space_gate_id_is_accepted(self):
        # Munbon gate ids legitimately carry interior spaces, e.g. "M(0,0; 1,0)".
        payload = _payload()
        payload["section_bindings"][0]["gate_id"] = "M(0,0; 1,0)"
        payload["flow_candidates"][0]["gate_id"] = "M(0,0; 1,0)"
        payload["pulse_duties"][0]["gate_id"] = "M(0,0; 1,0)"
        request = DraftControlPlanRequest.model_validate(payload)
        assert request.flow_candidates[0].gate_id == "M(0,0; 1,0)"

    def test_blank_withdrawal_purpose_is_rejected(self):
        payload = _payload(
            operator_withdrawals=[
                {
                    "structure_id": "NW",
                    "effective_at": "2026-07-20T06:00:00+00:00",
                    "planned_flow_m3s": 0.4,
                    "purpose": "   ",
                }
            ]
        )
        with pytest.raises(ValidationError):
            DraftControlPlanRequest.model_validate(payload)

    def test_blank_operator_reference_is_rejected(self):
        payload = _payload(
            operator_withdrawals=[
                {
                    "structure_id": "NW",
                    "effective_at": "2026-07-20T06:00:00+00:00",
                    "planned_flow_m3s": 0.4,
                    "purpose": "flushing",
                    "operator_reference": "",
                }
            ]
        )
        with pytest.raises(ValidationError):
            DraftControlPlanRequest.model_validate(payload)
