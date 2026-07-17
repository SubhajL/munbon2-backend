import copy
import json
import math
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, strategies as st

from core.demand_contract import content_hash
from core.model_release import (
    EvidenceClass,
    ModelReleaseError,
    ParameterDistribution,
    load_configured_hydraulic_model_release,
    load_hydraulic_model_release,
    model_release_content_hash,
    validate_model_release,
)

EXPECTED_REACH_IDS = (
    "C_S_M(0,0)",
    "C_M(0,0)_M(0,1)",
    "C_M(0,1)_M(0,2)",
)
CANONICAL_NETWORK = (
    Path(__file__).resolve().parents[2] / "src" / "config" / "network.json"
)


def _release_payload() -> dict:
    return {
        "schema_version": 1,
        "release_id": "engineering-prior-2569-v1",
        "generated_at": "2026-07-16T02:00:00Z",
        "evidence_class": "engineering_prior",
        "commandable": False,
        "lineage": {
            "generator": "scripts/build_hydraulic_model_release.py",
            "generator_version": "1.0.0",
            "sources": [
                {
                    "source_id": "canonical-network",
                    "version": "scada-v2",
                    "sha256": "a" * 64,
                },
                {
                    "source_id": "surveyed-geometry",
                    "version": "rid-2569-draft",
                    "sha256": "b" * 64,
                },
            ],
        },
        "operating_envelope": {
            "minimum_flow_m3s": 0.0,
            "maximum_flow_m3s": 11.2,
            "minimum_timestep_seconds": 60.0,
            "maximum_timestep_seconds": 3600.0,
            "maximum_horizon_seconds": 604800.0,
        },
        "reach_parameters": [
            {
                "reach_id": "C_M(0,0)_M(0,1)",
                "delay_seconds": {"lower": 240.0, "nominal": 300.0, "upper": 420.0},
                "loss_fraction": {"lower": 0.01, "nominal": 0.02, "upper": 0.04},
                "dispersion_seconds": {
                    "lower": 30.0,
                    "nominal": 60.0,
                    "upper": 120.0,
                },
                "capacity_m3s": {"lower": 9.0, "nominal": 10.0, "upper": 11.2},
                "evidence_refs": ["canonical-network", "surveyed-geometry"],
            },
            {
                "reach_id": "C_S_M(0,0)",
                "delay_seconds": {"lower": 0.0, "nominal": 0.0, "upper": 0.0},
                "loss_fraction": {"lower": 0.0, "nominal": 0.0, "upper": 0.0},
                "dispersion_seconds": {"lower": 0.0, "nominal": 0.0, "upper": 0.0},
                "capacity_m3s": {"lower": 10.0, "nominal": 11.0, "upper": 11.2},
                "evidence_refs": ["canonical-network"],
            },
        ],
        "unavailable_reaches": [
            {
                "reach_id": "C_M(0,1)_M(0,2)",
                "reason": "surveyed geometry is unavailable",
            }
        ],
    }


def _write_release(tmp_path: Path, payload: dict) -> Path:
    release_path = tmp_path / "model-release.json"
    release_path.write_text(json.dumps(payload), encoding="utf-8")
    return release_path


def _valid_payload() -> dict:
    payload = _release_payload()
    payload["content_hash"] = content_hash(payload)
    return payload


def _rehash(payload: dict) -> None:
    payload["content_hash"] = content_hash(
        {key: value for key, value in payload.items() if key != "content_hash"}
    )


class TestLoadHydraulicModelRelease:
    def test_loads_complete_immutable_engineering_prior(self, tmp_path):
        payload = _valid_payload()
        release = load_hydraulic_model_release(
            str(_write_release(tmp_path, payload)), EXPECTED_REACH_IDS
        )

        assert (
            release.schema_version,
            release.release_id,
            release.evidence_class,
            release.commandable,
            tuple(parameter.reach_id for parameter in release.reach_parameters),
            tuple(unavailable.reach_id for unavailable in release.unavailable_reaches),
            release.content_hash,
        ) == (
            1,
            "engineering-prior-2569-v1",
            EvidenceClass.ENGINEERING_PRIOR,
            False,
            ("C_M(0,0)_M(0,1)", "C_S_M(0,0)"),
            ("C_M(0,1)_M(0,2)",),
            payload["content_hash"],
        )

    @pytest.mark.parametrize(
        "field",
        ["generator", "generator_version", "sources"],
    )
    def test_missing_lineage_is_rejected(self, tmp_path, field):
        payload = _valid_payload()
        del payload["lineage"][field]
        with pytest.raises(ModelReleaseError, match="lineage"):
            load_hydraulic_model_release(
                str(_write_release(tmp_path, payload)), EXPECTED_REACH_IDS
            )

    def test_unknown_evidence_class_is_rejected(self, tmp_path):
        payload = _valid_payload()
        payload["evidence_class"] = "assumed_default"
        with pytest.raises(ModelReleaseError, match="evidence_class"):
            load_hydraulic_model_release(
                str(_write_release(tmp_path, payload)), EXPECTED_REACH_IDS
            )

    def test_initial_commandable_release_is_rejected(self, tmp_path):
        payload = _valid_payload()
        payload["commandable"] = True
        with pytest.raises(ModelReleaseError, match="commandable"):
            load_hydraulic_model_release(
                str(_write_release(tmp_path, payload)), EXPECTED_REACH_IDS
            )

    def test_content_hash_drift_is_rejected(self, tmp_path):
        payload = _valid_payload()
        payload["operating_envelope"]["maximum_flow_m3s"] = 9.0
        with pytest.raises(ModelReleaseError, match="content_hash"):
            load_hydraulic_model_release(
                str(_write_release(tmp_path, payload)), EXPECTED_REACH_IDS
            )

    def test_unknown_schema_field_is_rejected(self, tmp_path):
        payload = _valid_payload()
        payload["fallback_delay_seconds"] = 300.0
        with pytest.raises(ModelReleaseError, match="unexpected"):
            load_hydraulic_model_release(
                str(_write_release(tmp_path, payload)), EXPECTED_REACH_IDS
            )

    def test_non_finite_json_is_rejected(self, tmp_path):
        payload = _valid_payload()
        payload["operating_envelope"]["maximum_flow_m3s"] = math.nan
        with pytest.raises(ModelReleaseError, match="strict JSON"):
            load_hydraulic_model_release(
                str(_write_release(tmp_path, payload)), EXPECTED_REACH_IDS
            )


class TestLoadConfiguredHydraulicModelRelease:
    def test_unconfigured_path_returns_explicit_unavailable_state(self):
        assert load_configured_hydraulic_model_release(None, []) is None

    def test_configured_release_uses_explicit_transport_reach_ids(self, tmp_path):
        release = load_configured_hydraulic_model_release(
            str(_write_release(tmp_path, _valid_payload())), EXPECTED_REACH_IDS
        )

        assert release is not None and release.release_id == "engineering-prior-2569-v1"

    def test_blank_configured_path_is_rejected(self):
        with pytest.raises(ModelReleaseError, match="model release path"):
            load_configured_hydraulic_model_release(" ", [])


class TestValidateModelRelease:
    def _canonical_transport_reach_ids(self) -> tuple[str, ...]:
        from core.routing_topology import derive_routing_topology

        config_dir = CANONICAL_NETWORK.parent
        network = json.loads(CANONICAL_NETWORK.read_text(encoding="utf-8"))
        coverage = json.loads(
            (config_dir / "geometry_coverage.json").read_text(encoding="utf-8")
        )
        canal_geometry = json.loads(
            (config_dir / "canal_geometry.json").read_text(encoding="utf-8")
        )
        return derive_routing_topology(
            network, coverage, canal_geometry
        ).transport_reach_ids()

    def test_transport_release_coverage_excludes_nontransport_elements(
        self, tmp_path
    ):
        expected = self._canonical_transport_reach_ids()
        payload = _valid_payload()
        payload["reach_parameters"] = []
        payload["unavailable_reaches"] = [
            {"reach_id": reach_id, "reason": "engineering evidence is unavailable"}
            for reach_id in sorted(expected)
        ]
        _rehash(payload)

        release = load_hydraulic_model_release(
            str(_write_release(tmp_path, payload)), expected
        )

        assert (
            len(expected),
            release.reach_parameters,
            len(release.unavailable_reaches),
        ) == (
            42,
            (),
            42,
        )
        assert not any(
            reach_id.startswith(("B_", "BR_", "WD_")) for reach_id in expected
        )

    def test_nontransport_elements_require_no_delay_loss_dispersion_or_capacity_distribution(
        self, tmp_path
    ):
        expected = self._canonical_transport_reach_ids()
        payload = _valid_payload()
        payload["reach_parameters"] = []
        payload["unavailable_reaches"] = [
            {"reach_id": reach_id, "reason": "engineering evidence is unavailable"}
            for reach_id in sorted(expected)
        ] + [
            {
                "reach_id": "BR_M(0,0)_M(0,0;2,0)",
                "reason": "engineering evidence is unavailable",
            }
        ]
        _rehash(payload)

        with pytest.raises(ModelReleaseError, match="unknown"):
            load_hydraulic_model_release(
                str(_write_release(tmp_path, payload)), expected
            )

    def test_missing_reach_must_be_explicitly_unavailable(self, tmp_path):
        payload = _valid_payload()
        payload["unavailable_reaches"] = []
        _rehash(payload)
        with pytest.raises(ModelReleaseError, match=r"missing.*C_M\(0,1\)_M\(0,2\)"):
            load_hydraulic_model_release(
                str(_write_release(tmp_path, payload)), EXPECTED_REACH_IDS
            )

    def test_unknown_reach_cannot_expand_declared_coverage(self, tmp_path):
        payload = _valid_payload()
        payload["unavailable_reaches"][0]["reach_id"] = "C_UNKNOWN_UNKNOWN"
        _rehash(payload)
        with pytest.raises(ModelReleaseError, match="unknown.*C_UNKNOWN_UNKNOWN"):
            load_hydraulic_model_release(
                str(_write_release(tmp_path, payload)), EXPECTED_REACH_IDS
            )

    def test_reach_cannot_be_available_and_unavailable(self, tmp_path):
        payload = _valid_payload()
        payload["unavailable_reaches"][0]["reach_id"] = "C_S_M(0,0)"
        _rehash(payload)
        with pytest.raises(ModelReleaseError, match="both available and unavailable"):
            load_hydraulic_model_release(
                str(_write_release(tmp_path, payload)), EXPECTED_REACH_IDS
            )

    @pytest.mark.parametrize(
        "field,value",
        [
            ("minimum_flow_m3s", -0.1),
            ("minimum_flow_m3s", 1.0),
            ("maximum_flow_m3s", 0.0),
            ("minimum_timestep_seconds", 0.0),
            ("maximum_timestep_seconds", 30.0),
            ("maximum_horizon_seconds", 1800.0),
        ],
    )
    def test_invalid_operating_envelope_is_rejected(self, tmp_path, field, value):
        payload = _valid_payload()
        payload["operating_envelope"][field] = value
        _rehash(payload)
        with pytest.raises(ModelReleaseError, match="operating_envelope"):
            load_hydraulic_model_release(
                str(_write_release(tmp_path, payload)), EXPECTED_REACH_IDS
            )

    @pytest.mark.parametrize(
        "parameter,value",
        [
            ("delay_seconds", {"lower": -1.0, "nominal": 1.0, "upper": 2.0}),
            ("loss_fraction", {"lower": 0.1, "nominal": 0.2, "upper": 1.0}),
            ("dispersion_seconds", {"lower": 2.0, "nominal": 1.0, "upper": 3.0}),
            ("capacity_m3s", {"lower": 0.0, "nominal": 1.0, "upper": 2.0}),
        ],
    )
    def test_invalid_response_distribution_is_rejected(
        self, tmp_path, parameter, value
    ):
        payload = _valid_payload()
        payload["reach_parameters"][0][parameter] = value
        _rehash(payload)
        with pytest.raises(ModelReleaseError, match=parameter):
            load_hydraulic_model_release(
                str(_write_release(tmp_path, payload)), EXPECTED_REACH_IDS
            )

    @pytest.mark.parametrize("evidence_refs", [[], ["unknown-source"]])
    def test_missing_or_unknown_reach_evidence_is_rejected(
        self, tmp_path, evidence_refs
    ):
        payload = _valid_payload()
        payload["reach_parameters"][0]["evidence_refs"] = evidence_refs
        _rehash(payload)
        with pytest.raises(ModelReleaseError, match="evidence_refs"):
            load_hydraulic_model_release(
                str(_write_release(tmp_path, payload)), EXPECTED_REACH_IDS
            )

    def test_direct_validation_rejects_commandable_release(self, tmp_path):
        release = load_hydraulic_model_release(
            str(_write_release(tmp_path, _valid_payload())), EXPECTED_REACH_IDS
        )
        with pytest.raises(ModelReleaseError, match="commandable"):
            validate_model_release(
                replace(release, commandable=True), EXPECTED_REACH_IDS
            )


class TestModelReleaseContentHash:
    def test_parameter_change_changes_hash(self, tmp_path):
        release = load_hydraulic_model_release(
            str(_write_release(tmp_path, _valid_payload())), EXPECTED_REACH_IDS
        )
        first = release.reach_parameters[0]
        changed = replace(
            release,
            reach_parameters=(
                replace(
                    first,
                    capacity_m3s=ParameterDistribution(9.0, 9.5, 11.2),
                ),
                *release.reach_parameters[1:],
            ),
        )
        assert model_release_content_hash(changed) != model_release_content_hash(
            release
        )

    @given(
        source_order=st.permutations((0, 1)),
        reach_order=st.permutations((0, 1)),
    )
    def test_hash_is_independent_of_source_and_reach_order(
        self, source_order, reach_order
    ):
        with TemporaryDirectory() as directory:
            release = load_hydraulic_model_release(
                str(_write_release(Path(directory), _valid_payload())),
                EXPECTED_REACH_IDS,
            )
        reordered_lineage = replace(
            release.lineage,
            sources=tuple(release.lineage.sources[index] for index in source_order),
        )
        reordered = replace(
            release,
            lineage=reordered_lineage,
            reach_parameters=tuple(
                release.reach_parameters[index] for index in reach_order
            ),
        )
        assert model_release_content_hash(reordered) == model_release_content_hash(
            release
        )

    def test_input_payload_is_not_mutated(self, tmp_path):
        payload = _valid_payload()
        before = copy.deepcopy(payload)
        load_hydraulic_model_release(
            str(_write_release(tmp_path, payload)), EXPECTED_REACH_IDS
        )
        assert payload == before
