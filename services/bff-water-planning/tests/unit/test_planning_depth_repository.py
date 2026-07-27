from decimal import Decimal

import pytest
from db.planning_depth_repository import load_planning_depth_roster


class _Connection:
    def __init__(self):
        self.query = None

    async def fetch(self, query):
        self.query = query
        return [
            {
                "section_id": f"01-{min(index // 7 + 1, 6):02d}-01-{number:02d}",
                "zone": min(index // 7 + 1, 6),
                "area_rai": Decimal("5204") if number == 43 else Decimal("1000"),
            }
            for index, number in enumerate(range(3, 44))
        ]


@pytest.mark.asyncio
async def test_load_planning_depth_roster_reads_active_versioned_section_master():
    connection = _Connection()

    roster = await load_planning_depth_roster(connection)

    assert "FROM ros_gis.sections_current" in connection.query
    assert "gis.zone" not in connection.query
    assert sum(item.area_rai for item in roster) == Decimal("45204")
    assert roster[0].section_id == "01-01-01-03"
    assert roster[-1].section_id == "01-06-01-43"
