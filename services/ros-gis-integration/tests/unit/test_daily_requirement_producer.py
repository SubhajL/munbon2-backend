from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from services.daily_requirement_producer import (
    RequirementConfigurationError,
    RequirementInputError,
    RequirementSnapshot,
    SectionCropInput,
    calculate_daily_water_requirements,
    requirement_run_content_hash,
)

UTC = timezone.utc
AS_OF = date(2026, 7, 16)
CUTOFF = datetime(2026, 7, 16, 1, tzinfo=UTC)


def _section(**overrides) -> SectionCropInput:
    values = {
        "section_id": "01-01-01-03",
        "zone": 1,
        "area_rai": Decimal("10"),
        "crop_type": "rice",
        "planting_date": date(2026, 7, 9),
        "expected_harvest_date": date(2026, 12, 31),
        "delivery_gate": "M(0,2)",
        "source": "operator-fe",
        "as_of_date": AS_OF,
    }
    values.update(overrides)
    return SectionCropInput(**values)


def _snapshot(**overrides) -> RequirementSnapshot:
    values = {
        "sections": (_section(),),
        "eto_monthly_mm": {7: Decimal("93")},
        "kc_weekly": {("rice", 2): Decimal("1.2")},
        "effective_rainfall_monthly_mm": {("rice", 7): Decimal("31")},
        "section_dataset_version_id": 11,
        "gate_mapping_dataset_version_id": 12,
        "crop_register_version": "crop-v1",
        "weather_version": "weather-v1",
        "annual_plan_version": "annual-plan-v1",
        "source_effective_date": AS_OF,
        "input_cutoff_at": CUTOFF,
    }
    values.update(overrides)
    return RequirementSnapshot(**values)


def test_calculate_daily_water_requirements_publishes_section_level_d_through_d_plus_6():
    snapshot = _snapshot(
        kc_weekly={
            ("rice", 2): Decimal("1.2"),
            ("rice", 3): Decimal("1.2"),
        }
    )

    batch = calculate_daily_water_requirements(snapshot, AS_OF)

    assert [item.service_date for item in batch.requirements] == [
        date(2026, 7, day) for day in range(16, 23)
    ]
    assert batch.requirements[0].required_gross_volume_m3 == Decimal("73.600000")
    assert batch.requirements[0].required_net_volume_m3 == Decimal("73.600000")
    assert batch.requirements[0].quality == "estimated"
    assert {item.quality for item in batch.requirements[1:]} == {"forecast"}
    assert batch.contributions[0].area_id == "01-01-01-03"
    assert batch.contributions[0].crop_stage == "seedling"
    assert batch.contributions[0].net_volume_m3 == Decimal("73.600000")


def test_calculate_daily_water_requirements_accepts_setting_effective_on_operational_date_before_utc_date_boundary():
    operational_date = date(2026, 8, 12)
    snapshot = _snapshot(
        sections=(_section(as_of_date=operational_date),),
        eto_monthly_mm={8: Decimal("93")},
        kc_weekly={("rice", 5): Decimal("1.2")},
        effective_rainfall_monthly_mm={("rice", 8): Decimal("31")},
        source_effective_date=operational_date,
        input_cutoff_at=datetime(2026, 8, 11, 23, 59, 16, tzinfo=UTC),
    )

    batch = calculate_daily_water_requirements(
        snapshot, operational_date, horizon_days=1
    )

    assert [item.service_date for item in batch.requirements] == [operational_date]


def test_calculate_daily_water_requirements_rejects_setting_newer_than_operational_date():
    operational_date = date(2026, 8, 12)
    snapshot = _snapshot(
        sections=(_section(as_of_date=date(2026, 8, 13)),),
        source_effective_date=operational_date,
        input_cutoff_at=datetime(2026, 8, 13, 1, tzinfo=UTC),
    )

    with pytest.raises(RequirementInputError) as exc_info:
        calculate_daily_water_requirements(snapshot, operational_date, horizon_days=1)

    assert str(exc_info.value).splitlines() == [
        "authoritative requirement inputs are incomplete:",
        "- section 01-01-01-03 is newer than the source effective date",
    ]


def test_calculate_daily_water_requirements_aggregates_missing_authoritative_inputs():
    snapshot = _snapshot(
        sections=(
            _section(crop_type=None, delivery_gate=None, planting_date=None),
            _section(section_id="01-01-01-04", zone=7),
        )
    )

    with pytest.raises(RequirementInputError) as exc_info:
        calculate_daily_water_requirements(snapshot, AS_OF)

    assert str(exc_info.value).splitlines() == [
        "authoritative requirement inputs are incomplete:",
        "- section 01-01-01-03 has no crop type",
        "- section 01-01-01-03 has no delivery gate",
        "- section 01-01-01-03 has no zone planting date",
        "- section 01-01-01-04 has invalid zone 7",
    ]


@pytest.mark.parametrize(
    ("planting_date", "expected_harvest_date", "expected_stage"),
    [
        (date(2026, 7, 17), date(2026, 12, 31), "not_planted"),
        (date(2026, 1, 1), date(2026, 7, 15), "harvested"),
    ],
)
def test_calculate_daily_water_requirements_keeps_valid_inactive_crop_as_explicit_zero(
    planting_date,
    expected_harvest_date,
    expected_stage,
):
    batch = calculate_daily_water_requirements(
        _snapshot(
            sections=(
                _section(
                    planting_date=planting_date,
                    expected_harvest_date=expected_harvest_date,
                ),
            )
        ),
        AS_OF,
        horizon_days=1,
    )

    assert batch.requirements[0].required_net_volume_m3 == Decimal("0.000000")
    assert batch.requirements[0].required_gross_volume_m3 == Decimal("0.000000")
    assert batch.contributions[0].crop_stage == expected_stage


def test_requirement_run_content_hash_is_order_independent_and_input_sensitive():
    first = _section()
    second = _section(section_id="01-01-01-04", delivery_gate="M(0,3)")
    left = _snapshot(sections=(first, second))
    right = _snapshot(sections=(second, first))

    assert requirement_run_content_hash(left, AS_OF, 7) == requirement_run_content_hash(
        right, AS_OF, 7
    )
    assert requirement_run_content_hash(left, AS_OF, 7) != requirement_run_content_hash(
        _snapshot(sections=(first, second), weather_version="weather-v2"), AS_OF, 7
    )


def test_requirement_run_content_hash_locks_v2_golden_and_effective_date_identity():
    baseline = requirement_run_content_hash(_snapshot(), AS_OF, 7)

    assert (
        baseline == "b36c5c568b54bb67065d4765d081e5485e1029c3a60d4167845a80f0e562ecf7"
    )
    assert baseline != requirement_run_content_hash(
        _snapshot(source_effective_date=date(2026, 7, 15)), AS_OF, 7
    )
    assert baseline != requirement_run_content_hash(
        _snapshot(section_dataset_version_id=2), AS_OF, 7
    )
    assert baseline != requirement_run_content_hash(
        _snapshot(gate_mapping_dataset_version_id=2), AS_OF, 7
    )


@pytest.mark.parametrize("horizon_days", [True, 0, 32])
def test_requirement_run_content_hash_classifies_invalid_horizon_as_configuration_error(
    horizon_days,
):
    with pytest.raises(RequirementConfigurationError):
        requirement_run_content_hash(_snapshot(), AS_OF, horizon_days)
