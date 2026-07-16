from dataclasses import replace
from datetime import datetime, timezone

import pytest

from core.demand_contract import content_hash
from core.model_release import (
    EvidenceClass,
    HydraulicModelRelease,
    ModelLineage,
    OperatingEnvelope,
    ParameterDistribution,
    ReachResponseParameters,
    SourceArtifact,
    UnavailableReach,
    model_release_content_hash,
)
from core.model_snapshot import ModelSnapshotError, build_model_snapshot
from core.reach_response import reach_responses_from_model_release

NETWORK_EDGES = (("S", "A"), ("A", "B"), ("A", "C"))
CONFIG_SHA256 = {
    "network": "a" * 64,
    "canal_geometry": "b" * 64,
    "gate_calibrations": "c" * 64,
}
OPERATING_ENVELOPE = OperatingEnvelope(0.0, 4.0, 60.0, 300.0, 604800.0)


def _parameters(reach_id: str, capacity_m3s: float) -> ReachResponseParameters:
    return ReachResponseParameters(
        reach_id=reach_id,
        delay_seconds=ParameterDistribution(60.0, 90.0, 120.0),
        loss_fraction=ParameterDistribution(0.01, 0.02, 0.03),
        dispersion_seconds=ParameterDistribution(30.0, 45.0, 60.0),
        capacity_m3s=ParameterDistribution(
            capacity_m3s - 1.0,
            capacity_m3s,
            capacity_m3s + 1.0,
        ),
        evidence_refs=("network", "geometry"),
    )


def _release(
    *,
    reach_parameters: tuple[ReachResponseParameters, ...] | None = None,
    unavailable_reaches: tuple[UnavailableReach, ...] | None = None,
) -> HydraulicModelRelease:
    release = HydraulicModelRelease(
        schema_version=1,
        release_id="engineering-prior-v1",
        generated_at=datetime(2026, 7, 16, 2, 0, tzinfo=timezone.utc),
        evidence_class=EvidenceClass.ENGINEERING_PRIOR,
        commandable=False,
        lineage=ModelLineage(
            generator="build_hydraulic_model_release",
            generator_version="1.0.0",
            sources=(
                SourceArtifact("network", "v2", "d" * 64),
                SourceArtifact("geometry", "draft", "e" * 64),
            ),
        ),
        operating_envelope=OPERATING_ENVELOPE,
        reach_parameters=reach_parameters
        if reach_parameters is not None
        else (_parameters("C_S_A", 2.0), _parameters("C_A_B", 3.0)),
        unavailable_reaches=unavailable_reaches
        if unavailable_reaches is not None
        else (UnavailableReach("C_A_C", "geometry is unavailable"),),
        content_hash="0" * 64,
    )
    return replace(release, content_hash=model_release_content_hash(release))


class TestBuildModelSnapshot:
    def test_returns_exact_partial_network_action_and_response_lineage(self):
        release = _release()
        snapshot = build_model_snapshot(
            NETWORK_EDGES,
            reach_responses_from_model_release(release),
            release,
            CONFIG_SHA256,
            False,
        )

        assert {
            "schema_version": snapshot["schema_version"],
            "data_status": snapshot["data_status"],
            "mode": snapshot["mode"],
            "open_loop": snapshot["open_loop"],
            "actual_state_known": snapshot["actual_state_known"],
            "commandable": snapshot["commandable"],
            "network": snapshot["network"],
            "action_model": snapshot["action_model"],
            "coverage": snapshot["coverage"],
            "unavailable_reaches": snapshot["unavailable_reaches"],
        } == {
            "schema_version": 1,
            "data_status": "partial",
            "mode": "open_loop_prediction",
            "open_loop": True,
            "actual_state_known": False,
            "commandable": False,
            "network": {
                "config_sha256": "a" * 64,
                "reach_count": 3,
                "reaches": [
                    {
                        "reach_id": "C_A_B",
                        "upstream_node_id": "A",
                        "downstream_node_id": "B",
                    },
                    {
                        "reach_id": "C_A_C",
                        "upstream_node_id": "A",
                        "downstream_node_id": "C",
                    },
                    {
                        "reach_id": "C_S_A",
                        "upstream_node_id": "S",
                        "downstream_node_id": "A",
                    },
                ],
            },
            "action_model": {
                "kind": "gate_flow_event",
                "flow_unit": "m3/s",
                "allowed_node_ids": ["S"],
                "requires_explicit_branch_allocations": True,
                "commandable": False,
                "actuation_approved": False,
                "config_sha256": {
                    "canal_geometry": "b" * 64,
                    "gate_calibrations": "c" * 64,
                },
                "operating_envelope": {
                    "minimum_flow_m3s": 0.0,
                    "maximum_flow_m3s": 4.0,
                    "minimum_timestep_seconds": 60.0,
                    "maximum_timestep_seconds": 300.0,
                    "maximum_horizon_seconds": 604800.0,
                },
            },
            "coverage": {
                "total_reaches": 3,
                "available_reaches": 2,
                "unavailable_reaches": 1,
            },
            "unavailable_reaches": [
                {"reach_id": "C_A_C", "reason": "geometry is unavailable"}
            ],
        }
        assert snapshot["response_model"] == {
            "schema_version": 1,
            "release_id": "engineering-prior-v1",
            "generated_at": "2026-07-16T02:00:00Z",
            "evidence_class": "engineering_prior",
            "commandable": False,
            "content_hash": release.content_hash,
            "lineage": {
                "generator": "build_hydraulic_model_release",
                "generator_version": "1.0.0",
                "sources": [
                    {
                        "source_id": "geometry",
                        "version": "draft",
                        "sha256": "e" * 64,
                    },
                    {
                        "source_id": "network",
                        "version": "v2",
                        "sha256": "d" * 64,
                    },
                ],
            },
            "reach_parameters": [
                {
                    "reach_id": "C_A_B",
                    "delay_seconds": {
                        "lower": 60.0,
                        "nominal": 90.0,
                        "upper": 120.0,
                    },
                    "loss_fraction": {
                        "lower": 0.01,
                        "nominal": 0.02,
                        "upper": 0.03,
                    },
                    "dispersion_seconds": {
                        "lower": 30.0,
                        "nominal": 45.0,
                        "upper": 60.0,
                    },
                    "capacity_m3s": {
                        "lower": 2.0,
                        "nominal": 3.0,
                        "upper": 4.0,
                    },
                    "evidence_refs": ["geometry", "network"],
                },
                {
                    "reach_id": "C_S_A",
                    "delay_seconds": {
                        "lower": 60.0,
                        "nominal": 90.0,
                        "upper": 120.0,
                    },
                    "loss_fraction": {
                        "lower": 0.01,
                        "nominal": 0.02,
                        "upper": 0.03,
                    },
                    "dispersion_seconds": {
                        "lower": 30.0,
                        "nominal": 45.0,
                        "upper": 60.0,
                    },
                    "capacity_m3s": {
                        "lower": 1.0,
                        "nominal": 2.0,
                        "upper": 3.0,
                    },
                    "evidence_refs": ["geometry", "network"],
                },
            ],
            "response_members": [
                {
                    "reach_id": response.reach_id,
                    "member": response.member.value,
                    "delay_seconds": response.delay_seconds,
                    "loss_fraction": response.loss_fraction,
                    "dispersion_seconds": response.dispersion_seconds,
                    "capacity_m3s": response.capacity_m3s,
                    "minimum_timestep_seconds": (response.minimum_timestep_seconds),
                    "maximum_timestep_seconds": (response.maximum_timestep_seconds),
                }
                for response in sorted(
                    reach_responses_from_model_release(release),
                    key=lambda item: (item.reach_id, item.member.value),
                )
            ],
        }
        payload = {
            key: value for key, value in snapshot.items() if key != "snapshot_id"
        }
        assert snapshot["snapshot_id"] == content_hash(payload)

    def test_unconfigured_release_returns_every_reach_explicitly_unavailable(
        self,
    ):
        snapshot = build_model_snapshot(
            NETWORK_EDGES,
            (),
            None,
            CONFIG_SHA256,
            False,
        )

        assert (
            snapshot["data_status"],
            snapshot["response_model"],
            snapshot["action_model"]["operating_envelope"],
            snapshot["coverage"],
            snapshot["unavailable_reaches"],
        ) == (
            "unavailable",
            None,
            None,
            {
                "total_reaches": 3,
                "available_reaches": 0,
                "unavailable_reaches": 3,
            },
            [
                {
                    "reach_id": reach_id,
                    "reason": "hydraulic model release is not configured",
                }
                for reach_id in ("C_A_B", "C_A_C", "C_S_A")
            ],
        )

    def test_snapshot_identity_is_independent_of_contract_collection_order(
        self,
    ):
        release = _release()
        responses = reach_responses_from_model_release(release)
        reordered_release = replace(
            release,
            lineage=replace(release.lineage, sources=release.lineage.sources[::-1]),
            reach_parameters=release.reach_parameters[::-1],
        )

        first = build_model_snapshot(
            NETWORK_EDGES, responses, release, CONFIG_SHA256, False
        )
        reordered = build_model_snapshot(
            NETWORK_EDGES[::-1],
            responses[::-1],
            reordered_release,
            dict(reversed(CONFIG_SHA256.items())),
            False,
        )

        assert reordered == first

    def test_all_unavailable_release_preserves_release_lineage(self):
        release = _release(
            reach_parameters=(),
            unavailable_reaches=tuple(
                UnavailableReach(f"C_{upstream}_{downstream}", "evidence unavailable")
                for upstream, downstream in NETWORK_EDGES
            ),
        )

        snapshot = build_model_snapshot(
            NETWORK_EDGES, (), release, CONFIG_SHA256, False
        )

        assert (
            snapshot["data_status"],
            snapshot["response_model"]["release_id"],
            snapshot["coverage"]["available_reaches"],
        ) == ("unavailable", release.release_id, 0)

    def test_runtime_response_drift_is_rejected(self):
        release = _release()
        responses = reach_responses_from_model_release(release)

        with pytest.raises(ModelSnapshotError, match="runtime response members"):
            build_model_snapshot(
                NETWORK_EDGES,
                responses[:-1],
                release,
                CONFIG_SHA256,
                False,
            )

    @pytest.mark.parametrize(
        "config_sha256",
        [
            {"network": "a" * 64, "canal_geometry": "b" * 64},
            {**CONFIG_SHA256, "unexpected": "f" * 64},
            {**CONFIG_SHA256, "network": "not-a-sha256"},
        ],
    )
    def test_invalid_action_lineage_is_rejected(self, config_sha256):
        with pytest.raises(ModelSnapshotError, match="config_sha256"):
            build_model_snapshot(
                NETWORK_EDGES,
                (),
                None,
                config_sha256,
                False,
            )
