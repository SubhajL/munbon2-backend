import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from schemas.planning_depth_v2 import PlanningDepthSubmissionRequestV2
from services.planning_depth_submission import canonicalize_planning_depth_request_v2

REPO_ROOT = Path(__file__).resolve().parents[4]
RID_VECTORS = (
    REPO_ROOT / "contracts" / "rid-calendar" / "v1" / "irrigation-week.vectors.json"
)
EXPECTED_CANONICAL_TEXT = (
    '{"calendar_system":"rid-irrigation-v1","levels":['
    '{"area_id":"01-01","area_type":"zone","planning_depth_mm":"1.500"}],'
    '"project_key":"mun-bon","schema_version":2,"week_date":"2025-11-01",'
    '"week_key":"2026-R01"}'
)
EXPECTED_CANONICAL_SHA256 = (
    "244d9fbb13cbd97654e993012b398d2bfb789cd277318bb677a48b570f1a2e22"
)


def _payload(**overrides):
    payload = {
        "schema_version": 2,
        "client_submission_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "project_key": "mun-bon",
        "calendar_system": "rid-irrigation-v1",
        "week_key": "2026-R01",
        "week_date": "2025-11-01",
        "expected_active_submission_id": None,
        "levels": [
            {
                "area_type": "zone",
                "area_id": "01-01",
                "planning_depth_mm": 1.5,
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_v2_request_matches_every_unique_rid_week_start_vector():
    vectors = json.loads(RID_VECTORS.read_text(encoding="utf-8"))["vectors"]
    identities = {(item["week_key"], item["week_start"]) for item in vectors}

    validated = [
        PlanningDepthSubmissionRequestV2.model_validate(
            _payload(week_key=week_key, week_date=week_start)
        )
        for week_key, week_start in sorted(identities)
    ]

    assert [
        (item.week_key, item.week_date.isoformat()) for item in validated
    ] == sorted(identities)


@pytest.mark.parametrize(
    "overrides",
    [
        {"calendar_system": "legacy-calendar-v1"},
        {"calendar_system": "rid-irrigation-v2"},
        {"week_key": "2026-W01"},
        {"week_key": "2026-R00"},
        {"week_key": "2026-R54"},
        {"week_key": "2025-R01"},
        {"week_key": "1900-R01", "week_date": "1899-11-01"},
        {"week_key": "2402-R01", "week_date": "2401-11-01"},
        {"week_date": "2025-11-02"},
        {"week_date": "2025-11-01T00:00:00Z"},
    ],
)
def test_v2_request_rejects_calendar_key_or_date_drift(overrides):
    with pytest.raises(ValidationError):
        PlanningDepthSubmissionRequestV2.model_validate(_payload(**overrides))


def test_v2_canonicalization_includes_explicit_calendar_identity():
    request = PlanningDepthSubmissionRequestV2.model_validate(_payload())

    canonical = canonicalize_planning_depth_request_v2(request)

    assert (canonical.text, canonical.sha256) == (
        EXPECTED_CANONICAL_TEXT,
        EXPECTED_CANONICAL_SHA256,
    )
