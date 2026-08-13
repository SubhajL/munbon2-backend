from datetime import date
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "seed-approved-sources.py"
SPEC = importlib.util.spec_from_file_location("local_approved_sources", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
approved_sources = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(approved_sources)
REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "services/ros-gis-integration/data/requirement_sources.json"


def test_local_source_scenario_seeds_the_approved_hybrid_section_areas():
    manifest = approved_sources.load_manifest(MANIFEST_PATH)

    scenario = approved_sources.build_approved_source_scenario(
        manifest,
        date(2026, 7, 27),
    )
    areas = {
        int(row["code"].rsplit("-", 1)[1]): int(row["props"]["Area_Rai"])
        for row in scenario["tables"]["gis.zone"]
    }

    expected = {
        int(row["section_number"]): int(row["area_rai"])
        for source in ("excel_overrides", "gis_expected_areas")
        for row in manifest["section_master"][source]
    }
    assert scenario["scenario_version"] == "local-ac-1-v6"
    assert areas == expected
    assert sum(areas.values()) == 45204
    assert scenario["tables"]["gis.zone"][32]["props"]["NameArea"] == "RMC"


def test_local_source_scenario_uses_bangkok_midnight_as_inclusive_cutoff():
    scenario = approved_sources.build_approved_source_scenario(
        approved_sources.load_manifest(MANIFEST_PATH),
        date(2026, 8, 12),
    )
    expected = "2026-08-11T17:00:00+00:00"

    assert {
        scenario["tables"]["gis.zone"][0]["create_date"],
        scenario["tables"]["water_planning.zone_planting_dates"][0]["updated_at"],
        scenario["tables"]["ros_gis.section_crop_settings"][0]["created_at"],
        scenario["tables"]["ros.eto_monthly"][0]["updated_at"],
        scenario["tables"]["ros.kc_weekly"][0]["updated_at"],
        scenario["tables"]["ros.effective_rainfall_monthly"][0]["updated_at"],
    } == {expected}
    legacy_setting_id = str(
        approved_sources.uuid5(
            approved_sources.NAMESPACE_URL,
            "local-ac-1-v5:2026-08-12:01-01-01-03",
        )
    )
    assert (
        scenario["tables"]["ros_gis.section_crop_settings"][0]["setting_id"]
        != legacy_setting_id
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda manifest: manifest["section_master"]["excel_overrides"].append(
            deepcopy(manifest["section_master"]["excel_overrides"][0])
        ),
        lambda manifest: manifest["section_master"]["excel_overrides"][0].pop(
            "area_rai"
        ),
        lambda manifest: manifest["section_master"]["excel_overrides"][0].update(
            {"area_rai": "not-a-number"}
        ),
        lambda manifest: manifest["section_master"]["excel_overrides"][0].update(
            {"area_rai": "-1"}
        ),
        lambda manifest: manifest["section_master"]["excel_overrides"][0].update(
            {"area_rai": "973"}
        ),
        lambda manifest: manifest["section_master"]["excel_overrides"][0].update(
            {"start_km": "not-chainage"}
        ),
        lambda manifest: manifest["section_master"]["excel_overrides"][0].update(
            {"start_km": "7+000"}
        ),
    ],
)
def test_local_manifest_rejects_data_that_production_would_reject(mutate):
    manifest = approved_sources.load_manifest(MANIFEST_PATH)
    mutate(manifest)

    with pytest.raises(
        approved_sources.ApprovedSourceError,
        match="approved_manifest_invalid",
    ):
        approved_sources.validate_manifest(manifest)


class _Connection:
    def __init__(self):
        self.ddl = []

    async def execute(self, sql):
        self.ddl.append(sql)

    async def executemany(self, sql, rows):
        pass


@pytest.mark.asyncio
async def test_local_seed_schema_supports_the_gis_geometry_projection():
    connection = _Connection()
    manifest = approved_sources.load_manifest(MANIFEST_PATH)
    scenario = approved_sources.build_approved_source_scenario(
        manifest,
        date(2026, 7, 27),
    )

    await approved_sources._seed_connection(connection, scenario)

    ddl = "\n".join(connection.ddl)
    assert "ADD COLUMN IF NOT EXISTS geom geometry(MULTIPOLYGON, 4326)" in ddl
    assert "WHERE source ~ '^local-ac-1-v[0-9]+$'" in ddl
