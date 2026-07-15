"""Canonical versioned daily water-requirement publication contract."""

import subprocess
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from db.water_requirement_repository import (
    RequirementRepositoryError,
    fail_requirement_run,
    get_published_requirements,
    publish_requirement_run,
    start_requirement_run,
)

SERVICE_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = SERVICE_ROOT / "migrations"
UP_SQL = MIGRATIONS / "0002_water_requirement_publication.up.sql"
DOWN_SQL = MIGRATIONS / "0002_water_requirement_publication.down.sql"
UTC = timezone.utc
AS_OF = date(2026, 7, 16)
HORIZON_END = AS_OF + timedelta(days=6)
HASH_A = "a" * 64
HASH_B = "b" * 64


def _instant(hour: int = 0) -> datetime:
    return datetime(2026, 7, 16, hour, tzinfo=UTC)


def _run_args(**overrides) -> dict:
    values = {
        "as_of_date": AS_OF,
        "horizon_start": AS_OF,
        "horizon_end": HORIZON_END,
        "input_cutoff_at": _instant(1),
        "section_dataset_version_id": 11,
        "gate_mapping_dataset_version_id": 12,
        "crop_register_version": "crop-2026-07-16",
        "weather_version": "weather-2026-07-16T01:00Z",
        "method_version": "daily-requirement-v1",
        "content_hash": HASH_A,
        "computed_at": _instant(2),
    }
    values.update(overrides)
    return values


def _requirement(**overrides) -> dict:
    values = {
        "requirement_id": uuid4(),
        "service_date": AS_OF,
        "zone": 1,
        "section_id": "section-1",
        "required_net_volume_m3": Decimal("800.000000"),
        "required_gross_volume_m3": Decimal("1000.000000"),
        "delivery_window_start": _instant(6),
        "delivery_window_end": _instant(18),
        "quality": "estimated",
        "input_versions": {"crop": "crop-2026-07-16"},
        "content_hash": HASH_A,
    }
    values.update(overrides)
    return values


def _contribution(requirement_id: UUID, **overrides) -> dict:
    values = {
        "requirement_id": requirement_id,
        "area_id": "plot-1",
        "area_rai": Decimal("20.000000"),
        "crop_type": "rice",
        "crop_stage": "vegetative",
        "net_volume_m3": Decimal("800.000000"),
        "source_payload_hash": HASH_B,
    }
    values.update(overrides)
    return values


class _PublicationConn:
    def __init__(self):
        self.runs: dict[UUID, dict] = {}
        self.requirements: list[dict] = []
        self.contributions: list[dict] = []
        self.calls: list[tuple] = []
        self.transaction_depth = 0

    @asynccontextmanager
    async def transaction(self):
        self.transaction_depth += 1
        try:
            yield self
        finally:
            self.transaction_depth -= 1

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args, self.transaction_depth))
        if "INSERT INTO ros_gis.water_requirement_runs" in sql:
            (
                run_id,
                as_of_date,
                horizon_start,
                horizon_end,
                input_cutoff_at,
                section_dataset_version_id,
                gate_mapping_dataset_version_id,
                crop_register_version,
                weather_version,
                method_version,
                content_hash,
                computed_at,
            ) = args
            row = {
                "run_id": run_id,
                "as_of_date": as_of_date,
                "timezone": "Asia/Bangkok",
                "horizon_start": horizon_start,
                "horizon_end": horizon_end,
                "input_cutoff_at": input_cutoff_at,
                "section_dataset_version_id": section_dataset_version_id,
                "gate_mapping_dataset_version_id": gate_mapping_dataset_version_id,
                "crop_register_version": crop_register_version,
                "weather_version": weather_version,
                "method_version": method_version,
                "content_hash": content_hash,
                "status": "calculating",
                "computed_at": computed_at,
                "published_at": None,
                "failure_reason": None,
            }
            self.runs[run_id] = row
            return dict(row)
        if "FOR UPDATE" in sql and "water_requirement_runs" in sql:
            row = self.runs.get(args[0])
            return dict(row) if row is not None else None
        if "SET status = 'published'" in sql:
            row = self.runs.get(args[0])
            if row is None or row["status"] != "calculating":
                return None
            row["status"] = "published"
            row["published_at"] = args[1]
            return dict(row)
        if "SET status = 'failed'" in sql:
            row = self.runs.get(args[0])
            if row is None or row["status"] != "calculating":
                return None
            row["status"] = "failed"
            row["failure_reason"] = args[1]
            return dict(row)
        raise AssertionError(f"unexpected fetchrow: {sql}")

    async def execute(self, sql, *args):
        self.calls.append(("execute", sql, args, self.transaction_depth))
        if "SET status = 'superseded'" in sql:
            as_of_date, replacement_run_id = args
            for row in self.runs.values():
                if (
                    row["as_of_date"] == as_of_date
                    and row["status"] == "published"
                    and row["run_id"] != replacement_run_id
                ):
                    row["status"] = "superseded"
            return "UPDATE"
        raise AssertionError(f"unexpected execute: {sql}")

    async def executemany(self, sql, args):
        values = list(args)
        self.calls.append(("executemany", sql, values, self.transaction_depth))
        if "INSERT INTO ros_gis.daily_water_requirements" in sql:
            fields = (
                "requirement_id",
                "run_id",
                "service_date",
                "zone",
                "section_id",
                "required_net_volume_m3",
                "required_gross_volume_m3",
                "delivery_window_start",
                "delivery_window_end",
                "quality",
                "input_versions",
                "content_hash",
            )
            self.requirements.extend(dict(zip(fields, row)) for row in values)
            return
        if "INSERT INTO ros_gis.water_requirement_contributions" in sql:
            fields = (
                "requirement_id",
                "area_id",
                "area_rai",
                "crop_type",
                "crop_stage",
                "net_volume_m3",
                "source_payload_hash",
            )
            self.contributions.extend(dict(zip(fields, row)) for row in values)
            return
        raise AssertionError(f"unexpected executemany: {sql}")

    async def fetch(self, sql, *args):
        self.calls.append(("fetch", sql, args, self.transaction_depth))
        if "FROM ros_gis.water_requirement_runs" not in sql:
            raise AssertionError(f"unexpected fetch: {sql}")
        as_of_date = args[0]
        published_ids = {
            run_id
            for run_id, row in self.runs.items()
            if row["as_of_date"] == as_of_date and row["status"] == "published"
        }
        return [
            dict(requirement)
            for requirement in self.requirements
            if requirement["run_id"] in published_ids
        ]


class TestWaterRequirementMigration:
    def test_migration_pair_is_tracked_and_owned_by_checksum_runner(self):
        assert UP_SQL.is_file() and DOWN_SQL.is_file()
        for path in (UP_SQL, DOWN_SQL):
            ignored = subprocess.run(
                ["git", "check-ignore", "-q", str(path)],
                cwd=SERVICE_ROOT,
                capture_output=True,
            )
            assert ignored.returncode != 0

    def test_up_creates_append_only_publication_schema(self):
        up = UP_SQL.read_text(encoding="utf-8")

        for table in (
            "ros_gis.water_requirement_runs",
            "ros_gis.daily_water_requirements",
            "ros_gis.water_requirement_contributions",
        ):
            assert f"CREATE TABLE {table}" in up
            assert f"CREATE TABLE IF NOT EXISTS {table}" not in up
        assert up.count("BEFORE UPDATE OR DELETE") == 3
        assert "water_requirement_runs_are_append_only" in up
        assert "daily_water_requirements_are_immutable" in up
        assert "water_requirement_contributions_are_immutable" in up
        assert "BEFORE INSERT ON ros_gis.water_requirement_contributions" in up
        assert "publication needs at least one requirement" in up
        assert (
            "SUM(contribution.net_volume_m3) <> requirement.required_net_volume_m3"
            in up
        )
        assert "uq_water_requirement_runs_one_published_day" in up

    def test_run_lineage_uses_real_dataset_parent_key_types_and_kinds(self):
        up = UP_SQL.read_text(encoding="utf-8")

        assert "section_dataset_version_id INTEGER NOT NULL" in up
        assert "gate_mapping_dataset_version_id INTEGER NOT NULL" in up
        assert "section_dataset_kind = 'section_master'" in up
        assert "gate_mapping_dataset_kind = 'gate_crosswalk'" in up
        assert up.count("REFERENCES ros_gis.dataset_versions") == 2
        assert "horizon_start = as_of_date" in up
        assert "horizon_start <= horizon_end" in up
        assert "calculating" in up and "published" in up
        assert "failed" in up and "superseded" in up

    def test_requirement_constraints_lock_horizon_volume_window_and_hashes(self):
        up = UP_SQL.read_text(encoding="utf-8")

        assert "UNIQUE (run_id, service_date, section_id)" in up
        assert "required_net_volume_m3 >= 0" in up
        assert "required_gross_volume_m3 >= required_net_volume_m3" in up
        assert "delivery_window_start < delivery_window_end" in up
        assert "quality IN ('estimated', 'forecast')" in up
        assert "zone BETWEEN 1 AND 6" in up
        assert "service_date = run.as_of_date AND NEW.quality <> 'estimated'" in up
        assert "service_date > run.as_of_date AND NEW.quality <> 'forecast'" in up
        assert "input_cutoff_at <= computed_at" in up
        assert "published_at >= computed_at" in up
        assert "jsonb_typeof(input_versions) = 'object'" in up
        assert "service_date < run.horizon_start" in up
        assert "service_date > run.horizon_end" in up
        assert up.count("~ '^[0-9a-f]{64}$'") >= 3

    def test_down_drops_only_publication_objects_in_dependency_order(self):
        down = DOWN_SQL.read_text(encoding="utf-8")

        assert down.index("water_requirement_contributions") < down.index(
            "daily_water_requirements"
        )
        assert down.index("daily_water_requirements") < down.index(
            "water_requirement_runs"
        )
        assert "dataset_versions" not in down
        assert "DROP TABLE IF EXISTS ros_gis.daily_demands" not in down


class TestWaterRequirementRepository:
    @pytest.mark.asyncio
    async def test_failed_run_is_not_readable_as_published(self):
        conn = _PublicationConn()
        run = await start_requirement_run(conn, **_run_args())

        failed = await fail_requirement_run(conn, run["run_id"], "weather unavailable")

        assert failed["status"] == "failed"
        assert failed["failure_reason"] == "weather unavailable"
        assert await get_published_requirements(conn, AS_OF) == []

    @pytest.mark.asyncio
    async def test_correction_creates_new_run_without_mutating_requirements(self):
        conn = _PublicationConn()
        first = await start_requirement_run(conn, **_run_args())
        first_requirement = _requirement()
        await publish_requirement_run(
            conn, first["run_id"], [first_requirement], published_at=_instant(3)
        )

        second = await start_requirement_run(
            conn, **_run_args(content_hash=HASH_B, computed_at=_instant(3))
        )
        second_requirement = _requirement(
            requirement_id=uuid4(),
            required_net_volume_m3=Decimal("900.000000"),
            required_gross_volume_m3=Decimal("1100.000000"),
            content_hash=HASH_B,
        )
        await publish_requirement_run(
            conn, second["run_id"], [second_requirement], published_at=_instant(4)
        )

        assert first["run_id"] != second["run_id"]
        assert conn.runs[first["run_id"]]["status"] == "superseded"
        assert conn.runs[second["run_id"]]["status"] == "published"
        assert [row["required_net_volume_m3"] for row in conn.requirements] == [
            Decimal("800.000000"),
            Decimal("900.000000"),
        ]
        published = await get_published_requirements(conn, AS_OF)
        assert published == [
            {
                **second_requirement,
                "run_id": second["run_id"],
            }
        ]

    @pytest.mark.asyncio
    async def test_publication_persists_traceable_contribution_atomically(self):
        conn = _PublicationConn()
        run = await start_requirement_run(conn, **_run_args())
        requirement = _requirement()
        contribution = _contribution(requirement["requirement_id"])

        published = await publish_requirement_run(
            conn,
            run["run_id"],
            [requirement],
            [contribution],
            published_at=_instant(3),
        )

        assert published == [{**requirement, "run_id": run["run_id"]}]
        assert conn.contributions == [contribution]
        publication_calls = [
            call
            for call in conn.calls
            if "daily_water_requirements" in call[1]
            or "water_requirement_contributions" in call[1]
            or "SET status = 'published'" in call[1]
        ]
        assert all(call[3] > 0 for call in publication_calls)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "overrides",
        [
            {"service_date": HORIZON_END + timedelta(days=1)},
            {"required_net_volume_m3": Decimal("-0.000001")},
            {"required_gross_volume_m3": Decimal("799.999999")},
            {"required_net_volume_m3": Decimal("NaN")},
            {"required_net_volume_m3": Decimal("0.0000001")},
            {"delivery_window_end": _instant(6)},
            {"input_versions": []},
            {"input_versions": {"not_json": {1, 2}}},
            {"input_versions": {"rainfall_mm": float("nan")}},
            {"zone": 7},
            {"quality": "forecast"},
            {"service_date": AS_OF + timedelta(days=1), "quality": "estimated"},
        ],
    )
    async def test_invalid_horizon_volume_or_window_never_publishes(self, overrides):
        conn = _PublicationConn()
        run = await start_requirement_run(conn, **_run_args())

        with pytest.raises(RequirementRepositoryError):
            await publish_requirement_run(
                conn,
                run["run_id"],
                [_requirement(**overrides)],
                published_at=_instant(3),
            )

        assert conn.requirements == []
        assert conn.runs[run["run_id"]]["status"] == "calculating"

    @pytest.mark.asyncio
    async def test_contribution_sum_must_match_requirement_net_volume(self):
        conn = _PublicationConn()
        run = await start_requirement_run(conn, **_run_args())
        requirement = _requirement()
        contribution = _contribution(
            requirement["requirement_id"], net_volume_m3=Decimal("799.999999")
        )

        with pytest.raises(RequirementRepositoryError, match="contribution"):
            await publish_requirement_run(
                conn,
                run["run_id"],
                [requirement],
                [contribution],
                published_at=_instant(3),
            )

        assert conn.requirements == [] and conn.contributions == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "overrides",
        [
            {"horizon_start": AS_OF + timedelta(days=1)},
            {"horizon_end": AS_OF - timedelta(days=1)},
            {"section_dataset_version_id": True},
            {"crop_register_version": " "},
            {"content_hash": "not-sha256"},
            {"input_cutoff_at": datetime(2026, 7, 16, 1)},
            {"input_cutoff_at": _instant(3), "computed_at": _instant(2)},
        ],
    )
    async def test_invalid_run_identity_or_horizon_is_rejected_before_insert(
        self, overrides
    ):
        conn = _PublicationConn()

        with pytest.raises(RequirementRepositoryError):
            await start_requirement_run(conn, **_run_args(**overrides))

        assert conn.runs == {}

    @pytest.mark.asyncio
    async def test_publication_cannot_predate_computation(self):
        conn = _PublicationConn()
        run = await start_requirement_run(conn, **_run_args())

        with pytest.raises(RequirementRepositoryError, match="published_at"):
            await publish_requirement_run(
                conn,
                run["run_id"],
                [_requirement()],
                published_at=_instant(1),
            )

        assert conn.requirements == []

    @pytest.mark.asyncio
    async def test_published_read_query_includes_run_lineage(self):
        conn = _PublicationConn()

        assert await get_published_requirements(conn, AS_OF) == []
        query = conn.calls[-1][1]
        for field in (
            "run.content_hash AS run_content_hash",
            "run.section_dataset_version_id",
            "run.gate_mapping_dataset_version_id",
            "run.crop_register_version",
            "run.weather_version",
            "run.method_version",
            "run.published_at",
        ):
            assert field in query

    @pytest.mark.asyncio
    async def test_empty_publication_and_invalid_transition_fail_closed(self):
        conn = _PublicationConn()
        run = await start_requirement_run(conn, **_run_args())

        with pytest.raises(RequirementRepositoryError, match="at least one"):
            await publish_requirement_run(conn, run["run_id"], [])
        await fail_requirement_run(conn, run["run_id"], "crop register missing")
        with pytest.raises(RequirementRepositoryError, match="calculating"):
            await publish_requirement_run(conn, run["run_id"], [_requirement()])

        assert conn.requirements == []
