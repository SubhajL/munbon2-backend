import asyncio
import json
import os
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
    get_active_planning_depth_submission,
    load_authoritative_planning_depth_roster,
    load_planning_depth_roster,
)
from schemas.planning_depth import (
    EffectivePrincipalProjection,
    PlanningDepthSubmissionRequest,
)

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


PRINCIPAL = EffectivePrincipalProjection(
    subject="operator-1",
    effective_roles=["field_team", "operator"],
)


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
async def test_roster_projects_only_the_active_v5_hybrid_dataset(connection):
    roster = await load_planning_depth_roster(connection)

    assert (
        len(roster),
        {item.section_id for item in roster},
        sum((item.area_rai for item in roster), Decimal("0")),
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
    roster = await load_planning_depth_roster(connection)
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
        await load_planning_depth_roster(connection)


@pytest.mark.asyncio
async def test_concurrent_successors_serialize_to_one_commit(connection):
    roster = await load_planning_depth_roster(connection)
    initial = await create_planning_depth_submission(
        connection,
        _request(),
        PRINCIPAL,
        roster,
    )

    async def submit(depth):
        candidate_connection = await asyncpg.connect(TEST_URL)
        try:
            candidate_roster = await load_planning_depth_roster(candidate_connection)
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
    roster = await load_planning_depth_roster(connection)

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
async def test_database_enforces_immutable_rows_and_one_successor(connection):
    root_id = uuid4()
    successor_id = uuid4()
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
            request_document_text, request_sha256, expanded_sha256
        )
        VALUES ($1, 1, $2, 'mun-bon', '2026-W30', $3, 'operator-1', $4,
                '{}', $5, $5)
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
                request_document_text, request_sha256, expanded_sha256
            )
            VALUES ($1, 1, $2, 'mun-bon', '2026-W30', $3, 'operator-1', $4,
                    '{}', $5, $5)
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
                request_document_text, request_sha256, expanded_sha256
            )
            VALUES ($1, 1, $2, 'mun-bon', '2026-W30', $3, 'operator-1', NULL,
                    '{}', $4, $4)
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
