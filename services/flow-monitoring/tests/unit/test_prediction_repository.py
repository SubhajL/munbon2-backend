"""Repository unit tests — Codex plan §4 "Repository" slice.

Covers: in-memory replay/conflict/defensive-copy, interface pinning
(Postgres repo method names/signatures match twin via inspect), and source
greps proving the Postgres repo contains no DDL, UPDATE, UPSERT, or DELETE.
"""
import ast
import hashlib
import importlib
import inspect
from datetime import datetime, timezone

import pytest

from core.prediction_engine import descriptor_from_build_digest, engine_identity_fields
from core.prediction_repository import (
    PREDICTION_ENGINE_REQUEST_KEY,
    PREDICTION_RUN_IDENTITY_PREFIX,
    PREDICTION_RUN_IDENTITY_PREFIX_V2,
    PREDICTION_RUN_IDENTITY_VERSION_V2,
    PredictionArtifactRecord,
    PredictionRunConflict,
    PredictionRunRecord,
    InMemoryPredictionRepository,
    canonical_json_bytes,
    prediction_run_id_for,
)
from services.prediction_artifact_service import encode_prediction_artifact


def _artifact_record(for_content: bytes | None = None) -> PredictionArtifactRecord:
    content = canonical_json_bytes({"ok": True}) if for_content is None else for_content
    return encode_prediction_artifact(content)


def _run(payload_override: dict | None = None) -> PredictionRunRecord:
    """Build a PredictionRunRecord whose id is ALWAYS computed from the
    merged payload, consistent with __post_init__ validation."""
    base_payload = {
        "model_snapshot_id": "a" * 64,
        "model_release_id": "test-release",
        "model_release_content_hash": "b" * 64,
        "starts_at": "2026-07-20T23:00:00Z",
    }
    payload = {**base_payload, **(payload_override or {})}
    return PredictionRunRecord(
        prediction_run_id=prediction_run_id_for(payload),
        identity_version=1,
        response_schema_version=2,
        request_payload=payload,
        model_snapshot_id=payload["model_snapshot_id"],
        model_release_id=payload["model_release_id"],
        model_release_content_hash=payload["model_release_content_hash"],
        starts_at=datetime(2026, 7, 20, 23, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 7, 21, 5, 0, tzinfo=timezone.utc),
        timestep_seconds=300.0,
        member_summaries=(
            {"member": "lower", "status": "completed"},
            {"member": "nominal", "status": "completed"},
            {"member": "upper", "status": "completed"},
        ),
        artifact=_artifact_record(),
    )


class TestInMemoryPredictionRepository:
    """The in-memory twin must replay identical requests, reject collisions,
    isolate callers from stored state, and never mutate inputs."""

    @pytest.mark.asyncio
    async def test_prediction_replay_returns_first_stored_record(self):
        repo = InMemoryPredictionRepository()
        run = _run()

        first = await repo.persist_prediction_run(run)
        assert first[1] is False, "first store must not be a replay"

        second = await repo.persist_prediction_run(run)
        assert second[1] is True, "identical id+content must replay"

        assert second[0].prediction_run_id == first[0].prediction_run_id
        assert second[0].model_snapshot_id == first[0].model_snapshot_id

        stored = await repo.load_prediction_run(run.prediction_run_id)
        assert stored is not None

    @pytest.mark.asyncio
    async def test_prediction_same_id_different_content_conflicts(self):
        """Persist run_a, then tamper the stored request_payload so the next
        persist of run_b (same id, different canonical request) conflicts."""
        repo = InMemoryPredictionRepository()

        payload_a = {
            "model_snapshot_id": "a" * 64,
            "model_release_id": "test-a",
            "model_release_content_hash": "b" * 64,
            "starts_at": "2026-07-20T23:00:00Z",
        }

        run_a = _run(payload_override=payload_a)
        stored, was_replay = await repo.persist_prediction_run(run_a)
        assert not was_replay

        # Tamper with the stored request_payload in-place (bypass frozen
        # validation via object.__setattr__) to seed a collision scenario.
        payload_b = {
            "model_snapshot_id": "a" * 64,
            "model_release_id": "test-b-different",
            "model_release_content_hash": "b" * 64,
            "starts_at": "2026-07-20T23:00:00Z",
        }
        tampered = repo._runs[run_a.prediction_run_id]
        object.__setattr__(tampered, "request_payload", payload_b)

        # Now try to persist run_a again with the original content — the
        # stored entry's canonical payload now differs, so it MUST conflict.
        with pytest.raises(PredictionRunConflict):
            await repo.persist_prediction_run(run_a)

    @pytest.mark.asyncio
    async def test_in_memory_repository_returns_defensive_copies(self):
        repo = InMemoryPredictionRepository()
        run = _run()
        await repo.persist_prediction_run(run)

        loaded = await repo.load_prediction_run(run.prediction_run_id)
        assert loaded is not None

        loaded.request_payload["model_release_id"] = "tampered"
        second_load = await repo.load_prediction_run(run.prediction_run_id)
        assert second_load is not None
        assert second_load.request_payload["model_release_id"] == run.model_release_id

        loaded.member_summaries[0]["status"] = "tampered"
        third_load = await repo.load_prediction_run(run.prediction_run_id)
        assert third_load is not None
        assert third_load.member_summaries[0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_load_prediction_run_unknown_id_returns_none(self):
        repo = InMemoryPredictionRepository()
        result = await repo.load_prediction_run("e" * 64)
        assert result is None


class TestPredictionRunIdentityDispatch:
    """The v1 prefix and canonicalization are FROZEN so persisted v1 runs
    replay byte-identically; v2 is a distinct domain-separated prefix."""

    def test_v1_prefix_and_canonicalization_are_byte_frozen(self):
        # Independent oracle: compact sorted-key JSON under the exact v1 prefix.
        payload = {"b": "x", "a": 1}
        canonical = b'{"a":1,"b":"x"}'
        assert canonical_json_bytes(payload) == canonical
        expected = hashlib.sha256(
            PREDICTION_RUN_IDENTITY_PREFIX + canonical
        ).hexdigest()
        assert PREDICTION_RUN_IDENTITY_PREFIX == b"flow-monitoring:prediction-run:v1\n"
        assert prediction_run_id_for(payload) == expected
        assert prediction_run_id_for(payload, 1) == expected

    def test_v2_is_domain_separated_from_v1(self):
        payload = {"a": 1, "b": "x"}
        expected_v2 = hashlib.sha256(
            PREDICTION_RUN_IDENTITY_PREFIX_V2 + b'{"a":1,"b":"x"}'
        ).hexdigest()
        assert PREDICTION_RUN_IDENTITY_PREFIX_V2 == (
            b"flow-monitoring:prediction-run:v2\n"
        )
        assert prediction_run_id_for(payload, PREDICTION_RUN_IDENTITY_VERSION_V2) == (
            expected_v2
        )
        # Same bytes, different prefix -> different id (no cross-version collision).
        assert prediction_run_id_for(payload, 1) != prediction_run_id_for(payload, 2)

    def test_unknown_identity_version_is_rejected(self):
        with pytest.raises(ValueError, match="unsupported identity_version"):
            prediction_run_id_for({"a": 1}, 3)


def _engine_descriptor(build_digest: str = "a" * 64) -> dict:
    return descriptor_from_build_digest(build_digest)


def _v2_run(engine_descriptor: dict, extra_payload: dict | None = None):
    base = {"model_release_id": "r", "starts_at": "2026-07-20T23:00:00Z"}
    payload = {
        **base,
        **(extra_payload or {}),
        PREDICTION_ENGINE_REQUEST_KEY: {
            key: engine_descriptor[key]
            for key in (
                "schema_version", "engine_id", "semantic_contract_version",
                "build_digest", "content_hash",
            )
        },
    }
    fields = engine_identity_fields(engine_descriptor)
    return PredictionRunRecord(
        prediction_run_id=prediction_run_id_for(
            payload, PREDICTION_RUN_IDENTITY_VERSION_V2
        ),
        identity_version=PREDICTION_RUN_IDENTITY_VERSION_V2,
        response_schema_version=2,
        request_payload=payload,
        model_snapshot_id="a" * 64,
        model_release_id="r",
        model_release_content_hash="b" * 64,
        starts_at=datetime(2026, 7, 20, 23, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 7, 21, 5, 0, tzinfo=timezone.utc),
        timestep_seconds=300.0,
        member_summaries=(),
        artifact=_artifact_record(),
        **fields,
    )


def _valid_embedded(build_digest: str = "a" * 64) -> dict:
    """The five-key engine block a v2 request embeds, projected from a valid
    descriptor (the exact shape the API write path produces)."""
    descriptor = descriptor_from_build_digest(build_digest)
    return {
        key: descriptor[key]
        for key in (
            "schema_version", "engine_id", "semantic_contract_version",
            "build_digest", "content_hash",
        )
    }


def _columns_matching(embedded: dict) -> dict:
    """The four engine columns set to the embedded block's values — so the
    record passes the column<->embedded equality check and ONLY the embedded
    block's shape can reject it."""
    return {
        "engine_id": embedded.get("engine_id"),
        "semantic_contract_version": embedded.get("semantic_contract_version"),
        "build_digest": embedded.get("build_digest"),
        "engine_descriptor_content_hash": embedded.get("content_hash"),
    }


def _v2_run_embedding(embedded: dict, columns: dict) -> PredictionRunRecord:
    payload = {
        "model_release_id": "r",
        "starts_at": "2026-07-20T23:00:00Z",
        PREDICTION_ENGINE_REQUEST_KEY: embedded,
    }
    return PredictionRunRecord(
        prediction_run_id=prediction_run_id_for(
            payload, PREDICTION_RUN_IDENTITY_VERSION_V2
        ),
        identity_version=PREDICTION_RUN_IDENTITY_VERSION_V2,
        response_schema_version=2,
        request_payload=payload,
        model_snapshot_id="a" * 64,
        model_release_id="r",
        model_release_content_hash="b" * 64,
        starts_at=datetime(2026, 7, 20, 23, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 7, 21, 5, 0, tzinfo=timezone.utc),
        timestep_seconds=300.0,
        member_summaries=(),
        artifact=_artifact_record(),
        engine_id=columns["engine_id"],
        semantic_contract_version=columns["semantic_contract_version"],
        build_digest=columns["build_digest"],
        engine_descriptor_content_hash=columns["engine_descriptor_content_hash"],
    )


class TestPredictionRunRecordEngineIdentity:
    def test_v2_record_pins_engine_fields_matching_the_embedded_descriptor(self):
        descriptor = _engine_descriptor()
        run = _v2_run(descriptor)
        assert run.identity_version == 2
        assert run.build_digest == descriptor["build_digest"]
        assert run.engine_descriptor_content_hash == descriptor["content_hash"]

    def test_v2_run_id_changes_when_engine_digest_changes(self):
        run_a = _v2_run(_engine_descriptor("a" * 64))
        run_b = _v2_run(_engine_descriptor("c" * 64))
        # Identical hydraulic payload, different engine -> different v2 run id.
        assert run_a.prediction_run_id != run_b.prediction_run_id

    def test_v2_record_rejects_engine_fields_inconsistent_with_payload(self):
        descriptor = _engine_descriptor("a" * 64)
        run = _v2_run(descriptor)
        with pytest.raises(PredictionRunConflict, match="engine identity fields"):
            PredictionRunRecord(
                prediction_run_id=run.prediction_run_id,
                identity_version=2,
                response_schema_version=2,
                request_payload=run.request_payload,
                model_snapshot_id=run.model_snapshot_id,
                model_release_id=run.model_release_id,
                model_release_content_hash=run.model_release_content_hash,
                starts_at=run.starts_at,
                ends_at=run.ends_at,
                timestep_seconds=run.timestep_seconds,
                member_summaries=run.member_summaries,
                artifact=run.artifact,
                engine_id=run.engine_id,
                semantic_contract_version=run.semantic_contract_version,
                build_digest="f" * 64,  # does not match the embedded descriptor
                engine_descriptor_content_hash=run.engine_descriptor_content_hash,
            )

    def test_v2_record_rejects_embedded_descriptor_with_bad_schema_version(self):
        embedded = _valid_embedded()
        embedded["schema_version"] = 999
        with pytest.raises(PredictionRunConflict, match="malformed"):
            _v2_run_embedding(embedded, _columns_matching(embedded))

    def test_v2_record_rejects_embedded_descriptor_with_extra_key(self):
        embedded = _valid_embedded()
        embedded["rogue"] = "x"
        with pytest.raises(PredictionRunConflict, match="malformed"):
            _v2_run_embedding(embedded, _columns_matching(embedded))

    def test_v2_record_rejects_embedded_descriptor_with_boolean_version(self):
        embedded = _valid_embedded()
        embedded["semantic_contract_version"] = True
        with pytest.raises(PredictionRunConflict, match="malformed"):
            _v2_run_embedding(embedded, _columns_matching(embedded))

    def test_v2_record_rejects_embedded_descriptor_with_drifted_content_hash(self):
        embedded = _valid_embedded()
        embedded["content_hash"] = "f" * 64  # not re-derivable from the fields
        with pytest.raises(PredictionRunConflict, match="malformed"):
            _v2_run_embedding(embedded, _columns_matching(embedded))

    def test_v1_record_must_not_carry_engine_fields(self):
        payload = {"model_release_id": "r", "starts_at": "2026-07-20T23:00:00Z"}
        with pytest.raises(ValueError, match="must not carry engine identity"):
            PredictionRunRecord(
                prediction_run_id=prediction_run_id_for(payload, 1),
                identity_version=1,
                response_schema_version=2,
                request_payload=payload,
                model_snapshot_id="a" * 64,
                model_release_id="r",
                model_release_content_hash="b" * 64,
                starts_at=datetime(2026, 7, 20, 23, 0, tzinfo=timezone.utc),
                ends_at=datetime(2026, 7, 21, 5, 0, tzinfo=timezone.utc),
                timestep_seconds=300.0,
                member_summaries=(),
                artifact=_artifact_record(),
                engine_id="munbon.flow-monitoring.network-transient",
            )

    def test_v2_record_requires_all_engine_fields(self):
        descriptor = _engine_descriptor()
        run = _v2_run(descriptor)
        with pytest.raises(ValueError, match="require the four engine"):
            PredictionRunRecord(
                prediction_run_id=run.prediction_run_id,
                identity_version=2,
                response_schema_version=2,
                request_payload=run.request_payload,
                model_snapshot_id=run.model_snapshot_id,
                model_release_id=run.model_release_id,
                model_release_content_hash=run.model_release_content_hash,
                starts_at=run.starts_at,
                ends_at=run.ends_at,
                timestep_seconds=run.timestep_seconds,
                member_summaries=run.member_summaries,
                artifact=run.artifact,
                engine_id=None,  # missing engine pins on a v2 row
            )


# ---------------------------------------------------------------------------
# Interface pinning
# ---------------------------------------------------------------------------

_POSTGRES_REPO_PATH = "db.prediction_repository"
_POSTGRES_REPO_CLASS = "PostgresPredictionRepository"

# method_name -> total param count INCLUDING self
_PROTOCOL_METHODS = {
    "persist_prediction_run": 2,
    "load_prediction_run": 2,
}


@pytest.fixture(scope="module")
def postgres_repo_class():
    mod = importlib.import_module(_POSTGRES_REPO_PATH)
    return getattr(mod, _POSTGRES_REPO_CLASS)


class TestPostgresRepositoryInterfacePinning:
    def test_postgres_repository_pins_in_memory_interface(
        self, postgres_repo_class
    ):
        for method_name, param_count in _PROTOCOL_METHODS.items():
            method = getattr(postgres_repo_class, method_name, None)
            assert method is not None, (
                f"PostgresPredictionRepository missing method {method_name}"
            )
            sig = inspect.signature(method)
            params = [
                name
                for name, param in sig.parameters.items()
                if param.kind
                not in (
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD,
                )
            ]
            assert len(params) == param_count, (
                f"{method_name} must accept {param_count} params "
                f"(incl. self), got {params}"
            )

    def test_postgres_repository_contains_no_schema_creation(
        self, postgres_repo_class
    ):
        source_file = inspect.getfile(postgres_repo_class)
        source = open(source_file).read()

        forbidden_ddl = (
            "CREATE SCHEMA",
            "CREATE TABLE",
            "CREATE OR REPLACE",
            "ALTER TABLE",
        )
        for keyword in forbidden_ddl:
            assert keyword not in source, (
                f"PostgresPredictionRepository contains forbidden DDL: "
                f"{keyword!r}"
            )

    def test_postgres_repository_contains_no_update_or_upsert(
        self, postgres_repo_class
    ):
        source_file = inspect.getfile(postgres_repo_class)
        source = open(source_file).read()

        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(
                node.func, ast.Attribute
            ):
                if node.func.attr in ("execute", "executemany"):
                    if node.args and isinstance(node.args[0], ast.Constant):
                        sql = node.args[0].value.upper().strip()
                        assert not sql.startswith("UPDATE"), (
                            f"Repository contains UPDATE: {sql[:60]}"
                        )
                        assert not sql.startswith("DELETE"), (
                            f"Repository contains DELETE: {sql[:60]}"
                        )
                        assert "UPSERT" not in sql, (
                            f"Repository contains UPSERT: {sql[:60]}"
                        )
                        assert "ON CONFLICT" not in sql, (
                            f"Repository contains ON CONFLICT: {sql[:60]}"
                        )
