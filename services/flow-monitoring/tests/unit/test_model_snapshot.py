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
from core.routing_topology import (
    RoutingElement,
    RoutingGeometryStatus,
    RoutingRole,
    build_routing_topology,
)

NETWORK_EDGES = (("S", "A"), ("A", "B"), ("A", "C"))
SOURCE_SHA256 = "5" * 64
CONFIG_SHA256 = {
    "network": "a" * 64,
    "canal_geometry": "b" * 64,
    "gate_calibrations": "c" * 64,
    "geometry_coverage": "1" * 64,
    "routing_topology": "2" * 64,
}
OPERATING_ENVELOPE = OperatingEnvelope(0.0, 4.0, 60.0, 300.0, 604800.0)


def _transport_element(upstream: str, downstream: str) -> RoutingElement:
    return RoutingElement(
        element_id=f"C_{upstream}_{downstream}",
        upstream_node_id=upstream,
        downstream_node_id=downstream,
        role=RoutingRole.TRANSPORT,
        canonical_edges=((upstream, downstream),),
        canal=None,
        span_m=100.0,
        geometry_status=RoutingGeometryStatus.SURVEYED,
        located_at_km=None,
    )


TOPOLOGY = build_routing_topology(
    tuple(_transport_element(*edge) for edge in NETWORK_EDGES),
    SOURCE_SHA256,
)


def _element_payload(upstream: str, downstream: str) -> dict:
    return {
        "element_id": f"C_{upstream}_{downstream}",
        "upstream_node_id": upstream,
        "downstream_node_id": downstream,
        "role": "transport",
        "canonical_edges": [[upstream, downstream]],
        "canal": None,
        "span_m": 100.0,
        "geometry_status": "surveyed",
        "located_at_km": None,
    }


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
    def test_model_snapshot_v2_separates_scada_graph_from_transport_coverage(self):
        release = _release()
        snapshot = build_model_snapshot(
            TOPOLOGY,
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
            "scada_graph": snapshot["scada_graph"],
            "routing_topology": snapshot["routing_topology"],
            "action_model": snapshot["action_model"],
            "transport_response_coverage": snapshot[
                "transport_response_coverage"
            ],
            "unavailable_transport_reaches": snapshot[
                "unavailable_transport_reaches"
            ],
        } == {
            "schema_version": 2,
            "data_status": "partial",
            "mode": "open_loop_prediction",
            "open_loop": True,
            "actual_state_known": False,
            "commandable": False,
            "scada_graph": {
                "config_sha256": "a" * 64,
                "source_workbook_sha256": SOURCE_SHA256,
                "root_node_id": "S",
                "gate_count": 3,
                "edge_count": 3,
                "edges": [
                    {"upstream_node_id": "S", "downstream_node_id": "A"},
                    {"upstream_node_id": "A", "downstream_node_id": "B"},
                    {"upstream_node_id": "A", "downstream_node_id": "C"},
                ],
            },
            "routing_topology": {
                "schema_version": 1,
                "config_sha256": "2" * 64,
                "content_hash": TOPOLOGY.content_hash,
                "root_node_id": "S",
                "node_count": 4,
                "element_count": 3,
                "role_counts": {"transport": 3},
                "elements": [
                    _element_payload("S", "A"),
                    _element_payload("A", "B"),
                    _element_payload("A", "C"),
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
                    "geometry_coverage": "1" * 64,
                },
                "operating_envelope": {
                    "minimum_flow_m3s": 0.0,
                    "maximum_flow_m3s": 4.0,
                    "minimum_timestep_seconds": 60.0,
                    "maximum_timestep_seconds": 300.0,
                    "maximum_horizon_seconds": 604800.0,
                },
            },
            "transport_response_coverage": {
                "total_transport_reaches": 3,
                "available_transport_reaches": 2,
                "unavailable_transport_reaches": 1,
            },
            "unavailable_transport_reaches": [
                {"reach_id": "C_A_C", "reason": "geometry is unavailable"}
            ],
        }
        payload = {
            key: value for key, value in snapshot.items() if key != "snapshot_id"
        }
        assert snapshot["snapshot_id"] == content_hash(payload)

    def test_response_model_projection_remains_release_schema_v1(self):
        release = _release()
        snapshot = build_model_snapshot(
            TOPOLOGY,
            reach_responses_from_model_release(release),
            release,
            CONFIG_SHA256,
            False,
        )

        response_model = snapshot["response_model"]
        assert (
            response_model["schema_version"],
            response_model["release_id"],
            response_model["content_hash"],
            [
                parameters["reach_id"]
                for parameters in response_model["reach_parameters"]
            ],
            len(response_model["response_members"]),
        ) == (1, "engineering-prior-v1", release.content_hash, ["C_A_B", "C_S_A"], 6)

    def test_unconfigured_release_returns_every_transport_explicitly_unavailable(
        self,
    ):
        snapshot = build_model_snapshot(
            TOPOLOGY,
            (),
            None,
            CONFIG_SHA256,
            False,
        )

        assert (
            snapshot["data_status"],
            snapshot["response_model"],
            snapshot["action_model"]["operating_envelope"],
            snapshot["transport_response_coverage"],
            snapshot["unavailable_transport_reaches"],
        ) == (
            "unavailable",
            None,
            None,
            {
                "total_transport_reaches": 3,
                "available_transport_reaches": 0,
                "unavailable_transport_reaches": 3,
            },
            [
                {
                    "reach_id": reach_id,
                    "reason": "hydraulic model release is not configured",
                }
                for reach_id in ("C_A_B", "C_A_C", "C_S_A")
            ],
        )

    def test_snapshot_identity_is_independent_of_unordered_collection_order(
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
            TOPOLOGY, responses, release, CONFIG_SHA256, False
        )
        reordered = build_model_snapshot(
            TOPOLOGY,
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
            TOPOLOGY, (), release, CONFIG_SHA256, False
        )

        assert (
            snapshot["data_status"],
            snapshot["response_model"]["release_id"],
            snapshot["transport_response_coverage"][
                "available_transport_reaches"
            ],
        ) == ("unavailable", release.release_id, 0)

    def test_runtime_response_drift_is_rejected(self):
        release = _release()
        responses = reach_responses_from_model_release(release)

        with pytest.raises(ModelSnapshotError, match="runtime response members"):
            build_model_snapshot(
                TOPOLOGY,
                responses[:-1],
                release,
                CONFIG_SHA256,
                False,
            )

    def test_untyped_topology_is_rejected(self):
        with pytest.raises(ModelSnapshotError, match="typed RoutingTopology"):
            build_model_snapshot(
                NETWORK_EDGES,
                (),
                None,
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
                TOPOLOGY,
                (),
                None,
                config_sha256,
                False,
            )
