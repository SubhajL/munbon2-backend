"""Unit tests for the content-addressed prediction-engine descriptor (PR 4.4b-1).

The descriptor MUST be reproducible from file bytes alone, change when any
closure file's bytes change, and fail closed on a missing/extra/drifted field.
The committed artifact MUST match a rebuild from the live source (the local
re-pin gate).
"""

import hashlib
import json
from pathlib import Path

import pytest

from core.demand_contract import content_hash
from core.prediction_engine import (
    PREDICTION_ENGINE_ID,
    PREDICTION_ENGINE_MANIFEST,
    PREDICTION_ENGINE_MANIFEST_PREFIX,
    PredictionEngineError,
    build_prediction_engine_descriptor,
    descriptor_from_build_digest,
    engine_identity_fields,
    load_prediction_engine_descriptor,
    validate_prediction_engine_descriptor,
)
from core.prediction_repository import canonical_json_bytes

SERVICE_ROOT = Path(__file__).resolve().parents[2]
COMMITTED_DESCRIPTOR = (
    SERVICE_ROOT / "data" / "prediction-engine" / "prediction-engine-v1.json"
)


def _seed_manifest_tree(root: Path) -> None:
    """Write a distinct byte string for every manifest file under ``root``."""
    for index, relative_path in enumerate(PREDICTION_ENGINE_MANIFEST):
        file_path = root / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(f"content-of-{relative_path}-{index}\n", encoding="utf-8")


class TestManifestShape:
    def test_manifest_is_the_twelve_closure_files_sorted(self):
        assert PREDICTION_ENGINE_MANIFEST == tuple(sorted(PREDICTION_ENGINE_MANIFEST))
        assert len(PREDICTION_ENGINE_MANIFEST) == 12
        assert "requirements.txt" in PREDICTION_ENGINE_MANIFEST
        assert "src/api/control.py" in PREDICTION_ENGINE_MANIFEST
        assert "src/core/model_snapshot.py" in PREDICTION_ENGINE_MANIFEST
        # The identity module itself is NOT part of its own fingerprint.
        assert "src/core/prediction_engine.py" not in PREDICTION_ENGINE_MANIFEST


class TestByteReproducibility:
    def test_engine_descriptor_is_byte_reproducible_from_manifest(self, tmp_path):
        tree_a = tmp_path / "a"
        tree_b = tmp_path / "b"
        _seed_manifest_tree(tree_a)
        _seed_manifest_tree(tree_b)

        first = build_prediction_engine_descriptor(tree_a)
        second = build_prediction_engine_descriptor(tree_b)

        assert first == second
        assert first["schema_version"] == 1
        assert first["engine_id"] == PREDICTION_ENGINE_ID
        assert first["semantic_contract_version"] == 1

    def test_build_digest_is_domain_separated_sha256_over_ordered_manifest(
        self, tmp_path
    ):
        _seed_manifest_tree(tmp_path)
        descriptor = build_prediction_engine_descriptor(tmp_path)

        ordered = [
            [relative_path, hashlib.sha256((tmp_path / relative_path).read_bytes()).hexdigest()]
            for relative_path in PREDICTION_ENGINE_MANIFEST
        ]
        expected_digest = hashlib.sha256(
            PREDICTION_ENGINE_MANIFEST_PREFIX + canonical_json_bytes(ordered)
        ).hexdigest()

        assert descriptor["build_digest"] == expected_digest
        assert descriptor["content_hash"] == content_hash(
            {
                "schema_version": 1,
                "engine_id": PREDICTION_ENGINE_ID,
                "semantic_contract_version": 1,
                "build_digest": expected_digest,
            }
        )

    def test_real_source_tree_rebuilds_identically(self):
        assert build_prediction_engine_descriptor(
            SERVICE_ROOT
        ) == build_prediction_engine_descriptor(SERVICE_ROOT)


class TestSourceChangeChangesHashes:
    def test_engine_source_change_changes_build_and_content_hashes(self, tmp_path):
        _seed_manifest_tree(tmp_path)
        before = build_prediction_engine_descriptor(tmp_path)

        # Mutate exactly one closure file's bytes.
        mutated = tmp_path / "src" / "core" / "network_transient.py"
        mutated.write_text(mutated.read_text() + "# behaviour changed\n")
        after = build_prediction_engine_descriptor(tmp_path)

        assert after["build_digest"] != before["build_digest"]
        assert after["content_hash"] != before["content_hash"]

    def test_missing_manifest_file_fails_closed(self, tmp_path):
        _seed_manifest_tree(tmp_path)
        (tmp_path / "requirements.txt").unlink()
        with pytest.raises(PredictionEngineError, match="unreadable"):
            build_prediction_engine_descriptor(tmp_path)


class TestLoadAndValidate:
    def _valid(self) -> dict:
        return descriptor_from_build_digest("a" * 64)

    def test_load_round_trips_a_valid_descriptor(self, tmp_path):
        descriptor = self._valid()
        path = tmp_path / "engine.json"
        path.write_text(json.dumps(descriptor))
        assert load_prediction_engine_descriptor(path) == descriptor

    def test_load_rejects_missing_field(self, tmp_path):
        descriptor = self._valid()
        del descriptor["build_digest"]
        path = tmp_path / "missing.json"
        path.write_text(json.dumps(descriptor))
        with pytest.raises(PredictionEngineError, match="keys must be exactly"):
            load_prediction_engine_descriptor(path)

    def test_load_rejects_extra_field(self, tmp_path):
        descriptor = self._valid()
        descriptor["extra"] = "nope"
        path = tmp_path / "extra.json"
        path.write_text(json.dumps(descriptor))
        with pytest.raises(PredictionEngineError, match="keys must be exactly"):
            load_prediction_engine_descriptor(path)

    def test_load_rejects_drifted_content_hash(self, tmp_path):
        descriptor = self._valid()
        descriptor["content_hash"] = "f" * 64  # inconsistent with the fields
        path = tmp_path / "drift.json"
        path.write_text(json.dumps(descriptor))
        with pytest.raises(PredictionEngineError, match="content_hash does not match"):
            load_prediction_engine_descriptor(path)

    def test_load_rejects_bad_schema_version(self, tmp_path):
        descriptor = self._valid()
        descriptor["schema_version"] = 2
        descriptor["content_hash"] = content_hash(
            {k: descriptor[k] for k in (
                "schema_version", "engine_id", "semantic_contract_version",
                "build_digest",
            )}
        )
        path = tmp_path / "schema.json"
        path.write_text(json.dumps(descriptor))
        with pytest.raises(PredictionEngineError, match="schema_version"):
            load_prediction_engine_descriptor(path)

    def test_load_rejects_missing_file(self, tmp_path):
        with pytest.raises(PredictionEngineError, match="not readable"):
            load_prediction_engine_descriptor(tmp_path / "absent.json")

    def test_engine_identity_fields_projects_the_four_columns(self):
        descriptor = self._valid()
        assert engine_identity_fields(descriptor) == {
            "engine_id": descriptor["engine_id"],
            "semantic_contract_version": descriptor["semantic_contract_version"],
            "build_digest": descriptor["build_digest"],
            "engine_descriptor_content_hash": descriptor["content_hash"],
        }

    def test_validate_rejects_boolean_semantic_contract_version(self):
        descriptor = self._valid()
        descriptor["semantic_contract_version"] = True
        with pytest.raises(PredictionEngineError, match="semantic_contract_version"):
            validate_prediction_engine_descriptor(descriptor)


class TestCommittedDescriptor:
    def test_committed_descriptor_matches_the_live_source(self):
        """The re-pin gate: the tracked artifact must equal a rebuild from the
        exact prediction closure bytes now on disk."""
        committed = load_prediction_engine_descriptor(COMMITTED_DESCRIPTOR)
        assert committed == build_prediction_engine_descriptor(SERVICE_ROOT)


class TestGeneratorCheckMode:
    def test_generator_check_mode_fails_on_drift(self, tmp_path):
        import importlib.util

        script_path = (
            SERVICE_ROOT / "scripts" / "build_prediction_engine_descriptor.py"
        )
        spec = importlib.util.spec_from_file_location(
            "build_prediction_engine_descriptor_under_test", str(script_path)
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        source_root = tmp_path / "src_tree"
        _seed_manifest_tree(source_root)
        output = tmp_path / "engine.json"

        # Fresh write then check: no drift.
        module.write_descriptor(source_root, output)
        assert module.descriptor_drift(source_root, output) is None

        # Mutate a closure file WITHOUT re-pinning: check must report drift.
        mutated = source_root / "src" / "api" / "control.py"
        mutated.write_text(mutated.read_text() + "# drift\n")
        drift = module.descriptor_drift(source_root, output)
        assert isinstance(drift, str) and "drift" in drift.lower()

    def test_generator_check_mode_passes_against_committed_artifact(self):
        import importlib.util

        script_path = (
            SERVICE_ROOT / "scripts" / "build_prediction_engine_descriptor.py"
        )
        spec = importlib.util.spec_from_file_location(
            "build_prediction_engine_descriptor_check_committed", str(script_path)
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # main() builds from the real service root and compares to the tracked
        # artifact — the committed descriptor must be in sync (exit 0).
        assert module.main(["--check"]) == 0
