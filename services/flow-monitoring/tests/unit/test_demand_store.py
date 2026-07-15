"""
Unit tests for the Wave 2.4 immutable versioned stores (HIGH #8): demand records,
allocation records, and delivery observations live in SEPARATE append-only stores —
no upsert, no in-place update, strict version+1 monotonicity, idempotent replay,
content-hash immutability.

Two implementations share one contract:
- core.demand_store.InMemoryDemandStore — the pure reference implementation;
- db.demand_store_postgres.PostgresDemandStore — asyncpg twin (stub pool here; the
  2.6b rule applies: the fake pins the REAL interface, and infra failures are
  injected at every stage/exception type — the store must fail closed, never
  degrade to silent emptiness).
"""
import inspect

import pytest

from core.demand_store import (
    EXCLUDED_FROM_HASH,
    KINDS,
    DemandStoreError,
    DuplicateIdempotencyKey,
    ImmutabilityViolation,
    InMemoryDemandStore,
    VersionConflict,
    semantic_content_hash,
)
from db.demand_store_postgres import (
    DDL_STATEMENTS,
    IDEMPOTENCY_TABLE,
    DemandStoreUnavailable,
    PostgresDemandStore,
    TABLES,
)

KEY = "section|Z1|2026-07-01T00:00:00+00:00|2026-07-08T00:00:00+00:00|ros|bff"
RECORD_V1 = {"area_id": "Z1", "volume_m3": 311040.0}
RECORD_V2 = {"area_id": "Z1", "volume_m3": 320000.0}


@pytest.fixture
def store():
    return InMemoryDemandStore()


class TestInMemoryAppendOnlySemantics:
    @pytest.mark.asyncio
    async def test_first_version_is_accepted_and_returned_as_latest(self, store):
        result = await store.put("demand", KEY, 1, "idem-1", RECORD_V1)
        assert result.replayed is False and result.version == 1
        latest = await store.latest("demand", KEY)
        assert latest["record"] == RECORD_V1 and latest["version"] == 1

    @pytest.mark.asyncio
    async def test_next_version_supersedes_without_destroying_history(self, store):
        await store.put("demand", KEY, 1, "idem-1", RECORD_V1)
        await store.put("demand", KEY, 2, "idem-2", RECORD_V2)
        assert (await store.latest("demand", KEY))["record"] == RECORD_V2
        history = await store.history("demand", KEY)
        assert [h["version"] for h in history] == [1, 2]
        assert history[0]["record"] == RECORD_V1  # v1 survives immutably

    @pytest.mark.asyncio
    async def test_get_version_returns_exact_older_record_not_latest(self, store):
        await store.put("demand", KEY, 1, "idem-1", RECORD_V1)
        await store.put("demand", KEY, 2, "idem-2", RECORD_V2)

        exact = await store.get_version("demand", KEY, 1)

        assert exact == {
            "logical_key": KEY,
            "version": 1,
            "content_hash": semantic_content_hash(RECORD_V1),
            "record": RECORD_V1,
        }

    @pytest.mark.asyncio
    async def test_get_version_returns_defensive_copy(self, store):
        await store.put("demand", KEY, 1, "idem-1", RECORD_V1)

        exact = await store.get_version("demand", KEY, 1)
        exact["record"]["volume_m3"] = 0.0

        assert await store.get_version("demand", KEY, 1) == {
            "logical_key": KEY,
            "version": 1,
            "content_hash": semantic_content_hash(RECORD_V1),
            "record": RECORD_V1,
        }

    @pytest.mark.asyncio
    async def test_get_version_returns_none_when_exact_version_is_missing(self, store):
        await store.put("demand", KEY, 1, "idem-1", RECORD_V1)

        assert await store.get_version("demand", KEY, 2) is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("version", [0, -1, True])
    async def test_get_version_rejects_invalid_version(self, store, version):
        with pytest.raises(DemandStoreError, match="version"):
            await store.get_version("demand", KEY, version)

    @pytest.mark.asyncio
    async def test_version_gap_is_rejected(self, store):
        await store.put("demand", KEY, 1, "idem-1", RECORD_V1)
        with pytest.raises(VersionConflict, match="expected version 2"):
            await store.put("demand", KEY, 3, "idem-3", RECORD_V2)

    @pytest.mark.asyncio
    async def test_first_version_must_be_one(self, store):
        with pytest.raises(VersionConflict, match="expected version 1"):
            await store.put("demand", KEY, 2, "idem-1", RECORD_V1)

    @pytest.mark.asyncio
    async def test_rewriting_an_existing_version_is_an_immutability_violation(
        self, store
    ):
        await store.put("demand", KEY, 1, "idem-1", RECORD_V1)
        with pytest.raises(ImmutabilityViolation):
            await store.put("demand", KEY, 1, "idem-other", RECORD_V2)

    @pytest.mark.asyncio
    async def test_identical_resubmission_same_idempotency_key_replays(self, store):
        await store.put("demand", KEY, 1, "idem-1", RECORD_V1)
        result = await store.put("demand", KEY, 1, "idem-1", RECORD_V1)
        assert result.replayed is True and result.version == 1
        assert len(await store.history("demand", KEY)) == 1

    @pytest.mark.asyncio
    async def test_identical_content_new_idempotency_key_replays_without_growth(
        self, store
    ):
        await store.put("demand", KEY, 1, "idem-1", RECORD_V1)
        result = await store.put("demand", KEY, 1, "idem-9", RECORD_V1)
        assert result.replayed is True
        assert len(await store.history("demand", KEY)) == 1

    @pytest.mark.asyncio
    async def test_same_idempotency_key_different_content_is_rejected(self, store):
        await store.put("demand", KEY, 1, "idem-1", RECORD_V1)
        with pytest.raises(DuplicateIdempotencyKey):
            await store.put("demand", "other-key", 1, "idem-1", RECORD_V2)

    @pytest.mark.asyncio
    async def test_current_returns_latest_version_per_logical_key(self, store):
        await store.put("demand", KEY, 1, "idem-1", RECORD_V1)
        await store.put("demand", KEY, 2, "idem-2", RECORD_V2)
        await store.put("demand", "other-key", 1, "idem-3", RECORD_V1)
        current = await store.current("demand")
        by_key = {c["logical_key"]: c["version"] for c in current}
        assert by_key == {KEY: 2, "other-key": 1}

    @pytest.mark.asyncio
    async def test_kinds_are_isolated_stores(self, store):
        await store.put("demand", KEY, 1, "idem-1", RECORD_V1)
        await store.put("allocation", KEY, 1, "idem-2", RECORD_V2)
        assert (await store.latest("demand", KEY))["record"] == RECORD_V1
        assert (await store.latest("allocation", KEY))["record"] == RECORD_V2
        assert await store.latest("delivery", KEY) is None

    @pytest.mark.asyncio
    async def test_unknown_kind_is_rejected(self, store):
        with pytest.raises(DemandStoreError, match="kind"):
            await store.put("weekly", KEY, 1, "idem-1", RECORD_V1)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_version", [0, -1])
    async def test_nonpositive_versions_are_rejected(self, store, bad_version):
        with pytest.raises(DemandStoreError, match="version"):
            await store.put("demand", KEY, bad_version, "idem-1", RECORD_V1)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", ["", " "])
    async def test_blank_idempotency_key_is_rejected(self, store, bad):
        with pytest.raises(DemandStoreError, match="idempotency"):
            await store.put("demand", KEY, 1, bad, RECORD_V1)

    @pytest.mark.asyncio
    async def test_stored_record_is_a_defensive_copy(self, store):
        payload = dict(RECORD_V1)
        await store.put("demand", KEY, 1, "idem-1", payload)
        payload["volume_m3"] = -999.0
        assert (await store.latest("demand", KEY))["record"] == RECORD_V1

    @pytest.mark.asyncio
    async def test_transport_fields_do_not_defeat_replay(self, store):
        # QCHECK: a crash-recovered client regenerates its idempotency key and
        # computed_at; the record is semantically identical and must replay, not 409.
        original = dict(
            RECORD_V1, idempotency_key="idem-1", computed_at="2026-07-01T00:00:00+00:00"
        )
        retry = dict(
            RECORD_V1,
            idempotency_key="idem-retry",
            computed_at="2026-07-01T06:00:00+00:00",
        )
        await store.put("demand", KEY, 1, "idem-1", original)
        result = await store.put("demand", KEY, 1, "idem-retry", retry)
        assert result.replayed is True
        assert len(await store.history("demand", KEY)) == 1

    @pytest.mark.asyncio
    async def test_semantic_hash_excludes_exactly_the_transport_fields(self):
        assert EXCLUDED_FROM_HASH == frozenset({"idempotency_key", "computed_at"})
        a = dict(RECORD_V1, idempotency_key="x", computed_at="t1")
        b = dict(RECORD_V1, idempotency_key="y", computed_at="t2")
        assert semantic_content_hash(a) == semantic_content_hash(b)
        assert semantic_content_hash(a) != semantic_content_hash(dict(a, volume_m3=1.0))

    @pytest.mark.asyncio
    async def test_replay_binds_the_new_idempotency_key(self, store):
        # QCHECK: a key acknowledged in a replay is BOUND — reusing it later for
        # different content must raise, or the idempotency guarantee is hollow.
        await store.put("demand", KEY, 1, "idem-1", RECORD_V1)
        replay = await store.put("demand", KEY, 1, "idem-9", RECORD_V1)
        assert replay.replayed is True
        with pytest.raises(DuplicateIdempotencyKey):
            await store.put("demand", "other-key", 1, "idem-9", RECORD_V2)

    @pytest.mark.asyncio
    async def test_version_conflict_leaves_no_poisoned_history(self, store):
        # QCHECK: setdefault-before-validation left an empty history that crashed
        # current() with IndexError forever after a single 409.
        with pytest.raises(VersionConflict):
            await store.put("demand", KEY, 2, "idem-1", RECORD_V1)
        assert await store.current("demand") == []
        assert await store.latest("demand", KEY) is None


class TestInterfacePinning:
    """2.6b lesson: a fake encoding a wrong interface makes the suite false assurance."""

    @pytest.mark.parametrize(
        "method", ["put", "latest", "get_version", "current", "history"]
    )
    def test_postgres_store_pins_the_reference_interface(self, method):
        mem = getattr(InMemoryDemandStore, method)
        pg = getattr(PostgresDemandStore, method)
        assert inspect.iscoroutinefunction(
            mem
        ), f"{method} must be async on the reference"
        assert inspect.iscoroutinefunction(pg), f"{method} must be async on postgres"
        assert inspect.signature(mem) == inspect.signature(
            pg
        ), f"PostgresDemandStore.{method} drifted from the reference interface"


class TestPostgresQueryShape:
    """Append-only means append-only at the SQL level too."""

    def test_no_update_or_upsert_anywhere(self):
        import db.demand_store_postgres as mod

        sql_blobs = [
            v for k, v in vars(mod).items() if isinstance(v, str) and k.isupper()
        ] + list(DDL_STATEMENTS)
        joined = "\n".join(sql_blobs).upper()
        assert "ON CONFLICT DO UPDATE" not in joined
        assert "\nUPDATE " not in joined and not joined.startswith("UPDATE ")
        assert " SET " not in joined  # no UPDATE ... SET path at all

    def test_three_separate_tables_one_per_concept_plus_key_registry(self):
        assert set(TABLES) == set(KINDS)
        assert len(set(TABLES.values())) == 3
        for table in TABLES.values():
            assert table.startswith("ros_gis.")
        assert IDEMPOTENCY_TABLE.startswith("ros_gis.")
        assert IDEMPOTENCY_TABLE not in TABLES.values()

    def test_ddl_enforces_immutability_and_utc_instants(self):
        ddl = "\n".join(DDL_STATEMENTS).upper()
        assert ddl.count("UNIQUE (LOGICAL_KEY, VERSION)") == 3
        # Idempotency keys are bound in ONE registry (kind-namespaced) so replays
        # can register new keys against existing record versions.
        assert "PRIMARY KEY (KIND, IDEMPOTENCY_KEY)" in ddl
        assert "TIMESTAMPTZ" in ddl and "TIMESTAMP " not in ddl.replace(
            "TIMESTAMPTZ", ""
        )
        assert "TRIGGER" not in ddl  # no updated_at machinery on an append-only table


class _StubConn:
    """Drives PostgresDemandStore against scripted state; records every call."""

    def __init__(self, state):
        self.state = state

    def transaction(self):
        conn = self

        class _Tx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *exc):
                return False

        return _Tx()

    async def fetchrow(self, sql, *args):
        self.state["calls"].append(("fetchrow", sql, args))
        self.state.get("maybe_raise", lambda stage: None)("fetchrow")
        if "contract_idempotency_keys" in sql and sql.lstrip().startswith("SELECT"):
            return self.state.get("idem_row")
        if "FILTER (WHERE version = $2)" in sql:
            return {
                "latest_version": self.state.get("latest_version", 0),
                "existing_hash": self.state.get("existing_hash"),
            }
        if "ORDER BY version DESC" in sql:
            return self.state.get("latest_row")
        if "logical_key = $1 AND version = $2" in sql:
            return self.state.get("version_row")
        raise AssertionError(f"unexpected fetchrow: {sql}")

    async def fetch(self, sql, *args):
        self.state["calls"].append(("fetch", sql, args))
        self.state.get("maybe_raise", lambda stage: None)("fetch")
        return self.state.get("rows", [])

    async def execute(self, sql, *args):
        self.state["calls"].append(("execute", sql, args))
        self.state.get("maybe_raise", lambda stage: None)("execute")
        return "INSERT 0 1"


class _StubPool:
    def __init__(self, state):
        self.state = state

    def acquire(self):
        state = self.state

        class _Ctx:
            async def __aenter__(self):
                state.get("maybe_raise", lambda stage: None)("acquire")
                return _StubConn(state)

            async def __aexit__(self, *exc):
                return False

        return _Ctx()


def _pg(state):
    state.setdefault("calls", [])
    return PostgresDemandStore(_StubPool(state))


class TestPostgresStoreBehaviour:
    @pytest.mark.asyncio
    async def test_fresh_record_inserts_record_and_binds_key(self):
        state = {"idem_row": None, "existing_hash": None, "latest_version": 0}
        result = await _pg(state).put("demand", KEY, 1, "idem-1", RECORD_V1)
        assert result.replayed is False
        inserts = [c for c in state["calls"] if c[0] == "execute"]
        assert len(inserts) == 2
        assert "INSERT INTO ros_gis.demand_records" in inserts[0][1]
        assert "INSERT INTO ros_gis.contract_idempotency_keys" in inserts[1][1]

    @pytest.mark.asyncio
    async def test_replay_same_idempotency_key_and_content_skips_all_inserts(self):
        state = {
            "idem_row": {
                "logical_key": KEY,
                "version": 1,
                "content_hash": semantic_content_hash(RECORD_V1),
            },
        }
        result = await _pg(state).put("demand", KEY, 1, "idem-1", RECORD_V1)
        assert result.replayed is True
        assert all(c[0] != "execute" for c in state["calls"])

    @pytest.mark.asyncio
    async def test_replay_by_content_binds_the_new_key_only(self):
        # New idempotency key, existing identical version: no record insert, but
        # the key must be REGISTERED so later reuse for different content raises.
        state = {
            "idem_row": None,
            "existing_hash": semantic_content_hash(RECORD_V1),
            "latest_version": 1,
        }
        result = await _pg(state).put("demand", KEY, 1, "idem-9", RECORD_V1)
        assert result.replayed is True
        inserts = [c for c in state["calls"] if c[0] == "execute"]
        assert len(inserts) == 1
        assert "INSERT INTO ros_gis.contract_idempotency_keys" in inserts[0][1]

    @pytest.mark.asyncio
    async def test_same_idempotency_key_different_content_is_rejected(self):
        state = {
            "idem_row": {
                "logical_key": KEY,
                "version": 1,
                "content_hash": semantic_content_hash(RECORD_V1),
            },
        }
        with pytest.raises(DuplicateIdempotencyKey):
            await _pg(state).put("demand", KEY, 1, "idem-1", RECORD_V2)

    @pytest.mark.asyncio
    async def test_rewriting_existing_version_is_immutability_violation(self):
        state = {
            "idem_row": None,
            "existing_hash": semantic_content_hash(RECORD_V1),
            "latest_version": 1,
        }
        with pytest.raises(ImmutabilityViolation):
            await _pg(state).put("demand", KEY, 1, "idem-9", RECORD_V2)

    @pytest.mark.asyncio
    async def test_version_gap_is_rejected_against_db_latest(self):
        state = {"idem_row": None, "existing_hash": None, "latest_version": 1}
        with pytest.raises(VersionConflict, match="expected version 2"):
            await _pg(state).put("demand", KEY, 3, "idem-3", RECORD_V2)

    @pytest.mark.asyncio
    async def test_race_loser_reclassifies_on_retry_instead_of_503(self):
        # QCHECK: a concurrent identical submission losing the UNIQUE race was
        # surfaced as 503 "store down" even though the record IS stored. The
        # store retries classification once and answers the honest replay.
        import asyncpg.exceptions

        raised = {"count": 0}

        def maybe_raise(at):
            if at == "execute" and raised["count"] == 0:
                raised["count"] += 1
                # Winner's row appears; loser's re-read must classify replay.
                state["existing_hash"] = semantic_content_hash(RECORD_V1)
                state["latest_version"] = 1
                raise asyncpg.exceptions.UniqueViolationError("duplicate key")

        state = {
            "idem_row": None,
            "existing_hash": None,
            "latest_version": 0,
            "maybe_raise": maybe_raise,
        }
        result = await _pg(state).put("demand", KEY, 1, "idem-1", RECORD_V1)
        assert result.replayed is True
        assert raised["count"] == 1

    @pytest.mark.asyncio
    async def test_persistent_unique_race_fails_closed(self):
        import asyncpg.exceptions

        def maybe_raise(at):
            if at == "execute":
                raise asyncpg.exceptions.UniqueViolationError("duplicate key")

        state = {
            "idem_row": None,
            "existing_hash": None,
            "latest_version": 0,
            "maybe_raise": maybe_raise,
        }
        with pytest.raises(DemandStoreUnavailable):
            await _pg(state).put("demand", KEY, 1, "idem-1", RECORD_V1)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("stage", ["acquire", "fetchrow", "execute"])
    @pytest.mark.parametrize(
        "exc", [ConnectionError("down"), TimeoutError("slow"), RuntimeError("boom")]
    )
    async def test_infra_failure_at_every_stage_fails_closed(self, stage, exc):
        # 2.6b lesson: a failing dependency must surface, never degrade to
        # fabricated/empty results that read as "no demand".
        def maybe_raise(at):
            if at == stage:
                raise exc

        state = {
            "idem_row": None,
            "existing_hash": None,
            "latest_version": 0,
            "maybe_raise": maybe_raise,
        }
        with pytest.raises(DemandStoreUnavailable):
            await _pg(state).put("demand", KEY, 1, "idem-1", RECORD_V1)

    @pytest.mark.asyncio
    async def test_latest_deserializes_the_stored_envelope(self):
        import json

        state = {
            "latest_row": {
                "logical_key": KEY,
                "version": 2,
                "content_hash": "x" * 64,
                "record": json.dumps(RECORD_V2),
            }
        }
        latest = await _pg(state).latest("demand", KEY)
        assert latest["version"] == 2 and latest["record"] == RECORD_V2

    @pytest.mark.asyncio
    async def test_get_version_queries_logical_key_and_exact_version(self):
        import json

        state = {
            "version_row": {
                "logical_key": KEY,
                "version": 1,
                "content_hash": "x" * 64,
                "record": json.dumps(RECORD_V1),
            }
        }

        exact = await _pg(state).get_version("demand", KEY, 1)

        assert exact == {
            "logical_key": KEY,
            "version": 1,
            "content_hash": "x" * 64,
            "record": RECORD_V1,
        }
        fetch = [call for call in state["calls"] if call[0] == "fetchrow"]
        assert len(fetch) == 1
        assert "logical_key = $1 AND version = $2" in fetch[0][1]
        assert fetch[0][2] == (KEY, 1)

    @pytest.mark.asyncio
    async def test_get_version_returns_none_when_exact_version_is_missing(self):
        assert await _pg({"version_row": None}).get_version("demand", KEY, 1) is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("stage", ["acquire", "fetchrow"])
    async def test_get_version_failure_fails_closed(self, stage):
        def maybe_raise(at):
            if at == stage:
                raise ConnectionError("down")

        with pytest.raises(DemandStoreUnavailable):
            await _pg({"maybe_raise": maybe_raise}).get_version("demand", KEY, 1)

    @pytest.mark.asyncio
    async def test_current_uses_distinct_on_latest_version_per_key(self):
        import json

        state = {
            "rows": [
                {
                    "logical_key": KEY,
                    "version": 2,
                    "content_hash": "x" * 64,
                    "record": json.dumps(RECORD_V2),
                }
            ]
        }
        current = await _pg(state).current("demand")
        assert current == [
            {
                "logical_key": KEY,
                "version": 2,
                "content_hash": "x" * 64,
                "record": RECORD_V2,
            }
        ]
        fetches = [c for c in state["calls"] if c[0] == "fetch"]
        assert len(fetches) == 1 and "DISTINCT ON (logical_key)" in fetches[0][1]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("stage", ["acquire", "fetchrow"])
    async def test_reads_fail_closed_too(self, stage):
        def maybe_raise(at):
            if at == stage:
                raise ConnectionError("down")

        state = {"maybe_raise": maybe_raise}
        with pytest.raises(DemandStoreUnavailable):
            await _pg(state).latest("demand", KEY)
