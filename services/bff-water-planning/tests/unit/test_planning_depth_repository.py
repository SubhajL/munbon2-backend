from decimal import Decimal

import pytest
from db.planning_depth_repository import (
    PlanningDepthRosterUnavailableError,
    load_authoritative_planning_depth_roster,
    load_planning_depth_roster_snapshot,
)
from schemas.planning_depth_roster import CANONICAL_SECTION_AREAS_RAI


def _zone(number):
    if number <= 7:
        return 1
    if number <= 14:
        return 2
    if number <= 19:
        return 3
    if number <= 26:
        return 4
    if number <= 34:
        return 5
    return 6


class _Connection:
    def __init__(self, rows=None):
        self.query = None
        self.rows = rows

    async def fetch(self, query):
        self.query = query
        return (
            self.rows
            if self.rows is not None
            else [
                {
                    "dataset_version_id": 42,
                    "source_hash": "1" * 64,
                    "section_id": f"01-{_zone(number):02d}-01-{number:02d}",
                    "zone": _zone(number),
                    "area_rai": CANONICAL_SECTION_AREAS_RAI[number],
                }
                for number in range(3, 44)
            ]
        )


@pytest.mark.asyncio
async def test_load_planning_depth_roster_reads_active_versioned_section_master():
    connection = _Connection()

    roster = await load_planning_depth_roster_snapshot(connection)

    assert "FROM ros_gis.sections_current" in connection.query
    assert "gis.zone" not in connection.query
    assert sum(item.area_rai for item in roster.sections) == Decimal("45204")
    assert roster.sections[0].section_id == "01-01-01-03"
    assert roster.sections[-1].section_id == "01-06-01-43"
    # provenance travels with the sections (same projection, one query)
    assert roster.dataset_version_id > 0
    assert len(roster.source_hash) == 64


@pytest.mark.asyncio
async def test_authoritative_roster_returns_active_dataset_identity_and_source_hash():
    connection = _Connection()

    projection = await load_authoritative_planning_depth_roster(connection)

    assert "JOIN ros_gis.dataset_versions" in connection.query
    assert "FROM ros_gis.sections_current" in connection.query
    assert "gis.zone" not in connection.query
    assert projection.model_dump() == {
        "schema_version": 1,
        "project_key": "mun-bon",
        "dataset_version_id": 42,
        "source_hash": "1" * 64,
        "total_area_rai": Decimal("45204"),
        "sections": [
            {
                "section_id": f"01-{_zone(number):02d}-01-{number:02d}",
                "zone_id": f"01-{_zone(number):02d}",
                "area_rai": CANONICAL_SECTION_AREAS_RAI[number],
            }
            for number in range(3, 44)
        ],
    }


@pytest.mark.asyncio
async def test_authoritative_roster_rejects_mixed_dataset_versions():
    connection = _Connection()
    rows = await connection.fetch("seed")
    rows[-1] = {**rows[-1], "dataset_version_id": 43}
    connection = _Connection(rows)

    with pytest.raises(PlanningDepthRosterUnavailableError):
        await load_authoritative_planning_depth_roster(connection)


@pytest.mark.asyncio
async def test_authoritative_roster_rejects_missing_active_rows():
    with pytest.raises(PlanningDepthRosterUnavailableError):
        await load_authoritative_planning_depth_roster(_Connection([]))
