import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from core.commandability_approval import (
    CommandabilityApprovalError,
    commandability_approval_content_hash,
    is_commandability_approved,
    load_commandability_approval,
    verify_commandability_approval,
)
from core.model_release import (
    EvidenceClass,
    HydraulicModelRelease,
    ModelLineage,
    OperatingEnvelope,
    ParameterDistribution,
    ReachResponseParameters,
    SourceArtifact,
    model_release_content_hash,
)

SHA = {letter: letter * 64 for letter in "abcdef"}
CONFIG_SHA256 = {
    "network": SHA["a"],
    "canal_geometry": SHA["b"],
    "gate_calibrations": SHA["c"],
    "geometry_coverage": SHA["d"],
    "routing_topology": SHA["e"],
}
ENVELOPE = OperatingEnvelope(0.0, 8.0, 60.0, 300.0, 604800.0)
ENGINE = {"content_hash": SHA["f"]}


def _release() -> HydraulicModelRelease:
    release = HydraulicModelRelease(
        schema_version=1,
        release_id="engineering-prior-v1",
        generated_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
        evidence_class=EvidenceClass.ENGINEERING_PRIOR,
        commandable=False,
        lineage=ModelLineage(
            generator="test-generator",
            generator_version="1",
            sources=(SourceArtifact("network", "v1", SHA["a"]),),
        ),
        operating_envelope=ENVELOPE,
        reach_parameters=(
            ReachResponseParameters(
                reach_id="C_S_A",
                delay_seconds=ParameterDistribution(60.0, 90.0, 120.0),
                loss_fraction=ParameterDistribution(0.01, 0.02, 0.03),
                dispersion_seconds=ParameterDistribution(30.0, 45.0, 60.0),
                capacity_m3s=ParameterDistribution(6.0, 7.0, 8.0),
                evidence_refs=("network",),
            ),
        ),
        unavailable_reaches=(),
        content_hash="0" * 64,
    )
    return replace(release, content_hash=model_release_content_hash(release))


def _document(*, approved: bool = True) -> dict:
    release = _release()
    payload = {
        "schema_version": 1,
        "approval_state": "approved" if approved else "not_approved",
        "base_model_release": {
            "release_id": release.release_id,
            "content_hash": release.content_hash,
        },
        "prediction_engine": {"content_hash": ENGINE["content_hash"]},
        "model_config_sha256": dict(CONFIG_SHA256),
        "operating_envelope": {
            "minimum_flow_m3s": 0.0,
            "maximum_flow_m3s": 8.0,
            "minimum_timestep_seconds": 60.0,
            "maximum_timestep_seconds": 300.0,
            "maximum_horizon_seconds": 604800.0,
        },
        "device_capability": {
            "capability_release_id": "d6-pilot-v1",
            "capability_hash": SHA["a"],
            "approved_gate_ids": ["M(0,0)"],
        },
        "approval": (
            {
                "approved_by_role": "RID hydraulic model authority",
                "approved_at": "2026-07-21T08:00:00Z",
                "approval_reference": "RID-COMMISSIONING-2026-001",
                "evidence": [
                    {
                        "kind": "signed-assessment",
                        "reference": "doc://rid/commissioning/2026-001",
                        "sha256": SHA["b"],
                    }
                ],
            }
            if approved
            else None
        ),
    }
    return {**payload, "content_hash": commandability_approval_content_hash(payload)}


def _write(tmp_path, document: dict, name: str = "approval.json") -> str:
    path = tmp_path / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return str(path)


def test_load_commandability_approval_accepts_exact_content_hashed_contract(tmp_path):
    document = _document()

    loaded = load_commandability_approval(_write(tmp_path, document))

    assert loaded == document
    assert is_commandability_approved(loaded) is True


def test_valid_nonapproved_contract_stays_dark(tmp_path):
    document = _document(approved=False)

    loaded = load_commandability_approval(_write(tmp_path, document))

    assert loaded == document
    assert is_commandability_approved(loaded) is False


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda doc: doc.update({"unexpected": True}), "exactly"),
        (lambda doc: doc.update({"content_hash": SHA["f"]}), "content_hash"),
        (lambda doc: doc.update({"approval_state": "pending"}), "approval_state"),
        (lambda doc: doc.update({"approval": None}), "approved state"),
        (
            lambda doc: doc["device_capability"].update({"approved_gate_ids": []}),
            "approved_gate_ids",
        ),
    ],
)
def test_load_commandability_approval_rejects_contract_drift(
    tmp_path, mutation, message
):
    document = _document()
    mutation(document)

    with pytest.raises(CommandabilityApprovalError, match=message):
        load_commandability_approval(_write(tmp_path, document))


def test_load_commandability_approval_rejects_oversized_input(tmp_path):
    path = tmp_path / "approval.json"
    path.write_bytes(b" " * (262_144 + 1))

    with pytest.raises(CommandabilityApprovalError, match="256 KiB"):
        load_commandability_approval(str(path))


@pytest.mark.parametrize(
    "drift",
    [
        "release_id",
        "release_hash",
        "engine_hash",
        "config_hash",
        "operating_envelope",
    ],
)
def test_verify_commandability_approval_requires_exact_runtime_cross_binding(drift):
    document = _document()
    release = _release()
    engine = dict(ENGINE)
    config = dict(CONFIG_SHA256)
    if drift == "release_id":
        release = replace(release, release_id="different-release")
    elif drift == "release_hash":
        release = replace(release, content_hash=SHA["f"])
    elif drift == "engine_hash":
        engine["content_hash"] = SHA["e"]
    elif drift == "config_hash":
        config["network"] = SHA["f"]
    else:
        release = replace(
            release,
            operating_envelope=replace(
                release.operating_envelope, maximum_flow_m3s=7.5
            ),
        )

    with pytest.raises(CommandabilityApprovalError, match="does not match"):
        verify_commandability_approval(document, release, engine, config)


def test_verify_commandability_approval_accepts_exact_runtime_binding():
    verify_commandability_approval(_document(), _release(), ENGINE, CONFIG_SHA256)


def test_unset_commandability_approval_is_the_dark_default():
    assert load_commandability_approval(None) is None
    assert is_commandability_approved(None) is False
