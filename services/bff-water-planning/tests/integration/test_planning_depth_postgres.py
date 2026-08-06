import asyncio
import json
import os
import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio
from db.migration_runner import (
    MigrationChecksumError,
    apply_migrations,
    migration_status,
)
from db.planning_depth_repository import (
    PlanningDepthConflictError,
    PlanningDepthRosterUnavailableError,
    create_planning_depth_submission,
    create_planning_depth_submission_v2,
    get_active_planning_depth_submission,
    get_active_planning_depth_submission_v2,
    load_authoritative_planning_depth_roster,
    load_planning_depth_roster_snapshot,
)
from schemas.planning_depth import (
    EffectivePrincipalProjection,
    PlanningDepthSubmissionRequest,
)
from schemas.planning_depth_v2 import PlanningDepthSubmissionRequestV2

TEST_URL = os.getenv("BFF_TEST_POSTGRES_URL")
MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
ROS_SECTION_MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "ros-gis-integration/migrations/0001_dataset_version_parent.up.sql"
)
ROSTER_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "contracts/planning-depth-roster/v1/roster.active-v5.example.json"
)
ROSTER_DOCUMENT = json.loads(ROSTER_FIXTURE.read_text(encoding="utf-8"))

pytestmark = pytest.mark.skipif(
    not TEST_URL,
    reason="BFF_TEST_POSTGRES_URL is not configured",
)


def _assert_disposable_loopback_url() -> None:
    parsed = urlparse(TEST_URL)
    if (
        parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or "test" not in parsed.path.lower()
    ):
        pytest.fail(
            "BFF_TEST_POSTGRES_URL must target a loopback database containing 'test'"
        )


async def _reset_database(connection) -> None:
    await connection.execute("DROP SCHEMA IF EXISTS water_planning CASCADE")
    await connection.execute("DROP SCHEMA IF EXISTS ros_gis CASCADE")
    await apply_migrations(connection, MIGRATIONS)
    await connection.execute(ROS_SECTION_MIGRATION.read_text(encoding="utf-8"))
    superseded_id = await connection.fetchval(
        """
        INSERT INTO ros_gis.dataset_versions (
            dataset_kind, source_hash, source_description, status,
            effective_from, effective_to
        ) VALUES (
            'section_master', repeat('0', 64), 'superseded test roster',
            'superseded', now() - interval '2 days', now() - interval '1 day'
        )
        RETURNING dataset_version_id
        """
    )
    active_id = await connection.fetchval(
        """
        INSERT INTO ros_gis.dataset_versions (
            dataset_kind, source_hash, source_description, status, effective_from
        ) VALUES (
            'section_master', repeat('1', 64), 'active V5 hybrid roster',
            'active', now() - interval '1 day'
        )
        RETURNING dataset_version_id
        """
    )
    rows = [
        (
            row["section_id"],
            int(row["zone_id"].rsplit("-", 1)[1]),
            str(row["area_rai"]),
        )
        for row in ROSTER_DOCUMENT["sections"]
    ]
    await connection.executemany(
        """
        INSERT INTO ros_gis.section_master_history (
            dataset_version_id, section_id, valid_from, zone, area_rai
        ) VALUES ($1, $2, now() - interval '1 day', $3, $4::numeric)
        """,
        [(active_id, *row) for row in rows],
    )
    await connection.executemany(
        """
        INSERT INTO ros_gis.section_master_history (
            dataset_version_id, section_id, valid_from, valid_to, zone, area_rai
        ) VALUES (
            $1, $2, now() - interval '2 days', now() - interval '1 day',
            $3, $4::numeric
        )
        """,
        [(superseded_id, section_id, zone, "1") for section_id, zone, _ in rows],
    )


@pytest_asyncio.fixture
async def connection():
    _assert_disposable_loopback_url()
    connection = await asyncpg.connect(TEST_URL)
    await _reset_database(connection)
    try:
        yield connection
    finally:
        await connection.close()


def _request(
    *,
    client_submission_id=None,
    expected_active_submission_id=None,
    first_zone_depth=1.5,
):
    return PlanningDepthSubmissionRequest.model_validate(
        {
            "schema_version": 1,
            "client_submission_id": str(client_submission_id or uuid4()),
            "project_key": "mun-bon",
            "week_key": "2026-W30",
            "week_date": "2026-07-20",
            "expected_active_submission_id": (
                None
                if expected_active_submission_id is None
                else str(expected_active_submission_id)
            ),
            "levels": [
                {
                    "area_type": "zone",
                    "area_id": f"01-{zone_number:02d}",
                    "planning_depth_mm": (
                        first_zone_depth if zone_number == 1 else zone_number + 0.5
                    ),
                }
                for zone_number in range(1, 7)
            ],
        }
    )


def _request_v2(
    *,
    client_submission_id=None,
    expected_active_submission_id=None,
    first_zone_depth=1.5,
):
    return PlanningDepthSubmissionRequestV2.model_validate(
        {
            "schema_version": 2,
            "client_submission_id": str(client_submission_id or uuid4()),
            "project_key": "mun-bon",
            "calendar_system": "rid-irrigation-v1",
            "week_key": "2026-R01",
            "week_date": "2025-11-01",
            "expected_active_submission_id": (
                None
                if expected_active_submission_id is None
                else str(expected_active_submission_id)
            ),
            "levels": [
                {
                    "area_type": "zone",
                    "area_id": f"01-{zone_number:02d}",
                    "planning_depth_mm": (
                        first_zone_depth if zone_number == 1 else zone_number + 0.5
                    ),
                }
                for zone_number in range(1, 7)
            ],
        }
    )


PRINCIPAL = EffectivePrincipalProjection(
    subject="operator-1",
    effective_roles=["field_team", "operator"],
)


async def _insert_submission(
    connection,
    *,
    schema_version,
    calendar_system,
    week_key,
    week_date,
    submission_id=None,
    client_submission_id=None,
    supersedes_submission_id=None,
    roster_dataset_version_id=None,
    roster_source_hash=None,
):
    # Every NEW submission must carry roster provenance that identifies a REAL
    # section_master dataset (migration 012 trigger). These seed rows are not the
    # subject of provenance tests, so default to the seeded active roster's real
    # (id, hash) pair rather than a fabricated one.
    if roster_dataset_version_id is None or roster_source_hash is None:
        provenance = await connection.fetchrow(
            "SELECT dataset_version_id, source_hash FROM ros_gis.dataset_versions "
            "WHERE dataset_kind = 'section_master' AND status = 'active' LIMIT 1"
        )
        roster_dataset_version_id = provenance["dataset_version_id"]
        roster_source_hash = provenance["source_hash"]
    submission_id = submission_id or uuid4()
    await connection.execute(
        """
        INSERT INTO water_planning.planning_depth_submissions (
            submission_id, schema_version, client_submission_id, project_key,
            calendar_system, week_key, week_date, submitted_by,
            supersedes_submission_id, request_document_text, request_sha256,
            expanded_sha256, roster_dataset_version_id, roster_source_hash
        )
        VALUES ($1, $2, $3, 'mun-bon', $4, $5, $6, 'operator-1', $7,
                '{}', $8, $8, $9, $10)
        """,
        submission_id,
        schema_version,
        client_submission_id or uuid4(),
        calendar_system,
        week_key,
        week_date,
        supersedes_submission_id,
        "a" * 64,
        roster_dataset_version_id,
        roster_source_hash,
    )
    return submission_id


@pytest.mark.asyncio
async def test_apply_reapply_and_checksum_drift_refusal(connection):
    status = await migration_status(connection, MIGRATIONS)
    reapplied = await apply_migrations(connection, MIGRATIONS)

    assert status == [
        {
            "migration_id": "009_crop_registry",
            "sha256": "060062baf15d384730ec1284abb7fb8a39eaa86d238d63140a4648afc79f7d82",
            "applied": True,
        },
        {
            "migration_id": "010_planning_depth_submissions",
            "sha256": "c904510204c97269a73ee4592c06c1a35c1fd8f13b53b47885a21b4c5a5c62f6",
            "applied": True,
        },
        {
            "migration_id": "011_planning_depth_rid_calendar_v2",
            "sha256": "3b9244902872aa7ce9d0e5d24add43e132cbc8f8a159cc486a360c78f816098e",
            "applied": True,
        },
        {
            "migration_id": "012_planning_depth_roster_provenance",
            "sha256": "a557b99068afcaedc12578cc4b45cbad3f2585bbb845bebc995ac0a44b0a165b",
            "applied": True,
        },
    ]
    assert reapplied == []

    await connection.execute(
        "UPDATE water_planning.schema_migrations SET checksum = $1 "
        "WHERE migration_id = '009_crop_registry'",
        "0" * 64,
    )
    with pytest.raises(MigrationChecksumError):
        await apply_migrations(connection, MIGRATIONS)


@pytest.mark.asyncio
async def test_migration_011_preserves_seeded_v1_row_and_legacy_default(connection):
    await connection.execute("DROP SCHEMA IF EXISTS water_planning CASCADE")
    migration_010 = MIGRATIONS / "010_planning_depth_submissions.sql"
    migration_011 = MIGRATIONS / "011_planning_depth_rid_calendar_v2.sql"
    await connection.execute(migration_010.read_text(encoding="utf-8"))
    submission_id = uuid4()
    await connection.execute(
        """
        INSERT INTO water_planning.planning_depth_submissions (
            submission_id, schema_version, client_submission_id, project_key,
            week_key, week_date, submitted_by, supersedes_submission_id,
            request_document_text, request_sha256, expanded_sha256
        )
        VALUES ($1, 1, $2, 'mun-bon', '2026-W30', $3, 'operator-1', NULL,
                '{}', $4, $4)
        """,
        submission_id,
        uuid4(),
        date(2026, 7, 20),
        "a" * 64,
    )
    before = dict(
        await connection.fetchrow(
            "SELECT * FROM water_planning.planning_depth_submissions "
            "WHERE submission_id = $1",
            submission_id,
        )
    )

    await connection.execute(migration_011.read_text(encoding="utf-8"))
    after = dict(
        await connection.fetchrow(
            "SELECT * FROM water_planning.planning_depth_submissions "
            "WHERE submission_id = $1",
            submission_id,
        )
    )

    assert after == {**before, "calendar_system": "legacy-calendar-v1"}


@pytest.mark.asyncio
async def test_v1_and_v2_roots_replay_and_active_reads_are_calendar_scoped(connection):
    roster = await load_planning_depth_roster_snapshot(connection)
    shared_client_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")

    legacy = await create_planning_depth_submission(
        connection,
        _request(client_submission_id=shared_client_id),
        PRINCIPAL,
        roster,
    )
    rid = await create_planning_depth_submission_v2(
        connection,
        _request_v2(client_submission_id=shared_client_id),
        PRINCIPAL,
        roster,
    )
    legacy_active = await get_active_planning_depth_submission(
        connection,
        "mun-bon",
        "2026-W30",
    )
    rid_active = await get_active_planning_depth_submission_v2(
        connection,
        "mun-bon",
        "rid-irrigation-v1",
        "2026-R01",
    )

    assert (
        legacy.schema_version,
        rid.schema_version,
        rid.calendar_system,
        legacy_active.submission_id,
        rid_active.submission_id,
    ) == (
        1,
        2,
        "rid-irrigation-v1",
        legacy.submission_id,
        rid.submission_id,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "schema_version",
        "calendar_system",
        "week_key",
        "week_date",
    ),
    [
        (1, "rid-irrigation-v1", "2026-R01", date(2025, 11, 1)),
        (2, "legacy-calendar-v1", "2026-W30", date(2026, 7, 20)),
        (2, "rid-irrigation-v1", "2026-R54", date(2026, 10, 31)),
        (2, "rid-irrigation-v1", "2026-R01", date(2025, 11, 2)),
        (2, "rid-irrigation-v1", "1900-R01", date(1899, 11, 1)),
    ],
)
async def test_database_rejects_invalid_schema_calendar_key_date_combinations(
    connection,
    schema_version,
    calendar_system,
    week_key,
    week_date,
):
    with pytest.raises(asyncpg.CheckViolationError):
        await _insert_submission(
            connection,
            schema_version=schema_version,
            calendar_system=calendar_system,
            week_key=week_key,
            week_date=week_date,
        )


@pytest.mark.asyncio
async def test_database_rejects_cross_calendar_successor(connection):
    legacy_id = await _insert_submission(
        connection,
        schema_version=1,
        calendar_system="legacy-calendar-v1",
        week_key="2026-W30",
        week_date=date(2026, 7, 20),
    )

    with pytest.raises(asyncpg.CheckViolationError):
        await _insert_submission(
            connection,
            schema_version=2,
            calendar_system="rid-irrigation-v1",
            week_key="2026-R01",
            week_date=date(2025, 11, 1),
            supersedes_submission_id=legacy_id,
        )


@pytest.mark.asyncio
async def test_roster_projects_only_the_active_v5_hybrid_dataset(connection):
    roster = await load_planning_depth_roster_snapshot(connection)

    assert (
        len(roster.sections),
        {item.section_id for item in roster.sections},
        sum((item.area_rai for item in roster.sections), Decimal("0")),
    ) == (
        41,
        {row["section_id"] for row in ROSTER_DOCUMENT["sections"]},
        Decimal("45204"),
    )


@pytest.mark.asyncio
async def test_authoritative_roster_projects_active_version_and_source_hash(connection):
    projection = await load_authoritative_planning_depth_roster(connection)
    active_dataset_id = await connection.fetchval(
        "SELECT dataset_version_id FROM ros_gis.dataset_versions "
        "WHERE dataset_kind = 'section_master' AND status = 'active'"
    )

    assert projection.model_dump(mode="json") == {
        **ROSTER_DOCUMENT,
        "dataset_version_id": active_dataset_id,
    }


@pytest.mark.asyncio
async def test_replay_conflict_successor_and_active_projection(connection):
    roster = await load_planning_depth_roster_snapshot(connection)
    client_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    initial_request = _request(client_submission_id=client_id)

    initial = await create_planning_depth_submission(
        connection,
        initial_request,
        PRINCIPAL,
        roster,
    )
    replay = await create_planning_depth_submission(
        connection,
        initial_request,
        PRINCIPAL,
        roster,
    )

    assert initial.replayed is False
    assert replay.model_copy(update={"replayed": False}) == initial

    with pytest.raises(PlanningDepthConflictError) as changed_client:
        await create_planning_depth_submission(
            connection,
            _request(client_submission_id=client_id, first_zone_depth=2.5),
            PRINCIPAL,
            roster,
        )
    assert str(changed_client.value) == "client_submission_id_conflict"

    same_content_new_client = await create_planning_depth_submission(
        connection,
        _request(),
        PRINCIPAL,
        roster,
    )
    assert same_content_new_client.submission_id == initial.submission_id
    assert same_content_new_client.replayed is True

    successor_request = _request(
        expected_active_submission_id=initial.submission_id,
        first_zone_depth=2.5,
    )
    successor = await create_planning_depth_submission(
        connection,
        successor_request,
        PRINCIPAL,
        roster,
    )
    active = await get_active_planning_depth_submission(
        connection,
        "mun-bon",
        "2026-W30",
    )

    assert successor.supersedes_submission_id == initial.submission_id
    assert active.submission_id == successor.submission_id
    assert len(active.levels) == 41
    assert (
        active.levels[0].planning_depth_mm
        == successor_request.levels[0].planning_depth_mm
    )

    replay_after_successor = await create_planning_depth_submission(
        connection,
        initial_request,
        PRINCIPAL,
        roster,
    )
    assert replay_after_successor.model_copy(update={"replayed": False}) == initial

    with pytest.raises(PlanningDepthConflictError) as stale:
        await create_planning_depth_submission(
            connection,
            _request(
                expected_active_submission_id=initial.submission_id,
                first_zone_depth=3.5,
            ),
            PRINCIPAL,
            roster,
        )
    assert str(stale.value) == "stale_active_submission"


@pytest.mark.asyncio
async def test_roster_requires_an_active_ros_gis_dataset(connection):
    await connection.execute(
        """
        UPDATE ros_gis.dataset_versions
        SET status = 'superseded', effective_to = now()
        WHERE dataset_kind = 'section_master' AND status = 'active'
        """
    )

    with pytest.raises(
        PlanningDepthRosterUnavailableError,
        match="canonical roster is unavailable",
    ):
        await load_planning_depth_roster_snapshot(connection)


@pytest.mark.asyncio
async def test_concurrent_successors_serialize_to_one_commit(connection):
    roster = await load_planning_depth_roster_snapshot(connection)
    initial = await create_planning_depth_submission(
        connection,
        _request(),
        PRINCIPAL,
        roster,
    )

    async def submit(depth):
        candidate_connection = await asyncpg.connect(TEST_URL)
        try:
            candidate_roster = await load_planning_depth_roster_snapshot(candidate_connection)
            return await create_planning_depth_submission(
                candidate_connection,
                _request(
                    expected_active_submission_id=initial.submission_id,
                    first_zone_depth=depth,
                ),
                PRINCIPAL,
                candidate_roster,
            )
        finally:
            await candidate_connection.close()

    results = await asyncio.gather(
        submit(2.5),
        submit(3.5),
        return_exceptions=True,
    )

    assert sum(not isinstance(item, Exception) for item in results) == 1
    assert [
        str(item) for item in results if isinstance(item, PlanningDepthConflictError)
    ] == ["stale_active_submission"]


@pytest.mark.asyncio
async def test_concurrent_v2_successors_serialize_to_one_commit(connection):
    roster = await load_planning_depth_roster_snapshot(connection)
    initial = await create_planning_depth_submission_v2(
        connection,
        _request_v2(),
        PRINCIPAL,
        roster,
    )

    async def submit(depth):
        candidate_connection = await asyncpg.connect(TEST_URL)
        try:
            candidate_roster = await load_planning_depth_roster_snapshot(candidate_connection)
            return await create_planning_depth_submission_v2(
                candidate_connection,
                _request_v2(
                    expected_active_submission_id=initial.submission_id,
                    first_zone_depth=depth,
                ),
                PRINCIPAL,
                candidate_roster,
            )
        finally:
            await candidate_connection.close()

    results = await asyncio.gather(
        submit(2.5),
        submit(3.5),
        return_exceptions=True,
    )

    assert sum(not isinstance(item, Exception) for item in results) == 1
    assert [
        str(item) for item in results if isinstance(item, PlanningDepthConflictError)
    ] == ["stale_active_submission"]


@pytest.mark.asyncio
async def test_transaction_failure_leaves_no_submission_or_values(connection):
    await connection.execute(
        """
        CREATE FUNCTION water_planning.reject_test_value()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'injected value failure';
        END;
        $$;
        CREATE TRIGGER reject_test_value
        BEFORE INSERT ON water_planning.planning_depth_values
        FOR EACH ROW EXECUTE FUNCTION water_planning.reject_test_value();
        """
    )
    roster = await load_planning_depth_roster_snapshot(connection)

    with pytest.raises(asyncpg.RaiseError):
        await create_planning_depth_submission(
            connection,
            _request(),
            PRINCIPAL,
            roster,
        )

    assert (
        await connection.fetchval(
            "SELECT count(*) FROM water_planning.planning_depth_submissions"
        )
        == 0
    )
    assert (
        await connection.fetchval(
            "SELECT count(*) FROM water_planning.planning_depth_values"
        )
        == 0
    )


@pytest.mark.asyncio
async def test_v2_transaction_failure_leaves_no_submission_or_values(connection):
    await connection.execute(
        """
        CREATE FUNCTION water_planning.reject_test_v2_value()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'injected v2 value failure';
        END;
        $$;
        CREATE TRIGGER reject_test_v2_value
        BEFORE INSERT ON water_planning.planning_depth_values
        FOR EACH ROW EXECUTE FUNCTION water_planning.reject_test_v2_value();
        """
    )
    roster = await load_planning_depth_roster_snapshot(connection)

    with pytest.raises(asyncpg.RaiseError):
        await create_planning_depth_submission_v2(
            connection,
            _request_v2(),
            PRINCIPAL,
            roster,
        )

    assert (
        await connection.fetchval(
            "SELECT count(*) FROM water_planning.planning_depth_submissions"
        ),
        await connection.fetchval(
            "SELECT count(*) FROM water_planning.planning_depth_values"
        ),
    ) == (0, 0)


@pytest.mark.asyncio
async def test_database_enforces_immutable_rows_and_one_successor(connection):
    root_id = uuid4()
    successor_id = uuid4()
    # Every insert carries roster provenance (migration 012 trigger fires BEFORE
    # the uniqueness constraints these cases exercise), using a literal valid
    # value so the params below are not renumbered.
    await connection.execute(
        """
        INSERT INTO water_planning.planning_depth_submissions (
            submission_id, schema_version, client_submission_id, project_key,
            week_key, week_date, submitted_by, supersedes_submission_id,
            request_document_text, request_sha256, expanded_sha256,
            roster_dataset_version_id, roster_source_hash
        )
        VALUES ($1, 1, $2, 'mun-bon', '2026-W30', $3, 'operator-1', NULL,
                '{}', $4, $4, (SELECT dataset_version_id FROM ros_gis.dataset_versions WHERE dataset_kind = 'section_master' AND status = 'active'), (SELECT source_hash FROM ros_gis.dataset_versions WHERE dataset_kind = 'section_master' AND status = 'active'))
        """,
        root_id,
        uuid4(),
        date(2026, 7, 20),
        "a" * 64,
    )
    await connection.execute(
        """
        INSERT INTO water_planning.planning_depth_submissions (
            submission_id, schema_version, client_submission_id, project_key,
            week_key, week_date, submitted_by, supersedes_submission_id,
            request_document_text, request_sha256, expanded_sha256,
            roster_dataset_version_id, roster_source_hash
        )
        VALUES ($1, 1, $2, 'mun-bon', '2026-W30', $3, 'operator-1', $4,
                '{}', $5, $5, (SELECT dataset_version_id FROM ros_gis.dataset_versions WHERE dataset_kind = 'section_master' AND status = 'active'), (SELECT source_hash FROM ros_gis.dataset_versions WHERE dataset_kind = 'section_master' AND status = 'active'))
        """,
        successor_id,
        uuid4(),
        date(2026, 7, 20),
        root_id,
        "b" * 64,
    )
    await connection.execute(
        """
        INSERT INTO water_planning.planning_depth_values (
            submission_id, section_id, zone_id, planning_depth_mm,
            source_kind, source_area_id
        )
        VALUES ($1, '01-01-01-03', '01-01', 1.000,
                'zone_default', '01-01')
        """,
        successor_id,
    )

    with pytest.raises(asyncpg.UniqueViolationError):
        await connection.execute(
            """
            INSERT INTO water_planning.planning_depth_submissions (
                submission_id, schema_version, client_submission_id, project_key,
                week_key, week_date, submitted_by, supersedes_submission_id,
                request_document_text, request_sha256, expanded_sha256,
                roster_dataset_version_id, roster_source_hash
            )
            VALUES ($1, 1, $2, 'mun-bon', '2026-W30', $3, 'operator-1', $4,
                    '{}', $5, $5, (SELECT dataset_version_id FROM ros_gis.dataset_versions WHERE dataset_kind = 'section_master' AND status = 'active'), (SELECT source_hash FROM ros_gis.dataset_versions WHERE dataset_kind = 'section_master' AND status = 'active'))
            """,
            uuid4(),
            uuid4(),
            date(2026, 7, 20),
            root_id,
            "c" * 64,
        )

    with pytest.raises(asyncpg.UniqueViolationError):
        await connection.execute(
            """
            INSERT INTO water_planning.planning_depth_submissions (
                submission_id, schema_version, client_submission_id, project_key,
                week_key, week_date, submitted_by, supersedes_submission_id,
                request_document_text, request_sha256, expanded_sha256,
                roster_dataset_version_id, roster_source_hash
            )
            VALUES ($1, 1, $2, 'mun-bon', '2026-W30', $3, 'operator-1', NULL,
                    '{}', $4, $4, (SELECT dataset_version_id FROM ros_gis.dataset_versions WHERE dataset_kind = 'section_master' AND status = 'active'), (SELECT source_hash FROM ros_gis.dataset_versions WHERE dataset_kind = 'section_master' AND status = 'active'))
            """,
            uuid4(),
            uuid4(),
            date(2026, 7, 20),
            "d" * 64,
        )

    for statement in (
        "UPDATE water_planning.planning_depth_submissions "
        "SET submitted_by = 'other' WHERE submission_id = $1",
        "DELETE FROM water_planning.planning_depth_submissions "
        "WHERE submission_id = $1",
        "UPDATE water_planning.planning_depth_values "
        "SET planning_depth_mm = 2 WHERE submission_id = $1",
        "DELETE FROM water_planning.planning_depth_values " "WHERE submission_id = $1",
    ):
        with pytest.raises(asyncpg.ObjectNotInPrerequisiteStateError):
            await connection.execute(statement, successor_id)


# --- R0: roster provenance binding (migration 012) ---


async def _stored_provenance(connection, submission_id):
    return await connection.fetchrow(
        """
        SELECT roster_dataset_version_id, roster_source_hash
        FROM water_planning.planning_depth_submissions
        WHERE submission_id = $1
        """,
        submission_id,
    )


async def _activate_replacement_roster(connection, new_source_hash):
    """Supersede the current active section_master roster and activate a fresh one
    (new_source_hash) with a full section_master_history, so a later snapshot load
    resolves to this new dataset. Returns the new dataset_version_id."""
    await connection.execute(
        "UPDATE ros_gis.dataset_versions SET status = 'superseded', "
        "effective_to = now() "
        "WHERE dataset_kind = 'section_master' AND status = 'active'"
    )
    new_id = await connection.fetchval(
        """
        INSERT INTO ros_gis.dataset_versions (
            dataset_kind, source_hash, source_description, status, effective_from
        ) VALUES ('section_master', $1, 'replacement roster', 'active', now())
        RETURNING dataset_version_id
        """,
        new_source_hash,
    )
    rows = [
        (row["section_id"], int(row["zone_id"].rsplit("-", 1)[1]), str(row["area_rai"]))
        for row in ROSTER_DOCUMENT["sections"]
    ]
    await connection.executemany(
        """
        INSERT INTO ros_gis.section_master_history (
            dataset_version_id, section_id, valid_from, zone, area_rai
        ) VALUES ($1, $2, now(), $3, $4::numeric)
        """,
        [(new_id, *row) for row in rows],
    )
    return new_id


@pytest.mark.asyncio
async def test_new_v1_submission_persists_active_roster_provenance(connection):
    snapshot = await load_planning_depth_roster_snapshot(connection)
    receipt = await create_planning_depth_submission(
        connection, _request(), PRINCIPAL, snapshot
    )

    stored = await _stored_provenance(connection, receipt.submission_id)
    # Assert by IDENTITY, not values: the seeded active V5 roster has
    # source_hash = repeat('1',64); every valid roster normalizes to the same 41
    # sections, so values alone would not distinguish which roster was used.
    assert stored["roster_dataset_version_id"] == snapshot.dataset_version_id
    assert stored["roster_source_hash"] == snapshot.source_hash
    assert stored["roster_source_hash"] == "1" * 64


@pytest.mark.asyncio
async def test_new_v2_submission_persists_active_roster_provenance(connection):
    snapshot = await load_planning_depth_roster_snapshot(connection)
    receipt = await create_planning_depth_submission_v2(
        connection, _request_v2(), PRINCIPAL, snapshot
    )

    stored = await _stored_provenance(connection, receipt.submission_id)
    assert stored["roster_dataset_version_id"] == snapshot.dataset_version_id
    assert stored["roster_source_hash"] == snapshot.source_hash
    assert stored["roster_source_hash"] == "1" * 64


@pytest.mark.asyncio
async def test_stored_provenance_is_the_snapshot_used_not_the_current_roster(
    connection,
):
    # Deterministic snapshot-used proof (no sleep/barrier needed): capture V1,
    # then activate a DIFFERENT roster V2 in ros_gis, then create using the V1
    # snapshot. The stored provenance must be V1's identity -- proving the
    # submission records the roster it EXPANDED FROM, not whatever is active at
    # commit time.
    snapshot_v1 = await load_planning_depth_roster_snapshot(connection)
    assert snapshot_v1.source_hash == "1" * 64

    # Activate a different roster V2 (sections_current is a derived view and
    # cannot be written directly).
    await _activate_replacement_roster(connection, "2" * 64)

    # sanity: the currently-active roster is now V2, distinct from the snapshot
    snapshot_v2 = await load_planning_depth_roster_snapshot(connection)
    assert snapshot_v2.source_hash == "2" * 64
    assert snapshot_v2.dataset_version_id != snapshot_v1.dataset_version_id

    receipt = await create_planning_depth_submission(
        connection, _request(), PRINCIPAL, snapshot_v1
    )
    stored = await _stored_provenance(connection, receipt.submission_id)
    assert stored["roster_dataset_version_id"] == snapshot_v1.dataset_version_id
    assert stored["roster_source_hash"] == "1" * 64  # V1, NOT V2


@pytest.mark.asyncio
async def test_post_012_replay_retains_original_provenance(connection):
    snapshot = await load_planning_depth_roster_snapshot(connection)
    request = _request(client_submission_id=uuid4())
    first = await create_planning_depth_submission(
        connection, request, PRINCIPAL, snapshot
    )
    # Between create and replay a DIFFERENT roster becomes active; the replay
    # passes that new snapshot. Replay must return the original row with its
    # ORIGINAL provenance -- never overwrite it with the incoming/current snapshot.
    await _activate_replacement_roster(connection, "2" * 64)
    new_snapshot = await load_planning_depth_roster_snapshot(connection)
    assert new_snapshot.source_hash != snapshot.source_hash

    replay = await create_planning_depth_submission(
        connection, request, PRINCIPAL, new_snapshot
    )
    assert replay.replayed is True
    assert replay.submission_id == first.submission_id

    stored = await _stored_provenance(connection, first.submission_id)
    assert stored["roster_dataset_version_id"] == snapshot.dataset_version_id
    assert stored["roster_source_hash"] == snapshot.source_hash  # original, not V2


@pytest.mark.asyncio
async def test_all_or_none_check_rejects_half_null_when_trigger_removed(connection):
    # The require-provenance trigger fires BEFORE constraint checks, so it masks
    # the all-or-none CHECK. Drop only that trigger (this connection's schema is
    # reset by the fixture for every test) to exercise the CHECK in isolation,
    # and assert the specific constraint -- not merely the exception class.
    await connection.execute(
        "DROP TRIGGER planning_depth_require_roster_provenance "
        "ON water_planning.planning_depth_submissions"
    )
    with pytest.raises(asyncpg.CheckViolationError) as exc:
        await connection.execute(
            """
            INSERT INTO water_planning.planning_depth_submissions (
                submission_id, schema_version, client_submission_id, project_key,
                week_key, week_date, submitted_by, supersedes_submission_id,
                request_document_text, request_sha256, expanded_sha256,
                roster_dataset_version_id, roster_source_hash
            )
            VALUES ($1, 1, $2, 'mun-bon', '2026-W30', $3, 'operator-1', NULL,
                    '{}', $4, $4, 7, NULL)
            """,
            uuid4(),
            uuid4(),
            date(2026, 7, 20),
            "a" * 64,
        )
    assert exc.value.constraint_name == "planning_depth_roster_provenance_all_or_none"


@pytest.mark.asyncio
async def test_migration_012_upgrades_db_with_existing_v1_and_v2_rows(tmp_path):
    conn = await asyncpg.connect(TEST_URL)
    try:
        await conn.execute("DROP SCHEMA IF EXISTS water_planning CASCADE")
        await conn.execute("DROP SCHEMA IF EXISTS ros_gis CASCADE")

        # Apply only 009-011 via the real runner (pre-012 state).
        pre = tmp_path / "pre_migrations"
        pre.mkdir()
        pre_manifest = {"manifest_version": 1, "owned_migration_number_min": 9,
                        "migrations": []}
        for mid in (
            "009_crop_registry",
            "010_planning_depth_submissions",
            "011_planning_depth_rid_calendar_v2",
        ):
            src = MIGRATIONS / f"{mid}.sql"
            shutil.copy(src, pre / f"{mid}.sql")
            import hashlib as _hashlib

            pre_manifest["migrations"].append(
                {
                    "migration_id": mid,
                    "filename": f"{mid}.sql",
                    "sha256": _hashlib.sha256(src.read_bytes()).hexdigest(),
                }
            )
        (pre / "manifest.json").write_text(json.dumps(pre_manifest), encoding="utf-8")
        applied_pre = await apply_migrations(conn, pre)
        assert applied_pre[-1] == "011_planning_depth_rid_calendar_v2"

        # Seed one legacy v1 row and one v2 row (columns 012 adds do not exist yet).
        legacy_v1 = uuid4()
        legacy_v2 = uuid4()
        await conn.execute(
            """
            INSERT INTO water_planning.planning_depth_submissions (
                submission_id, schema_version, client_submission_id, project_key,
                calendar_system, week_key, week_date, submitted_by,
                supersedes_submission_id, request_document_text, request_sha256,
                expanded_sha256
            ) VALUES ($1, 1, $2, 'mun-bon', 'legacy-calendar-v1', '2026-W30',
                      $3, 'op', NULL, '{}', $4, $4)
            """,
            legacy_v1, uuid4(), date(2026, 7, 20), "a" * 64,
        )
        await conn.execute(
            """
            INSERT INTO water_planning.planning_depth_submissions (
                submission_id, schema_version, client_submission_id, project_key,
                calendar_system, week_key, week_date, submitted_by,
                supersedes_submission_id, request_document_text, request_sha256,
                expanded_sha256
            ) VALUES ($1, 2, $2, 'mun-bon', 'rid-irrigation-v1', '2026-R01',
                      $3, 'op', NULL, '{}', $4, $4)
            """,
            legacy_v2, uuid4(), date(2025, 11, 1), "b" * 64,
        )

        # Upgrade: only 012 should run.
        applied = await apply_migrations(conn, MIGRATIONS)
        assert applied == ["012_planning_depth_roster_provenance"]

        # Legacy rows keep NULL provenance (never fabricated); all-or-none holds.
        legacy_rows = await conn.fetch(
            "SELECT roster_dataset_version_id, roster_source_hash "
            "FROM water_planning.planning_depth_submissions "
            "WHERE submission_id = ANY($1::uuid[])",
            [legacy_v1, legacy_v2],
        )
        assert len(legacy_rows) == 2
        for row in legacy_rows:
            assert row["roster_dataset_version_id"] is None
            assert row["roster_source_hash"] is None

        # A NEW insert without provenance is now rejected (fail-closed trigger).
        with pytest.raises(asyncpg.RaiseError) as exc:
            await conn.execute(
                """
                INSERT INTO water_planning.planning_depth_submissions (
                    submission_id, schema_version, client_submission_id,
                    project_key, calendar_system, week_key, week_date,
                    submitted_by, supersedes_submission_id, request_document_text,
                    request_sha256, expanded_sha256
                ) VALUES ($1, 1, $2, 'mun-bon', 'legacy-calendar-v1', '2026-W31',
                          $3, 'op', NULL, '{}', $4, $4)
                """,
                uuid4(), uuid4(), date(2026, 7, 27), "e" * 64,
            )
        assert "planning_depth_roster_provenance_required" in str(exc.value)
    finally:
        await conn.close()


async def _insert_direct_with_provenance(connection, dataset_version_id, source_hash):
    await connection.execute(
        """
        INSERT INTO water_planning.planning_depth_submissions (
            submission_id, schema_version, client_submission_id, project_key,
            calendar_system, week_key, week_date, submitted_by,
            supersedes_submission_id, request_document_text, request_sha256,
            expanded_sha256, roster_dataset_version_id, roster_source_hash
        )
        VALUES ($1, 1, $2, 'mun-bon', 'legacy-calendar-v1', '2026-W30', $3,
                'op', NULL, '{}', $4, $4, $5, $6)
        """,
        uuid4(), uuid4(), date(2026, 7, 20), "a" * 64,
        dataset_version_id, source_hash,
    )


@pytest.mark.asyncio
async def test_database_rejects_mismatched_or_nonexistent_roster_provenance(connection):
    # A well-formed but fabricated (id, hash) pair -- one that identifies no real
    # section_master dataset -- must be rejected, so provenance cannot be forged
    # into an immutable audit record.
    active = await connection.fetchrow(
        "SELECT dataset_version_id, source_hash FROM ros_gis.dataset_versions "
        "WHERE dataset_kind = 'section_master' AND status = 'active' LIMIT 1"
    )

    # Right id, wrong (but valid-format) hash -> mismatch.
    with pytest.raises(asyncpg.RaiseError) as mismatch:
        await _insert_direct_with_provenance(
            connection, active["dataset_version_id"], "b" * 64
        )
    assert "planning_depth_roster_provenance_unknown" in str(mismatch.value)

    # Nonexistent id with a valid-format hash -> unknown.
    with pytest.raises(asyncpg.RaiseError) as unknown:
        await _insert_direct_with_provenance(connection, 999999, "a" * 64)
    assert "planning_depth_roster_provenance_unknown" in str(unknown.value)


@pytest.mark.asyncio
async def test_superseded_but_real_roster_provenance_is_accepted(connection):
    # "Snapshot used" must accept a real pair even after it is superseded -- the
    # existence check deliberately does NOT require status = 'active'.
    superseded = await connection.fetchrow(
        "SELECT dataset_version_id, source_hash FROM ros_gis.dataset_versions "
        "WHERE dataset_kind = 'section_master' AND status = 'superseded' LIMIT 1"
    )
    assert superseded is not None

    await _insert_direct_with_provenance(
        connection, superseded["dataset_version_id"], superseded["source_hash"]
    )
    stored = await connection.fetchval(
        "SELECT count(*) FROM water_planning.planning_depth_submissions "
        "WHERE roster_dataset_version_id = $1",
        superseded["dataset_version_id"],
    )
    assert stored == 1


@pytest.mark.asyncio
async def test_database_rejects_draft_roster_provenance(connection):
    # A real but DRAFT section_master version never appears in the app's snapshot
    # (sections_current filters status='active'); attaching one is a fabricated
    # provenance path and must be rejected.
    draft_id = await connection.fetchval(
        """
        INSERT INTO ros_gis.dataset_versions (
            dataset_kind, source_hash, source_description, status, effective_from
        ) VALUES ('section_master', $1, 'draft roster', 'draft', now())
        RETURNING dataset_version_id
        """,
        "d" * 64,
    )
    with pytest.raises(asyncpg.RaiseError) as exc:
        await _insert_direct_with_provenance(connection, draft_id, "d" * 64)
    assert "planning_depth_roster_provenance_unknown" in str(exc.value)


@pytest.mark.asyncio
async def test_source_hash_format_check_rejects_non_hex_when_trigger_removed(connection):
    # The provenance trigger fires before CHECK constraints and would mask the
    # format CHECK (a non-hex hash matches no dataset). Drop it to exercise the
    # CHECK in isolation and assert the specific constraint.
    await connection.execute(
        "DROP TRIGGER planning_depth_require_roster_provenance "
        "ON water_planning.planning_depth_submissions"
    )
    with pytest.raises(asyncpg.CheckViolationError) as exc:
        await _insert_direct_with_provenance(connection, 1, "NOT-HEX-" + "z" * 56)
    assert exc.value.constraint_name == "planning_depth_roster_source_hash_format"


@pytest.mark.asyncio
async def test_dataset_version_positivity_check_rejects_non_positive_when_trigger_removed(
    connection,
):
    await connection.execute(
        "DROP TRIGGER planning_depth_require_roster_provenance "
        "ON water_planning.planning_depth_submissions"
    )
    with pytest.raises(asyncpg.CheckViolationError) as exc:
        await _insert_direct_with_provenance(connection, -1, "a" * 64)
    assert exc.value.constraint_name == "planning_depth_roster_dataset_version_positive"


@pytest.mark.asyncio
async def test_post_012_replay_retains_original_provenance_v2(connection):
    snapshot = await load_planning_depth_roster_snapshot(connection)
    request = _request_v2(client_submission_id=uuid4())
    first = await create_planning_depth_submission_v2(
        connection, request, PRINCIPAL, snapshot
    )
    # A different roster becomes active before the replay; the original provenance
    # must survive rather than be overwritten with the now-active snapshot.
    await _activate_replacement_roster(connection, "2" * 64)
    new_snapshot = await load_planning_depth_roster_snapshot(connection)
    assert new_snapshot.source_hash != snapshot.source_hash

    replay = await create_planning_depth_submission_v2(
        connection, request, PRINCIPAL, new_snapshot
    )
    assert replay.replayed is True
    assert replay.submission_id == first.submission_id

    stored = await _stored_provenance(connection, first.submission_id)
    assert stored["roster_dataset_version_id"] == snapshot.dataset_version_id
    assert stored["roster_source_hash"] == snapshot.source_hash  # original, not V2
