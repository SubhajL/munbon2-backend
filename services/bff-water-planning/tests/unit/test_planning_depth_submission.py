from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from schemas.planning_depth import PlanningDepthSubmissionRequest
from services.planning_depth_submission import (
    PlanningDepthRateLimitExceeded,
    PlanningDepthValidationError,
    RosterSection,
    canonicalize_planning_depth_request,
    consume_planning_depth_write_limit,
    expand_planning_depth_values,
    validate_planning_depth_roster,
)

ROOT = Path(__file__).resolve().parents[2]


def _roster():
    sections = []
    for index, section_number in enumerate(range(3, 44)):
        zone_number = min(index // 7 + 1, 6)
        sections.append(
            RosterSection(
                section_id=f"01-{zone_number:02d}-01-{section_number:02d}",
                zone_id=f"01-{zone_number:02d}",
                area_rai=Decimal("7385") if section_number == 43 else Decimal("1000"),
            )
        )
    return sections


def _payload(levels, **overrides):
    payload = {
        "schema_version": 1,
        "client_submission_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "project_key": "mun-bon",
        "week_key": "2026-W30",
        "week_date": "2026-07-20",
        "expected_active_submission_id": None,
        "levels": levels,
    }
    payload.update(overrides)
    return PlanningDepthSubmissionRequest.model_validate(payload)


def _complete_levels():
    return [
        {
            "area_type": "zone",
            "area_id": f"01-{zone_number:02d}",
            "planning_depth_mm": zone_number + 0.5,
        }
        for zone_number in range(1, 7)
    ]


def test_numeric_overflow_is_a_validation_error():
    with pytest.raises(ValidationError):
        _payload(
            [
                {
                    "area_type": "zone",
                    "area_id": "01-01",
                    "planning_depth_mm": 1e100,
                }
            ]
        )


class TestCanonicalizePlanningDepthRequest:
    def test_decimal_is_rendered_to_three_places_in_a_stable_request_hash(self):
        request = _payload(
            [
                {
                    "area_type": "zone",
                    "area_id": "01-01",
                    "planning_depth_mm": 20.5,
                }
            ]
        )

        canonical = canonicalize_planning_depth_request(request)

        assert canonical.text == (
            '{"levels":[{"area_id":"01-01","area_type":"zone",'
            '"planning_depth_mm":"20.500"}],"project_key":"mun-bon",'
            '"schema_version":1,"week_date":"2026-07-20","week_key":"2026-W30"}'
        )
        assert canonical.sha256 == (
            "3aeb7c8094cc3f1855b42d772baa8c5249fcdc0e817bfb7b99b2c1a0f59d74d7"
        )

    def test_input_order_does_not_change_the_canonical_request_hash(self):
        levels = [
            {
                "area_type": "zone",
                "area_id": "01-01",
                "planning_depth_mm": 20.5,
            },
            {
                "area_type": "section",
                "area_id": "01-01-01-03",
                "zone_id": "01-01",
                "planning_depth_mm": 15,
            },
        ]

        first = canonicalize_planning_depth_request(_payload(levels))
        second = canonicalize_planning_depth_request(_payload(list(reversed(levels))))

        assert first == second


class TestValidatePlanningDepthRoster:
    def test_missing_zone_default_rejects_incomplete_roster_coverage(self):
        levels = _complete_levels()[:-1]

        with pytest.raises(PlanningDepthValidationError) as info:
            validate_planning_depth_roster(_payload(levels).levels, _roster())

        assert info.value.code == "missing_zone_coverage"

    def test_unknown_section_rejects_before_expansion(self):
        levels = _complete_levels() + [
            {
                "area_type": "section",
                "area_id": "01-01-01-99",
                "zone_id": "01-01",
                "planning_depth_mm": 10,
            }
        ]

        with pytest.raises(PlanningDepthValidationError) as info:
            validate_planning_depth_roster(_payload(levels).levels, _roster())

        assert info.value.code == "unknown_area"

    def test_wrong_section_zone_membership_rejects_exact_identity(self):
        levels = _complete_levels() + [
            {
                "area_type": "section",
                "area_id": "01-01-01-03",
                "zone_id": "01-02",
                "planning_depth_mm": 10,
            }
        ]

        with pytest.raises(PlanningDepthValidationError) as info:
            validate_planning_depth_roster(_payload(levels).levels, _roster())

        assert info.value.code == "wrong_section_zone"

    def test_section_override_wins_and_expansion_is_exactly_sorted_roster(self):
        levels = _complete_levels() + [
            {
                "area_type": "section",
                "area_id": "01-01-01-03",
                "zone_id": "01-01",
                "planning_depth_mm": 10.125,
            }
        ]
        request = _payload(levels)

        validate_planning_depth_roster(request.levels, _roster())
        expanded = expand_planning_depth_values(request.levels, _roster())

        assert len(expanded) == 41
        assert [item.section_id for item in expanded] == sorted(
            item.section_id for item in expanded
        )
        assert expanded[0].model_dump() == {
            "section_id": "01-01-01-03",
            "zone_id": "01-01",
            "planning_depth_mm": Decimal("10.125"),
            "source_kind": "section_override",
            "source_area_id": "01-01-01-03",
        }
        assert expanded[1].model_dump() == {
            "section_id": "01-01-01-04",
            "zone_id": "01-01",
            "planning_depth_mm": Decimal("1.500"),
            "source_kind": "zone_default",
            "source_area_id": "01-01",
        }

    def test_roster_requires_41_sections_six_zones_and_47385_rai(self):
        invalid = _roster()
        invalid[-1] = RosterSection(
            section_id=invalid[-1].section_id,
            zone_id=invalid[-1].zone_id,
            area_rai=Decimal("7384"),
        )

        with pytest.raises(PlanningDepthValidationError) as info:
            validate_planning_depth_roster(
                _payload(_complete_levels()).levels,
                invalid,
            )

        assert info.value.code == "invalid_canonical_roster"

    def test_roster_rejects_noncanonical_section_identity_with_valid_suffix(self):
        invalid = _roster()
        invalid[0] = RosterSection(
            section_id="99-01-01-03",
            zone_id=invalid[0].zone_id,
            area_rai=invalid[0].area_rai,
        )

        with pytest.raises(PlanningDepthValidationError) as info:
            validate_planning_depth_roster(
                _payload(_complete_levels()).levels,
                invalid,
            )

        assert info.value.code == "invalid_canonical_roster"


def test_storage_sql_never_uses_observed_water_level_vocabulary():
    sql = (ROOT / "migrations" / "010_planning_depth_submissions.sql").read_text(
        encoding="utf-8"
    )

    assert "observed_water_level" not in sql.lower()
    assert "water_level" not in sql.lower()
    assert "planning_depth_mm" in sql


class _RateLimitRedis:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def eval(self, script, key_count, key, window_seconds):
        self.calls.append((script, key_count, key, window_seconds))
        return self.result


@pytest.mark.asyncio
async def test_rate_limit_key_hashes_subject_and_returns_fixed_window_ttl():
    redis = _RateLimitRedis((11, 42))

    with pytest.raises(PlanningDepthRateLimitExceeded) as info:
        await consume_planning_depth_write_limit(
            redis,
            "operator-1",
            limit=10,
            window_seconds=300,
        )

    assert info.value.retry_after_seconds == 42
    assert len(redis.calls) == 1
    assert redis.calls[0][1] == 1
    assert "operator-1" not in redis.calls[0][2]
    assert redis.calls[0][2].startswith(
        "bff-water-planning:rate:planning_depth.submit:"
    )
    assert redis.calls[0][3] == 300
    assert "if ttl < 0 then" in redis.calls[0][0]
