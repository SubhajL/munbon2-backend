from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.demand_contract import content_hash
from core.prediction_engine import (
    build_prediction_engine_descriptor,
    descriptor_from_build_digest,
)
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
SERVICE_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DESCRIPTOR = build_prediction_engine_descriptor(SERVICE_ROOT)


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
    def test_model_snapshot_v3_separates_scada_graph_from_transport_coverage(self):
        release = _release()
        snapshot = build_model_snapshot(
            TOPOLOGY,
            reach_responses_from_model_release(release),
            release,
            CONFIG_SHA256,
            False,
            ENGINE_DESCRIPTOR,
        )

        assert {
            "schema_version": snapshot["schema_version"],
            "data_status": snapshot["data_status"],
            "mode": snapshot["mode"],
            "open_loop": snapshot["open_loop"],
            "actual_state_known": snapshot["actual_state_known"],
            "commandable": snapshot["commandable"],
            "prediction_engine": snapshot["prediction_engine"],
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
            "schema_version": 3,
            "data_status": "partial",
            "mode": "open_loop_prediction",
            "open_loop": True,
            "actual_state_known": False,
            "commandable": False,
            "prediction_engine": ENGINE_DESCRIPTOR,
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

    def test_snapshot_id_changes_when_engine_digest_changes(self):
        release = _release()
        responses = reach_responses_from_model_release(release)
        engine_b = descriptor_from_build_digest("d" * 64)
        assert ENGINE_DESCRIPTOR["build_digest"] != engine_b["build_digest"]

        snapshot_a = build_model_snapshot(
            TOPOLOGY, responses, release, CONFIG_SHA256, False, ENGINE_DESCRIPTOR
        )
        snapshot_b = build_model_snapshot(
            TOPOLOGY, responses, release, CONFIG_SHA256, False, engine_b
        )

        assert snapshot_a["prediction_engine"] == ENGINE_DESCRIPTOR
        assert snapshot_b["prediction_engine"] == engine_b
        # Only the engine differs, so ONLY the snapshot id may move.
        assert snapshot_a["snapshot_id"] != snapshot_b["snapshot_id"]
        assert {
            key: value
            for key, value in snapshot_a.items()
            if key not in ("snapshot_id", "prediction_engine")
        } == {
            key: value
            for key, value in snapshot_b.items()
            if key not in ("snapshot_id", "prediction_engine")
        }

    def test_build_model_snapshot_rejects_invalid_engine_descriptor(self):
        release = _release()
        responses = reach_responses_from_model_release(release)
        with pytest.raises(ModelSnapshotError, match="prediction engine descriptor"):
            build_model_snapshot(
                TOPOLOGY, responses, release, CONFIG_SHA256, False,
                {"schema_version": 1, "engine_id": "x"},
            )

    def test_response_model_projection_remains_release_schema_v1(self):
        release = _release()
        snapshot = build_model_snapshot(
            TOPOLOGY,
            reach_responses_from_model_release(release),
            release,
            CONFIG_SHA256,
            False,
            ENGINE_DESCRIPTOR,
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
            ENGINE_DESCRIPTOR,
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
            TOPOLOGY, responses, release, CONFIG_SHA256, False,
            ENGINE_DESCRIPTOR
        )
        reordered = build_model_snapshot(
            TOPOLOGY,
            responses[::-1],
            reordered_release,
            dict(reversed(CONFIG_SHA256.items())),
            False,
            ENGINE_DESCRIPTOR,
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
            TOPOLOGY, (), release, CONFIG_SHA256, False,
            ENGINE_DESCRIPTOR
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
                ENGINE_DESCRIPTOR,
            )

    def test_untyped_topology_is_rejected(self):
        with pytest.raises(ModelSnapshotError, match="typed RoutingTopology"):
            build_model_snapshot(
                NETWORK_EDGES,
                (),
                None,
                CONFIG_SHA256,
                False,
                ENGINE_DESCRIPTOR,
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
                ENGINE_DESCRIPTOR,
            )


def test_committed_release_snapshot_reports_partial_41_available_1_unavailable():
    from pathlib import Path

    from core.config_loader import (
        file_sha256,
        load_routing_topology,
    )
    from core.model_release import load_configured_hydraulic_model_release
    from core.reach_response import reach_responses_from_model_release

    service_root = Path(__file__).resolve().parents[2]
    config_dir = service_root / "src" / "config"
    topology = load_routing_topology(
        str(config_dir / "routing_topology.json"),
        str(config_dir / "network.json"),
        str(config_dir / "geometry_coverage.json"),
        str(config_dir / "canal_geometry.json"),
    )
    release = load_configured_hydraulic_model_release(
        str(
            service_root
            / "data"
            / "model-releases"
            / "engineering-prior-v3-v1.json"
        ),
        topology.transport_reach_ids(),
    )
    config_sha256 = {
        name: file_sha256(str(config_dir / f"{name}.json"))
        for name in (
            "network",
            "canal_geometry",
            "gate_calibrations",
            "geometry_coverage",
            "routing_topology",
        )
    }

    snapshot = build_model_snapshot(
        topology,
        reach_responses_from_model_release(release),
        release,
        config_sha256,
        False,
        ENGINE_DESCRIPTOR,
    )

    assert snapshot["data_status"] == "partial"
    assert snapshot["transport_response_coverage"] == {
        "total_transport_reaches": 42,
        "available_transport_reaches": 41,
        "unavailable_transport_reaches": 1,
    }
    assert snapshot["unavailable_transport_reaches"][0]["reach_id"] == (
        "C_M(0,0)_J(LMC,0+170)"
    )
