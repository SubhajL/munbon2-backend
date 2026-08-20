#!/usr/bin/env python3
"""Run the progressive all-local control-plan acceptance stages."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
import errno
from http.cookiejar import CookieJar
import hashlib
from hmac import compare_digest
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import re
import stat
import subprocess
import tempfile
import sys
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import (
    HTTPCookieProcessor,
    Request,
    build_opener,
    urlopen,
)
from uuid import NAMESPACE_DNS, UUID, uuid5


class StageGateError(RuntimeError):
    """A local stage gate failed with a fixed safe code."""


PROCESS_NAMES = (
    "flow-monitoring",
    "scheduler",
    "ros-gis-integration",
    "bff-water-planning",
)
STAGE_ORDER = (
    "LOCAL-BASE-0",
    "LOCAL-RTA-1",
    "LOCAL-AC-1",
    "LOCAL-READ-ACT-1",
    "LOCAL-EVIDENCE-1",
    "LOCAL-GO-READ-1",
    "LOCAL-WRITE-FOUNDATION-1",
    "LOCAL-WRITE-UI-1",
    "LOCAL-PERSIST-ONLY-1",
    "LOCAL-WRITE-ACT-1",
)
WRITE_UI_DIAGNOSTIC_STAGE = "LOCAL-WRITE-UI-DIAGNOSTIC"
FAILURE_MANIFEST_EXIT_CODE = 70
ACCEPTANCE_MACHINE_NAME = "munbon-control-plan-local"
REHEARSAL_MACHINE_NAME = "munbon-control-plan-rehearsal"
DEFAULT_ACCEPTANCE_EVIDENCE_ROOT = Path("/var/lib/munbon-local-acceptance/evidence")
READINESS_URLS = {
    "flow-monitoring": "http://127.0.0.1:3011/ready",
    "scheduler": "http://127.0.0.1:3021/ready",
    "ros-gis-integration": "http://127.0.0.1:3047/ready",
    "bff-water-planning": "http://127.0.0.1:3022/ready",
}
WRITE_FOUNDATION_NAMESPACE = uuid5(
    NAMESPACE_DNS, "local-write-foundation.munbon.invalid"
)
WRITE_UI_NAMESPACE = uuid5(NAMESPACE_DNS, "local-write-ui.munbon.invalid")
# The frontend's Next.js planning-depth proxy routes fetch `${API_SERVER}${PATH}`
# for the three write-path env vars below. Values are the exact real BFF routes:
# v2 submit/active (planning_depths_v2.py prefix + POST ""/GET "/active") and the
# v1 roster (planning_depth_roster.py prefix + GET "/v1").
FRONTEND_WRITE_PATH_ENVIRONMENT = {
    "API_SERVER": "http://127.0.0.1:3022",
    "PLANNING_DEPTH_SUBMIT_PATH": "/api/v2/water-planning/planning-depth-submissions",
    "PLANNING_DEPTH_ACTIVE_PATH": (
        "/api/v2/water-planning/planning-depth-submissions/active"
    ),
    "PLANNING_DEPTH_ROSTER_PATH": "/api/v1/water-planning/planning-depth-roster/v1",
}
NODE_ROOT = Path("/opt/node-v22.23.1-linux-arm64")
DEPENDENCY_ROOT = Path("/opt/munbon/dependencies")
_NODE_PRELOAD_ENV_VARS = frozenset({"NODE_OPTIONS", "NODE_REPL_EXTERNAL_MODULE"})
BROWSER_ROOT = Path("/opt/munbon/browser")
PM2_CLI = BROWSER_ROOT / "node_modules/pm2/bin/pm2"
PLAYWRIGHT_BROWSERS_ROOT = Path("/opt/munbon/playwright-browsers")
HARNESS_ARTIFACTS = (
    "local-ac1.py",
    "run-evidence-browser.js",
    "run-go-read-browser.js",
    "run-read-browser.js",
    "run-ros-manual-producer.sh",
    "run-stage-suite.py",
    "run-write-browser.js",
    "seed-approved-sources.py",
    "seed-local-operators.js",
    "provisioning_contract.py",
    "validate-dependency-bundle-linux.sh",
    "verify_bearer.py",
)
GATE_ENV_NAMES = {
    "ALLOW_MACHINE_COMMANDS",
    "CONTROL_EXECUTION_MODE",
    "CONTROL_READBACK_RECONCILIATION_MODE",
    "DAILY_REQUIREMENT_ENABLED",
    "DAILY_REQUIREMENT_SCHEDULE_ENABLED",
    "DAILY_REQUIREMENT_STARTUP_CATCHUP_ENABLED",
    "GATES_API_ENABLED",
    "PLANNING_DEPTH_WRITES_ENABLED",
    "REQUIREMENT_SOURCE_POSTGRES_URL",
    "SCHEDULER_DEVICE_CAPABILITY_SNAPSHOT_PATH",
    "SCHEDULER_SCADA_BASE_URL",
    "SCHEDULER_SERVICE_JWT_SECRET",
}
GO_READ_FORBIDDEN_SCADA_ENV = {
    "SCHEDULER_SERVICE_JWT_SECRET",
    "SCADA_SITE_CANONICAL_GATE_ID",
    "SCADA_APPROVED_FIELD_BUNDLE_PATH",
    "SCADA_DEVICE_REGISTRY_PATH",
    "SCADA_APPROVED_LINEAGE_ANCHOR_PATH",
}


@dataclass(frozen=True)
class StageContext:
    release_sha: str
    frontend_sha: str
    repo_root: Path
    harness_root: Path
    evidence_root: Path
    runtime_env_dir: Path
    frontend_root: Path = Path("/opt/munbon/frontend")
    stability_duration: int = 300
    as_of_date: date = date.today()
    execution_kind: str = "canonical"
    owner_path: Path = Path("/var/lib/munbon-local-acceptance/owner.json")
    rc_attempt: dict[str, Any] | None = None


@dataclass(frozen=True)
class HttpResult:
    status: int
    body: Any
    headers: dict[str, str]


class LocalHttpClient:
    def __init__(self) -> None:
        self.cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))

    def request(
        self,
        method: str,
        url: str,
        *,
        payload: dict | None = None,
        bearer: str | None = None,
        internal_trigger: str | None = None,
        timeout: int = 30,
    ) -> HttpResult:
        headers = {"Accept": "application/json"}
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        if bearer is not None:
            headers["Authorization"] = f"Bearer {bearer}"
        if internal_trigger is not None:
            headers["X-Munbon-Internal-Token"] = internal_trigger
        request = Request(url, data=data, headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=timeout)
        except HTTPError as error:
            response = error
        except (OSError, URLError) as exc:
            raise StageGateError("local_http_request_failed") from exc
        try:
            raw = response.read(16 * 1024 * 1024 + 1)
            if len(raw) > 16 * 1024 * 1024:
                raise ValueError
            body = json.loads(raw) if raw else None
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise StageGateError("local_http_response_invalid") from exc
        return HttpResult(
            status=response.status,
            body=body,
            headers={key.lower(): value for key, value in response.headers.items()},
        )

    def refresh_cookie(self) -> str:
        for cookie in self.cookies:
            if cookie.name == "refreshToken" and cookie.value:
                return cookie.value
        raise StageGateError("refresh_cookie_missing")


def validate_runtime_urls(urls: dict[str, str]) -> dict[str, str]:
    for value in urls.values():
        parsed = urlsplit(value)
        if (
            parsed.scheme != "http"
            or parsed.hostname != "127.0.0.1"
            or parsed.port is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise StageGateError("runtime_url_not_loopback")
    return urls


def validate_stage_transition(completed: tuple[str, ...], requested: str) -> None:
    expected_index = len(completed)
    if (
        completed != STAGE_ORDER[:expected_index]
        or expected_index >= len(STAGE_ORDER)
        or requested != STAGE_ORDER[expected_index]
    ):
        raise StageGateError("stage_transition_invalid")


def validate_ros_lifecycle(payload: Any, *, manual_enabled: bool) -> dict:
    try:
        lifecycle = payload["daily_requirement"]
        expected = {
            "enabled": manual_enabled,
            "startup_catchup_enabled": False,
            "schedule_enabled": False,
            "schedule_running": False,
        }
        projected = {name: lifecycle[name] for name in expected}
        if projected != expected:
            raise ValueError
        return projected
    except (KeyError, TypeError, ValueError) as exc:
        raise StageGateError("ros_lifecycle_not_accepted") from exc


def validate_manual_requirement_run(status: int, body: Any, *, as_of_date: str) -> dict:
    try:
        if type(body) is not dict or set(body) != {
            "status",
            "runId",
            "asOfDate",
            "requirementCount",
        }:
            raise ValueError
        if type(body["runId"]) is not str:
            raise ValueError
        run_id = str(UUID(body["runId"]))
        if (
            status != 200
            or body["runId"] != run_id
            or body["status"] not in {"published", "deduplicated"}
            or body["asOfDate"] != as_of_date
            or type(body["requirementCount"]) is not int
            or body["requirementCount"] != 287
        ):
            raise ValueError
        return {
            "status": body["status"],
            "run_id": run_id,
            "as_of_date": body["asOfDate"],
            "requirement_count": body["requirementCount"],
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise StageGateError("manual_requirement_run_not_accepted") from exc


def validate_manual_requirement_failure(
    status: int, body: Any, *, as_of_date: str
) -> None:
    gates = {
        "requirement_source_invalid": (
            "failed_incomplete_source",
            {"status", "reason", "asOfDate"},
            "manual_requirement_source_invalid",
        ),
        "requirement_inputs_incomplete": (
            "failed_incomplete_source",
            {"status", "reason", "asOfDate"},
            "manual_requirement_inputs_incomplete",
        ),
        "superseded_lineage": (
            "rejected",
            {"status", "reason", "asOfDate"},
            "manual_requirement_superseded_lineage",
        ),
        "operational_date_mismatch": (
            "rejected",
            {"status", "reason", "asOfDate", "expectedAsOfDate"},
            "manual_requirement_operational_date_mismatch",
        ),
    }
    try:
        if type(body) is not dict or set(body) != {"detail"}:
            raise ValueError
        detail = body["detail"]
        if type(detail) is not dict:
            raise ValueError
        reason = detail["reason"]
        expected_status, expected_keys, gate = gates[reason]
        if (
            status != 409
            or set(detail) != expected_keys
            or detail["status"] != expected_status
            or detail["asOfDate"] != as_of_date
            or (
                reason == "operational_date_mismatch"
                and (
                    type(detail["expectedAsOfDate"]) is not str
                    or date.fromisoformat(detail["expectedAsOfDate"]).isoformat()
                    != detail["expectedAsOfDate"]
                )
            )
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        raise StageGateError("manual_requirement_run_not_accepted") from exc
    raise StageGateError(gate)


def validate_requirement_run_lineage(
    row: str,
    *,
    run_id: str,
    approved_source_sha256: str,
) -> dict:
    try:
        fields = row.strip().split("\t")
        if len(fields) != 9:
            raise ValueError
        actual_run_id = str(UUID(fields[0]))
        expected_run_id = str(UUID(run_id))
        run_content_sha256 = fields[1]
        section_version_id = int(fields[2])
        section_source_sha256 = fields[3]
        gate_mapping_version_id = int(fields[4])
        gate_mapping_source_sha256 = fields[5]
        versions = fields[6:]
        hashes = (
            run_content_sha256,
            approved_source_sha256,
            section_source_sha256,
            gate_mapping_source_sha256,
        )
        if (
            actual_run_id != expected_run_id
            or section_version_id <= 0
            or gate_mapping_version_id <= 0
            or any(re.fullmatch(r"[0-9a-f]{64}", value) is None for value in hashes)
            or any(not value or value.strip() != value for value in versions)
        ):
            raise ValueError
        return {
            "run_id": actual_run_id,
            "run_content_sha256": run_content_sha256,
            "approved_source_content_sha256": approved_source_sha256,
            "section_dataset": {
                "version_id": section_version_id,
                "source_sha256": section_source_sha256,
            },
            "gate_mapping_dataset": {
                "version_id": gate_mapping_version_id,
                "source_sha256": gate_mapping_source_sha256,
            },
            "crop_register_version": versions[0],
            "weather_version": versions[1],
            "method_version": versions[2],
        }
    except (TypeError, ValueError) as exc:
        raise StageGateError("requirement_run_lineage_not_accepted") from exc


def collect_requirement_run_lineage(
    context: StageContext,
    *,
    run_id: str,
    approved_source_sha256: str,
) -> dict:
    try:
        normalized_run_id = str(UUID(run_id))
    except (TypeError, ValueError) as exc:
        raise StageGateError("requirement_run_lineage_not_accepted") from exc
    row = _psql(
        context,
        f"""
        SELECT run.run_id,
               run.content_hash,
               run.section_dataset_version_id,
               section_dataset.source_hash,
               run.gate_mapping_dataset_version_id,
               gate_mapping_dataset.source_hash,
               run.crop_register_version,
               run.weather_version,
               run.method_version
        FROM ros_gis.water_requirement_runs AS run
        JOIN ros_gis.dataset_versions AS section_dataset
          ON section_dataset.dataset_version_id =
             run.section_dataset_version_id
         AND section_dataset.dataset_kind = 'section_master'
        JOIN ros_gis.dataset_versions AS gate_mapping_dataset
          ON gate_mapping_dataset.dataset_version_id =
             run.gate_mapping_dataset_version_id
         AND gate_mapping_dataset.dataset_kind = 'gate_crosswalk'
        WHERE run.run_id = '{normalized_run_id}'::uuid
          AND run.status = 'published'
        """,
    )
    return validate_requirement_run_lineage(
        row,
        run_id=normalized_run_id,
        approved_source_sha256=approved_source_sha256,
    )


def validate_zone_requirements(
    status: int,
    body: Any,
    *,
    as_of_date: str,
    run_id: str,
) -> dict:
    try:
        expected_sections = {f"01-06-01-{number:02d}" for number in range(35, 44)}
        requirements = body["requirements"]
        if (
            status != 200
            or body["serviceDate"] != as_of_date
            or body["zone"] != 6
            or body["dataStatus"] != "published"
            or not isinstance(requirements, list)
            or len(requirements) != len(expected_sections)
        ):
            raise ValueError
        versions = set()
        sections = set()
        positive_count = 0
        for requirement in requirements:
            UUID(str(requirement["requirementId"]))
            if (
                str(UUID(str(requirement["runId"]))) != run_id
                or requirement["serviceDate"] != as_of_date
                or requirement["zone"] != 6
                or requirement["dataStatus"] != "published"
                or isinstance(requirement["requiredVolumeM3"], bool)
                or not isinstance(requirement["requiredVolumeM3"], (int, float))
                or requirement["requiredVolumeM3"] < 0
            ):
                raise ValueError
            versions.add(requirement["version"])
            sections.add(requirement["sectionId"])
            positive_count += requirement["requiredVolumeM3"] > 0
        if (
            sections != expected_sections
            or len(versions) != 1
            or next(iter(versions)) < 1
            or positive_count == 0
        ):
            raise ValueError
        return {
            "service_date": body["serviceDate"],
            "zone": body["zone"],
            "data_status": body["dataStatus"],
            "requirement_count": len(requirements),
            "run_id": run_id,
            "version": next(iter(versions)),
            "positive_requirement_count": positive_count,
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise StageGateError("zone_requirements_not_accepted") from exc


def validate_draft_result(status: int, body: Any, *, requirement_run_id: str) -> dict:
    try:
        plan_id = str(UUID(str(body["plan_id"])))
        plan_version = body["plan_version"]
        if (
            status not in {200, 201}
            or str(UUID(str(body["requirement_run_id"]))) != requirement_run_id
            or isinstance(plan_version, bool)
            or not isinstance(plan_version, int)
            or plan_version < 1
            or body["lifecycle_state"] != "draft"
            or body["optimizer_status"] != "feasible"
            or body["prediction_status"] != "completed"
            or not isinstance(body["requirements"], list)
            or not body["requirements"]
            or not isinstance(body["events"], list)
            or not body["events"]
            or not isinstance(body["transitions"], list)
            or not body["transitions"]
        ):
            raise ValueError
        return {
            "status": status,
            "plan_id": plan_id,
            "plan_version": plan_version,
            "lifecycle_state": body["lifecycle_state"],
            "optimizer_status": body["optimizer_status"],
            "prediction_status": body["prediction_status"],
            "requirement_count": len(body["requirements"]),
            "event_count": len(body["events"]),
            "transition_count": len(body["transitions"]),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise StageGateError("draft_result_not_accepted") from exc


def validate_projection_result(
    path: str,
    status: int,
    headers: dict[str, str],
    body: Any,
    *,
    plan_id: str,
    plan_version: int,
) -> dict:
    try:
        no_store = "no-store" in headers.get("cache-control", "").lower()
        if status != 200 or not no_store or not isinstance(body, dict):
            raise ValueError
        if path == "/api/v1/control-plans":
            items = body["items"]
            if (
                body["projection_schema_version"] != 2
                or not isinstance(items, list)
                or not any(
                    item.get("plan_id") == plan_id
                    and item.get("plan_version") == plan_version
                    for item in items
                    if isinstance(item, dict)
                )
            ):
                raise ValueError
        elif body.get("plan_id") != plan_id or body.get("plan_version") != plan_version:
            raise ValueError
        return {
            "status": status,
            "no_store": True,
            "plan_id": plan_id,
            "plan_version": plan_version,
            "top_level_keys": sorted(body),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise StageGateError("projection_result_not_accepted") from exc


def validate_read_browser_result(
    body: Any,
    *,
    mode: str,
    plan_id: str,
    plan_version: int,
) -> dict:
    try:
        normalized_plan_id = str(UUID(plan_id))
        if mode == "dark":
            expected = {
                "mode": "dark",
                "signed_in": True,
                "navigation_link_count": 0,
                "route_status": 404,
            }
        elif mode == "visible":
            expected = {
                "mode": "visible",
                "signed_out_redirect": "/login",
                "navigation_link_count": 1,
                "list_plan_found": True,
                "detail_plan_id": normalized_plan_id,
                "detail_plan_version": plan_version,
                "refresh_preserved_detail": True,
                "deep_link_loaded": True,
                "missing_plan_alerts": 4,
                "independent_panel_failure": "ledger-only",
                "action_controls": 0,
                "unexpected_control_plan_mutations": 0,
                "mutation_route_denial_count": 5,
            }
        else:
            raise ValueError
        if not isinstance(body, dict) or body != expected or plan_version < 1:
            raise ValueError
        return expected
    except (TypeError, ValueError) as exc:
        raise StageGateError("read_browser_result_not_accepted") from exc


def validate_evidence_browser_result(
    body: Any,
    *,
    plan_id: str,
    plan_version: int,
    gate_id: str,
) -> dict:
    try:
        normalized_plan_id = str(UUID(plan_id))
        if plan_version < 1 or gate_id != "waste-way" or not isinstance(body, dict):
            raise ValueError
        projection_names = (
            "execution-state",
            "intent-timeline",
            "readback-observations",
        )
        expected = {
            "mode": "evidence-visible",
            "projection_statuses": {name: 200 for name in projection_names},
            "projection_no_store_count": 3,
            "evidence_panel_count": 3,
            "absent_projection_alerts": 3,
            "unavailable_projection": "readback-observations",
            "malformed_projection": "intent-timeline",
            "intent_timeline_state": "empty-not-execution",
            "held_state": True,
            "gate_link": (f"http://127.0.0.1:9998/read-only/gates/{gate_id}"),
            "gate_operations_navigation_requests": 0,
            "request_inventory_scope": "post-auth-plan-detail",
            "evidence_request_paths": [
                (
                    "/api/smart-water-backend/control-plans/"
                    f"{normalized_plan_id}/versions/{plan_version}/{name}"
                )
                for name in projection_names
            ],
            "forbidden_product_requests": [],
            "product_mutation_requests": 0,
        }
        if body != expected:
            raise ValueError
        return expected
    except (TypeError, ValueError) as exc:
        raise StageGateError("evidence_browser_result_not_accepted") from exc


def validate_go_read_browser_result(body: Any, *, gate_id: str) -> dict:
    try:
        expected = {
            "mode": "go-read",
            "signed_out_redirect": "/login",
            "signed_out_status_requests": 0,
            "login_status": 200,
            "gate_id": gate_id,
            "gate_name": "Waste Way",
            "connection": "offline",
            "read_status": 200,
            "read_no_store": True,
            "unknown_gate_status": 404,
            "unknown_gate_no_store": True,
            "outage_status": 503,
            "outage_no_store": True,
            "outage_alert_visible": True,
            "stale_status_hidden": True,
            "action_controls": 0,
            "same_origin_status_path": (f"/api/read-only/gates/{gate_id}/status"),
            "direct_scada_browser_requests": 0,
            "forbidden_product_requests": [],
            "product_mutation_requests": 0,
            "request_inventory_scope": "full-signed-out-through-outage",
            "screenshots": [
                "LOCAL-GO-READ-1-live.png",
                "LOCAL-GO-READ-1-outage.png",
            ],
        }
        if (
            gate_id != "waste-way"
            or not isinstance(body, dict)
            or isinstance(body.get("live_status_responses"), bool)
            or not isinstance(body.get("live_status_responses"), int)
            or body["live_status_responses"] < 3
            or {key: body.get(key) for key in expected} != expected
            or set(body) != {*expected, "live_status_responses"}
        ):
            raise ValueError
        return body
    except (KeyError, TypeError, ValueError) as exc:
        raise StageGateError("go_read_browser_result_not_accepted") from exc


def validate_go_read_status_results(
    known: HttpResult,
    unknown: HttpResult,
) -> dict[str, Any]:
    try:
        body = known.body
        points = [body[name] for name in ("gateLevel", "doorSw", "horn", "gateCf")]
        if (
            known.status != 200
            or "no-store" not in known.headers.get("cache-control", "").lower()
            or body["id"] != "waste-way"
            or body["name"] != "Waste Way"
            or body["connection"] != "offline"
            or body["endpoint"] != {"host": "127.0.0.1", "port": 65534, "unitId": 1}
            or body["markerColor"] != "red"
            or body["lastUpdated"] is not None
            or not isinstance(body["lastError"], str)
            or not body["lastError"]
            or any(
                not isinstance(point, dict)
                or point.get("raw") is not None
                or point.get("value") is not None
                or point.get("quality") != "offline"
                or point.get("lastUpdated") is not None
                or not isinstance(point.get("lastError"), str)
                or not point["lastError"]
                for point in points
            )
            or unknown.status != 404
            or "no-store" not in unknown.headers.get("cache-control", "").lower()
            or unknown.body != {"error": "unknown gate"}
        ):
            raise ValueError
        return {
            "known_gate_status": known.status,
            "known_gate_no_store": True,
            "gate_id": body["id"],
            "gate_name": body["name"],
            "connection": body["connection"],
            "endpoint": {
                "host": body["endpoint"]["host"],
                "port": body["endpoint"]["port"],
                "unit_id": body["endpoint"]["unitId"],
            },
            "null_observations": sum(point.get("value") is None for point in points),
            "unknown_gate_status": unknown.status,
            "unknown_gate_no_store": True,
            "http_methods": ["GET", "GET"],
            "product_mutations": 0,
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise StageGateError("go_read_status_result_not_accepted") from exc


def validate_evidence_projection_results(
    results: dict[str, HttpResult],
    *,
    absent_statuses: dict[str, int],
    plan_id: str,
    plan_version: int,
) -> dict:
    names = (
        "intent-timeline",
        "readback-observations",
        "execution-state",
    )
    try:
        normalized_plan_id = str(UUID(plan_id))
        if set(results) != set(names) or set(absent_statuses) != set(names):
            raise ValueError
        for name in names:
            result = results[name]
            if (
                result.status != 200
                or "no-store" not in result.headers.get("cache-control", "").lower()
                or result.body["plan_id"] != normalized_plan_id
                or result.body["plan_version"] != plan_version
                or absent_statuses[name] != 404
            ):
                raise ValueError
        intents = results["intent-timeline"].body["intents"]
        observations = results["readback-observations"].body["observations"]
        execution = results["execution-state"].body
        unavailable = [
            item
            for item in observations
            if isinstance(item, dict)
            and item.get("canonical_gate_id") == "waste-way"
            and item.get("verdict") == "unavailable"
            and "observed_level" in item
            and item.get("observed_level") is None
        ]
        hold_events = execution["hold_events"]
        if (
            not isinstance(intents, list)
            or len(intents) != 0
            or not isinstance(observations, list)
            or len(unavailable) < 1
            or execution["is_held"] is not True
            or not isinstance(hold_events, list)
            or not any(
                isinstance(event, dict) and event.get("event_type") == "held"
                for event in hold_events
            )
        ):
            raise ValueError
        return {
            "statuses": {name: results[name].status for name in names},
            "no_store_count": len(names),
            "intent_count": len(intents),
            "observation_count": len(observations),
            "unavailable_observation_count": len(unavailable),
            "is_held": True,
            "hold_event_count": len(hold_events),
            "absent_statuses": absent_statuses,
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise StageGateError("evidence_projection_result_not_accepted") from exc


def read_activation_flag_sequence() -> tuple[bool, ...]:
    return (False, True, False)


def evidence_activation_flag_sequence() -> tuple[tuple[bool, bool], ...]:
    return ((True, False), (True, True), (False, False))


def _normalized_text_sha256(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    except (OSError, UnicodeDecodeError) as exc:
        raise StageGateError("evidence_contract_parity_failed") from exc
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_evidence_contract_parity(
    backend_root: Path,
    frontend_root: Path,
) -> dict:
    try:
        manifest = json.loads(
            (backend_root / "manifest.json").read_text(encoding="utf-8")
        )
        if (
            manifest["contract_family"] != "control-plan-evidence"
            or manifest["contract_version"] != 1
            or not isinstance(manifest["schemas"], list)
            or not isinstance(manifest["fixtures"], list)
        ):
            raise ValueError
        roster = [
            "manifest.json",
            *[entry["relative_path"] for entry in manifest["schemas"]],
            *[entry["relative_path"] for entry in manifest["fixtures"]],
        ]
        if len(roster) != len(set(roster)):
            raise ValueError
        records = []
        for entry in manifest["schemas"]:
            path = backend_root / entry["relative_path"]
            actual_sha = _normalized_text_sha256(path)
            if actual_sha != entry["sha256"]:
                raise ValueError
            records.append(
                {
                    "relative_path": entry["relative_path"],
                    "sha256": actual_sha,
                }
            )
        for entry in manifest["fixtures"]:
            path = backend_root / entry["relative_path"]
            actual_sha = _normalized_text_sha256(path)
            if actual_sha != entry["sha256"]:
                raise ValueError
            records.append(
                {
                    "expected_valid": entry["expected_valid"],
                    "relative_path": entry["relative_path"],
                    "schema": entry["schema"],
                    "sha256": actual_sha,
                }
            )
        aggregate = hashlib.sha256(
            json.dumps(records, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        actual_roster = sorted(
            str(path.relative_to(backend_root)).replace(os.sep, "/")
            for path in backend_root.rglob("*")
            if path.is_file()
        )
        frontend_roster = sorted(
            str(path.relative_to(frontend_root)).replace(os.sep, "/")
            for path in frontend_root.rglob("*")
            if path.is_file()
        )
        if (
            sorted(roster) != actual_roster
            or frontend_roster != actual_roster
            or aggregate != manifest["contract_set_sha256"]
            or any(
                (backend_root / relative_path).read_bytes()
                != (frontend_root / relative_path).read_bytes()
                for relative_path in actual_roster
            )
        ):
            raise ValueError
        return {
            "contract_version": 1,
            "file_count": len(actual_roster),
            "contract_set_sha256": aggregate,
            "exact_bytes": True,
        }
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise StageGateError("evidence_contract_parity_failed") from exc


def verify_read_only_gate_source(repo_root: Path) -> dict:
    try:
        page_source = (
            repo_root
            / "services/scada-gate-control-web/src/app/read-only/gates/[id]/page.tsx"
        ).read_text(encoding="utf-8")
        client_source = (
            repo_root
            / "services/scada-gate-control-web/src/lib/read-only-gate-status.ts"
        ).read_text(encoding="utf-8")
        forbidden_imports = (
            "createApiClient",
            "ConfirmCommandModal",
            "LevelSensors",
            "SidePanel",
            "commandLevel",
            "commandHorn",
            "control-authority",
        )
        import_pattern = re.compile(
            r"""^\s*import(?:\s+type)?(?:[^"'\n]*\s+from\s+)?["']([^"']+)["']""",
            re.MULTILINE,
        )
        runtime_import_pattern = re.compile(
            r"""^\s*import(?!\s+type\b)(?:[^"'\n]*\s+from\s+)?["'][^"']+["']""",
            re.MULTILINE,
        )
        page_imports = set(import_pattern.findall(page_source))
        client_imports = set(import_pattern.findall(client_source))
        allowed_page_imports = {
            "react",
            "next/navigation",
            "@/components/AuthProvider",
            "@/components/GateDetailHeader",
            "@/components/RequireAuth",
            "@/hooks/usePolling",
            "@/lib/config",
            "@/lib/read-only-gate-status",
        }
        allowed_client_imports = {"./api"}
        mutation_pattern = re.compile(
            r"""method\s*:\s*["'](?:POST|PUT|PATCH|DELETE)["']""",
            re.IGNORECASE,
        )
        if (
            "@/components/RequireAuth" not in page_imports
            or "@/lib/read-only-gate-status" not in page_imports
            or not page_imports.issubset(allowed_page_imports)
            or not client_imports.issubset(allowed_client_imports)
            or runtime_import_pattern.search(client_source)
            or "import(" in page_source
            or "import(" in client_source
            or "require(" in page_source
            or "require(" in client_source
            or "/api/read-only/gates/" not in client_source
            or "/api/gates/" in client_source
            or "/status" not in client_source
            or any(name in page_source for name in forbidden_imports)
            or any(name in client_source for name in forbidden_imports)
            or mutation_pattern.search(page_source)
            or mutation_pattern.search(client_source)
        ):
            raise ValueError
        return {
            "route": "/read-only/gates/[id]",
            "command_capable_imports": 0,
            "mutation_methods": 0,
        }
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise StageGateError("read_only_gate_source_invalid") from exc


def build_evidence_seed_sql(plan_id: str, plan_version: int) -> str:
    try:
        normalized_plan_id = str(UUID(plan_id))
        if isinstance(plan_version, bool) or plan_version < 1:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise StageGateError("evidence_seed_identity_invalid") from exc
    return f"""
BEGIN;
INSERT INTO scheduler.control_command_execution_events (
    event_id, plan_id, plan_version, intent_id, event_type, worker_id,
    detail_document_text, occurred_at
) VALUES (
    gen_random_uuid(), '{normalized_plan_id}'::uuid, {plan_version},
    NULL, 'held', 'local-evidence-1', NULL, now()
);
INSERT INTO scheduler.control_gate_readback_observations (
    observation_id, plan_id, plan_version, canonical_gate_id, observed_level,
    expected_level, quality, verdict, reconciliation_mode, observed_at
) VALUES (
    gen_random_uuid(), '{normalized_plan_id}'::uuid, {plan_version},
    'waste-way', NULL, 2, 'offline', 'unavailable', 'observe', now()
);
COMMIT;
"""


def build_evidence_resume_sql(plan_id: str, plan_version: int) -> str:
    try:
        normalized_plan_id = str(UUID(plan_id))
        if isinstance(plan_version, bool) or plan_version < 1:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise StageGateError("evidence_seed_identity_invalid") from exc
    return f"""
INSERT INTO scheduler.control_command_execution_events (
    event_id, plan_id, plan_version, intent_id, event_type, worker_id,
    detail_document_text, occurred_at
) VALUES (
    gen_random_uuid(), '{normalized_plan_id}'::uuid, {plan_version},
    NULL, 'resumed', 'local-evidence-1', NULL, now()
);
"""


def restore_evidence_safety(
    context: StageContext,
    *,
    plan_id: str,
    plan_version: int,
    resume_required: bool,
    dark_build_required: bool,
) -> None:
    failures = []
    if resume_required:
        try:
            _psql(context, build_evidence_resume_sql(plan_id, plan_version))
        except StageGateError:
            failures.append("evidence_resume_failed")
    if dark_build_required:
        try:
            _build_frontend(
                context,
                control_plan_reads=False,
                control_plan_evidence_reads=False,
                run_tests=False,
                build_label="evidence-emergency-dark",
            )
        except StageGateError:
            failures.append("frontend_dark_rollback_failed")
    if failures:
        raise StageGateError(failures[0])


def rta_step_order() -> tuple[str, ...]:
    return (
        "capture_baseline",
        "verify_source_sha",
        "capacity_gate",
        "capacity_stop_rule",
        "install_manifests",
        "migration_parity",
        "monitoring_preflight",
        "start_four_processes",
        "verify_dark_flags",
        "five_minute_stability",
        "bearer_lifecycle",
        "pm2_save_and_evidence",
    )


def validate_evidence_payload(payload: object) -> None:
    forbidden_keys = (
        "password",
        "authorization",
        "token",
        "cookie",
        "secret",
        "dsn",
        "database_url",
        "postgres_url",
        "redis_url",
    )
    credential_url = re.compile(r"\b(?:postgres(?:ql)?|redis)://[^\s/@:]+:[^\s/@]+@")

    def inspect(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                normalized = str(key).lower()
                if any(forbidden in normalized for forbidden in forbidden_keys):
                    raise StageGateError("evidence_contains_secret")
                inspect(item)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                inspect(item)
            return
        if isinstance(value, str) and (
            value.lower().startswith("bearer ") or credential_url.search(value)
        ):
            raise StageGateError("evidence_contains_secret")

    inspect(payload)


def project_pm2_state(pm2_json: str) -> list[dict]:
    try:
        raw = json.loads(pm2_json)
        if not isinstance(raw, list):
            raise ValueError
        projection = []
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError
            env = item.get("pm2_env")
            monitor = item.get("monit", {})
            if not isinstance(env, dict) or not isinstance(monitor, dict):
                raise ValueError
            values = {
                "name": item.get("name"),
                "status": env.get("status"),
                "restarts": env.get("restart_time"),
                "pid": item.get("pid"),
                "memory_bytes": monitor.get("memory", 0),
                "cpu_percent": monitor.get("cpu", 0),
            }
            if (
                not isinstance(values["name"], str)
                or not isinstance(values["status"], str)
                or not isinstance(values["restarts"], int)
                or not isinstance(values["pid"], int)
                or not isinstance(values["memory_bytes"], int)
                or not isinstance(values["cpu_percent"], (int, float))
            ):
                raise ValueError
            projection.append(values)
        return sorted(projection, key=lambda item: item["name"])
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise StageGateError("pm2_state_invalid") from exc


def _pm2_runtime_identity(pm2_json: str) -> list[dict[str, Any]]:
    return [
        {
            "name": item["name"],
            "status": item["status"],
            "restarts": item["restarts"],
            "pid": item["pid"],
        }
        for item in project_pm2_state(pm2_json)
    ]


def collect_dark_runtime_contract(pm2_json: str, model_release: dict) -> dict:
    try:
        raw = json.loads(pm2_json)
        if not isinstance(raw, list) or not isinstance(model_release, dict):
            raise ValueError
        environments = {}
        for item in raw:
            name = item.get("name")
            pm2_env = item.get("pm2_env")
            if not isinstance(name, str) or not isinstance(pm2_env, dict):
                raise ValueError
            nested = pm2_env.get("env", {})
            if not isinstance(nested, dict):
                raise ValueError
            environments[name] = {**nested, **pm2_env}
        required_names = {
            "flow-monitoring",
            "scheduler",
            "ros-gis-integration",
            "bff-water-planning",
        }
        if not required_names.issubset(environments):
            raise ValueError
        flow = environments["flow-monitoring"]
        scheduler = environments["scheduler"]
        ros = environments["ros-gis-integration"]
        bff = environments["bff-water-planning"]
        contract = {
            "flow_gates_api": flow.get("GATES_API_ENABLED") == "true",
            "scheduler_execution": scheduler.get("CONTROL_EXECUTION_MODE"),
            "scheduler_readback": scheduler.get("CONTROL_READBACK_RECONCILIATION_MODE"),
            "scheduler_scada_configured": any(
                scheduler.get(name)
                for name in (
                    "SCHEDULER_SCADA_BASE_URL",
                    "SCHEDULER_SERVICE_JWT_SECRET",
                    "SCHEDULER_DEVICE_CAPABILITY_SNAPSHOT_PATH",
                )
            ),
            "ros_manual_producer": ros.get("DAILY_REQUIREMENT_ENABLED") == "true",
            "ros_startup_producer": ros.get("DAILY_REQUIREMENT_STARTUP_CATCHUP_ENABLED")
            == "true",
            "ros_recurring_producer": ros.get("DAILY_REQUIREMENT_SCHEDULE_ENABLED")
            == "true",
            "ros_source_configured": bool(ros.get("REQUIREMENT_SOURCE_POSTGRES_URL")),
            "planning_depth_writes": bff.get("PLANNING_DEPTH_WRITES_ENABLED") == "true",
            "machine_commands_configured": any(
                env.get("ALLOW_MACHINE_COMMANDS") not in (None, "false")
                for env in environments.values()
            ),
            "model_release_commandable": model_release.get("commandable"),
            "control_plan_reads_visible": False,
            "planning_depth_writes_visible": False,
        }
        expected = {
            "flow_gates_api": False,
            "scheduler_execution": "disabled",
            "scheduler_readback": "off",
            "scheduler_scada_configured": False,
            "ros_manual_producer": False,
            "ros_startup_producer": False,
            "ros_recurring_producer": False,
            "ros_source_configured": False,
            "planning_depth_writes": False,
            "machine_commands_configured": False,
            "model_release_commandable": False,
            "control_plan_reads_visible": False,
            "planning_depth_writes_visible": False,
        }
        if contract != expected:
            raise ValueError
        return contract
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise StageGateError("dark_runtime_contract_failed") from exc


def write_stage_manifest(path, payload: dict) -> None:
    target = Path(path)
    validate_evidence_payload(payload)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = target.with_suffix(f"{target.suffix}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        os.chmod(target, 0o600)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def clear_failure_manifest(evidence_root: Path, stage: str) -> None:
    if stage not in (*STAGE_ORDER, WRITE_UI_DIAGNOSTIC_STAGE):
        raise StageGateError("stage_not_supported")
    _clear_checksum_artifact(evidence_root, f"{stage}-failure.json")


def _clear_checksum_artifact(evidence_root: Path, filename: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", filename):
        raise StageGateError("evidence_artifact_name_invalid")
    (evidence_root / filename).unlink(missing_ok=True)
    index = evidence_root / "SHA256SUMS"
    entries = _read_checksum_index(index)
    if filename in entries:
        del entries[filename]
        _write_checksum_index(index, entries)


def parse_listening_sockets(ss_output: str) -> list[dict]:
    listeners = []
    for line in ss_output.splitlines():
        fields = line.split()
        if len(fields) < 5 or fields[0] != "LISTEN":
            continue
        endpoint = fields[3]
        if endpoint.startswith("["):
            match = re.fullmatch(r"\[([^]]+)]:(\d+)", endpoint)
        else:
            match = re.fullmatch(r"(.+):(\d+)", endpoint)
        if match is None:
            continue
        listeners.append({"address": match.group(1), "port": int(match.group(2))})
    return listeners


def application_port_conflicts(listeners: list[dict]) -> list[int]:
    application_ports = {3011, 3021, 3022, 3047}
    return sorted(
        {
            listener["port"]
            for listener in listeners
            if listener.get("port") in application_ports
        }
    )


def unexpected_non_loopback_listeners(listeners: list[dict]) -> list[int]:
    loopback_addresses = {"127.0.0.1", "::1"}
    return sorted(
        {
            listener["port"]
            for listener in listeners
            if listener.get("address") not in loopback_addresses
            and isinstance(listener.get("port"), int)
        }
    )


def go_read_listener_projection(listeners: list[dict]) -> dict[str, list[str]]:
    try:
        projected = {
            str(port): sorted(
                {
                    item["address"]
                    for item in listeners
                    if item.get("port") == port and isinstance(item.get("address"), str)
                }
            )
            for port in (3030, 9998)
        }
        if projected != {
            "3030": ["127.0.0.1"],
            "9998": ["127.0.0.1"],
        }:
            raise ValueError
        return projected
    except (KeyError, TypeError, ValueError) as exc:
        raise StageGateError("go_read_listener_binding_invalid") from exc


def validate_migration_parity(
    scheduler_ids: list[str], ros_ids: list[str], bff_ids: list[str]
) -> dict:
    expected_ros = [
        "0001_dataset_version_parent",
        "0002_water_requirement_publication",
        "0003_daily_requirement_producer",
        "0004_dataset_version_identity_immutable",
    ]
    expected_bff = [
        "009_crop_registry",
        "010_planning_depth_submissions",
        "011_planning_depth_rid_calendar_v2",
        "012_planning_depth_roster_provenance",
    ]
    if (
        len(scheduler_ids) != 13
        or scheduler_ids[-1:] != ["0013_operator_approved_execution"]
        or ros_ids != expected_ros
        or bff_ids != expected_bff
    ):
        raise StageGateError("migration_parity_failed")
    return {
        "scheduler_latest": scheduler_ids[-1],
        "scheduler_count": len(scheduler_ids),
        "ros_latest": ros_ids[-1],
        "ros_count": len(ros_ids),
        "bff_latest": bff_ids[-1],
        "bff_count": len(bff_ids),
    }


ROS_DATASET_VERSION_TRIGGER_QUERY = (
    "SELECT t.tgname, t.tgenabled, t.tgtype::integer, t.tgattr::text, "
    "(t.tgqual IS NULL)::text, t.tgfoid::regprocedure::text "
    "FROM pg_trigger AS t "
    "WHERE t.tgrelid = 'ros_gis.dataset_versions'::regclass "
    "AND NOT t.tgisinternal ORDER BY t.tgname"
)
ROS_DATASET_VERSION_TRIGGER_ROWS = (
    # pg_trigger.tgtype: 27 = ROW|BEFORE|DELETE|UPDATE; 34 = BEFORE|TRUNCATE.
    "dataset_versions_identity_is_immutable\tO\t27\t\ttrue\t"
    "ros_gis.reject_dataset_version_identity_change()",
    "dataset_versions_no_truncate\tO\t34\t\ttrue\t"
    "ros_gis.reject_dataset_version_identity_change()",
)


def validate_ros_dataset_version_triggers(trigger_rows: list[str]) -> dict:
    if tuple(trigger_rows) != ROS_DATASET_VERSION_TRIGGER_ROWS:
        raise StageGateError("ros_dataset_version_trigger_parity_failed")
    projected = []
    for row in trigger_rows:
        name, enabled, type_mask, column_filter, unconditional, function = row.split(
            "\t"
        )
        projected.append(
            {
                "name": name,
                "enabled": enabled,
                "type_mask": int(type_mask),
                "column_filter": column_filter or None,
                "unconditional": unconditional == "true",
                "function": function,
            }
        )
    return {"dataset_version_triggers": projected}


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _utc_timestamp_seconds() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _canonical_json_sha256(value: Any) -> str:
    validate_evidence_payload(value)
    try:
        text = json.dumps(value, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise StageGateError("canonical_json_unserializable") from exc
    return hashlib.sha256((text + "\n").encode("utf-8")).hexdigest()


def safe_subprocess_failure_code(stderr: str, prefix: str) -> str | None:
    matches = []
    for line in stderr.splitlines():
        if not line.startswith(prefix):
            continue
        code = line.removeprefix(prefix)
        if re.fullmatch(r"[a-z][a-z0-9_]{0,127}", code):
            matches.append(code)
    return matches[0] if len(matches) == 1 else None


def _run_checked(
    code: str,
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 600,
    safe_error_prefix: str | None = None,
) -> str:
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StageGateError(f"{code}_failed") from exc
    if result.returncode != 0:
        if safe_error_prefix is not None:
            safe_code = safe_subprocess_failure_code(
                result.stderr,
                safe_error_prefix,
            )
            if safe_code is not None:
                raise StageGateError(safe_code)
        raise StageGateError(f"{code}_failed")
    print(f"PASS {code}")
    return result.stdout


def _load_env_file(path: Path) -> dict[str, str]:
    try:
        result = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            key, separator, value = line.partition("=")
            if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
                raise ValueError
            result[key] = value
        return result
    except (OSError, ValueError) as exc:
        raise StageGateError("runtime_env_invalid") from exc


def frontend_process_environment(
    runtime_env_dir: Path,
    *,
    control_plan_reads: bool,
    control_plan_evidence_reads: bool = False,
    gate_operations_base_url: str | None = None,
    water_planning_v2: bool = False,
    water_planning_submit: bool = False,
) -> dict[str, str]:
    auth = _load_env_file(runtime_env_dir / "auth.env")
    try:
        jwt = {
            name: auth[name] for name in ("JWT_SECRET", "JWT_ISSUER", "JWT_AUDIENCE")
        }
        if any(not value for value in jwt.values()):
            raise ValueError
    except (KeyError, ValueError) as exc:
        raise StageGateError("frontend_auth_environment_invalid") from exc
    validate_runtime_urls(
        {
            "auth": "http://127.0.0.1:3005",
            "bff": "http://127.0.0.1:3022",
        }
    )
    if water_planning_submit and not water_planning_v2:
        raise StageGateError("frontend_activation_gates_invalid")
    if control_plan_evidence_reads:
        try:
            gate_url = urlsplit(gate_operations_base_url or "")
            if (
                not control_plan_reads
                or gate_url.scheme != "http"
                or gate_url.hostname != "127.0.0.1"
                or gate_url.port != 9998
                or gate_url.path != "/read-only/gates"
                or gate_url.username is not None
                or gate_url.password is not None
                or gate_url.query
                or gate_url.fragment
            ):
                raise ValueError
        except ValueError as exc:
            raise StageGateError("gate_operations_url_invalid") from exc
    environment = {
        **os.environ,
        **jwt,
        "PATH": f"{NODE_ROOT / 'bin'}:/usr/bin:/bin",
        "NODE_ENV": "production",
        "NEXT_PUBLIC_CONTROL_PLAN_READS": ("true" if control_plan_reads else "false"),
        "NEXT_PUBLIC_CONTROL_PLAN_EVIDENCE_READS": (
            "true" if control_plan_evidence_reads else "false"
        ),
        "NEXT_PUBLIC_WATER_PLANNING_V2": ("true" if water_planning_v2 else "false"),
        "NEXT_PUBLIC_WATER_PLANNING_SUBMIT_ENABLED": (
            "true" if water_planning_submit else "false"
        ),
        "CENTRAL_AUTH_URL": "http://127.0.0.1:3005",
        "WATER_PLANNING_BFF_URL": "http://127.0.0.1:3022",
    }
    if gate_operations_base_url is not None:
        environment["NEXT_PUBLIC_GATE_OPERATIONS_URL"] = gate_operations_base_url
    # The frontend's planning-depth proxy routes read API_SERVER +
    # PLANNING_DEPTH_{SUBMIT,ACTIVE,ROSTER}_PATH (smart-cms-app
    # app/api/smart-water-backend/water-planning/*/route.ts) and fetch
    # `${API_SERVER}${PATH}`. Provide the exact real BFF v2/v1 paths when armed;
    # when dark, strip any inherited value so a polluted parent env can never
    # pre-configure the write path behind the SUBMIT flag.
    if water_planning_submit:
        environment.update(FRONTEND_WRITE_PATH_ENVIRONMENT)
    else:
        for name in FRONTEND_WRITE_PATH_ENVIRONMENT:
            environment.pop(name, None)
    return environment


def project_frontend_activation_gates(environment: dict[str, str]) -> dict[str, bool]:
    names = {
        "control_plan_reads": "NEXT_PUBLIC_CONTROL_PLAN_READS",
        "control_plan_evidence_reads": "NEXT_PUBLIC_CONTROL_PLAN_EVIDENCE_READS",
        "water_planning_v2": "NEXT_PUBLIC_WATER_PLANNING_V2",
        "water_planning_submit": "NEXT_PUBLIC_WATER_PLANNING_SUBMIT_ENABLED",
    }
    try:
        values = {name: environment[key] for name, key in names.items()}
        if any(value not in {"true", "false"} for value in values.values()):
            raise ValueError
        return {name: value == "true" for name, value in values.items()}
    except (KeyError, ValueError) as exc:
        raise StageGateError("frontend_activation_gates_invalid") from exc


def validate_go_read_runtime_environment(
    scada: dict[str, str],
    gate_web: dict[str, str],
) -> dict[str, Any]:
    try:
        validate_runtime_urls(
            {
                "auth": gate_web["AUTH_SERVICE_URL"],
                "scada": gate_web["SCADA_GATE_CONTROL_URL"],
            }
        )
        expected_scada = {
            "NODE_ENV": "production",
            "HTTP_HOST": "127.0.0.1",
            "PORT": "3030",
            "MODBUS_HOST": "127.0.0.1",
            "MODBUS_PORT": "65534",
            "ALLOW_IN_MEMORY_AUDIT": "false",
            "ALLOW_MACHINE_COMMANDS": "false",
        }
        if (
            any(scada.get(name) != value for name, value in expected_scada.items())
            or not scada.get("DATABASE_URL")
            or not scada.get("JWT_SECRET")
            or any(name in scada for name in GO_READ_FORBIDDEN_SCADA_ENV)
            or gate_web.get("NODE_ENV") != "production"
            or gate_web["AUTH_SERVICE_URL"] != "http://127.0.0.1:3005"
            or gate_web["SCADA_GATE_CONTROL_URL"] != "http://127.0.0.1:3030"
            or gate_web.get("NEXT_PUBLIC_DEV_TOKEN") not in (None, "")
            or gate_web.get("NEXT_PUBLIC_API_BASE_URL") not in (None, "")
        ):
            raise ValueError
        return {
            "scada_bind": "127.0.0.1:3030",
            "modbus_target": "127.0.0.1:65534",
            "machine_commands": False,
            "durable_audit": True,
            "service_auth": "dark",
            "gate_web_bind": "127.0.0.1:9998",
            "auth_origin": gate_web["AUTH_SERVICE_URL"],
            "scada_origin": gate_web["SCADA_GATE_CONTROL_URL"],
            "dev_bypass": False,
            "legacy_direct_scada": False,
        }
    except (KeyError, TypeError, ValueError, StageGateError) as exc:
        raise StageGateError("go_read_runtime_environment_invalid") from exc


def _service_environment(context: StageContext, service: str) -> dict[str, str]:
    return {
        **os.environ,
        **_load_env_file(context.runtime_env_dir / f"{service}.env"),
    }


def _postgres_process_env(postgres_url: str) -> dict[str, str]:
    parsed = urlsplit(postgres_url)
    if (
        parsed.scheme not in {"postgres", "postgresql"}
        or parsed.hostname != "127.0.0.1"
        or not parsed.username
        or parsed.password is None
        or not parsed.path.lstrip("/")
    ):
        raise StageGateError("postgres_url_invalid")
    from urllib.parse import unquote

    return {
        **os.environ,
        "PGHOST": parsed.hostname,
        "PGPORT": str(parsed.port or 5432),
        "PGUSER": unquote(parsed.username),
        "PGPASSWORD": unquote(parsed.password),
        "PGDATABASE": unquote(parsed.path.lstrip("/")),
        "PGOPTIONS": "-c statement_timeout=10000",
    }


def _psql(context: StageContext, query: str) -> str:
    postgres_url = _load_env_file(context.runtime_env_dir / "bff.env")["POSTGRES_URL"]
    return _run_checked(
        "postgres_probe",
        ["psql", "--no-psqlrc", "-X", "-At", "-F", "\t", "-c", query],
        env=_postgres_process_env(postgres_url),
        timeout=30,
    )


def _pm2_command(*arguments: str) -> list[str]:
    return [str(NODE_ROOT / "bin/node"), str(PM2_CLI), *arguments]


def _pm2_runtime_environment(context: StageContext) -> dict[str, str]:
    return {
        **os.environ,
        "MUNBON_RUNTIME_ENV_DIR": str(context.runtime_env_dir),
        "PATH": os.pathsep.join(
            (str(PM2_CLI.parent), str(NODE_ROOT / "bin"), "/usr/bin", "/bin")
        ),
    }


def _pm2_json() -> str:
    return _run_checked("pm2_snapshot", _pm2_command("jlist"), timeout=30)


def _capacity_snapshot() -> dict[str, int]:
    values = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            name, separator, remainder = line.partition(":")
            if separator and name in {"MemAvailable", "SwapTotal", "SwapFree"}:
                amount, unit = remainder.split()
                if unit != "kB":
                    raise ValueError
                values[name] = int(amount) // 1024
        if set(values) != {"MemAvailable", "SwapTotal", "SwapFree"}:
            raise ValueError
    except (OSError, ValueError) as exc:
        raise StageGateError("capacity_probe_failed") from exc
    return {
        "mem_available_mib": values["MemAvailable"],
        "swap_used_mib": values["SwapTotal"] - values["SwapFree"],
    }


def _listener_snapshot() -> list[dict]:
    output = _run_checked("listener_probe", ["ss", "-H", "-ltn"], timeout=30)
    return parse_listening_sockets(output)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        if path.stat().st_size > 1024 * 1024:
            raise ValueError
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise StageGateError("json_artifact_invalid") from exc


def _hash_file(path: Path) -> str:
    try:
        if path.stat().st_size > 16 * 1024 * 1024:
            raise ValueError
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except (OSError, ValueError) as exc:
        raise StageGateError("stage_identity_unavailable") from exc


def _stage_identity(context: StageContext) -> dict[str, Any]:
    identity = {
        "release_sha": context.release_sha,
        "frontend_sha": context.frontend_sha,
        "harness_hashes": {
            name: _hash_file(context.harness_root / name) for name in HARNESS_ARTIFACTS
        },
    }
    if context.execution_kind == "rehearsal":
        owner = _read_json(context.owner_path)
        _validate_execution_owner(context, owner)
        identity.update(
            {
                "execution_kind": "rehearsal",
                "machine": REHEARSAL_MACHINE_NAME,
                "acceptance_evidence": False,
                "dependency_sha256": owner["dependency_sha256"],
                "as_of_date": context.as_of_date.isoformat(),
            }
        )
    return identity


def _execution_stages(context: StageContext) -> tuple[str, ...]:
    if context.execution_kind == "canonical":
        return STAGE_ORDER
    if context.execution_kind == "rehearsal":
        return STAGE_ORDER[:3]
    raise StageGateError("execution_kind_not_accepted")


def _validate_execution_owner(context: StageContext, owner: dict[str, Any]) -> None:
    common_is_valid = (
        owner.get("architecture") == "arm64"
        and owner.get("state") == "ready"
        and owner.get("release_sha") == context.release_sha
        and owner.get("frontend_sha") == context.frontend_sha
        and re.fullmatch(r"[0-9a-f]{64}", owner.get("dependency_sha256", ""))
    )
    if context.execution_kind == "canonical":
        valid = common_is_valid and owner.get("machine") == ACCEPTANCE_MACHINE_NAME
    elif context.execution_kind == "rehearsal":
        valid = (
            common_is_valid
            and owner.get("machine") == REHEARSAL_MACHINE_NAME
            and owner.get("execution_kind") == "rehearsal"
            and owner.get("acceptance_evidence") is False
        )
    else:
        raise StageGateError("execution_kind_not_accepted")
    if not valid:
        raise StageGateError("local_baseline_invalid")


def _verify_source_checkouts(context: StageContext) -> None:
    for label, root, expected_sha in (
        ("backend", context.repo_root, context.release_sha),
        ("frontend", context.frontend_root, context.frontend_sha),
    ):
        actual_sha = _run_checked(
            f"{label}_source_identity",
            ["git", "rev-parse", "HEAD"],
            cwd=root,
        ).strip()
        tracked_status = _run_checked(
            f"{label}_tracked_identity",
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=root,
        ).strip()
        if actual_sha != expected_sha or tracked_status:
            raise StageGateError(f"{label}_source_identity_stale")


def _load_state(context: StageContext) -> dict[str, Any]:
    path = context.evidence_root / "stage-state.json"
    if not path.exists():
        _verify_source_checkouts(context)
        if (context.evidence_root / "SHA256SUMS").exists():
            raise StageGateError("stage_state_missing")
        return {**_stage_identity(context), "completed": []}
    _verify_checksum_entry(path)
    state = _read_json(path)
    completed = state.get("completed")
    if completed:
        _verify_source_checkouts(context)
    expected_identity = _stage_identity(context)
    if (
        not isinstance(completed, list)
        or tuple(completed) != _execution_stages(context)[: len(completed)]
        or set(state) != {*expected_identity, "completed"}
        or {key: state.get(key) for key in expected_identity} != expected_identity
    ):
        raise StageGateError("stage_state_stale")
    _verify_source_checkouts(context)
    for stage in completed:
        _verify_checksum_entry(context.evidence_root / f"{stage}.json")
    return state


def _discard_rc_stage_artifact(context: StageContext, stage: str) -> None:
    target = context.evidence_root / f"{stage}.json"
    index = context.evidence_root / "SHA256SUMS"
    try:
        target.unlink(missing_ok=True)
        if target.exists():
            raise OSError("RC PASS artifact remained after cleanup")
        if index.exists():
            entries = _read_checksum_index(index)
            if target.name in entries:
                entries.pop(target.name)
                _write_checksum_index(index, entries)
            if target.name in _read_checksum_index(index):
                raise OSError("RC PASS checksum remained after cleanup")
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as exc:
        raise StageGateError("rc_stage_publication_rollback_failed") from exc


def _restore_rc_stage_publication(
    context: StageContext,
    stage: str,
    *,
    prior_state_exists: bool,
    prior_state: bytes | None,
    prior_index_exists: bool,
    prior_index_entries: dict[str, str],
) -> None:
    target = context.evidence_root / f"{stage}.json"
    state_path = context.evidence_root / "stage-state.json"
    index_path = context.evidence_root / "SHA256SUMS"
    expected_entries = dict(prior_index_entries)
    expected_entries.pop(target.name, None)
    try:
        target.unlink(missing_ok=True)
        if target.exists():
            raise OSError("RC PASS artifact remained after rollback")
        if prior_state_exists:
            if prior_state is None:
                raise OSError("prior stage state bytes were unavailable")
            state_path.write_bytes(prior_state)
            if state_path.read_bytes() != prior_state:
                raise OSError("prior stage state was not restored")
        else:
            state_path.unlink(missing_ok=True)
            if state_path.exists():
                raise OSError("stage state remained after rollback")
        if prior_index_exists:
            _write_checksum_index(index_path, expected_entries)
            if _read_checksum_index(index_path) != expected_entries:
                raise OSError("checksum index was not restored")
        else:
            index_path.unlink(missing_ok=True)
            if index_path.exists():
                raise OSError("checksum index remained after rollback")
        if target.name in _read_checksum_index(index_path):
            raise OSError("RC PASS checksum remained after rollback")
        if prior_state_exists:
            restored_entries = _read_checksum_index(index_path)
            if restored_entries.get(state_path.name) != _hash_file(state_path):
                raise OSError("restored stage state checksum did not match")
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as exc:
        raise StageGateError("rc_stage_publication_rollback_failed") from exc


def _save_state(context: StageContext, completed: list[str]) -> None:
    if context.rc_attempt is not None and completed:
        stage = completed[-1]
        if stage in STAGE_ORDER:
            state_path = context.evidence_root / "stage-state.json"
            index_path = context.evidence_root / "SHA256SUMS"
            try:
                prior_state_exists = state_path.exists()
                prior_state = state_path.read_bytes() if prior_state_exists else None
                prior_index_exists = index_path.exists()
                prior_index_entries = (
                    _read_checksum_index(index_path) if prior_index_exists else {}
                )
            except (KeyboardInterrupt, SystemExit) as primary:
                try:
                    _discard_rc_stage_artifact(context, stage)
                except (KeyboardInterrupt, SystemExit) as cleanup:
                    if cleanup is primary:
                        raise
                    raise primary from cleanup
                except BaseException as cleanup_exc:
                    raise primary from cleanup_exc
                raise
            except BaseException as primary:
                try:
                    _discard_rc_stage_artifact(context, stage)
                except (KeyboardInterrupt, SystemExit) as cleanup:
                    raise cleanup from primary
                except BaseException as cleanup_exc:
                    raise StageGateError(
                        "rc_stage_publication_rollback_failed"
                    ) from cleanup_exc
                raise StageGateError(
                    "rc_stage_publication_rollback_failed"
                ) from primary
            try:
                _bind_rc_stage_attempt(context, stage, context.rc_attempt)
            except BaseException as exc:
                try:
                    _discard_rc_stage_artifact(context, stage)
                except (KeyboardInterrupt, SystemExit):
                    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                        raise exc
                    raise
                except BaseException:
                    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                        raise exc
                    raise
                raise
            try:
                write_stage_manifest(
                    state_path, {**_stage_identity(context), "completed": completed}
                )
                _checksum_manifest(state_path)
            except (KeyboardInterrupt, SystemExit) as primary:
                try:
                    _restore_rc_stage_publication(
                        context,
                        stage,
                        prior_state_exists=prior_state_exists,
                        prior_state=prior_state,
                        prior_index_exists=prior_index_exists,
                        prior_index_entries=prior_index_entries,
                    )
                except (KeyboardInterrupt, SystemExit) as cleanup:
                    if cleanup is primary:
                        raise
                    raise primary from cleanup
                except BaseException as cleanup_exc:
                    raise primary from cleanup_exc
                raise
            except Exception as primary:
                try:
                    _restore_rc_stage_publication(
                        context,
                        stage,
                        prior_state_exists=prior_state_exists,
                        prior_state=prior_state,
                        prior_index_exists=prior_index_exists,
                        prior_index_entries=prior_index_entries,
                    )
                except (KeyboardInterrupt, SystemExit) as cleanup:
                    raise cleanup from primary
                except StageGateError:
                    raise
                raise
            return
    path = context.evidence_root / "stage-state.json"
    write_stage_manifest(path, {**_stage_identity(context), "completed": completed})
    _checksum_manifest(path)


def _verify_rc_post_stage_state(
    context: StageContext, stage: str, attempt: dict[str, Any]
) -> None:
    state_path = context.evidence_root / "stage-state.json"
    pass_path = context.evidence_root / f"{stage}.json"
    try:
        expected_state = {
            **_stage_identity(context),
            "completed": list(STAGE_ORDER[: STAGE_ORDER.index(stage) + 1]),
        }
        _verify_checksum_entry(state_path)
        raw_state = state_path.read_bytes()
        state = json.loads(raw_state.decode("utf-8"))
        canonical_state = (json.dumps(state, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        if raw_state != canonical_state or state != expected_state:
            raise ValueError
        _verify_checksum_entry(pass_path)
        manifest = _read_json(pass_path)
        if (
            manifest.get("stage") != stage
            or manifest.get("verdict") != "PASS"
            or manifest.get("release_sha", manifest.get("backend_sha"))
            != context.release_sha
            or manifest.get("frontend_sha") != context.frontend_sha
            or manifest.get("rc_attempt") != attempt
        ):
            raise ValueError
    except (KeyboardInterrupt, SystemExit) as primary:
        try:
            _discard_rc_stage_artifact(context, stage)
        except (KeyboardInterrupt, SystemExit) as cleanup:
            if cleanup is primary:
                raise
            raise primary from cleanup
        except BaseException as cleanup_exc:
            raise primary from cleanup_exc
        raise
    except BaseException as exc:
        try:
            _discard_rc_stage_artifact(context, stage)
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as cleanup_exc:
            raise StageGateError(
                "rc_stage_publication_rollback_failed"
            ) from cleanup_exc
        raise StageGateError("rc_stage_publication_rollback_failed") from exc


def _accepted_frontend_sha(frontend_sha: str) -> str:
    """Accept any validated 40-hex frontend SHA (no pin to one historical value).

    The frontend identity is bound elsewhere: orchestrate validates it equals
    frontend origin/main, and `_verify_frontend_source` rejects any guest checkout
    whose HEAD differs. LOCAL-BASE-0 therefore needs only a format gate, not a
    brittle constant that forces a code change on every frontend commit.
    """
    if not re.fullmatch(r"[0-9a-f]{40}", frontend_sha):
        raise StageGateError("frontend_sha_not_accepted")
    return frontend_sha


def run_local_base(context: StageContext) -> dict:
    state = _load_state(context)
    validate_stage_transition(tuple(state["completed"]), "LOCAL-BASE-0")
    _accepted_frontend_sha(context.frontend_sha)
    actual_sha = _run_checked(
        "backend_sha", ["git", "rev-parse", "HEAD"], cwd=context.repo_root
    ).strip()
    tracked_status = _run_checked(
        "tracked_tree",
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=context.repo_root,
    ).strip()
    owner = _read_json(Path("/var/lib/munbon-local-acceptance/owner.json"))
    if (
        actual_sha != context.release_sha
        or tracked_status
        or os.uname().machine != "aarch64"
    ):
        raise StageGateError("local_baseline_invalid")
    _validate_execution_owner(context, owner)
    manifest = {
        "stage": "LOCAL-BASE-0",
        "verdict": "PASS",
        "captured_at": _utc_timestamp(),
        "backend_sha": actual_sha,
        "frontend_sha": context.frontend_sha,
        "dependency_bundle_sha256": owner["dependency_sha256"],
        "frontend_status": {
            "FE-0": "complete",
            "FE-1": "complete",
            "FE-2": "complete",
            "FE-3": "complete",
            "FE-4": "complete",
            "FE-8": "complete",
        },
        "pending_starts": ["LOCAL-RTA-1"],
        "activation_flags": {
            "scheduler_execution": False,
            "machine_commands": False,
            "ros_manual_production": False,
            "ros_startup_production": False,
            "ros_recurring_production": False,
            "control_plan_reads": False,
            "control_plan_evidence_reads": False,
            "planning_depth_writes": False,
            "planning_depth_writes_visible": False,
        },
    }
    clear_failure_manifest(context.evidence_root, "LOCAL-BASE-0")
    target = context.evidence_root / "LOCAL-BASE-0.json"
    write_stage_manifest(target, manifest)
    _checksum_manifest(target)
    _save_state(context, ["LOCAL-BASE-0"])
    print("PASS LOCAL-BASE-0")
    return manifest


def _install_manifests(context: StageContext) -> dict:
    results = {}
    for service in PROCESS_NAMES:
        root = context.repo_root / "services" / service
        python = root / ".venv" / "bin" / "python"
        pip = root / ".venv" / "bin" / "pip"
        _run_checked(
            f"{service}_venv",
            ["python3", "-m", "venv", str(root / ".venv")],
            timeout=120,
        )
        _run_checked(
            f"{service}_manifest",
            [
                str(pip),
                "install",
                "--disable-pip-version-check",
                "--quiet",
                "--no-index",
                "--find-links",
                str(DEPENDENCY_ROOT / "python" / service),
                "--requirement",
                str(root / "requirements.txt"),
            ],
            timeout=1200,
        )
        _run_checked(f"{service}_pip_check", [str(python), "-m", "pip", "check"])
        results[service] = "manifest-installed-pip-check-pass"
    return results


def _apply_migrations(context: StageContext) -> dict:
    for service in ("flow-monitoring", "scheduler"):
        root = context.repo_root / "services" / service
        env = _service_environment(
            context, "flow" if service == "flow-monitoring" else service
        )
        _run_checked(
            f"{service}_migrations",
            [str(root / ".venv/bin/python"), "migrations/migrate.py", "apply-all"],
            cwd=root,
            env=env,
            timeout=180,
        )
    ros_root = context.repo_root / "services/ros-gis-integration"
    ros_env = _service_environment(context, "ros")
    for migration_id in (
        "0001_dataset_version_parent",
        "0002_water_requirement_publication",
        "0003_daily_requirement_producer",
        "0004_dataset_version_identity_immutable",
    ):
        _run_checked(
            f"ros_{migration_id}",
            [
                str(ros_root / ".venv/bin/python"),
                "migrations/migrate.py",
                "apply",
                migration_id,
            ],
            cwd=ros_root,
            env=ros_env,
            timeout=180,
        )
    bff_root = context.repo_root / "services/bff-water-planning"
    _run_checked(
        "bff_migrations",
        [
            str(bff_root / ".venv/bin/python"),
            str(
                context.repo_root
                / "ops/control-plan-read-runtime/apply_bff_migration.py"
            ),
        ],
        cwd=context.repo_root,
        env=_service_environment(context, "bff"),
        timeout=180,
    )
    scheduler_rows = _psql(
        context,
        "SELECT migration_id, checksum FROM scheduler.schema_migrations ORDER BY migration_id",
    ).splitlines()
    ros_rows = _psql(
        context,
        "SELECT migration_id, checksum FROM ros_gis.schema_migrations ORDER BY migration_id",
    ).splitlines()
    bff_rows = _psql(
        context,
        "SELECT migration_id, checksum "
        "FROM water_planning.schema_migrations ORDER BY migration_id",
    ).splitlines()
    bff_tables_present = (
        _psql(
            context,
            "SELECT to_regclass('gis.crop_registry') IS NOT NULL "
            "AND to_regclass("
            "'water_planning.planning_depth_submissions') IS NOT NULL "
            "AND to_regclass('water_planning.planning_depth_values') IS NOT NULL",
        ).strip()
        == "t"
    )
    ros_dataset_version_triggers = _psql(
        context,
        ROS_DATASET_VERSION_TRIGGER_QUERY,
    ).splitlines()
    scheduler_ids = [row.split("\t", 1)[0] for row in scheduler_rows]
    ros_ids = [row.split("\t", 1)[0] for row in ros_rows]
    bff_ids = [row.split("\t", 1)[0] for row in bff_rows]
    if not bff_tables_present:
        raise StageGateError("migration_parity_failed")
    parity = validate_migration_parity(scheduler_ids, ros_ids, bff_ids)
    parity.update(validate_ros_dataset_version_triggers(ros_dataset_version_triggers))
    parity["scheduler_migrations"] = scheduler_ids
    parity["ros_migrations"] = ros_ids
    parity["bff_migrations"] = bff_ids
    parity["bff_migration_sha256"] = {
        path.stem: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((bff_root / "migrations").glob("*.sql"))
    }
    return parity


def _monitoring_preflight(context: StageContext) -> dict:
    _run_checked(
        "prometheus_rules",
        ["promtool", "check", "rules", "/etc/prometheus/control-plane-alerts.yml"],
    )
    _run_checked(
        "prometheus_config",
        ["promtool", "check", "config", "/etc/prometheus/control-plane-prometheus.yml"],
    )
    infra = context.repo_root / "infra/pm2"
    node_environment = {
        **os.environ,
        "PATH": f"{NODE_ROOT / 'bin'}:{os.environ.get('PATH', '')}",
    }
    _run_checked(
        "infra_verify",
        [str(NODE_ROOT / "bin/npm"), "run", "verify"],
        cwd=infra,
        env=node_environment,
        timeout=900,
    )
    _run_checked(
        "infra_build",
        [str(NODE_ROOT / "bin/npm"), "run", "build"],
        cwd=infra,
        env=node_environment,
        timeout=300,
    )
    scheduler_env = _service_environment(context, "scheduler")
    bff_env = _service_environment(context, "bff")
    flow_env = _service_environment(context, "flow")
    secrets = _load_env_file(context.runtime_env_dir / "local-secrets.env")
    preflight_env = {
        **os.environ,
        **scheduler_env,
        "GIS_DATABASE_URL": bff_env["POSTGRES_URL"],
        "TIMESCALE_URL": flow_env["TIMESCALE_URL"],
        "POSTGRES_PASSWORD": secrets["DB_PASSWORD"],
        "TIMESCALE_PASSWORD": secrets["DB_PASSWORD"],
    }
    output = _run_checked(
        "repository_preflight",
        [
            str(NODE_ROOT / "bin/node"),
            "dist/deploy-preflight-cli.js",
            "--role",
            "central",
            "--expected-commit",
            context.release_sha,
        ],
        cwd=infra,
        env={**preflight_env, "PATH": node_environment["PATH"]},
        timeout=120,
    )
    try:
        report = json.loads(output)
        return {
            "approved": report["approved"],
            "commit": report["commit"],
            "latest_migration": report["latestMigration"],
            "process_names": report["processNames"],
            "command_gates": report["commandGates"],
            "promtool": "PASS",
        }
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise StageGateError("repository_preflight_output_invalid") from exc


def _actual_gate_environment(pm2_json: str) -> str:
    try:
        raw = json.loads(pm2_json)
        projected = []
        for item in raw:
            if item.get("name") not in PROCESS_NAMES or not isinstance(
                item.get("pid"), int
            ):
                continue
            environ = Path(f"/proc/{item['pid']}/environ").read_bytes().split(b"\0")
            selected = {}
            for entry in environ:
                key, separator, value = entry.partition(b"=")
                decoded_key = key.decode("utf-8", errors="strict")
                if separator and decoded_key in GATE_ENV_NAMES:
                    selected[decoded_key] = value.decode("utf-8", errors="strict")
            projected.append(
                {"name": item["name"], "pm2_env": {"env": selected, **selected}}
            )
        return json.dumps(projected)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise StageGateError("process_gate_environment_invalid") from exc


def _readiness_snapshot() -> dict[str, dict]:
    results = {}
    for name, url in READINESS_URLS.items():
        try:
            request = Request(url, headers={"Accept": "application/json"})
            with urlopen(request, timeout=5) as response:
                body = json.loads(response.read(64 * 1024))
            if response.status != 200 or body.get("status") != "ready":
                raise ValueError
            checks = body.get("checks", {})
            if not isinstance(checks, dict):
                raise ValueError
            results[name] = {
                "status_code": response.status,
                "status": "ready",
                "checks": checks,
            }
        except Exception as exc:
            raise StageGateError(f"{name}_readiness_evidence_failed") from exc
    validate_evidence_payload(results)
    return results


@contextmanager
def _temporary_environment(values: dict[str, str]):
    previous = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _run_bearer(context: StageContext) -> dict:
    path = context.harness_root / "verify_bearer.py"
    spec = importlib.util.spec_from_file_location("local_verify_bearer", path)
    if spec is None or spec.loader is None:
        raise StageGateError("bearer_verifier_unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    operator_env = _load_env_file(context.runtime_env_dir / "operator.env")
    try:
        with _temporary_environment(operator_env):
            config = module.Config.from_environment()
            evidence = module.run_verification(config, module.SafeReporter())
    except module.VerificationError as exc:
        raise StageGateError(f"bearer_{exc}") from exc
    validate_evidence_payload(evidence)
    return evidence


def _stop_runtime() -> None:
    subprocess.run(
        _pm2_command("stop", *PROCESS_NAMES),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
    )


def _checksum_manifest(path: Path) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    index = path.parent / "SHA256SUMS"
    entries = _read_checksum_index(index)
    entries[path.name] = digest
    _write_checksum_index(index, entries)


def _write_checksum_index(index: Path, entries: dict[str, str]) -> None:
    temporary = index.with_suffix(".tmp")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            for name in sorted(entries):
                stream.write(f"{entries[name]}  {name}\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, index)
        os.chmod(index, 0o600)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _read_checksum_index(index: Path) -> dict[str, str]:
    if not index.exists():
        return {}
    try:
        entries = {}
        for line in index.read_text(encoding="utf-8").splitlines():
            match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
            if match is None or match.group(2) in entries:
                raise ValueError
            entries[match.group(2)] = match.group(1)
        return entries
    except (OSError, ValueError) as exc:
        raise StageGateError("checksum_index_invalid") from exc


def _verify_checksum_entry(path: Path) -> None:
    entries = _read_checksum_index(path.parent / "SHA256SUMS")
    expected = entries.get(path.name)
    if expected is None or not compare_digest(expected, _hash_file(path)):
        raise StageGateError("evidence_checksum_mismatch")


def run_local_rta(context: StageContext) -> dict:
    state = _load_state(context)
    validate_stage_transition(tuple(state["completed"]), "LOCAL-RTA-1")
    steps: dict[str, Any] = {}
    before_pm2_json = _pm2_json()
    steps["capture_baseline"] = {
        "captured_at": _utc_timestamp(),
        "hostname": os.uname().nodename,
        "kernel_machine": os.uname().machine,
        "release_sha": context.release_sha,
        "pm2": project_pm2_state(before_pm2_json),
        "capacity": _capacity_snapshot(),
        "listeners": _listener_snapshot(),
    }
    actual_sha = _run_checked(
        "release_sha", ["git", "rev-parse", "HEAD"], cwd=context.repo_root
    ).strip()
    if actual_sha != context.release_sha:
        raise StageGateError("release_sha_mismatch")
    steps["verify_source_sha"] = {"actual_sha": actual_sha}
    capacity = _capacity_snapshot()
    conflicts = application_port_conflicts(steps["capture_baseline"]["listeners"])
    exposed_ports = unexpected_non_loopback_listeners(
        steps["capture_baseline"]["listeners"]
    )
    if capacity["mem_available_mib"] < 512:
        raise StageGateError("mem_available_below_512_mib")
    if capacity["swap_used_mib"] > 1024:
        raise StageGateError("swap_used_above_1024_mib")
    if conflicts:
        raise StageGateError("application_port_conflict")
    if exposed_ports:
        raise StageGateError("unexpected_non_loopback_listener")
    _run_checked(
        "capacity_gate",
        ["python3", "ops/control-plan-read-runtime/runtime_gate.py", "capacity"],
        cwd=context.repo_root,
    )
    steps["capacity_gate"] = {
        **capacity,
        "port_conflicts": conflicts,
        "non_loopback_ports": exposed_ports,
    }
    steps["capacity_stop_rule"] = {"triggered": False, "gate_lowered": False}
    steps["install_manifests"] = _install_manifests(context)
    steps["migration_parity"] = _apply_migrations(context)
    steps["monitoring_preflight"] = _monitoring_preflight(context)
    runtime_env = _pm2_runtime_environment(context)
    _run_checked(
        "start_four_processes",
        _pm2_command("start", "ecosystem.config.cjs", "--update-env"),
        cwd=context.repo_root / "ops/control-plan-read-runtime",
        env=runtime_env,
        timeout=120,
    )
    baseline_output = _run_checked(
        "restart_baseline",
        ["python3", "runtime_gate.py", "snapshot"],
        cwd=context.repo_root / "ops/control-plan-read-runtime",
        env=runtime_env,
    )
    try:
        restart_baseline = json.loads(baseline_output)
    except json.JSONDecodeError as exc:
        raise StageGateError("restart_baseline_invalid") from exc
    steps["start_four_processes"] = {"restart_baseline": restart_baseline}
    running_pm2_json = _pm2_json()
    model_release = _read_json(
        context.repo_root
        / "services/flow-monitoring/data/model-releases/engineering-prior-v5-v1.json"
    )
    steps["verify_dark_flags"] = collect_dark_runtime_contract(
        _actual_gate_environment(running_pm2_json), model_release
    )
    baseline_path = context.evidence_root / ".restart-baseline.json"
    write_stage_manifest(baseline_path, restart_baseline)
    _run_checked(
        "five_minute_stability",
        [
            "python3",
            "runtime_gate.py",
            "stability",
            "--baseline",
            str(baseline_path),
            "--startup-timeout",
            "120",
            "--duration",
            str(context.stability_duration),
            "--interval",
            "5",
        ],
        cwd=context.repo_root / "ops/control-plan-read-runtime",
        env=runtime_env,
        timeout=context.stability_duration + 180,
    )
    baseline_path.unlink(missing_ok=True)
    stable_pm2_json = _pm2_json()
    stable_state = project_pm2_state(stable_pm2_json)
    steps["five_minute_stability"] = {
        "duration_seconds": context.stability_duration,
        "readiness": _readiness_snapshot(),
        "pm2": stable_state,
        "restart_counts_unchanged": all(
            item["restarts"] == restart_baseline[item["name"]]
            for item in stable_state
            if item["name"] in restart_baseline
        ),
    }
    if not steps["five_minute_stability"]["restart_counts_unchanged"]:
        raise StageGateError("restart_counts_changed")
    steps["bearer_lifecycle"] = _run_bearer(context)
    after_capacity = _capacity_snapshot()
    after_listeners = _listener_snapshot()
    if unexpected_non_loopback_listeners(after_listeners):
        raise StageGateError("unexpected_non_loopback_listener")
    expected_listeners = {
        ("127.0.0.1", 3011),
        ("127.0.0.1", 3021),
        ("127.0.0.1", 3022),
        ("127.0.0.1", 3047),
    }
    actual_application_listeners = {
        (item["address"], item["port"])
        for item in after_listeners
        if item["port"] in {3011, 3021, 3022, 3047}
    }
    if actual_application_listeners != expected_listeners:
        raise StageGateError("loopback_listener_contract_failed")
    steps["pm2_save_and_evidence"] = {
        "saved": True,
        "capacity_after_startup": after_capacity,
        "application_listeners": after_listeners,
    }
    manifest = {
        "stage": "LOCAL-RTA-1",
        "verdict": "PASS",
        "release_sha": context.release_sha,
        "frontend_sha": context.frontend_sha,
        "completed_at": _utc_timestamp(),
        "step_order": list(rta_step_order()),
        "steps": steps,
    }
    validate_evidence_payload(manifest)
    _run_checked("pm2_save", _pm2_command("save"), timeout=60)
    target = context.evidence_root / "LOCAL-RTA-1.json"
    clear_failure_manifest(context.evidence_root, "LOCAL-RTA-1")
    write_stage_manifest(target, manifest)
    _checksum_manifest(target)
    _save_state(context, ["LOCAL-BASE-0", "LOCAL-RTA-1"])
    print("PASS LOCAL-RTA-1")
    return manifest


def _load_harness_module(context: StageContext, filename: str, module_name: str):
    path = context.harness_root / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise StageGateError("local_harness_module_unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _wait_json(
    client: LocalHttpClient, url: str, *, timeout_seconds: int = 120
) -> object:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            result = client.request("GET", url, timeout=5)
            if result.status == 200 and isinstance(result.body, dict):
                return result.body
        except StageGateError:
            pass
        time.sleep(1)
    raise StageGateError("local_service_readiness_failed")


def _start_manual_ros(context: StageContext, client: LocalHttpClient) -> dict:
    _run_checked(
        "stop_dark_ros",
        _pm2_command("delete", "ros-gis-integration"),
        timeout=30,
    )
    _run_checked(
        "start_manual_ros",
        _pm2_command(
            "start",
            str(context.harness_root / "run-ros-manual-producer.sh"),
            "--name",
            "ros-gis-integration",
            "--interpreter",
            "bash",
            "--update-env",
        ),
        env={
            **os.environ,
            "MUNBON_RUNTIME_ENV_DIR": str(context.runtime_env_dir),
        },
        timeout=60,
    )
    _wait_json(client, READINESS_URLS["ros-gis-integration"])
    status = _wait_json(client, "http://127.0.0.1:3047/api/v1/status")
    return validate_ros_lifecycle(status, manual_enabled=True)


def _restore_dark_ros(context: StageContext, client: LocalHttpClient) -> dict:
    subprocess.run(
        _pm2_command("delete", "ros-gis-integration"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
    )
    runtime_env = {
        **os.environ,
        "MUNBON_RUNTIME_ENV_DIR": str(context.runtime_env_dir),
    }
    _run_checked(
        "restore_dark_ros",
        _pm2_command(
            "start",
            "ecosystem.config.cjs",
            "--only",
            "ros-gis-integration",
            "--update-env",
        ),
        cwd=context.repo_root / "ops/control-plan-read-runtime",
        env=runtime_env,
        timeout=60,
    )
    _wait_json(client, READINESS_URLS["ros-gis-integration"])
    status = _wait_json(client, "http://127.0.0.1:3047/api/v1/status")
    lifecycle = validate_ros_lifecycle(status, manual_enabled=False)
    _run_checked("pm2_save_dark_runtime", _pm2_command("save"), timeout=60)
    return lifecycle


def _seed_approved_sources(context: StageContext) -> tuple[dict, dict[str, str]]:
    postgres_url = _load_env_file(context.runtime_env_dir / "bff.env")["POSTGRES_URL"]
    output = _run_checked(
        "seed_approved_sources",
        [
            str(context.repo_root / "services/ros-gis-integration/.venv/bin/python"),
            str(context.harness_root / "seed-approved-sources.py"),
            "--as-of-date",
            context.as_of_date.isoformat(),
            "--manifest",
            str(
                context.repo_root
                / "services/ros-gis-integration/data/requirement_sources.json"
            ),
        ],
        env={
            **os.environ,
            "LOCAL_ACCEPTANCE_POSTGRES_URL": postgres_url,
        },
        timeout=120,
    )
    try:
        evidence = json.loads(output)
        if (
            evidence["scenario_version"] != "local-ac-1-v6"
            or evidence["section_count"] != 41
            or evidence["total_area_rai"] != "45204"
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise StageGateError("approved_source_seed_result_invalid") from exc
    module = _load_harness_module(
        context, "seed-approved-sources.py", "local_approved_sources"
    )
    manifest = module.load_manifest(
        context.repo_root / "services/ros-gis-integration/data/requirement_sources.json"
    )
    scenario = module.build_approved_source_scenario(manifest, context.as_of_date)
    gate_by_section = {
        row["code"]: row["props"]["GateId"] for row in scenario["tables"]["gis.zone"]
    }
    validate_evidence_payload(evidence)
    return evidence, gate_by_section


def _login_operator(
    context: StageContext, client: LocalHttpClient, verifier
) -> tuple[str, str, dict]:
    operator_env = _load_env_file(context.runtime_env_dir / "operator.env")
    with _temporary_environment(operator_env):
        try:
            config = verifier.Config.from_environment()
        except verifier.VerificationError as exc:
            raise StageGateError(f"operator_{exc}") from exc
    validate_runtime_urls(
        {
            "auth": config.auth_url,
            "scheduler": config.scheduler_url,
            "bff": config.bff_url,
            "flow": "http://127.0.0.1:3011",
            "ros": "http://127.0.0.1:3047",
        }
    )
    login = client.request(
        "POST",
        f"{config.auth_url}/api/v1/auth/login",
        payload={"email": config.email, "password": config.password},
    )
    try:
        token = login.body["data"]["accessToken"]
        if login.status != 200 or not isinstance(token, str) or not token:
            raise ValueError
        errors = verifier.claim_errors(
            verifier.decode_jwt_claims(token),
            issuer=config.issuer,
            audience=config.audience,
            role=config.role,
        )
        if errors:
            raise ValueError
    except (KeyError, TypeError, ValueError, verifier.VerificationError) as exc:
        raise StageGateError("operator_login_not_accepted") from exc
    return (
        token,
        client.refresh_cookie(),
        {
            "status": login.status,
            "claims": "valid",
        },
    )


@contextmanager
def _fresh_write_activation_operator_session(
    context: StageContext,
    verifier,
    *,
    expected_subject: str,
):
    fresh_client = LocalHttpClient()
    refresh_cookie: str | None = None

    def cleanup_session(
        *,
        strict: bool,
        primary: BaseException | None,
        evidence: dict | None = None,
    ) -> None:
        cleanup_errors: list[BaseException] = []
        try:
            logout_result = _operator_logout(
                fresh_client,
                refresh_cookie,
                strict=strict,
                error_code="write_activation_fresh_operator_logout_failed",
            )
            if isinstance(logout_result, BaseException):
                cleanup_errors.append(logout_result)
            elif logout_result is False:
                cleanup_errors.append(
                    StageGateError("write_activation_fresh_operator_logout_failed")
                )
        except BaseException as exc:
            cleanup_errors.append(exc)

        reuse_evidence = None
        try:
            reuse_evidence = _assert_operator_refresh_reuse_rejected(
                fresh_client,
                refresh_cookie,
            )
            if not isinstance(reuse_evidence, dict):
                cleanup_errors.append(
                    StageGateError("write_activation_fresh_operator_cleanup_unproved")
                )
        except BaseException as exc:
            cleanup_errors.append(exc)

        primary_interrupt = (
            primary if isinstance(primary, (KeyboardInterrupt, SystemExit)) else None
        )
        cleanup_interrupt = next(
            (
                error
                for error in cleanup_errors
                if isinstance(error, (KeyboardInterrupt, SystemExit))
            ),
            None,
        )
        interrupt = primary_interrupt or cleanup_interrupt
        if interrupt is not None:
            if cleanup_errors:
                setattr(
                    interrupt,
                    "session_cleanup",
                    {
                        "logout_attempted": True,
                        "refresh_reuse_attempted": True,
                        "proved": False,
                    },
                )
                raise interrupt
            if evidence is not None:
                evidence["logout"] = {"accepted": True}
                evidence["refresh_revoked"] = reuse_evidence
            return
        if cleanup_errors:
            cleanup_error = StageGateError(
                "write_activation_fresh_operator_cleanup_unproved"
            )
            cause = primary if primary is not None else cleanup_errors[0]
            raise cleanup_error from cause
        if evidence is not None:
            evidence["logout"] = {"accepted": True}
            evidence["refresh_revoked"] = reuse_evidence

    try:
        try:
            fresh_access_token, refresh_cookie, login_evidence = _login_operator(
                context,
                fresh_client,
                verifier,
            )
        except BaseException as primary:
            try:
                refresh_cookie = fresh_client.refresh_cookie()
            except BaseException:
                refresh_cookie = None
            if refresh_cookie:
                record = {
                    "phase": "login",
                    "probe_outcome": "not_started",
                    "failed_gate": _safe_error_code(primary),
                }
                cleanup_session(strict=False, primary=primary, evidence=record)
                setattr(primary, "rollback_session_record", record)
            raise

        principal_evidence: dict | None = None
        try:
            principal = fresh_client.request(
                "GET",
                "http://127.0.0.1:3021/api/v1/auth/principal",
                bearer=fresh_access_token,
            )
            principal_evidence = validate_w1_principal_result(
                principal.status,
                principal.body,
                principal.headers,
            )
        except BaseException as primary:
            record = {
                "phase": "principal",
                "probe_outcome": "not_started",
                "failed_gate": _safe_error_code(primary),
                "login": login_evidence,
            }
            if principal_evidence is not None:
                record["principal"] = principal_evidence
            cleanup_session(strict=False, primary=primary, evidence=record)
            setattr(primary, "rollback_session_record", record)
            raise
        if principal_evidence["subject"] != expected_subject:
            primary = StageGateError("write_activation_operator_subject_changed")
            record = {
                "phase": "principal",
                "probe_outcome": "not_started",
                "failed_gate": _safe_error_code(primary),
                "login": login_evidence,
                "principal": principal_evidence,
            }
            cleanup_session(strict=False, primary=primary, evidence=record)
            setattr(primary, "rollback_session_record", record)
            raise primary
        evidence = {
            "login": login_evidence,
            "principal": principal_evidence,
        }

        try:
            yield fresh_client, fresh_access_token, evidence
        except BaseException as primary:
            cleanup_session(strict=False, primary=primary, evidence=evidence)
            setattr(primary, "rollback_session_record", dict(evidence))
            raise
        cleanup_session(strict=True, primary=None, evidence=evidence)
    except BaseException:
        raise


def _validate_flow_publication(result: HttpResult, *, requirement_run_id: str) -> dict:
    try:
        records = result.body["records"]
        matching = [
            item
            for item in records
            if isinstance(item, dict)
            and isinstance(item.get("record"), dict)
            and item["record"].get("source_service") == "ros-gis-integration"
            and item["record"].get("source_version") == requirement_run_id
            and item["record"].get("synthetic") is False
        ]
        if (
            result.status != 200
            or result.body["kind"] != "demand"
            or len(matching) != 287
        ):
            raise ValueError
        return {
            "status": result.status,
            "kind": result.body["kind"],
            "published_record_count": len(matching),
            "source_service": "ros-gis-integration",
            "synthetic": False,
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise StageGateError("flow_publication_not_accepted") from exc


def run_local_ac(context: StageContext) -> dict:
    state = _load_state(context)
    validate_stage_transition(tuple(state["completed"]), "LOCAL-AC-1")
    model_release = _read_json(
        context.repo_root
        / "services/flow-monitoring/data/model-releases/engineering-prior-v5-v1.json"
    )
    before_dark = collect_dark_runtime_contract(
        _actual_gate_environment(_pm2_json()), model_release
    )
    source_evidence, gate_by_section = _seed_approved_sources(context)
    ac_helpers = _load_harness_module(context, "local-ac1.py", "local_ac1_helpers")
    verifier = _load_harness_module(
        context, "verify_bearer.py", "local_ac1_bearer_verifier"
    )
    client = LocalHttpClient()
    as_of_date = context.as_of_date.isoformat()
    refresh_token = None
    logged_out = False
    steps: dict[str, Any] = {
        "approved_sources": source_evidence,
        "dark_contract_before": before_dark,
    }
    try:
        steps["manual_ros_lifecycle"] = _start_manual_ros(context, client)
        token, refresh_token, login_evidence = _login_operator(
            context, client, verifier
        )
        steps["operator_login"] = login_evidence
        manual_trigger = _load_env_file(
            context.runtime_env_dir / "local-secrets.env"
        ).get("DAILY_REQUIREMENT_MANUAL_TOKEN")
        if not manual_trigger:
            raise StageGateError("manual_trigger_unavailable")
        missing_trigger = client.request(
            "POST",
            "http://127.0.0.1:3047/api/v1/water-requirements/runs",
            payload={"asOfDate": as_of_date},
        )
        invalid_trigger = client.request(
            "POST",
            "http://127.0.0.1:3047/api/v1/water-requirements/runs",
            payload={"asOfDate": as_of_date},
            internal_trigger="invalid-local-trigger",
        )
        if missing_trigger.status != 403 or invalid_trigger.status != 403:
            raise StageGateError("manual_trigger_denial_not_accepted")
        run = client.request(
            "POST",
            "http://127.0.0.1:3047/api/v1/water-requirements/runs",
            payload={"asOfDate": as_of_date},
            internal_trigger=manual_trigger,
            timeout=120,
        )
        if run.status == 409:
            validate_manual_requirement_failure(
                run.status,
                run.body,
                as_of_date=as_of_date,
            )
        run_evidence = validate_manual_requirement_run(
            run.status,
            run.body,
            as_of_date=as_of_date,
        )
        run_id = run_evidence["run_id"]
        steps["manual_requirement_run"] = {
            **run_evidence,
            "lineage": collect_requirement_run_lineage(
                context,
                run_id=run_id,
                approved_source_sha256=source_evidence["content_sha256"],
            ),
            "route_authentication": "local_internal_header",
            "missing_header_status": missing_trigger.status,
            "invalid_header_status": invalid_trigger.status,
        }
        daily = client.request(
            "GET",
            "http://127.0.0.1:3047/api/v1/water-requirements/daily?"
            + urlencode({"service_date": as_of_date, "zone": 6}),
        )
        steps["zone_requirements"] = validate_zone_requirements(
            daily.status,
            daily.body,
            as_of_date=as_of_date,
            run_id=run_id,
        )
        flow_demands = client.request(
            "GET",
            "http://127.0.0.1:3011/api/v1/control/demands?kind=demand",
        )
        steps["flow_publication"] = _validate_flow_publication(
            flow_demands, requirement_run_id=run_id
        )
        snapshot = client.request(
            "POST",
            "http://127.0.0.1:3011/api/v1/control/model-snapshots",
            timeout=60,
        )
        if snapshot.status != 200 or not isinstance(snapshot.body, dict):
            raise StageGateError("model_snapshot_not_accepted")
        draft_request = ac_helpers.build_control_plan_draft(
            daily.body["requirements"],
            snapshot.body,
            gate_by_section,
        )
        draft = client.request(
            "POST",
            "http://127.0.0.1:3021/api/v1/control-plans/drafts",
            payload=draft_request,
            bearer=token,
            timeout=300,
        )
        draft_evidence = validate_draft_result(
            draft.status,
            draft.body,
            requirement_run_id=run_id,
        )
        steps["scheduler_draft"] = draft_evidence
        plan_id = draft_evidence["plan_id"]
        plan_version = draft_evidence["plan_version"]
        projection_evidence = {}
        for path in ac_helpers.projection_paths(plan_id, plan_version):
            result = client.request(
                "GET",
                f"http://127.0.0.1:3022{path}",
                bearer=token,
                timeout=60,
            )
            projection_evidence[path] = validate_projection_result(
                path,
                result.status,
                result.headers,
                result.body,
                plan_id=plan_id,
                plan_version=plan_version,
            )
        steps["bff_projections"] = projection_evidence
        missing_path = (
            "/api/v1/control-plans/" "00000000-0000-0000-0000-000000000000/versions/1"
        )
        missing = client.request(
            "GET",
            f"http://127.0.0.1:3022{missing_path}",
            bearer=token,
        )
        if (
            missing.status != 404
            or "no-store" not in missing.headers.get("cache-control", "").lower()
        ):
            raise StageGateError("missing_plan_not_preserved")
        steps["missing_plan"] = {"status": 404, "no_store": True}
        logout = client.request(
            "POST",
            "http://127.0.0.1:3005/api/v1/auth/logout",
            payload={"refreshToken": refresh_token},
        )
        reuse = client.request(
            "POST",
            "http://127.0.0.1:3005/api/v1/auth/refresh",
            payload={"refreshToken": refresh_token},
        )
        if logout.status != 200 or reuse.status != 401:
            raise StageGateError("operator_logout_not_accepted")
        logged_out = True
        steps["operator_logout"] = {
            "status": logout.status,
            "refresh_reuse": reuse.status,
        }
    finally:
        if refresh_token is not None and not logged_out:
            try:
                client.request(
                    "POST",
                    "http://127.0.0.1:3005/api/v1/auth/logout",
                    payload={"refreshToken": refresh_token},
                )
            except StageGateError:
                pass
        steps["restored_ros_lifecycle"] = _restore_dark_ros(context, client)
    after_dark = collect_dark_runtime_contract(
        _actual_gate_environment(_pm2_json()), model_release
    )
    steps["dark_contract_after"] = after_dark
    if before_dark != after_dark:
        raise StageGateError("dark_contract_not_restored")
    manifest = {
        "stage": "LOCAL-AC-1",
        "verdict": "PASS",
        "release_sha": context.release_sha,
        "frontend_sha": context.frontend_sha,
        "completed_at": _utc_timestamp(),
        "steps": steps,
    }
    validate_evidence_payload(manifest)
    target = context.evidence_root / "LOCAL-AC-1.json"
    clear_failure_manifest(context.evidence_root, "LOCAL-AC-1")
    write_stage_manifest(target, manifest)
    _checksum_manifest(target)
    _save_state(context, list(STAGE_ORDER[:3]))
    print("PASS LOCAL-AC-1")
    return manifest


def _verify_frontend_source(context: StageContext) -> dict:
    actual_sha = _run_checked(
        "frontend_sha",
        ["git", "rev-parse", "HEAD"],
        cwd=context.frontend_root,
    ).strip()
    tracked_status = _run_checked(
        "frontend_tracked_tree",
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=no",
        ],
        cwd=context.frontend_root,
    ).strip()
    if actual_sha != context.frontend_sha or tracked_status:
        raise StageGateError("frontend_source_not_accepted")
    return {"sha": actual_sha, "tracked_tree_clean": True}


def _frontend_test_paths() -> tuple[str, ...]:
    return (
        "lib/control-plan-evidence/contract-pin.test.ts",
        "lib/control-plan-evidence/contract.test.ts",
        "lib/control-plan-evidence/feature.test.ts",
        "lib/control-plan-evidence/gate-operations-url.test.ts",
        "lib/control-plans/feature.test.ts",
        "lib/control-plans/contract-pin.test.ts",
        "lib/control-plans/server.test.ts",
        "components/smart-water/shared/SmartWaterNavigation.test.tsx",
        "components/smart-water/control-plans/ControlPlanListPage.test.tsx",
        "components/smart-water/control-plans/ControlPlanDetailPage.test.tsx",
        "components/smart-water/control-plans/ControlPlanEvidenceSummary.test.tsx",
        "components/smart-water/control-plans/useControlPlanQueries.test.tsx",
        "app/smart-water/control-plans/page.test.tsx",
        "app/smart-water/control-plans/[planId]/versions/[version]/page.test.tsx",
        "app/api/smart-water-backend/control-plans/route.test.ts",
        "app/api/smart-water-backend/control-plans/[planId]/versions/[version]/route.test.ts",
        "app/api/smart-water-backend/control-plans/[planId]/versions/[version]/[projection]/route.test.ts",
    )


def _build_frontend(
    context: StageContext,
    *,
    control_plan_reads: bool,
    run_tests: bool,
    control_plan_evidence_reads: bool = False,
    gate_operations_base_url: str | None = None,
    water_planning_v2: bool = False,
    water_planning_submit: bool = False,
    build_label: str | None = None,
) -> dict:
    mode = build_label or ("visible" if control_plan_reads else "dark")
    environment = frontend_process_environment(
        context.runtime_env_dir,
        control_plan_reads=control_plan_reads,
        control_plan_evidence_reads=control_plan_evidence_reads,
        gate_operations_base_url=gate_operations_base_url,
        water_planning_v2=water_planning_v2,
        water_planning_submit=water_planning_submit,
    )
    activation_gates = project_frontend_activation_gates(environment)
    if activation_gates != {
        "control_plan_reads": control_plan_reads,
        "control_plan_evidence_reads": control_plan_evidence_reads,
        "water_planning_v2": water_planning_v2,
        "water_planning_submit": water_planning_submit,
    }:
        raise StageGateError("frontend_activation_gates_not_accepted")
    npm = str(NODE_ROOT / "bin/npm")
    if run_tests:
        _run_checked(
            f"frontend_{mode}_tests",
            [
                npm,
                "--prefix",
                str(context.frontend_root),
                "test",
                "--",
                *_frontend_test_paths(),
            ],
            env={**environment, "NODE_ENV": "test"},
            timeout=900,
        )
    _run_checked(
        f"frontend_{mode}_build",
        [
            npm,
            "--prefix",
            str(context.frontend_root),
            "run",
            "build",
        ],
        env=environment,
        timeout=1200,
    )
    return {
        "activation_gates": activation_gates,
        "focused_tests": "PASS" if run_tests else "rollback-only",
        "production_build": "PASS",
    }


def _wait_frontend(process: subprocess.Popen, *, timeout_seconds: int = 120) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise StageGateError("frontend_process_exited")
        try:
            with urlopen("http://127.0.0.1:9999/login", timeout=5) as response:
                if response.status == 200:
                    return
        except (HTTPError, OSError, URLError):
            pass
        time.sleep(1)
    raise StageGateError("frontend_readiness_failed")


@contextmanager
def _frontend_server(
    context: StageContext,
    *,
    control_plan_reads: bool,
    control_plan_evidence_reads: bool = False,
    gate_operations_base_url: str | None = None,
    water_planning_v2: bool = False,
    water_planning_submit: bool = False,
    server_label: str | None = None,
):
    mode = server_label or ("visible" if control_plan_reads else "dark")
    environment = frontend_process_environment(
        context.runtime_env_dir,
        control_plan_reads=control_plan_reads,
        control_plan_evidence_reads=control_plan_evidence_reads,
        gate_operations_base_url=gate_operations_base_url,
        water_planning_v2=water_planning_v2,
        water_planning_submit=water_planning_submit,
    )
    log_path = context.evidence_root / f".frontend-{mode}.log"
    descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    completed = False
    process = None
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            process = subprocess.Popen(
                [
                    str(NODE_ROOT / "bin/node"),
                    str(context.frontend_root / "node_modules/next/dist/bin/next"),
                    "start",
                    "-H",
                    "127.0.0.1",
                    "-p",
                    "9999",
                ],
                cwd=context.frontend_root,
                env=environment,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            _wait_frontend(process)
            yield
            completed = True
    except OSError as exc:
        raise StageGateError("frontend_process_failed") from exc
    finally:
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=15)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    pass
        if completed:
            log_path.unlink(missing_ok=True)


def _run_read_browser(
    context: StageContext,
    *,
    mode: str,
    plan_id: str,
    plan_version: int,
) -> dict:
    operator = _load_env_file(context.runtime_env_dir / "operator.env")
    output = _run_checked(
        f"read_browser_{mode}",
        [
            str(NODE_ROOT / "bin/node"),
            str(context.harness_root / "run-read-browser.js"),
        ],
        env={
            **os.environ,
            **operator,
            "PATH": f"{NODE_ROOT / 'bin'}:/usr/bin:/bin",
            "NODE_PATH": str(BROWSER_ROOT / "node_modules"),
            "PLAYWRIGHT_BROWSERS_PATH": str(PLAYWRIGHT_BROWSERS_ROOT),
            "LOCAL_READ_MODE": mode,
            "LOCAL_FRONTEND_URL": "http://127.0.0.1:9999",
            "LOCAL_PLAN_ID": plan_id,
            "LOCAL_PLAN_VERSION": str(plan_version),
        },
        timeout=300,
    )
    try:
        body = json.loads(output)
    except json.JSONDecodeError as exc:
        raise StageGateError("read_browser_output_invalid") from exc
    return validate_read_browser_result(
        body,
        mode=mode,
        plan_id=plan_id,
        plan_version=plan_version,
    )


def _run_evidence_browser(
    context: StageContext,
    *,
    plan_id: str,
    plan_version: int,
    gate_id: str,
) -> dict:
    operator = _load_env_file(context.runtime_env_dir / "operator.env")
    output = _run_checked(
        "evidence_browser_visible",
        [
            str(NODE_ROOT / "bin/node"),
            str(context.harness_root / "run-evidence-browser.js"),
        ],
        env={
            **os.environ,
            **operator,
            "PATH": f"{NODE_ROOT / 'bin'}:/usr/bin:/bin",
            "NODE_PATH": str(BROWSER_ROOT / "node_modules"),
            "PLAYWRIGHT_BROWSERS_PATH": str(PLAYWRIGHT_BROWSERS_ROOT),
            "LOCAL_FRONTEND_URL": "http://127.0.0.1:9999",
            "LOCAL_GATE_OPERATIONS_URL": ("http://127.0.0.1:9998/read-only/gates"),
            "LOCAL_PLAN_ID": plan_id,
            "LOCAL_PLAN_VERSION": str(plan_version),
            "LOCAL_GATE_ID": gate_id,
        },
        timeout=300,
        safe_error_prefix="FAIL evidence_browser: ",
    )
    try:
        body = json.loads(output)
    except json.JSONDecodeError as exc:
        raise StageGateError("evidence_browser_output_invalid") from exc
    return validate_evidence_browser_result(
        body,
        plan_id=plan_id,
        plan_version=plan_version,
        gate_id=gate_id,
    )


def _go_read_runtime_environments(
    context: StageContext,
) -> tuple[dict[str, str], dict[str, str], dict[str, Any]]:
    auth = _load_env_file(context.runtime_env_dir / "auth.env")
    bff = _load_env_file(context.runtime_env_dir / "bff.env")
    try:
        jwt = {
            name: auth[name] for name in ("JWT_SECRET", "JWT_ISSUER", "JWT_AUDIENCE")
        }
        if any(not value for value in jwt.values()) or not bff["POSTGRES_URL"]:
            raise ValueError
    except (KeyError, ValueError) as exc:
        raise StageGateError("go_read_runtime_environment_invalid") from exc
    path_value = f"{NODE_ROOT / 'bin'}:/usr/bin:/bin"
    scada_base = {
        name: value
        for name, value in os.environ.items()
        if name not in GO_READ_FORBIDDEN_SCADA_ENV
    }
    scada = {
        **scada_base,
        **jwt,
        "PATH": path_value,
        "NODE_ENV": "production",
        "LOG_LEVEL": "error",
        "HTTP_HOST": "127.0.0.1",
        "PORT": "3030",
        "SITE_GATE_ID": "waste-way",
        "SITE_NAME": "Waste Way",
        "MODBUS_HOST": "127.0.0.1",
        "MODBUS_PORT": "65534",
        "MODBUS_UNIT_ID": "1",
        "MODBUS_TIMEOUT_MS": "500",
        "MODBUS_POLL_INTERVAL_MS": "2000",
        "MODBUS_STALE_AFTER_MS": "5000",
        "MODBUS_OFFLINE_AFTER_MS": "10000",
        "DATABASE_URL": bff["POSTGRES_URL"],
        "ALLOW_IN_MEMORY_AUDIT": "false",
        "ALLOW_MACHINE_COMMANDS": "false",
    }
    gate_web = {
        **os.environ,
        "PATH": path_value,
        "NODE_ENV": "production",
        "NEXT_TELEMETRY_DISABLED": "1",
        "AUTH_SERVICE_URL": "http://127.0.0.1:3005",
        "SCADA_GATE_CONTROL_URL": "http://127.0.0.1:3030",
        "NEXT_PUBLIC_DEV_TOKEN": "",
        "NEXT_PUBLIC_API_BASE_URL": "",
    }
    projection = validate_go_read_runtime_environment(scada, gate_web)
    return scada, gate_web, projection


def _build_go_read_services(
    context: StageContext,
    scada_environment: dict[str, str],
    gate_web_environment: dict[str, str],
) -> dict[str, Any]:
    npm = str(NODE_ROOT / "bin/npm")
    scada_root = context.repo_root / "services/scada-gate-control"
    gate_web_root = context.repo_root / "services/scada-gate-control-web"
    for label, root, environment, commands in (
        (
            "go_read_scada",
            scada_root,
            scada_environment,
            ("test", "typecheck", "lint", "build"),
        ),
        (
            "go_read_gate_web",
            gate_web_root,
            gate_web_environment,
            ("test", "typecheck", "lint", "build"),
        ),
    ):
        for command in commands:
            command_environment = (
                {
                    **os.environ,
                    "PATH": environment["PATH"],
                    "NODE_ENV": "test",
                }
                if command == "test"
                else environment
            )
            _run_checked(
                f"{label}_{command}",
                [npm, "--prefix", str(root), "run", command],
                env=command_environment,
                timeout=1200,
            )
    return {
        "scada": {
            "tests": "PASS",
            "typecheck": "PASS",
            "lint": "PASS",
            "production_build": "PASS",
        },
        "gate_web": {
            "tests": "PASS",
            "typecheck": "PASS",
            "lint": "PASS",
            "production_build": "PASS",
        },
    }


def _wait_node_server(
    process: subprocess.Popen,
    url: str,
    *,
    process_code: str,
    readiness_code: str,
    timeout_seconds: int = 120,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise StageGateError(process_code)
        try:
            with urlopen(url, timeout=5) as response:
                if response.status == 200:
                    return
        except (HTTPError, OSError, URLError):
            pass
        time.sleep(1)
    raise StageGateError(readiness_code)


def _stop_temporary_process(process: subprocess.Popen) -> None:
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass


@contextmanager
def _temporary_node_server(
    *,
    argv: list[str],
    cwd: Path,
    environment: dict[str, str],
    readiness_url: str,
    log_path: Path,
    process_code: str,
    readiness_code: str,
):
    descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    completed = False
    process = None
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            process = subprocess.Popen(
                argv,
                cwd=cwd,
                env=environment,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            _wait_node_server(
                process,
                readiness_url,
                process_code=process_code,
                readiness_code=readiness_code,
            )
            yield process
            completed = True
    except OSError as exc:
        raise StageGateError(process_code) from exc
    finally:
        if process is not None:
            _stop_temporary_process(process)
        if completed:
            log_path.unlink(missing_ok=True)


def _verify_go_read_restoration(
    context: StageContext,
    before_pm2: dict[str, Any],
    before_dark: dict[str, Any],
    model_release: dict[str, Any],
) -> dict[str, Any]:
    after_listeners = _listener_snapshot()
    remaining_reserved = [
        {
            "address": listener.get("address"),
            "port": listener.get("port"),
        }
        for listener in after_listeners
        if listener.get("port") in {3030, 9998}
    ]
    if remaining_reserved:
        raise StageGateError("go_read_listener_cleanup_failed")
    if unexpected_non_loopback_listeners(after_listeners):
        raise StageGateError("unexpected_non_loopback_listener")
    after_pm2_json = _pm2_json()
    after_pm2 = _pm2_runtime_identity(after_pm2_json)
    if before_pm2 != after_pm2:
        raise StageGateError("go_read_pm2_state_changed")
    after_dark = collect_dark_runtime_contract(
        _actual_gate_environment(after_pm2_json),
        model_release,
    )
    if before_dark != after_dark:
        raise StageGateError("dark_contract_not_restored")
    final_activation_gates = project_frontend_activation_gates(
        frontend_process_environment(
            context.runtime_env_dir,
            control_plan_reads=False,
            control_plan_evidence_reads=False,
        )
    )
    if final_activation_gates != {
        "control_plan_reads": False,
        "control_plan_evidence_reads": False,
        "water_planning_v2": False,
        "water_planning_submit": False,
    }:
        raise StageGateError("frontend_dark_rollback_failed")
    auth_ready = LocalHttpClient().request(
        "GET",
        "http://127.0.0.1:3005/health/ready",
    )
    if auth_ready.status != 200:
        raise StageGateError("go_read_auth_not_restored")
    _verify_source_checkouts(context)
    return {
        "verified": True,
        "reserved_listeners": remaining_reserved,
        "pm2_unchanged": True,
        "auth_ready": True,
        "temporary_processes": 0,
        "dark_contract_after": after_dark,
        "final_activation_gates": final_activation_gates,
    }


@contextmanager
def _go_read_restoration_guard(
    context: StageContext,
    *,
    before_pm2: dict[str, Any],
    before_dark: dict[str, Any],
    model_release: dict[str, Any],
):
    restoration: dict[str, Any] = {}
    try:
        yield restoration
    except Exception as primary_error:
        try:
            proof = _verify_go_read_restoration(
                context,
                before_pm2,
                before_dark,
                model_release,
            )
        except StageGateError as cleanup_error:
            proof = {
                "verified": False,
                "failed_gate": str(cleanup_error),
            }
        setattr(primary_error, "restoration", proof)
        raise
    else:
        restoration.update(
            _verify_go_read_restoration(
                context,
                before_pm2,
                before_dark,
                model_release,
            )
        )


def _actual_process_environment(process: subprocess.Popen) -> dict[str, str]:
    try:
        values = {}
        for entry in Path(f"/proc/{process.pid}/environ").read_bytes().split(b"\0"):
            key, separator, value = entry.partition(b"=")
            if separator:
                values[key.decode("utf-8", errors="strict")] = value.decode(
                    "utf-8",
                    errors="strict",
                )
        return values
    except (OSError, UnicodeDecodeError) as exc:
        raise StageGateError("go_read_process_environment_unavailable") from exc


def _observe_go_read_stability(
    scada_process: subprocess.Popen,
    gate_web_process: subprocess.Popen,
    duration_seconds: int,
) -> dict[str, Any]:
    started = time.monotonic()
    deadline = started + duration_seconds
    samples = 0
    while True:
        if scada_process.poll() is not None or gate_web_process.poll() is not None:
            raise StageGateError("go_read_process_exited_during_stability")
        for url in (
            "http://127.0.0.1:3030/health",
            "http://127.0.0.1:9998/login",
        ):
            try:
                with urlopen(url, timeout=5) as response:
                    if response.status != 200:
                        raise ValueError
            except (HTTPError, OSError, URLError, ValueError) as exc:
                raise StageGateError("go_read_readiness_lost") from exc
        samples += 1
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(5, remaining))
    return {
        "duration_seconds": duration_seconds,
        "samples": samples,
        "processes_stable": True,
        "readiness": {
            "scada_health": 200,
            "gate_web_login": 200,
        },
    }


def _probe_go_read_scada(context: StageContext) -> dict[str, Any]:
    verifier = _load_harness_module(
        context,
        "verify_bearer.py",
        "local_go_read_bearer_verifier",
    )
    client = LocalHttpClient()
    token, refresh_cookie, login_evidence = _login_operator(
        context,
        client,
        verifier,
    )
    try:
        known = client.request(
            "GET",
            "http://127.0.0.1:3030/api/gates/waste-way/status",
            bearer=token,
        )
        unknown = client.request(
            "GET",
            "http://127.0.0.1:3030/api/gates/unknown-gate/status",
            bearer=token,
        )
        return {
            **validate_go_read_status_results(known, unknown),
            "login": login_evidence,
        }
    finally:
        logout = client.request(
            "POST",
            "http://127.0.0.1:3005/api/v1/auth/logout",
            payload={"refreshToken": refresh_cookie},
        )
        if logout.status not in {200, 204}:
            raise StageGateError("go_read_operator_logout_failed")


def _write_coordination_file(path: Path, value: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise StageGateError("coordination_file_not_private") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


def _run_go_read_browser(
    context: StageContext,
    *,
    scada_process: subprocess.Popen,
) -> dict[str, Any]:
    operator = _load_env_file(context.runtime_env_dir / "operator.env")
    ready_path = context.evidence_root / ".go-read-ready"
    outage_release_path = context.evidence_root / ".go-read-outage-release"
    live_screenshot = context.evidence_root / "LOCAL-GO-READ-1-live.png"
    outage_screenshot = context.evidence_root / "LOCAL-GO-READ-1-outage.png"
    for path in (
        ready_path,
        outage_release_path,
        live_screenshot,
        outage_screenshot,
    ):
        path.unlink(missing_ok=True)
    process = None
    try:
        process = subprocess.Popen(
            [
                str(NODE_ROOT / "bin/node"),
                str(context.harness_root / "run-go-read-browser.js"),
            ],
            env={
                **os.environ,
                **operator,
                "PATH": f"{NODE_ROOT / 'bin'}:/usr/bin:/bin",
                "NODE_PATH": str(BROWSER_ROOT / "node_modules"),
                "PLAYWRIGHT_BROWSERS_PATH": str(PLAYWRIGHT_BROWSERS_ROOT),
                "LOCAL_GATE_WEB_URL": "http://127.0.0.1:9998",
                "LOCAL_SCADA_URL": "http://127.0.0.1:3030",
                "LOCAL_GATE_ID": "waste-way",
                "LOCAL_GO_READ_READY_PATH": str(ready_path),
                "LOCAL_GO_READ_OUTAGE_RELEASE_PATH": str(outage_release_path),
                "LOCAL_GO_READ_LIVE_SCREENSHOT": str(live_screenshot),
                "LOCAL_GO_READ_OUTAGE_SCREENSHOT": str(outage_screenshot),
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        deadline = time.monotonic() + 120
        while not ready_path.exists():
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                safe_code = safe_subprocess_failure_code(
                    stderr,
                    "FAIL go_read_browser: ",
                )
                raise StageGateError(safe_code or "go_read_browser_failed")
            if time.monotonic() >= deadline:
                raise StageGateError("go_read_browser_ready_timeout")
            time.sleep(0.1)
        _stop_temporary_process(scada_process)
        if scada_process.poll() not in {0, -signal.SIGTERM}:
            raise StageGateError("go_read_scada_stop_failed")
        _write_coordination_file(outage_release_path, "released\n")
        try:
            stdout, stderr = process.communicate(timeout=180)
        except subprocess.TimeoutExpired as exc:
            raise StageGateError("go_read_browser_outage_timeout") from exc
        if process.returncode != 0:
            safe_code = safe_subprocess_failure_code(
                stderr,
                "FAIL go_read_browser: ",
            )
            raise StageGateError(safe_code or "go_read_browser_failed")
        try:
            body = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise StageGateError("go_read_browser_output_invalid") from exc
        result = validate_go_read_browser_result(body, gate_id="waste-way")
        for screenshot in (live_screenshot, outage_screenshot):
            if (
                not screenshot.is_file()
                or screenshot.stat().st_size < 1024
                or screenshot.stat().st_size > 16 * 1024 * 1024
            ):
                raise StageGateError("go_read_screenshot_invalid")
        return result
    except OSError as exc:
        raise StageGateError("go_read_browser_process_failed") from exc
    finally:
        if process is not None:
            _stop_temporary_process(process)
        ready_path.unlink(missing_ok=True)
        outage_release_path.unlink(missing_ok=True)


def _evidence_projection_path(
    plan_id: str,
    plan_version: int,
    projection: str,
) -> str:
    if projection not in {
        "intent-timeline",
        "readback-observations",
        "execution-state",
    }:
        raise StageGateError("evidence_projection_invalid")
    try:
        normalized_plan_id = str(UUID(plan_id))
        if isinstance(plan_version, bool) or plan_version < 1:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise StageGateError("evidence_projection_invalid") from exc
    return (
        f"/api/v1/control-plans/{normalized_plan_id}/versions/"
        f"{plan_version}/{projection}"
    )


def _run_evidence_projection_reads(
    context: StageContext,
    *,
    plan_id: str,
    plan_version: int,
) -> dict:
    verifier = _load_harness_module(
        context,
        "verify_bearer.py",
        "local_evidence_bearer_verifier",
    )
    client = LocalHttpClient()
    refresh_cookie = None
    token, refresh_cookie, login_evidence = _login_operator(
        context,
        client,
        verifier,
    )
    names = (
        "intent-timeline",
        "readback-observations",
        "execution-state",
    )
    try:
        results = {
            name: client.request(
                "GET",
                (
                    "http://127.0.0.1:3022"
                    + _evidence_projection_path(plan_id, plan_version, name)
                ),
                bearer=token,
            )
            for name in names
        }
        missing_id = "00000000-0000-0000-0000-000000000000"
        absent_statuses = {
            name: client.request(
                "GET",
                (
                    "http://127.0.0.1:3022"
                    + _evidence_projection_path(missing_id, 1, name)
                ),
                bearer=token,
            ).status
            for name in names
        }
        summary = validate_evidence_projection_results(
            results,
            absent_statuses=absent_statuses,
            plan_id=plan_id,
            plan_version=plan_version,
        )
        return {**summary, "login": login_evidence}
    finally:
        if refresh_cookie is not None:
            logout = client.request(
                "POST",
                "http://127.0.0.1:3005/api/v1/auth/logout",
                payload={"refreshToken": refresh_cookie},
            )
            if logout.status not in {200, 204}:
                raise StageGateError("evidence_operator_logout_failed")


def _verify_evidence_resumed(
    context: StageContext,
    *,
    plan_id: str,
    plan_version: int,
) -> dict:
    verifier = _load_harness_module(
        context,
        "verify_bearer.py",
        "local_evidence_resume_bearer_verifier",
    )
    client = LocalHttpClient()
    token, refresh_cookie, _login_evidence = _login_operator(
        context,
        client,
        verifier,
    )
    try:
        result = client.request(
            "GET",
            (
                "http://127.0.0.1:3022"
                + _evidence_projection_path(
                    plan_id,
                    plan_version,
                    "execution-state",
                )
            ),
            bearer=token,
        )
        try:
            hold_events = result.body["hold_events"]
            if (
                result.status != 200
                or "no-store" not in result.headers.get("cache-control", "").lower()
                or result.body["is_held"] is not False
                or not isinstance(hold_events, list)
                or not hold_events
                or hold_events[-1]["event_type"] != "resumed"
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError) as exc:
            raise StageGateError("evidence_resume_not_accepted") from exc
        return {
            "status": result.status,
            "no_store": True,
            "is_held": False,
            "hold_event_count": len(hold_events),
            "latest_event": "resumed",
        }
    finally:
        logout = client.request(
            "POST",
            "http://127.0.0.1:3005/api/v1/auth/logout",
            payload={"refreshToken": refresh_cookie},
        )
        if logout.status not in {200, 204}:
            raise StageGateError("evidence_operator_logout_failed")


def _probe_evidence_dark_routes(
    *,
    plan_id: str,
    plan_version: int,
) -> dict:
    client = LocalHttpClient()
    statuses = {
        name: client.request(
            "GET",
            (
                "http://127.0.0.1:9999/api/smart-water-backend/"
                f"control-plans/{plan_id}/versions/{plan_version}/{name}"
            ),
        )
        for name in (
            "intent-timeline",
            "readback-observations",
            "execution-state",
        )
    }
    if any(
        result.status != 404
        or "no-store" not in result.headers.get("cache-control", "").lower()
        for result in statuses.values()
    ):
        raise StageGateError("evidence_dark_routes_exposed")
    return {
        "statuses": {name: result.status for name, result in statuses.items()},
        "no_store_count": len(statuses),
    }


def run_local_read_activation(context: StageContext) -> dict:
    state = _load_state(context)
    validate_stage_transition(tuple(state["completed"]), "LOCAL-READ-ACT-1")
    source = _verify_frontend_source(context)
    ac_manifest = _read_json(context.evidence_root / "LOCAL-AC-1.json")
    try:
        draft = ac_manifest["steps"]["scheduler_draft"]
        plan_id = str(UUID(str(draft["plan_id"])))
        plan_version = draft["plan_version"]
        if (
            ac_manifest["verdict"] != "PASS"
            or ac_manifest["release_sha"] != context.release_sha
            or isinstance(plan_version, bool)
            or not isinstance(plan_version, int)
            or plan_version < 1
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        raise StageGateError("local_ac_evidence_not_accepted") from exc
    model_release = _read_json(
        context.repo_root
        / "services/flow-monitoring/data/model-releases/engineering-prior-v5-v1.json"
    )
    before_dark = collect_dark_runtime_contract(
        _actual_gate_environment(_pm2_json()),
        model_release,
    )
    steps: dict[str, Any] = {
        "frontend_source": source,
        "accepted_plan": {"plan_id": plan_id, "plan_version": plan_version},
        "dark_contract_before": before_dark,
        "activation_sequence": list(read_activation_flag_sequence()),
        "builds": [],
    }
    final_dark_build_complete = False
    visible_build_attempted = False
    try:
        for index, enabled in enumerate(read_activation_flag_sequence()):
            visible_build_attempted = visible_build_attempted or enabled
            build = _build_frontend(
                context,
                control_plan_reads=enabled,
                run_tests=True,
            )
            steps["builds"].append(build)
            with _frontend_server(context, control_plan_reads=enabled):
                browser = _run_read_browser(
                    context,
                    mode="visible" if enabled else "dark",
                    plan_id=plan_id,
                    plan_version=plan_version,
                )
            if index == 0:
                steps["initial_dark_browser"] = browser
            elif enabled:
                steps["visible_browser"] = browser
            else:
                steps["rollback_dark_browser"] = browser
                final_dark_build_complete = True
    finally:
        if visible_build_attempted and not final_dark_build_complete:
            try:
                _build_frontend(
                    context,
                    control_plan_reads=False,
                    run_tests=False,
                )
            except StageGateError as exc:
                raise StageGateError("frontend_dark_rollback_failed") from exc
    after_dark = collect_dark_runtime_contract(
        _actual_gate_environment(_pm2_json()),
        model_release,
    )
    if before_dark != after_dark:
        raise StageGateError("dark_contract_not_restored")
    steps["dark_contract_after"] = after_dark
    steps["frontend_source_after"] = _verify_frontend_source(context)
    manifest = {
        "stage": "LOCAL-READ-ACT-1",
        "verdict": "PASS",
        "release_sha": context.release_sha,
        "frontend_sha": context.frontend_sha,
        "completed_at": _utc_timestamp(),
        "steps": steps,
    }
    validate_evidence_payload(manifest)
    target = context.evidence_root / "LOCAL-READ-ACT-1.json"
    clear_failure_manifest(context.evidence_root, "LOCAL-READ-ACT-1")
    write_stage_manifest(target, manifest)
    _checksum_manifest(target)
    _save_state(context, list(STAGE_ORDER[:4]))
    print("PASS LOCAL-READ-ACT-1")
    return manifest


def run_local_evidence_activation(context: StageContext) -> dict:
    state = _load_state(context)
    validate_stage_transition(tuple(state["completed"]), "LOCAL-EVIDENCE-1")
    source = _verify_frontend_source(context)
    ac_manifest = _read_json(context.evidence_root / "LOCAL-AC-1.json")
    try:
        draft = ac_manifest["steps"]["scheduler_draft"]
        plan_id = str(UUID(str(draft["plan_id"])))
        plan_version = draft["plan_version"]
        if (
            ac_manifest["verdict"] != "PASS"
            or ac_manifest["release_sha"] != context.release_sha
            or isinstance(plan_version, bool)
            or not isinstance(plan_version, int)
            or plan_version < 1
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        raise StageGateError("local_ac_evidence_not_accepted") from exc

    model_release = _read_json(
        context.repo_root
        / "services/flow-monitoring/data/model-releases/engineering-prior-v5-v1.json"
    )
    before_dark = collect_dark_runtime_contract(
        _actual_gate_environment(_pm2_json()),
        model_release,
    )
    contract_parity = verify_evidence_contract_parity(
        context.repo_root / "contracts/control-plan-evidence/v1",
        context.frontend_root / "contracts/backend/control-plan-evidence/v1",
    )
    gate_source = verify_read_only_gate_source(context.repo_root)
    gate_base_url = "http://127.0.0.1:9998/read-only/gates"
    steps: dict[str, Any] = {
        "frontend_source": source,
        "accepted_plan": {
            "plan_id": plan_id,
            "plan_version": plan_version,
        },
        "contract_parity": contract_parity,
        "read_only_gate_source": gate_source,
        "dark_contract_before": before_dark,
        "activation_sequence": [
            {
                "control_plan_reads": control_reads,
                "control_plan_evidence_reads": evidence_reads,
            }
            for control_reads, evidence_reads in evidence_activation_flag_sequence()
        ],
        "builds": [],
    }

    seeded = False
    resumed = False
    visible_build_attempted = False
    final_dark_build_complete = False
    try:
        _psql(context, build_evidence_seed_sql(plan_id, plan_version))
        seeded = True
        steps["durable_evidence_preparation"] = {
            "method": "append-only disposable-local SQL",
            "hold_event": "held",
            "readback_gate_id": "waste-way",
            "readback_verdict": "unavailable",
            "product_http_mutations": 0,
        }
        steps["real_bearer_projections"] = _run_evidence_projection_reads(
            context,
            plan_id=plan_id,
            plan_version=plan_version,
        )

        for index, (
            control_plan_reads,
            evidence_reads,
        ) in enumerate(evidence_activation_flag_sequence()):
            label = (
                "evidence-visible"
                if evidence_reads
                else (
                    "evidence-dark" if control_plan_reads else "evidence-rollback-dark"
                )
            )
            visible_build_attempted = visible_build_attempted or evidence_reads
            build = _build_frontend(
                context,
                control_plan_reads=control_plan_reads,
                control_plan_evidence_reads=evidence_reads,
                gate_operations_base_url=(gate_base_url if evidence_reads else None),
                run_tests=True,
                build_label=label,
            )
            steps["builds"].append(build)
            with _frontend_server(
                context,
                control_plan_reads=control_plan_reads,
                control_plan_evidence_reads=evidence_reads,
                gate_operations_base_url=(gate_base_url if evidence_reads else None),
                server_label=label,
            ):
                if evidence_reads:
                    steps["visible_browser"] = _run_evidence_browser(
                        context,
                        plan_id=plan_id,
                        plan_version=plan_version,
                        gate_id="waste-way",
                    )
                else:
                    proof = _probe_evidence_dark_routes(
                        plan_id=plan_id,
                        plan_version=plan_version,
                    )
                    if index == 0:
                        steps["initial_evidence_dark_routes"] = proof
                    else:
                        steps["rollback_dark_routes"] = proof
                        final_dark_build_complete = True

        _psql(context, build_evidence_resume_sql(plan_id, plan_version))
        resumed = True
        steps["resumed_state"] = _verify_evidence_resumed(
            context,
            plan_id=plan_id,
            plan_version=plan_version,
        )
    finally:
        restore_evidence_safety(
            context,
            plan_id=plan_id,
            plan_version=plan_version,
            resume_required=seeded and not resumed,
            dark_build_required=(
                visible_build_attempted and not final_dark_build_complete
            ),
        )

    after_dark = collect_dark_runtime_contract(
        _actual_gate_environment(_pm2_json()),
        model_release,
    )
    if before_dark != after_dark:
        raise StageGateError("dark_contract_not_restored")
    final_environment = frontend_process_environment(
        context.runtime_env_dir,
        control_plan_reads=False,
        control_plan_evidence_reads=False,
    )
    final_activation_gates = project_frontend_activation_gates(final_environment)
    if final_activation_gates != {
        "control_plan_reads": False,
        "control_plan_evidence_reads": False,
        "water_planning_v2": False,
        "water_planning_submit": False,
    }:
        raise StageGateError("frontend_dark_rollback_failed")
    steps["final_activation_gates"] = final_activation_gates
    steps["dark_contract_after"] = after_dark
    steps["frontend_source_after"] = _verify_frontend_source(context)

    manifest = {
        "stage": "LOCAL-EVIDENCE-1",
        "verdict": "PASS",
        "release_sha": context.release_sha,
        "frontend_sha": context.frontend_sha,
        "completed_at": _utc_timestamp(),
        "steps": steps,
    }
    validate_evidence_payload(manifest)
    target = context.evidence_root / "LOCAL-EVIDENCE-1.json"
    clear_failure_manifest(context.evidence_root, "LOCAL-EVIDENCE-1")
    write_stage_manifest(target, manifest)
    _checksum_manifest(target)
    _save_state(context, list(STAGE_ORDER[:5]))
    print("PASS LOCAL-EVIDENCE-1")
    return manifest


def run_local_go_read(context: StageContext) -> dict:
    state = _load_state(context)
    validate_stage_transition(tuple(state["completed"]), "LOCAL-GO-READ-1")
    model_release = _read_json(
        context.repo_root
        / "services/flow-monitoring/data/model-releases/engineering-prior-v5-v1.json"
    )
    before_pm2_json = _pm2_json()
    before_pm2 = _pm2_runtime_identity(before_pm2_json)
    before_dark = collect_dark_runtime_contract(
        _actual_gate_environment(before_pm2_json),
        model_release,
    )
    before_listeners = _listener_snapshot()
    if any(
        listener.get("port") in {3030, 9998, 65534} for listener in before_listeners
    ):
        raise StageGateError("go_read_port_conflict")
    if unexpected_non_loopback_listeners(before_listeners):
        raise StageGateError("unexpected_non_loopback_listener")

    (
        scada_environment,
        gate_web_environment,
        environment_projection,
    ) = _go_read_runtime_environments(context)
    steps: dict[str, Any] = {
        "source": {
            "backend_sha": context.release_sha,
            "frontend_sha": context.frontend_sha,
            "tracked_trees_clean": True,
        },
        "dark_contract_before": before_dark,
        "pm2_before": before_pm2,
        "reserved_ports_before": [],
        "runtime_environment": environment_projection,
        "builds": _build_go_read_services(
            context,
            scada_environment,
            gate_web_environment,
        ),
    }
    scada_root = context.repo_root / "services/scada-gate-control"
    gate_web_root = context.repo_root / "services/scada-gate-control-web"
    scada_log = context.evidence_root / ".go-read-scada.log"
    gate_web_log = context.evidence_root / ".go-read-gate-web.log"
    with _go_read_restoration_guard(
        context,
        before_pm2=before_pm2,
        before_dark=before_dark,
        model_release=model_release,
    ) as restoration:
        with _temporary_node_server(
            argv=[
                str(NODE_ROOT / "bin/node"),
                str(scada_root / "dist/index.js"),
            ],
            cwd=scada_root,
            environment=scada_environment,
            readiness_url="http://127.0.0.1:3030/health",
            log_path=scada_log,
            process_code="go_read_scada_process_failed",
            readiness_code="go_read_scada_readiness_failed",
        ) as scada_process:
            with _temporary_node_server(
                argv=[
                    str(NODE_ROOT / "bin/node"),
                    str(gate_web_root / "node_modules/next/dist/bin/next"),
                    "start",
                    "-H",
                    "127.0.0.1",
                    "-p",
                    "9998",
                ],
                cwd=gate_web_root,
                environment=gate_web_environment,
                readiness_url="http://127.0.0.1:9998/login",
                log_path=gate_web_log,
                process_code="go_read_gate_web_process_failed",
                readiness_code="go_read_gate_web_readiness_failed",
            ) as gate_web_process:
                steps["actual_runtime_environment"] = (
                    validate_go_read_runtime_environment(
                        _actual_process_environment(scada_process),
                        _actual_process_environment(gate_web_process),
                    )
                )
                steps["loopback_listeners"] = go_read_listener_projection(
                    _listener_snapshot()
                )
                steps["five_minute_stability"] = _observe_go_read_stability(
                    scada_process,
                    gate_web_process,
                    context.stability_duration,
                )
                steps["direct_scada_reads"] = _probe_go_read_scada(context)
                steps["browser"] = _run_go_read_browser(
                    context,
                    scada_process=scada_process,
                )
                if gate_web_process.poll() is not None:
                    raise StageGateError("go_read_gate_web_exited_during_outage")

    after_dark = restoration["dark_contract_after"]
    final_activation_gates = restoration["final_activation_gates"]
    screenshots = {}
    for name in ("LOCAL-GO-READ-1-live.png", "LOCAL-GO-READ-1-outage.png"):
        screenshot = context.evidence_root / name
        screenshots[name] = {
            "bytes": screenshot.stat().st_size,
            "sha256": _hash_file(screenshot),
        }
        _checksum_manifest(screenshot)
    steps["cleanup"] = {
        key: restoration[key]
        for key in (
            "verified",
            "reserved_listeners",
            "pm2_unchanged",
            "auth_ready",
            "temporary_processes",
        )
    }
    steps["dark_contract_after"] = after_dark
    steps["final_activation_gates"] = final_activation_gates
    steps["screenshots"] = screenshots
    steps["aws_actions"] = False

    manifest = {
        "stage": "LOCAL-GO-READ-1",
        "verdict": "PASS",
        "release_sha": context.release_sha,
        "frontend_sha": context.frontend_sha,
        "completed_at": _utc_timestamp(),
        "steps": steps,
    }
    validate_evidence_payload(manifest)
    target = context.evidence_root / "LOCAL-GO-READ-1.json"
    clear_failure_manifest(context.evidence_root, "LOCAL-GO-READ-1")
    write_stage_manifest(target, manifest)
    _checksum_manifest(target)
    _save_state(context, list(STAGE_ORDER[:6]))
    print("PASS LOCAL-GO-READ-1")
    return manifest


# --- LOCAL-WRITE-FOUNDATION-1 helpers ---


def validate_w1_principal_result(
    status: int, body: Any, headers: dict[str, str]
) -> dict:
    try:
        no_store = "no-store" in headers.get("cache-control", "").lower()
        subject = str(body["subject"])
        roles = body["effective_roles"]
        if (
            status != 200
            or not no_store
            or not isinstance(roles, list)
            or "operator" not in roles
            or sorted(roles) != roles
        ):
            raise ValueError
        return {"subject": subject, "effective_roles": roles}
    except (KeyError, TypeError, ValueError) as exc:
        raise StageGateError("w1_principal_result_not_accepted") from exc


def validate_w2_write_disabled_result(
    status: int, body: Any, headers: dict[str, str]
) -> dict:
    try:
        no_store = "no-store" in headers.get("cache-control", "").lower()
        detail = str(body["detail"])
        if status != 503 or not no_store or detail != "planning_depth_writes_disabled":
            raise ValueError
        return {"status": 503, "detail": detail}
    except (KeyError, TypeError, ValueError) as exc:
        raise StageGateError("w2_write_disabled_result_not_accepted") from exc


def validate_w2_submission_result(
    status: int,
    body: Any,
    headers: dict[str, str],
    *,
    expected_status: int,
) -> dict:
    try:
        no_store = "no-store" in headers.get("cache-control", "").lower()
        submission_id = str(body["submission_id"])
        client_submission_id = str(body["client_submission_id"])
        request_sha256 = str(body["request_sha256"])
        replayed = body["replayed"]
        week_key = str(body["week_key"])
        if (
            status != expected_status
            or not no_store
            or not isinstance(replayed, bool)
            or len(request_sha256) != 64
        ):
            raise ValueError
        return {
            "submission_id": submission_id,
            "client_submission_id": client_submission_id,
            "request_sha256": request_sha256,
            "replayed": replayed,
            "week_key": week_key,
            "project_key": str(body["project_key"]),
            "submitted_at": str(body["submitted_at"]),
            "submitted_by": str(body["submitted_by"]),
            # Persist-only binds the stored row to the receipt's scope and
            # supersede chain, so these v2 fields are projected too (they were
            # previously discarded). Optional so the shared v1/ISO receipt path
            # -- which has no calendar_system -- is unaffected; the persist-only
            # diff independently asserts each is present and correct for v2.
            "calendar_system": (
                None
                if body.get("calendar_system") is None
                else str(body["calendar_system"])
            ),
            "week_date": (
                None if body.get("week_date") is None else str(body["week_date"])
            ),
            "supersedes_submission_id": (
                None
                if body.get("supersedes_submission_id") is None
                else str(body["supersedes_submission_id"])
            ),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise StageGateError("w2_submission_result_not_accepted") from exc


def validate_w2_active_result(
    status: int,
    body: Any,
    headers: dict[str, str],
    *,
    submission_id: str,
    expected_count: int,
    expected_zone_depths: dict[str, float],
) -> dict:
    """Validate the active read, including the zone -> section expansion.

    Counting levels is not enough: a fan-out that served every section one
    zone's default still returns exactly 41 rows. Each level is therefore
    checked against the depth its own zone was submitted with.
    """
    try:
        no_store = "no-store" in headers.get("cache-control", "").lower()
        levels = body["levels"]
        if (
            status != 200
            or not no_store
            or str(body["submission_id"]) != submission_id
            or not isinstance(levels, list)
            or len(levels) != expected_count
        ):
            raise ValueError
        for level in levels:
            zone_id = str(level["zone_id"])
            section_id = str(level["section_id"])
            if (
                zone_id not in expected_zone_depths
                or float(level["planning_depth_mm"]) != expected_zone_depths[zone_id]
                or level["source_kind"] != "zone_default"
                or str(level["source_area_id"]) != zone_id
                # section_id encodes its own zone, so a row relabelled into
                # another zone is caught even though the row is self-consistent.
                or not section_id.startswith(f"{zone_id}-")
            ):
                raise ValueError
        zones_covered = sorted({str(level["zone_id"]) for level in levels})
        # Per-row checks alone would accept 41 rows all relabelled into one
        # zone; require the whole expected zone set to appear.
        if zones_covered != sorted(expected_zone_depths):
            raise ValueError
        return {
            "submission_id": str(body["submission_id"]),
            "levels_count": len(levels),
            "zones_covered": zones_covered,
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise StageGateError("w2_active_result_not_accepted") from exc


def validate_w2_conflict_result(
    status: int, body: Any, headers: dict[str, str]
) -> dict:
    """Require the optimistic-concurrency 409, not merely any 409.

    The service emits three distinct 409s. Accepting a
    client_submission_id_conflict here would make this drill pass for the very
    id-collision the derived submission ids exist to prevent.
    """
    try:
        no_store = "no-store" in headers.get("cache-control", "").lower()
        detail = str(body["detail"])
        if status != 409 or not no_store or detail != "stale_active_submission":
            raise ValueError
        return {"status": 409, "detail": detail}
    except (KeyError, TypeError, ValueError) as exc:
        raise StageGateError("w2_conflict_result_not_accepted") from exc


def _require_absent_active_submission(
    status: int, body: Any, headers: dict[str, str], *, code: str
) -> None:
    no_store = "no-store" in headers.get("cache-control", "").lower()
    detail = body.get("detail") if isinstance(body, dict) else None
    if status != 404 or not no_store or detail != "planning_depth_submission_not_found":
        raise StageGateError(code)


def validate_write_flag_is_dark(flag_value: str) -> dict:
    """Refuse to probe the dark gate while planning-depth writes are armed.

    The dark-gate drill POSTs a well-formed submission and expects a 503. If the
    flag is still armed -- e.g. a previous run was killed between arming and
    restoring -- that POST instead inserts a real submission into an append-only
    table, poisoning the target week permanently.
    """
    if flag_value.strip().lower() == "true":
        raise StageGateError("write_foundation_flag_not_dark")
    return {"planning_depth_writes_enabled": flag_value}


def validate_w2_week_is_clean(status: int, body: Any, headers: dict[str, str]) -> dict:
    """Require the target week to hold no active submission before writing.

    The stage can only prove a first create (201) against a week with no active
    submission, and migration 010 makes submissions immutable, so a written week
    can never be cleaned. Remedy on failure: re-run with --as-of-date pointing at
    a different ISO week.
    """
    if status == 200:
        raise StageGateError("write_foundation_week_not_clean")
    # Anything else (401/403/503/...) is a broken precheck, not a dirty week.
    _require_absent_active_submission(
        status, body, headers, code="write_foundation_week_precheck_failed"
    )
    return {"status": 404, "clean": True}


def _write_foundation_week(as_of_date: date) -> tuple[str, str]:
    """Return (week_date, week_key) for the RID Monday of the as-of week.

    week_key uses the ISO year, which diverges from the calendar year around
    New Year (2027-01-01 belongs to 2026-W53).
    """
    monday = as_of_date - timedelta(days=as_of_date.weekday())
    iso_year, iso_week, _ = monday.isocalendar()
    return monday.isoformat(), f"{iso_year:04d}-W{iso_week:02d}"


def _write_foundation_client_submission_id(
    release_sha: str, week_key: str, drill: str
) -> str:
    """Derive a stable client submission id for one drill of one run.

    The BFF looks up client_submission_id globally, and week_key is part of the
    canonicalised request, so the id must co-vary with the week: reusing an id
    across weeks is a client_submission_id_conflict, not a replay.
    """
    return str(uuid5(WRITE_FOUNDATION_NAMESPACE, f"{release_sha}:{week_key}:{drill}"))


def validate_w2_not_found_result(
    status: int, body: Any, headers: dict[str, str]
) -> dict:
    _require_absent_active_submission(
        status, body, headers, code="w2_not_found_result_not_accepted"
    )
    return {"status": 404}


def _build_planning_depth_request(
    *,
    week_date: str,
    week_key: str,
    client_submission_id: str,
    active_submission_id: str | None,
    depth_offset: str,
) -> dict:
    offset = float(depth_offset)
    levels = []
    for index, zone in enumerate(range(1, 7)):
        levels.append(
            {
                "area_type": "zone",
                "area_id": f"01-{zone:02d}",
                "planning_depth_mm": round(150.0 + (index * 10.0) + (offset * 1000), 1),
            }
        )
    return {
        "schema_version": 1,
        "project_key": "mun-bon",
        "week_date": week_date,
        "week_key": week_key,
        "client_submission_id": client_submission_id,
        "expected_active_submission_id": active_submission_id,
        "levels": levels,
    }


def _build_dark_probe_request(
    *, week_date: str, week_key: str, client_submission_id: str
) -> dict:
    """Build a submission that the runtime can never persist.

    The write-flag gate runs before roster validation, so a schema-valid but
    roster-invalid body returns 503 while writes are dark and 422 unknown_area
    -- before the rate limiter and before any INSERT -- if the runtime turns out
    to be armed. Probing the dark gate with a fully valid body instead inserts a
    real submission, and migration 010 makes that permanent.
    """
    return {
        "schema_version": 1,
        "project_key": "mun-bon",
        "week_date": week_date,
        "week_key": week_key,
        "client_submission_id": client_submission_id,
        "expected_active_submission_id": None,
        "levels": [
            {
                "area_type": "zone",
                "area_id": "01-99",
                "planning_depth_mm": 250.0,
            }
        ],
    }


def _restart_bff_with_flag(context: StageContext, *, enabled: bool) -> None:
    bff_env_path = context.runtime_env_dir / "bff.env"
    current = _load_env_file(bff_env_path)
    current["PLANNING_DEPTH_WRITES_ENABLED"] = "true" if enabled else "false"
    lines = [f"{key}={value}" for key, value in current.items()]
    temporary = bff_env_path.with_suffix(".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, bff_env_path)
    _run_checked(
        "bff_restart",
        _pm2_command("restart", "bff-water-planning", "--update-env"),
        timeout=30,
    )
    client = LocalHttpClient()
    _wait_json(client, READINESS_URLS["bff-water-planning"])


def run_write_foundation_drills(
    client,
    *,
    token: str,
    week_date: str,
    week_key: str,
    drill_submission_id,
    arm_writes,
    read_write_flag,
) -> dict:
    """Drive the W1/W2 drills, arming planning-depth writes only in the middle.

    Collaborators are injected so the arming window -- the one part of this stage
    that can leave the runtime in a non-dark state -- is exercisable without a
    live runtime. `arm_writes(False)` MUST run on every path out of the armed
    section.
    """
    steps: dict[str, Any] = {}
    w1 = client.request(
        "GET",
        "http://127.0.0.1:3021/api/v1/auth/principal",
        bearer=token,
    )
    steps["w1_principal"] = validate_w1_principal_result(w1.status, w1.body, w1.headers)

    w2_base = "http://127.0.0.1:3022/api/v1/water-planning/planning-depth-submissions"
    active_url = f"{w2_base}/active?project_key=mun-bon&week_key={week_key}"

    def build(drill: str, *, depth_offset: str, active: str | None = None) -> dict:
        return _build_planning_depth_request(
            week_date=week_date,
            week_key=week_key,
            client_submission_id=drill_submission_id(drill),
            active_submission_id=active,
            depth_offset=depth_offset,
        )

    # Prove the week is writable before touching the flag, so a re-run fails here
    # with a remedy rather than as a 200 replay mid-drill.
    precheck = client.request("GET", active_url, bearer=token)
    steps["w2_week_clean"] = validate_w2_week_is_clean(
        precheck.status, precheck.body, precheck.headers
    )

    # bff.env is only the intended state -- a failed disarm restart leaves the
    # file dark while the process stays armed -- so this is a fast early signal,
    # not the safety mechanism. Safety comes from the probe body below, which
    # cannot be persisted even against an armed runtime.
    steps["migration_011"] = validate_write_flag_is_dark(read_write_flag())

    w2_disabled = client.request(
        "POST",
        w2_base,
        payload=_build_dark_probe_request(
            week_date=week_date,
            week_key=week_key,
            client_submission_id=drill_submission_id("dark-gate"),
        ),
        bearer=token,
    )
    steps["w2_dark_flag_gate"] = validate_w2_write_disabled_result(
        w2_disabled.status, w2_disabled.body, w2_disabled.headers
    )

    create_req = build("create", depth_offset="0.100")
    expected_zone_depths = {
        level["area_id"]: level["planning_depth_mm"] for level in create_req["levels"]
    }
    try:
        arm_writes(True)
        create = client.request("POST", w2_base, payload=create_req, bearer=token)
        steps["w2_create"] = validate_w2_submission_result(
            create.status, create.body, create.headers, expected_status=201
        )

        replay = client.request("POST", w2_base, payload=create_req, bearer=token)
        steps["w2_replay"] = validate_w2_submission_result(
            replay.status, replay.body, replay.headers, expected_status=200
        )
        if replay.body["submission_id"] != create.body["submission_id"]:
            raise StageGateError("w2_replay_submission_id_mismatch")

        conflict = client.request(
            "POST",
            w2_base,
            payload=build(
                "conflict",
                depth_offset="0.200",
                active=drill_submission_id("absent-active"),
            ),
            bearer=token,
        )
        steps["w2_conflict"] = validate_w2_conflict_result(
            conflict.status, conflict.body, conflict.headers
        )

        if create.body["week_key"] != week_key:
            raise StageGateError("w2_create_week_key_mismatch")
        active = client.request("GET", active_url, bearer=token)
        steps["w2_active"] = validate_w2_active_result(
            active.status,
            active.body,
            active.headers,
            submission_id=create.body["submission_id"],
            expected_count=41,
            expected_zone_depths=expected_zone_depths,
        )

        not_found_url = f"{w2_base}/active?project_key=mun-bon&week_key=2099-W01"
        not_found = client.request("GET", not_found_url, bearer=token)
        steps["w2_not_found"] = validate_w2_not_found_result(
            not_found.status, not_found.body, not_found.headers
        )
    finally:
        arm_writes(False)

    w2_restored = client.request(
        "POST",
        w2_base,
        payload=_build_dark_probe_request(
            week_date=week_date,
            week_key=week_key,
            client_submission_id=drill_submission_id("restored-gate"),
        ),
        bearer=token,
    )
    steps["w2_restored_gate"] = validate_w2_write_disabled_result(
        w2_restored.status, w2_restored.body, w2_restored.headers
    )
    return steps


def run_local_write_foundation(context: StageContext) -> dict:
    state = _load_state(context)
    validate_stage_transition(tuple(state["completed"]), "LOCAL-WRITE-FOUNDATION-1")

    verifier = _load_harness_module(
        context,
        "verify_bearer.py",
        "local_write_foundation_bearer_verifier",
    )
    client = LocalHttpClient()
    token, refresh_cookie, login_evidence = _login_operator(
        context,
        client,
        verifier,
    )

    week_date, week_key = _write_foundation_week(context.as_of_date)
    steps: dict[str, Any] = {
        "login": login_evidence,
        "target_week": {"week_date": week_date, "week_key": week_key},
    }

    try:
        steps.update(
            run_write_foundation_drills(
                client,
                token=token,
                week_date=week_date,
                week_key=week_key,
                drill_submission_id=lambda drill: (
                    _write_foundation_client_submission_id(
                        context.release_sha, week_key, drill
                    )
                ),
                arm_writes=lambda enabled: _restart_bff_with_flag(
                    context, enabled=enabled
                ),
                read_write_flag=lambda: _load_env_file(
                    context.runtime_env_dir / "bff.env"
                ).get("PLANNING_DEPTH_WRITES_ENABLED", ""),
            )
        )
    finally:
        logout = client.request(
            "POST",
            "http://127.0.0.1:3005/api/v1/auth/logout",
            payload={"refreshToken": refresh_cookie},
        )
        if logout.status not in {200, 204}:
            raise StageGateError("write_foundation_operator_logout_failed")

    steps["aws_actions"] = False

    manifest = {
        "stage": "LOCAL-WRITE-FOUNDATION-1",
        "verdict": "PASS",
        "release_sha": context.release_sha,
        "frontend_sha": context.frontend_sha,
        "completed_at": _utc_timestamp(),
        "steps": steps,
    }
    validate_evidence_payload(manifest)
    target = context.evidence_root / "LOCAL-WRITE-FOUNDATION-1.json"
    clear_failure_manifest(context.evidence_root, "LOCAL-WRITE-FOUNDATION-1")
    write_stage_manifest(target, manifest)
    _checksum_manifest(target)
    _save_state(context, list(STAGE_ORDER[:7]))
    print("PASS LOCAL-WRITE-FOUNDATION-1")
    return manifest


# --- LOCAL-WRITE-UI-1 helpers ---


W2_V2_BASE = "http://127.0.0.1:3022/api/v2/water-planning/planning-depth-submissions"


def _write_ui_rid_week(as_of_date: date) -> tuple[str, str]:
    ending_year = (
        as_of_date.year + 1
        if (as_of_date.month, as_of_date.day) >= (11, 1)
        else as_of_date.year
    )
    year_start = date(ending_year - 1, 11, 1)
    offset = (as_of_date - year_start).days
    week_number = offset // 7 + 1
    week_start = year_start + timedelta(days=7 * (week_number - 1))
    return week_start.isoformat(), f"{ending_year:04d}-R{week_number:02d}"


PERSIST_ONLY_MIN_ENDING_YEAR = 1901
PERSIST_ONLY_MAX_ENDING_YEAR = 2401


def _persist_only_rid_week(as_of_date: date) -> tuple[str, str]:
    """Return (week_date, week_key) for a RID week DISTINCT from write-ui's.

    Persist-only is API-driven and must create a fresh root, so it cannot share
    write-ui's (project, calendar, week) scope. Use the successor week within the
    same irrigation year: R(n+1) for write-ui weeks R01..R52, and R52 for R53
    (whose successor would overflow the year). week_date is the canonical span
    start. Reject an as-of whose irrigation ending-year is outside the supported
    1901..2401 range rather than silently produce an unusable key.
    """
    _, write_key = _write_ui_rid_week(as_of_date)
    ending_year = int(write_key[:4])
    if not (
        PERSIST_ONLY_MIN_ENDING_YEAR <= ending_year <= PERSIST_ONLY_MAX_ENDING_YEAR
    ):
        raise StageGateError("persist_only_week_out_of_supported_range")
    write_week = int(write_key[6:])
    persist_week = write_week + 1 if write_week <= 52 else 52
    year_start = date(ending_year - 1, 11, 1)
    week_start = year_start + timedelta(days=7 * (persist_week - 1))
    return week_start.isoformat(), f"{ending_year:04d}-R{persist_week:02d}"


def _write_activation_rid_week(as_of_date: date) -> tuple[str, str]:
    _, write_key = _write_ui_rid_week(as_of_date)
    ending_year = int(write_key[:4])
    if not (
        PERSIST_ONLY_MIN_ENDING_YEAR <= ending_year <= PERSIST_ONLY_MAX_ENDING_YEAR
    ):
        raise StageGateError("write_activation_week_out_of_supported_range")
    write_week = int(write_key[6:])
    activation_week = write_week + 2 if write_week <= 51 else 51
    year_start = date(ending_year - 1, 11, 1)
    week_start = year_start + timedelta(days=7 * (activation_week - 1))
    return week_start.isoformat(), f"{ending_year:04d}-R{activation_week:02d}"


def _write_ui_client_submission_id(release_sha: str, week_key: str, drill: str) -> str:
    return str(uuid5(WRITE_UI_NAMESPACE, f"{release_sha}:{week_key}:{drill}"))


def _build_planning_depth_request_v2(
    *,
    week_date: str,
    week_key: str,
    client_submission_id: str,
    active_submission_id: str | None,
    depth_offset: str,
) -> dict:
    offset = float(depth_offset)
    levels = []
    for index, zone in enumerate(range(1, 7)):
        levels.append(
            {
                "area_type": "zone",
                "area_id": f"01-{zone:02d}",
                "planning_depth_mm": round(150.0 + (index * 10.0) + (offset * 1000), 1),
            }
        )
    return {
        "schema_version": 2,
        "project_key": "mun-bon",
        "calendar_system": "rid-irrigation-v1",
        "week_date": week_date,
        "week_key": week_key,
        "client_submission_id": client_submission_id,
        "expected_active_submission_id": active_submission_id,
        "levels": levels,
    }


def _build_dark_probe_request_v2(
    *,
    week_date: str,
    week_key: str,
    client_submission_id: str,
) -> dict:
    return _build_planning_depth_request_v2(
        week_date=week_date,
        week_key=week_key,
        client_submission_id=client_submission_id,
        active_submission_id=None,
        depth_offset="0.000",
    )


# The six zone depths the write-UI browser submits (250.0 + 10 per zone). The
# roster fan-out must preserve them across all 41 expanded sections.
WRITE_UI_ZONE_DEPTHS = [250.0, 260.0, 270.0, 280.0, 290.0, 300.0]
# create + correct + stale-conflict + field-team probe + outage probe.
WRITE_UI_EXPECTED_MUTATIONS = 5
WATER_PLANNING_PATH = "/smart-water/dashboard"


def _is_strict_status(value: object, expected: int) -> bool:
    """A real HTTP status is a non-boolean int equal to `expected`. Guards the
    whole validator against float/bool/string lookalikes (403.0, True, "401")
    that Python's == would otherwise accept."""
    return isinstance(value, int) and not isinstance(value, bool) and value == expected


def _is_strict_status_in(value: object, allowed: set[int]) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value in allowed


def _is_uuid_value(value: object) -> bool:
    UUID(str(value))
    return True


def _write_browser_request_matches(
    request: object,
    *,
    base_depth: float,
    expected_active_submission_id: str | None,
) -> bool:
    if not isinstance(request, dict) or set(request) != {
        "schema_version",
        "project_key",
        "calendar_system",
        "week_key",
        "week_date",
        "client_submission_id",
        "expected_active_submission_id",
        "levels",
    }:
        return False
    try:
        UUID(str(request["client_submission_id"]))
        date.fromisoformat(request["week_date"])
        levels = request["levels"]
        if (
            type(request["schema_version"]) is not int
            or request["schema_version"] != 2
            or request["project_key"] != "mun-bon"
            or request["calendar_system"] != "rid-irrigation-v1"
            or not re.fullmatch(
                r"[0-9]{4}-R(?:0[1-9]|[1-4][0-9]|5[0-3])", request["week_key"]
            )
            or request["expected_active_submission_id"] != expected_active_submission_id
            or not isinstance(levels, list)
            or len(levels) != 6
        ):
            return False
        return levels == [
            {
                "area_type": "zone",
                "area_id": f"01-{zone:02d}",
                "planning_depth_mm": base_depth + 10.0 * (zone - 1),
            }
            for zone in range(1, 7)
        ]
    except (TypeError, ValueError):
        return False


def collect_write_browser_predicate_codes(body: Any) -> tuple[str, ...]:
    failures: list[str] = []

    def check(code: str, predicate: Callable[[], object]) -> None:
        try:
            if predicate() is not True:
                failures.append(code)
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
            failures.append(code)

    required_keys = (
        "create_result",
        "active_readback",
        "correct_result",
        "conflict_result",
        "conflict_reconciliation",
        "request_identity",
        "roster_provenance",
        "field_team_result",
        "outage_result",
        "logout_result",
        "reload_result",
        "request_inventory",
    )
    check("browser_result_not_object", lambda: isinstance(body, dict))
    sections = {
        key: body.get(key, {}) if isinstance(body, dict) else {}
        for key in required_keys
    }
    for key in required_keys:
        check(f"{key}_not_object", lambda key=key: isinstance(sections[key], dict))

    create = sections["create_result"]
    active = sections["active_readback"]
    correct = sections["correct_result"]
    conflict = sections["conflict_result"]
    reconciliation = sections["conflict_reconciliation"]
    request_identity = sections["request_identity"]
    roster_provenance = sections["roster_provenance"]
    field_team = sections["field_team_result"]
    outage = sections["outage_result"]
    logout = sections["logout_result"]
    reload_res = sections["reload_result"]
    inventory = sections["request_inventory"]

    check(
        "create_submission_id_not_uuid",
        lambda: _is_uuid_value(create["submission_id"]),
    )
    check(
        "create_status_not_201",
        lambda: _is_strict_status(create["status"], 201),
    )
    check(
        "active_submission_id_not_uuid",
        lambda: _is_uuid_value(active["submission_id"]),
    )
    check(
        "active_status_not_200",
        lambda: _is_strict_status(active["status"], 200),
    )
    check("active_levels_count_not_41", lambda: active["levels_count"] == 41)
    check(
        "active_distinct_depths_mismatch",
        lambda: [float(depth) for depth in active["distinct_depths"]]
        == WRITE_UI_ZONE_DEPTHS,
    )
    check(
        "correct_submission_id_not_uuid",
        lambda: _is_uuid_value(correct["submission_id"]),
    )
    check(
        "correct_status_not_201",
        lambda: _is_strict_status(correct["status"], 201),
    )
    check(
        "create_request_identity_invalid",
        lambda: _write_browser_request_matches(
            request_identity["create"],
            base_depth=250.0,
            expected_active_submission_id=None,
        ),
    )
    check(
        "correct_request_identity_invalid",
        lambda: _write_browser_request_matches(
            request_identity["correct"],
            base_depth=260.0,
            expected_active_submission_id=str(create["submission_id"]),
        ),
    )
    check(
        "request_identity_scope_mismatch",
        lambda: (
            request_identity["create"]["week_key"],
            request_identity["create"]["week_date"],
        )
        == (
            request_identity["correct"]["week_key"],
            request_identity["correct"]["week_date"],
        ),
    )
    check(
        "roster_dataset_version_invalid",
        lambda: type(roster_provenance["dataset_version_id"]) is int
        and roster_provenance["dataset_version_id"] > 0,
    )
    check(
        "roster_source_hash_invalid",
        lambda: isinstance(roster_provenance["source_hash"], str)
        and bool(re.fullmatch(r"[0-9a-f]{64}", roster_provenance["source_hash"])),
    )
    check(
        "conflict_status_not_409",
        lambda: _is_strict_status(conflict["status"], 409),
    )
    check(
        "reconciliation_submission_id_not_uuid",
        lambda: _is_uuid_value(reconciliation["submission_id"]),
    )
    check(
        "reconciliation_status_not_200",
        lambda: _is_strict_status(reconciliation["status"], 200),
    )

    check(
        "field_team_roster_status_not_403",
        lambda: _is_strict_status(field_team["roster_status"], 403),
    )
    check(
        "field_team_active_status_not_403",
        lambda: _is_strict_status(field_team["active_status"], 403),
    )
    check("field_team_submit_not_absent", lambda: field_team["submit_absent"] is True)
    check(
        "field_team_denied_banner_absent", lambda: field_team["denied_banner"] is True
    )
    check(
        "field_team_unavailable_banner_present",
        lambda: field_team["unavailable_banner"] is False,
    )
    check(
        "field_team_panel_roster_status_mismatch",
        lambda: _is_strict_status(
            field_team["panel_roster_status"], field_team["roster_status"]
        ),
    )
    check(
        "field_team_panel_active_status_mismatch",
        lambda: _is_strict_status(
            field_team["panel_active_status"], field_team["active_status"]
        ),
    )
    check(
        "field_team_observed_roster_status_mismatch",
        lambda: field_team["observed_roster_status"] is None
        or _is_strict_status(
            field_team["observed_roster_status"], field_team["roster_status"]
        ),
    )
    check(
        "field_team_submit_status_not_403",
        lambda: _is_strict_status(field_team["submit_status"], 403),
    )
    check(
        "field_team_logout_status_not_success",
        lambda: _is_strict_status_in(field_team["logout_status"], {200, 204}),
    )
    check(
        "field_team_refresh_reuse_status_not_401",
        lambda: _is_strict_status(field_team["refresh_reuse_status"], 401),
    )

    check("outage_reads_preserved_present", lambda: "reads_preserved" not in outage)
    check(
        "outage_roster_status_not_502",
        lambda: _is_strict_status(outage["roster_status"], 502),
    )
    check(
        "outage_active_status_not_502",
        lambda: _is_strict_status(outage["active_status"], 502),
    )
    check("outage_submit_not_absent", lambda: outage["submit_absent"] is True)
    check(
        "outage_unavailable_banner_absent",
        lambda: outage["unavailable_banner"] is True,
    )
    check("outage_denied_banner_present", lambda: outage["denied_banner"] is False)
    check(
        "outage_panel_roster_status_mismatch",
        lambda: _is_strict_status(
            outage["panel_roster_status"], outage["roster_status"]
        ),
    )
    check(
        "outage_panel_active_status_mismatch",
        lambda: _is_strict_status(
            outage["panel_active_status"], outage["active_status"]
        ),
    )
    check(
        "outage_observed_roster_status_mismatch",
        lambda: outage["observed_roster_status"] is None
        or _is_strict_status(outage["observed_roster_status"], outage["roster_status"]),
    )
    check(
        "outage_submit_status_not_502",
        lambda: _is_strict_status(outage["submit_status"], 502),
    )

    check(
        "logout_status_not_success",
        lambda: _is_strict_status_in(logout["status"], {200, 204}),
    )
    check(
        "logout_second_context_status_not_success",
        lambda: _is_strict_status_in(logout["second_context_status"], {200, 204}),
    )
    check(
        "logout_refresh_reuse_status_not_401",
        lambda: _is_strict_status(logout["refresh_reuse_status"], 401),
    )
    check(
        "logout_second_context_refresh_reuse_status_not_401",
        lambda: _is_strict_status(logout["second_context_refresh_reuse_status"], 401),
    )
    check("logout_redirect_not_login", lambda: logout["redirect_url"] == "/login")
    check(
        "reload_redirect_not_login",
        lambda: reload_res["redirect_url"] == "/login",
    )
    check(
        "reload_source_not_water_planning",
        lambda: reload_res["reloaded_from"] == WATER_PLANNING_PATH,
    )

    check(
        "forbidden_writes_not_empty",
        lambda: isinstance(inventory["forbidden_writes"], list)
        and not inventory["forbidden_writes"],
    )
    check(
        "forbidden_write_count_not_integer",
        lambda: isinstance(inventory.get("forbidden_write_count"), int),
    )
    check(
        "forbidden_write_count_not_zero",
        lambda: inventory["forbidden_write_count"] == 0,
    )
    check(
        "total_mutations_below_expected",
        lambda: inventory["total_mutations"] >= WRITE_UI_EXPECTED_MUTATIONS,
    )
    return tuple(failures)


def validate_write_browser_result(body: Any) -> dict:
    """Accept only evidence that satisfies every named browser predicate."""
    predicate_codes = collect_write_browser_predicate_codes(body)
    if predicate_codes:
        error = StageGateError("write_browser_result_not_accepted")
        error.predicate_codes = predicate_codes
        raise error

    create = body["create_result"]
    active = body["active_readback"]
    correct = body["correct_result"]
    conflict = body["conflict_result"]
    reconciliation = body["conflict_reconciliation"]
    request_identity = body["request_identity"]
    roster_provenance = body["roster_provenance"]
    field_team = body["field_team_result"]
    outage = body["outage_result"]
    logout = body["logout_result"]
    reload_res = body["reload_result"]
    inventory = body["request_inventory"]
    forbidden_writes = inventory["forbidden_writes"]
    return {
        "create_result": {
            "status": create["status"],
            "submission_id": str(create["submission_id"]),
        },
        "active_readback": {
            "status": active["status"],
            "levels_count": active["levels_count"],
            "distinct_depths": list(active["distinct_depths"]),
        },
        "correct_result": {
            "status": correct["status"],
            "submission_id": str(correct["submission_id"]),
        },
        "conflict_result": {"status": conflict["status"]},
        "conflict_reconciliation": {
            "status": reconciliation["status"],
            "submission_id": str(reconciliation["submission_id"]),
        },
        "request_identity": {
            "create": {
                **request_identity["create"],
                "levels": [
                    dict(level) for level in request_identity["create"]["levels"]
                ],
            },
            "correct": {
                **request_identity["correct"],
                "levels": [
                    dict(level) for level in request_identity["correct"]["levels"]
                ],
            },
        },
        "roster_provenance": {
            "dataset_version_id": roster_provenance["dataset_version_id"],
            "source_hash": roster_provenance["source_hash"],
        },
        # Every field below echoes an OBSERVED value. Emitting a literal
        # `True` that a preceding check happens to guarantee is structurally
        # the same shape as the fabrications this stage deletes, and survives
        # a reordering that drops the check.
        "field_team_result": {
            "roster_status": field_team["roster_status"],
            "active_status": field_team["active_status"],
            "observed_roster_status": field_team["observed_roster_status"],
            "panel_roster_status": field_team["panel_roster_status"],
            "submit_absent": field_team["submit_absent"],
            "denied_banner": field_team["denied_banner"],
            "unavailable_banner": field_team["unavailable_banner"],
            "submit_status": field_team["submit_status"],
            "logout_status": field_team["logout_status"],
            "refresh_reuse_status": field_team["refresh_reuse_status"],
        },
        "outage_result": {
            "roster_status": outage["roster_status"],
            "active_status": outage["active_status"],
            "observed_roster_status": outage["observed_roster_status"],
            "panel_roster_status": outage["panel_roster_status"],
            "submit_absent": outage["submit_absent"],
            "unavailable_banner": outage["unavailable_banner"],
            "denied_banner": outage["denied_banner"],
            "submit_status": outage["submit_status"],
        },
        "logout_result": {
            "status": logout["status"],
            "second_context_status": logout["second_context_status"],
            "refresh_reuse_status": logout["refresh_reuse_status"],
            "second_context_refresh_reuse_status": logout[
                "second_context_refresh_reuse_status"
            ],
            "redirect_to_login": logout["redirect_url"] == "/login",
        },
        "reload_result": {
            "redirect_to_login": reload_res["redirect_url"] == "/login",
            "reloaded_from": reload_res["reloaded_from"],
        },
        "request_inventory": {
            "forbidden_write_count": len(forbidden_writes),
            "total_mutations": inventory["total_mutations"],
        },
    }


def _persist_write_browser_result(
    context: StageContext,
    body: Any,
    *,
    stage: str = "LOCAL-WRITE-UI-1",
) -> Path:
    if stage not in {"LOCAL-WRITE-UI-1", "LOCAL-WRITE-ACT-1"}:
        raise StageGateError("write_browser_stage_invalid")
    validate_evidence_payload(body)
    target = context.evidence_root / f"{stage}-browser-result.json"
    write_stage_manifest(target, body)
    _checksum_manifest(target)
    return target


def _accept_write_browser_output(
    context: StageContext,
    stdout: str,
    *,
    stage: str = "LOCAL-WRITE-UI-1",
) -> dict:
    try:
        body = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise StageGateError("write_browser_output_invalid") from exc
    _persist_write_browser_result(context, body, stage=stage)
    return validate_write_browser_result(body)


WRITE_BROWSER_CREDENTIAL_FILES = (
    ("operator.env", ("MUNBON_OPERATOR_EMAIL", "MUNBON_OPERATOR_PASSWORD")),
    ("field-team.env", ("MUNBON_FIELD_TEAM_EMAIL", "MUNBON_FIELD_TEAM_PASSWORD")),
)


def _write_browser_environment(
    context: StageContext,
    *,
    week_key: str,
    week_date: str,
    ready_path: Path,
    release_path: Path,
) -> dict[str, str]:
    """Build the browser launcher env, failing closed on any missing credential.

    The names are the bootstrap's canonical MUNBON_* ones. The merged stage's
    browser required LOCAL_OPERATOR_*, which bootstrap never writes, so it
    aborted before login -- a defect no source test could see because nothing
    compared the two name sets.
    """
    credentials: dict[str, str] = {}
    missing: list[str] = []
    for filename, names in WRITE_BROWSER_CREDENTIAL_FILES:
        loaded = _load_env_file(context.runtime_env_dir / filename)
        for name in names:
            value = loaded.get(name, "").strip()
            if not value:
                missing.append(name)
            else:
                credentials[name] = value
    if missing:
        raise StageGateError("write_browser_credentials_missing")
    # Strip Node preload vectors: an inherited NODE_OPTIONS=--require/--import (or
    # NODE_REPL_EXTERNAL_MODULE) could replace globalThis.fetch in the launcher
    # and fabricate a refresh-reuse 401 the validator would accept, without ever
    # contacting central auth. Harness-file hashes do not cover preload code
    # (#160 review). The WHOLE variable is dropped (not parsed) — this is an
    # evidence-integrity harness, so failing closed on the injection vector wins
    # over honoring an inherited flag; the launcher needs none (it sets NODE_PATH
    # / PLAYWRIGHT_BROWSERS_PATH explicitly). Any legitimate launcher flag must be
    # set EXPLICITLY below, never inherited.
    base_env = {
        name: value
        for name, value in os.environ.items()
        if name not in _NODE_PRELOAD_ENV_VARS
        and name not in {"LOCAL_WRITE_UI_DIAGNOSTIC", "LOCAL_WRITE_UI_DARK_PROBE"}
    }
    return {
        **base_env,
        **credentials,
        "PATH": f"{NODE_ROOT / 'bin'}:/usr/bin:/bin",
        "NODE_PATH": str(BROWSER_ROOT / "node_modules"),
        "PLAYWRIGHT_BROWSERS_PATH": str(PLAYWRIGHT_BROWSERS_ROOT),
        "LOCAL_FRONTEND_URL": "http://127.0.0.1:9999",
        "LOCAL_WEEK_KEY": week_key,
        "LOCAL_WEEK_DATE": week_date,
        "LOCAL_WRITE_UI_EVIDENCE_ROOT": str(context.evidence_root.resolve()),
        "LOCAL_WRITE_UI_READY_FILE": str(ready_path),
        "LOCAL_WRITE_UI_OUTAGE_RELEASE_FILE": str(release_path),
    }


def validate_write_dark_browser_result(body: Any) -> dict[str, Any]:
    expected_keys = {
        "path",
        "submit_absent",
        "forbidden_write_count",
        "forbidden_writes",
        "mutation_attempt_count",
        "mutation_attempts",
        "total_mutations",
        "logout_status",
        "refresh_reuse_status",
    }
    if (
        not isinstance(body, dict)
        or set(body) != expected_keys
        or body["path"] != WATER_PLANNING_PATH
        or body["submit_absent"] is not True
        or type(body["forbidden_write_count"]) is not int
        or body["forbidden_write_count"] != 0
        or body["forbidden_writes"] != []
        or type(body["mutation_attempt_count"]) is not int
        or body["mutation_attempt_count"] != 0
        or body["mutation_attempts"] != []
        or type(body["total_mutations"]) is not int
        or body["total_mutations"] != 0
        or not _is_strict_status_in(body["logout_status"], {200, 204})
        or not _is_strict_status(body["refresh_reuse_status"], 401)
    ):
        raise StageGateError("write_activation_frontend_not_dark")
    return {
        "path": body["path"],
        "submit_absent": body["submit_absent"],
        "forbidden_write_count": body["forbidden_write_count"],
        "mutation_attempt_count": body["mutation_attempt_count"],
        "total_mutations": body["total_mutations"],
        "logout_status": body["logout_status"],
        "refresh_reuse_status": body["refresh_reuse_status"],
    }


def _run_write_dark_browser(context: StageContext) -> dict[str, Any]:
    week_date, week_key = _write_activation_rid_week(context.as_of_date)
    coordination_root = context.evidence_root.resolve()
    environment = _write_browser_environment(
        context,
        week_key=week_key,
        week_date=week_date,
        ready_path=coordination_root / ".write-ui-ready",
        release_path=coordination_root / ".write-ui-outage-release",
    )
    environment["LOCAL_WRITE_UI_DARK_PROBE"] = "1"
    stdout = _run_checked(
        "write_activation_dark_browser",
        [
            str(NODE_ROOT / "bin/node"),
            str(context.harness_root / "run-write-browser.js"),
        ],
        cwd=context.harness_root,
        env=environment,
        timeout=180,
    )
    try:
        body = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise StageGateError("write_activation_frontend_not_dark") from exc
    return validate_write_dark_browser_result(body)


def _restore_scheduler() -> None:
    _run_checked(
        "write_ui_scheduler_restart",
        _pm2_command("restart", "scheduler", "--update-env"),
        timeout=60,
    )
    _wait_json(LocalHttpClient(), READINESS_URLS["scheduler"])


def _safe_error_code(error: BaseException) -> str:
    """Only StageGateError codes are safe to persist: arbitrary exception text
    can carry credential context the sanitizer cannot recognize, and a sanitizer
    trip while writing the failure manifest silently discards the manifest."""
    if isinstance(error, StageGateError) and error.args:
        return str(error.args[0])
    return f"unexpected_{type(error).__name__}"


def _actual_machine_id() -> str:
    try:
        machine_id = Path("/etc/machine-id").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise StageGateError("rc_guest_machine_identity_mismatch") from exc
    if not re.fullmatch(r"[0-9a-f]{32}", machine_id):
        raise StageGateError("rc_guest_machine_identity_mismatch")
    return machine_id


def _verify_scheduler_restoration() -> None:
    """Independent final-state check (#160 HIGH-2): no restart here. Readiness
    is polled FIRST (up to _wait_json's own budget) so a restart that timed out
    yet took effect is not misjudged by a one-shot pm2 snapshot that races the
    respawn; only once readiness is healthy does pm2 confirm the process is the
    online scheduler rather than a stale errored duplicate."""
    _wait_json(LocalHttpClient(), READINESS_URLS["scheduler"])
    projection = project_pm2_state(_pm2_json())
    # Require AT LEAST ONE online 'scheduler' entry — readiness already proved
    # it is serving. pm2 may retain a stale errored/stopped duplicate beside the
    # healthy process; that must not FAIL an otherwise-restored stage.
    online = [
        item
        for item in projection
        if item.get("name") == "scheduler" and item.get("status") == "online"
    ]
    if not online:
        raise StageGateError("write_ui_scheduler_not_online_after_restore")


def _restore_scheduler_guarded(
    attempts: int = 3, backoff_seconds: float = 5.0
) -> dict[str, Any]:
    """Bounded restoration with an INDEPENDENT verdict. Raises nothing for
    Exception-class failures — the caller decides what a failed restoration
    means. Interrupt-class exits (KeyboardInterrupt/SystemExit) deliberately
    PROPAGATE: an operator abort must never be converted into a
    scheduler_restore_failed verdict. On the failure path the caller restores
    via this helper; on an interrupt the caller instead makes a bounded
    best-effort single restore and lets the interrupt propagate with no manifest.

    The final-state check is authoritative: if readiness+pm2 confirm the
    scheduler is up, the restoration succeeded even when individual `pm2
    restart` calls timed out (they frequently take effect anyway). When the
    verification fails, ITS code is the reported failure — it names the actual
    unmet final state, not an earlier restart hiccup."""
    report: dict[str, Any] = {"attempts": 0, "restored": False, "failed_gate": None}
    restart_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        report["attempts"] = attempt
        try:
            _restore_scheduler()
            restart_error = None
            break
        except Exception as exc:
            restart_error = exc
            if attempt < attempts:
                time.sleep(backoff_seconds)
    if restart_error is not None:
        report["failed_gate"] = _safe_error_code(restart_error)
    try:
        _verify_scheduler_restoration()
    except Exception as verify_error:
        # The final-state check is authoritative on failure: it names the
        # unmet condition (e.g. not online / not ready), superseding an earlier
        # restart timeout that may have taken effect anyway.
        report["restored"] = False
        report["failed_gate"] = _safe_error_code(verify_error)
    else:
        report["restored"] = True
    return report


def _drive_write_browser(
    context: StageContext,
    environment: dict[str, str],
    ready_path: Path,
    release_path: Path,
    state: dict[str, bool],
    *,
    stage: str = "LOCAL-WRITE-UI-1",
    healthy_boundary_probe: Callable[[], None] | None = None,
) -> dict:
    process = None
    # stderr goes to a spill FILE, not a pipe. Nothing drains the pipes until
    # after the outage release, so a chatty browser could fill the ~64KB buffer
    # during the healthy phase, block, never write the ready file, and surface as
    # a misleading `write_browser_ready_timeout`. The merged code used
    # `_run_checked`, which drains concurrently; the Popen rewrite lost that.
    stderr_sink = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
    stdout_sink = tempfile.TemporaryFile(mode="w+", encoding="utf-8")

    def _spilled(sink) -> str:
        sink.seek(0)
        return sink.read()

    try:
        process = subprocess.Popen(
            [
                str(NODE_ROOT / "bin/node"),
                str(context.harness_root / "run-write-browser.js"),
            ],
            env=environment,
            stdout=stdout_sink,
            stderr=stderr_sink,
            text=True,
            start_new_session=True,
        )
        deadline = time.monotonic() + 300
        while not ready_path.exists():
            if process.poll() is not None:
                process.communicate()
                safe_code = safe_subprocess_failure_code(
                    _spilled(stderr_sink),
                    "FAIL write_browser: ",
                )
                raise StageGateError(safe_code or "write_browser_failed")
            if time.monotonic() >= deadline:
                raise StageGateError("write_browser_ready_timeout")
            time.sleep(0.1)
        if healthy_boundary_probe is not None:
            healthy_boundary_probe()
        # The browser has finished every healthy-path drill and is parked. Only
        # now is it safe to take the scheduler down: with it stopped, the BFF
        # cannot resolve an operator principal, so planning-depth reads become
        # genuinely unavailable rather than merely asserted to be.
        # Set BEFORE the call, not after: a `pm2 stop` that exceeds the timeout
        # usually still takes effect, so a post-call assignment would skip the
        # restore and leave every later stage running against a dead scheduler.
        # `_restore_scheduler` is idempotent, so an unnecessary restore is free.
        state["scheduler_stopped"] = True
        _run_checked(
            "write_ui_scheduler_stop",
            _pm2_command("stop", "scheduler"),
            timeout=30,
        )
        _write_coordination_file(release_path, "released\n")
        try:
            process.communicate(timeout=300)
        except subprocess.TimeoutExpired as exc:
            raise StageGateError("write_browser_outage_timeout") from exc
        stdout = _spilled(stdout_sink)
        if process.returncode != 0:
            safe_code = safe_subprocess_failure_code(
                _spilled(stderr_sink),
                "FAIL write_browser: ",
            )
            raise StageGateError(safe_code or "write_browser_failed")
        return _accept_write_browser_output(context, stdout, stage=stage)
    except OSError as exc:
        raise StageGateError("write_browser_process_failed") from exc
    finally:
        if process is not None:
            _stop_temporary_process(process)
        stderr_sink.close()
        stdout_sink.close()
        ready_path.unlink(missing_ok=True)
        release_path.unlink(missing_ok=True)


def _run_write_browser(
    context: StageContext,
    *,
    week_key: str,
    week_date: str,
    stage: str = "LOCAL-WRITE-UI-1",
    healthy_boundary_probe: Callable[[], None] | None = None,
) -> dict:
    coordination_root = context.evidence_root.resolve()
    ready_path = coordination_root / ".write-ui-ready"
    release_path = coordination_root / ".write-ui-outage-release"
    # A leftover release file from an aborted run would let the browser skip the
    # outage wait entirely and report an "outage" that never happened.
    for path in (ready_path, release_path):
        path.unlink(missing_ok=True)
    environment = _write_browser_environment(
        context,
        week_key=week_key,
        week_date=week_date,
        ready_path=ready_path,
        release_path=release_path,
    )
    state = {"scheduler_stopped": False}
    try:
        if stage == "LOCAL-WRITE-UI-1":
            result = _drive_write_browser(
                context, environment, ready_path, release_path, state
            )
        else:
            result = _drive_write_browser(
                context,
                environment,
                ready_path,
                release_path,
                state,
                stage=stage,
                healthy_boundary_probe=healthy_boundary_probe,
            )
    except Exception as primary:
        # A real (non-interrupt) failure: restore the scheduler, attach the
        # report so it rides into the failure manifest, and if the restore ALSO
        # failed name BOTH — reporting "pm2 hiccuped" when the real finding was
        # "the evidence was untruthful" would hide the finding.
        if state["scheduler_stopped"]:
            report = _restore_scheduler_guarded()
            setattr(primary, "restoration", report)
            if not report["restored"]:
                combined = StageGateError(
                    f"{_safe_error_code(primary)}_and_scheduler_restore_failed"
                )
                combined.restoration = report
                predicate_codes = getattr(primary, "predicate_codes", None)
                if isinstance(predicate_codes, tuple):
                    combined.predicate_codes = predicate_codes
                raise combined from primary
        raise
    except BaseException:
        # An operator interrupt is not a stage verdict and writes no manifest.
        # Still make a bounded best-effort to bring the scheduler back so later
        # work is not left against a dead scheduler; contain any failure of that
        # attempt and let the interrupt propagate with its own exit semantics.
        if state["scheduler_stopped"]:
            try:
                _restore_scheduler()
            except Exception:
                pass
        raise
    # Success path (#160 HIGH-2): the restore verdict is part of the evidence,
    # and a restoration that could not be verified FAILS the stage.
    report = _restore_scheduler_guarded()
    if not report["restored"]:
        error = StageGateError("write_ui_scheduler_restore_failed")
        error.restoration = report
        raise error
    result["scheduler_restoration"] = report
    return result


def _probe_write_activation_frontend() -> dict[str, Any]:
    try:
        with urlopen(
            Request(
                "http://127.0.0.1:9999/smart-water/dashboard",
                method="GET",
            ),
            timeout=10,
        ) as response:
            return {
                "status_code": response.status,
                "path": urlsplit(response.geturl()).path,
            }
    except (HTTPError, URLError, TimeoutError) as exc:
        raise StageGateError("write_activation_frontend_drift") from exc


def _observe_write_activation_stability(
    *,
    duration_seconds: int,
    interval_seconds: int,
    readiness_probe: Callable[[], dict[str, dict]] | None = None,
    pm2_probe: Callable[[], list[dict]] | None = None,
    listener_probe: Callable[[], list[dict]] | None = None,
    frontend_probe: Callable[[], dict[str, Any]] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    if (
        duration_seconds < 0
        or interval_seconds <= 0
        or duration_seconds % interval_seconds != 0
    ):
        raise StageGateError("write_activation_stability_window_invalid")
    if readiness_probe is None:
        readiness_probe = _readiness_snapshot
    if pm2_probe is None:

        def pm2_probe() -> list[dict]:
            return project_pm2_state(_pm2_json())

    if listener_probe is None:
        listener_probe = _listener_snapshot
    if frontend_probe is None:
        frontend_probe = _probe_write_activation_frontend

    samples = []
    baseline_completed_at = None
    baseline_identity = None
    baseline_listeners = None
    for elapsed in range(0, duration_seconds + 1, interval_seconds):
        if baseline_completed_at is not None:
            sleep(max(0.0, baseline_completed_at + elapsed - monotonic()))
        readiness = readiness_probe()
        pm2 = pm2_probe()
        listeners = listener_probe()
        if set(readiness) != set(PROCESS_NAMES) or any(
            not isinstance(item, dict)
            or item.get("status_code") != 200
            or item.get("status") != "ready"
            or not isinstance(item.get("checks"), dict)
            for item in readiness.values()
        ):
            raise StageGateError("write_activation_readiness_drift")
        identity = [
            (item["name"], item["status"], item["restarts"], item["pid"])
            for item in pm2
        ]
        required_online = [
            item["name"]
            for item in pm2
            if item["name"] in PROCESS_NAMES and item["status"] == "online"
        ]
        if sorted(required_online) != sorted(PROCESS_NAMES):
            raise StageGateError("write_activation_process_not_online")
        if sorted(item["name"] for item in pm2) != sorted(PROCESS_NAMES):
            raise StageGateError("write_activation_process_inventory_unexpected")
        if unexpected_non_loopback_listeners(listeners):
            raise StageGateError("write_activation_listener_exposed")
        frontend = frontend_probe()
        completed_at = monotonic()
        if baseline_completed_at is None:
            baseline_completed_at = completed_at
        observed_elapsed = completed_at - baseline_completed_at
        if frontend != {
            "status_code": 200,
            "path": "/smart-water/dashboard",
        }:
            raise StageGateError("write_activation_frontend_drift")
        if observed_elapsed + 1e-6 < elapsed:
            raise StageGateError("write_activation_stability_window_short")
        if baseline_identity is None:
            baseline_identity = identity
            baseline_listeners = listeners
        elif identity != baseline_identity:
            raise StageGateError("write_activation_restart_or_process_drift")
        if listeners != baseline_listeners:
            raise StageGateError("write_activation_listener_drift")
        samples.append(
            {
                "scheduled_elapsed_seconds": elapsed,
                "observed_elapsed_seconds": observed_elapsed,
                "readiness": readiness,
                "pm2": pm2,
                "listeners": listeners,
                "frontend": frontend,
            }
        )
    observed_duration = monotonic() - baseline_completed_at
    if observed_duration + 1e-6 < duration_seconds:
        raise StageGateError("write_activation_stability_window_short")
    result = {
        "duration_seconds": duration_seconds,
        "observed_duration_seconds": observed_duration,
        "interval_seconds": interval_seconds,
        "sample_count": len(samples),
        "samples": samples,
    }
    validate_evidence_payload(result)
    return result


def _verify_bff_write_flag_dark() -> None:
    pm2_json = _pm2_json()
    actual_environment = _actual_gate_environment(pm2_json)
    flag_name = "PLANNING_DEPTH_WRITES_ENABLED"

    def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    try:
        projected = json.loads(actual_environment, object_pairs_hook=strict_object)
        if type(projected) is not list:
            raise ValueError
        bff_entries = 0
        for item in projected:
            if type(item) is not dict or set(item) != {"name", "pm2_env"}:
                raise ValueError
            name = item["name"]
            if name not in PROCESS_NAMES:
                raise ValueError
            pm2_environment = item["pm2_env"]
            if type(pm2_environment) is not dict:
                raise ValueError
            process_environment = pm2_environment.get("env")
            if type(process_environment) is not dict or any(
                type(key) is not str or type(value) is not str
                for key, value in process_environment.items()
            ):
                raise ValueError
            flattened_flag = pm2_environment.get(flag_name)
            if flattened_flag is not None and (
                type(flattened_flag) is not str
                or flattened_flag != process_environment.get(flag_name)
            ):
                raise ValueError
            if name == "bff-water-planning":
                bff_entries += 1
                if process_environment.get(flag_name) != "false":
                    raise ValueError
            elif flag_name in process_environment:
                raise ValueError
        if bff_entries != 1:
            raise ValueError
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise StageGateError("write_activation_bff_still_armed") from exc


def _verify_bff_fail_safe_stopped() -> None:
    readiness_url = READINESS_URLS.get("bff-water-planning")

    def fail() -> None:
        raise StageGateError("write_activation_bff_stop_not_verified")

    try:
        if not isinstance(readiness_url, str):
            fail()
        readiness_endpoint = urlsplit(readiness_url)
        if (
            readiness_endpoint.scheme != "http"
            or readiness_endpoint.hostname not in {"127.0.0.1", "localhost", "::1"}
            or readiness_endpoint.port != 3022
            or readiness_endpoint.path != "/ready"
            or readiness_endpoint.query
            or readiness_endpoint.fragment
        ):
            fail()

        expected_inventory = sorted(
            (
                name,
                "stopped" if name == "bff-water-planning" else "online",
            )
            for name in PROCESS_NAMES
        )
        for sample in range(3):
            pm2_projection = project_pm2_state(_pm2_json())
            if type(pm2_projection) is not list:
                fail()
            if any(type(process) is not dict for process in pm2_projection):
                fail()
            observed_inventory = sorted(
                (process.get("name"), process.get("status"))
                for process in pm2_projection
            )
            if observed_inventory != expected_inventory:
                fail()

            listeners = _listener_snapshot()
            if type(listeners) is not list:
                fail()
            for listener in listeners:
                if (
                    type(listener) is not dict
                    or not isinstance(listener.get("address"), str)
                    or type(listener.get("port")) is not int
                ):
                    fail()
                if listener["port"] == 3022:
                    fail()

            request = Request(readiness_url, method="GET")
            try:
                with urlopen(request, timeout=5):
                    fail()
            except HTTPError:
                fail()
            except URLError as exc:
                reason = exc.reason
                reason_text = str(reason).strip().casefold()
                if not (
                    isinstance(reason, ConnectionRefusedError)
                    or getattr(reason, "errno", None) == errno.ECONNREFUSED
                    or reason_text == "connection refused"
                ):
                    fail()
            except (OSError, TimeoutError, TypeError, ValueError):
                fail()
            if sample < 2:
                time.sleep(1.0)
    except Exception as exc:
        raise StageGateError("write_activation_bff_stop_not_verified") from exc


def _disarm_bff_guarded(
    context: StageContext,
    *,
    behavioral_dark_probe: Callable[[], Any],
    attempts: int = 3,
    backoff_seconds: float = 5.0,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "attempts": 0,
        "dark": False,
        "stopped": False,
        "failed_gate": None,
    }
    first_failure: Exception | None = None
    pending_interrupt: BaseException | None = None

    for attempt in range(1, attempts + 1):
        report["attempts"] = attempt
        try:
            _restart_bff_with_flag(context, enabled=False)
            _verify_bff_write_flag_dark()
            behavioral_dark_probe()
        except Exception as exc:
            if _safe_error_code(exc) in {
                "write_activation_fresh_operator_cleanup_unproved",
                "write_activation_rollback_session_evidence_incomplete",
            }:
                first_failure = exc
                break
            if first_failure is None:
                first_failure = exc
            if attempt < attempts:
                try:
                    time.sleep(backoff_seconds)
                except BaseException as sleep_interrupt:
                    pending_interrupt = sleep_interrupt
                    break
            continue
        except BaseException as interrupt:
            pending_interrupt = interrupt
            break
        else:
            report["dark"] = True
            return report

    if first_failure is not None:
        report["failed_gate"] = _safe_error_code(first_failure)

    stop_error: Exception | None = None
    stop_interrupt: BaseException | None = None
    try:
        _run_checked(
            "write_activation_bff_fail_safe_stop",
            _pm2_command("stop", "bff-water-planning"),
            timeout=30,
        )
    except Exception as caught_stop_error:
        stop_error = caught_stop_error
    except BaseException as interrupt:
        stop_interrupt = interrupt

    stop_verification_interrupt: BaseException | None = None
    try:
        if _verify_bff_fail_safe_stopped() is not None:
            raise StageGateError("write_activation_bff_stop_not_verified")
    except Exception as verification_error:
        if report["failed_gate"] is None:
            report["failed_gate"] = _safe_error_code(
                first_failure or stop_error or verification_error
            )
    except BaseException as interrupt:
        stop_verification_interrupt = interrupt
    else:
        report["stopped"] = True

    if report["failed_gate"] is None and first_failure is None:
        if stop_error is not None:
            report["failed_gate"] = _safe_error_code(stop_error)
        elif stop_interrupt is not None:
            report["failed_gate"] = _safe_error_code(stop_interrupt)
        elif stop_verification_interrupt is not None:
            report["failed_gate"] = _safe_error_code(stop_verification_interrupt)

    if pending_interrupt is not None:
        setattr(pending_interrupt, "disarm_report", report)
        raise pending_interrupt
    if stop_interrupt is not None:
        setattr(stop_interrupt, "disarm_report", report)
        raise stop_interrupt
    if stop_verification_interrupt is not None:
        setattr(stop_verification_interrupt, "disarm_report", report)
        raise stop_verification_interrupt
    return report


def _restore_write_activation_dark(
    context: StageContext,
    *,
    bff_dark_probe: Callable[[], Any],
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "frontend_dark_build": False,
        "frontend_dark_rendered": False,
        "bff_dark": False,
        "scheduler_restored": False,
        "restored": False,
        "failed_gate": None,
    }
    pending_interrupt: BaseException | None = None

    def record_failure(exc: BaseException) -> None:
        nonlocal pending_interrupt
        if report["failed_gate"] is None:
            report["failed_gate"] = _safe_error_code(exc)
        if not isinstance(exc, Exception) and pending_interrupt is None:
            pending_interrupt = exc

    try:
        _build_frontend(
            context,
            control_plan_reads=False,
            water_planning_v2=False,
            water_planning_submit=False,
            run_tests=False,
            build_label="write-activation-restored",
        )
        report["frontend_dark_build"] = True
    except BaseException as exc:
        record_failure(exc)
    if report["frontend_dark_build"]:
        try:
            with _frontend_server(
                context,
                control_plan_reads=False,
                water_planning_v2=False,
                water_planning_submit=False,
                server_label="write-activation-restored",
            ):
                report["frontend_dark_evidence"] = _run_write_dark_browser(context)
                report["frontend_dark_rendered"] = True
        except BaseException as exc:
            record_failure(exc)
    try:
        disarm = _disarm_bff_guarded(
            context,
            behavioral_dark_probe=bff_dark_probe,
        )
        report["bff_disarm"] = disarm
        report["bff_dark"] = disarm["dark"] is True
        if not report["bff_dark"] and report["failed_gate"] is None:
            failed_gate = disarm.get("failed_gate")
            if isinstance(failed_gate, str) and failed_gate:
                report["failed_gate"] = failed_gate
    except BaseException as exc:
        disarm = getattr(exc, "disarm_report", None)
        if not isinstance(disarm, dict):
            disarm = {
                "attempts": 0,
                "dark": False,
                "stopped": False,
                "failed_gate": _safe_error_code(exc),
            }
        report["bff_disarm"] = disarm
        report["bff_dark"] = disarm.get("dark") is True
        if not report["bff_dark"] and report["failed_gate"] is None:
            failed_gate = disarm.get("failed_gate")
            if isinstance(failed_gate, str) and failed_gate:
                report["failed_gate"] = failed_gate
        record_failure(exc)
    try:
        scheduler = _restore_scheduler_guarded()
        report["scheduler_restored"] = scheduler["restored"] is True
        if not report["scheduler_restored"] and report["failed_gate"] is None:
            report["failed_gate"] = scheduler["failed_gate"]
    except BaseException as exc:
        record_failure(exc)
    report["restored"] = (
        report["frontend_dark_build"]
        and report["frontend_dark_rendered"]
        and report["bff_dark"]
        and report["scheduler_restored"]
    )
    if pending_interrupt is not None:
        setattr(pending_interrupt, "restoration", report)
        raise pending_interrupt
    return report


def _verify_write_activation_restoration(
    context: StageContext,
    *,
    before_dark: dict[str, Any],
    model_release: dict[str, Any],
    before_listeners: list[dict],
) -> dict[str, Any]:
    after_pm2_json = _pm2_json()
    after_processes = project_pm2_state(after_pm2_json)
    expected_inventory = sorted((name, "online") for name in PROCESS_NAMES)
    observed_inventory = sorted(
        (item.get("name"), item.get("status")) for item in after_processes
    )
    if observed_inventory != expected_inventory:
        raise StageGateError("write_activation_process_restoration_failed")
    required_online = [
        item["name"]
        for item in after_processes
        if item["name"] in PROCESS_NAMES and item["status"] == "online"
    ]
    if sorted(required_online) != sorted(PROCESS_NAMES):
        raise StageGateError("write_activation_process_restoration_failed")
    after_dark = collect_dark_runtime_contract(
        _actual_gate_environment(after_pm2_json),
        model_release,
    )
    if after_dark != before_dark:
        raise StageGateError("write_activation_dark_contract_not_restored")
    after_listeners = _listener_snapshot()
    if after_listeners != before_listeners:
        raise StageGateError("write_activation_listener_restoration_failed")
    if unexpected_non_loopback_listeners(after_listeners):
        raise StageGateError("write_activation_listener_exposed")
    final_activation_gates = project_frontend_activation_gates(
        frontend_process_environment(
            context.runtime_env_dir,
            control_plan_reads=False,
            control_plan_evidence_reads=False,
            water_planning_v2=False,
            water_planning_submit=False,
        )
    )
    expected_gates = {
        "control_plan_reads": False,
        "control_plan_evidence_reads": False,
        "water_planning_v2": False,
        "water_planning_submit": False,
    }
    if final_activation_gates != expected_gates:
        raise StageGateError("write_activation_frontend_not_dark")
    readiness = _readiness_snapshot()
    if (
        type(readiness) is not dict
        or set(readiness) != set(PROCESS_NAMES)
        or any(
            type(value) is not dict
            or type(value.get("status_code")) is not int
            or value.get("status_code") != 200
            or value.get("status") != "ready"
            or type(value.get("checks")) is not dict
            for value in readiness.values()
        )
    ):
        raise StageGateError("write_activation_readiness_restoration_failed")
    _verify_frontend_source(context)
    return {
        "verified": True,
        "processes": after_processes,
        "processes_online": sorted(required_online),
        "listeners": after_listeners,
        "dark_contract_after": after_dark,
        "final_activation_gates": final_activation_gates,
        "readiness": readiness,
    }


def _run_local_write_activation_authenticated(
    context: StageContext,
    client,
    token: str,
    login_evidence: dict,
    *,
    verifier,
) -> dict[str, Any]:
    week_date, week_key = _write_activation_rid_week(context.as_of_date)
    model_release = _read_json(
        context.repo_root
        / "services/flow-monitoring/data/model-releases/engineering-prior-v5-v1.json"
    )
    before_pm2_json = _pm2_json()
    before_dark = collect_dark_runtime_contract(
        _actual_gate_environment(before_pm2_json),
        model_release,
    )
    before_listeners = _listener_snapshot()
    before_snapshot = _take_persist_snapshot(context)
    before_rate = _snapshot_planning_depth_rate_keys(context)
    before_rate_completed_at = time.monotonic()
    rollback_operator_sessions: list[dict[str, Any]] = []
    steps: dict[str, Any] = {
        "login": login_evidence,
        "frontend_source": _verify_frontend_source(context),
        "target_week": {"week_date": week_date, "week_key": week_key},
        "target_week_clean": assert_persist_target_week_clean(
            before_snapshot, week_key
        ),
        "dark_contract_before": before_dark,
        "listeners_before": before_listeners,
        "rollback_operator_sessions": rollback_operator_sessions,
    }
    steps["write_flag_dark"] = validate_write_flag_is_dark(
        _load_env_file(context.runtime_env_dir / "bff.env").get(
            "PLANNING_DEPTH_WRITES_ENABLED", ""
        )
    )
    principal = client.request(
        "GET",
        "http://127.0.0.1:3021/api/v1/auth/principal",
        bearer=token,
    )
    steps["operator_principal"] = validate_w1_principal_result(
        principal.status,
        principal.body,
        principal.headers,
    )
    dark_probe = client.request(
        "POST",
        W2_V2_BASE,
        payload=_build_dark_probe_request_v2(
            week_date=week_date,
            week_key=week_key,
            client_submission_id=_write_ui_client_submission_id(
                context.release_sha, week_key, "write-activation-dark-gate"
            ),
        ),
        bearer=token,
    )
    steps["initial_dark_gate"] = validate_w2_write_disabled_result(
        dark_probe.status,
        dark_probe.body,
        dark_probe.headers,
    )
    after_rate: dict | None = None
    after_rate_started_at: float | None = None
    after_rate_completed_at: float | None = None
    after_rate_completed_monotonic_ms: int | None = None

    def capture_rate_after_browser() -> None:
        nonlocal after_rate, after_rate_started_at, after_rate_completed_at
        nonlocal after_rate_completed_monotonic_ms
        after_rate_started_at = time.monotonic()
        after_rate = _snapshot_planning_depth_rate_keys(context)
        after_rate_completed_at = time.monotonic()
        if (
            type(after_rate_completed_at) not in {int, float}
            or isinstance(after_rate_completed_at, bool)
            or not math.isfinite(after_rate_completed_at)
            or after_rate_completed_at < 0
        ):
            raise StageGateError("write_activation_rate_snapshot_missing")
        try:
            after_rate_completed_monotonic_ms = math.ceil(
                after_rate_completed_at * 1000.0
            )
        except (OverflowError, TypeError, ValueError) as exc:
            raise StageGateError("write_activation_rate_snapshot_missing") from exc
        if after_rate_completed_monotonic_ms < 0:
            raise StageGateError("write_activation_rate_snapshot_missing")

    def capture_bff_dark_probe(fresh_client, fresh_token: str) -> dict:
        restored_probe = fresh_client.request(
            "POST",
            W2_V2_BASE,
            payload=_build_dark_probe_request_v2(
                week_date=week_date,
                week_key=week_key,
                client_submission_id=_write_ui_client_submission_id(
                    context.release_sha, week_key, "write-activation-restored-gate"
                ),
            ),
            bearer=fresh_token,
        )
        evidence = validate_w2_write_disabled_result(
            restored_probe.status,
            restored_probe.body,
            restored_probe.headers,
        )
        steps["restored_dark_gate"] = evidence
        return evidence

    def record_rollback_session(
        session_evidence: dict | None,
        *,
        probe_outcome: str | None = None,
        failed_gate: str | None = None,
        prebuilt_record: dict | None = None,
        primary_error: BaseException | None = None,
    ) -> None:
        record = dict(
            prebuilt_record
            if prebuilt_record is not None
            else session_evidence if isinstance(session_evidence, dict) else {}
        )
        if prebuilt_record is not None:
            phase = record.get("phase")
            expected_keys = {
                "phase",
                "probe_outcome",
                "failed_gate",
                "logout",
                "refresh_revoked",
            }
            if phase == "principal":
                expected_keys.update({"login", "principal"})
            incomplete = (
                set(record) != expected_keys
                or phase not in {"login", "principal"}
                or record.get("probe_outcome") != "not_started"
                or not isinstance(record.get("failed_gate"), str)
                or record.get("logout") != {"accepted": True}
                or not isinstance(record.get("refresh_revoked"), dict)
            )
            if phase == "principal":
                incomplete = incomplete or not isinstance(record.get("login"), dict)
                incomplete = incomplete or not isinstance(record.get("principal"), dict)
        else:
            incomplete = (
                set(record) != {"login", "principal", "logout", "refresh_revoked"}
                or not isinstance(record.get("login"), dict)
                or not isinstance(record.get("principal"), dict)
                or record.get("logout") != {"accepted": True}
                or not isinstance(record.get("refresh_revoked"), dict)
                or probe_outcome not in {"accepted", "failed", "interrupted"}
                or (probe_outcome != "accepted" and not isinstance(failed_gate, str))
            )
        if incomplete:
            if isinstance(primary_error, (KeyboardInterrupt, SystemExit)):
                setattr(
                    primary_error,
                    "rollback_session_evidence",
                    {"complete": False},
                )
                return
            raise StageGateError(
                "write_activation_rollback_session_evidence_incomplete"
            )
        if prebuilt_record is None:
            record["probe_outcome"] = probe_outcome
            if probe_outcome != "accepted":
                record["failed_gate"] = failed_gate
        rollback_operator_sessions.append(record)

    def capture_bff_dark_probe_with_fresh_session() -> dict:
        session_evidence: dict | None = None
        probe_error: BaseException | None = None
        probe_result: dict | None = None
        try:
            with _fresh_write_activation_operator_session(
                context,
                verifier,
                expected_subject=steps["operator_principal"]["subject"],
            ) as (fresh_client, fresh_token, current_session_evidence):
                session_evidence = current_session_evidence
                steps["rollback_operator_session"] = session_evidence
                try:
                    probe_result = capture_bff_dark_probe(fresh_client, fresh_token)
                except BaseException as exc:
                    probe_error = exc
                    raise
        except BaseException as cleanup_error:
            attached_record = getattr(cleanup_error, "rollback_session_record", None)
            if isinstance(attached_record, dict) and probe_error is None:
                record_rollback_session(
                    None,
                    prebuilt_record=attached_record,
                    primary_error=cleanup_error,
                )
            elif probe_error is not None and cleanup_error is probe_error:
                outcome = (
                    "interrupted"
                    if isinstance(probe_error, (KeyboardInterrupt, SystemExit))
                    else "failed"
                )
                record_rollback_session(
                    session_evidence,
                    probe_outcome=outcome,
                    failed_gate=_safe_error_code(probe_error),
                    primary_error=probe_error,
                )
            raise
        record_rollback_session(session_evidence, probe_outcome="accepted")
        return probe_result

    def rollback_session_snapshot() -> list[dict[str, Any]]:
        return [dict(record) for record in rollback_operator_sessions]

    def restore_after_armed_window() -> dict[str, Any]:
        try:
            restoration = _restore_write_activation_dark(
                context,
                bff_dark_probe=capture_bff_dark_probe_with_fresh_session,
            )
        except BaseException as exc:
            restoration = getattr(exc, "restoration", None)
            if isinstance(restoration, dict):
                restoration["rollback_operator_sessions"] = rollback_session_snapshot()
            raise
        restoration["rollback_operator_sessions"] = rollback_session_snapshot()
        return restoration

    try:
        _restart_bff_with_flag(context, enabled=True)
        steps["armed_frontend_build"] = _build_frontend(
            context,
            control_plan_reads=False,
            water_planning_v2=True,
            water_planning_submit=True,
            run_tests=False,
            build_label="write-activation-armed",
        )
        with _frontend_server(
            context,
            control_plan_reads=False,
            water_planning_v2=True,
            water_planning_submit=True,
            server_label="write-activation-armed",
        ):
            steps["write_browser"] = _run_write_browser(
                context,
                week_key=week_key,
                week_date=week_date,
                stage="LOCAL-WRITE-ACT-1",
                healthy_boundary_probe=capture_rate_after_browser,
            )
            steps["stability"] = _observe_write_activation_stability(
                duration_seconds=900,
                interval_seconds=30,
            )
    except BaseException as primary:
        restoration = restore_after_armed_window()
        setattr(primary, "restoration", restoration)
        if isinstance(primary, Exception) and not restoration["restored"]:
            combined = StageGateError(
                f"{_safe_error_code(primary)}_and_write_activation_restore_failed"
            )
            combined.restoration = restoration
            raise combined from primary
        raise

    restoration = restore_after_armed_window()
    if not restoration["restored"]:
        error = StageGateError("write_activation_restoration_failed")
        error.restoration = restoration
        raise error
    steps["restoration"] = restoration
    steps["restored_write_flag"] = validate_write_flag_is_dark(
        _load_env_file(context.runtime_env_dir / "bff.env").get(
            "PLANNING_DEPTH_WRITES_ENABLED", ""
        )
    )
    with _fresh_write_activation_operator_session(
        context,
        verifier,
        expected_subject=steps["operator_principal"]["subject"],
    ) as (readback_client, readback_token, session_evidence):
        steps["readback_operator_session"] = session_evidence
        active_after_rollback = readback_client.request(
            "GET",
            (
                f"{W2_V2_BASE}/active?project_key=mun-bon&"
                f"calendar_system=rid-irrigation-v1&week_key={week_key}"
            ),
            bearer=readback_token,
        )
        steps["active_after_rollback"] = validate_w2_active_result(
            active_after_rollback.status,
            active_after_rollback.body,
            active_after_rollback.headers,
            submission_id=steps["write_browser"]["correct_result"]["submission_id"],
            expected_count=PERSIST_ONLY_EXPECTED_VALUE_COUNT,
            expected_zone_depths={
                f"01-{zone:02d}": 260.0 + 10.0 * (zone - 1) for zone in range(1, 7)
            },
        )
    steps["runtime_restoration"] = _verify_write_activation_restoration(
        context,
        before_dark=before_dark,
        model_release=model_release,
        before_listeners=before_listeners,
    )
    after_snapshot = _take_persist_snapshot(context)
    steps["persist_snapshot_sha256"] = _canonical_json_sha256(after_snapshot)
    if after_rate is None:
        raise StageGateError("write_activation_rate_snapshot_missing")
    if after_rate_started_at is None:
        raise StageGateError("write_activation_rate_snapshot_missing")
    if after_rate_completed_at is None:
        raise StageGateError("write_activation_rate_snapshot_missing")
    if after_rate_completed_monotonic_ms is None:
        raise StageGateError("write_activation_rate_snapshot_missing")
    elapsed_ms = _rate_snapshot_elapsed_ms(
        before_rate_completed_at, after_rate_started_at
    )
    try:
        current_monotonic = time.monotonic()
        minimum_elapsed_seconds = current_monotonic - after_rate_completed_at
        minimum_elapsed_ms = math.floor(minimum_elapsed_seconds * 1000.0)
        timing_is_valid = (
            math.isfinite(current_monotonic)
            and math.isfinite(after_rate_completed_at)
            and math.isfinite(minimum_elapsed_seconds)
            and minimum_elapsed_seconds >= 0
            and minimum_elapsed_ms >= 0
        )
    except (TypeError, ValueError, OverflowError):
        timing_is_valid = False
    if not timing_is_valid:
        raise StageGateError("write_activation_rate_snapshot_missing")
    configured_window_ms = _planning_depth_write_window_ms(context)
    steps["rate_state_after_browser"] = {
        "configured_window_ms": configured_window_ms,
        "minimum_elapsed_ms": minimum_elapsed_ms,
        "snapshot_completed_monotonic_ms": after_rate_completed_monotonic_ms,
        "snapshot": after_rate,
    }
    steps["persisted_diff"] = validate_write_activation_diff(
        before_snapshot,
        after_snapshot,
        browser_result=steps["write_browser"],
        target_week_key=week_key,
        target_week_date=week_date,
        expected_submitted_by=steps["operator_principal"]["subject"],
    )
    rate_accounting = validate_persist_only_rate_accounting(
        before_rate,
        after_rate,
        expected_increment=3,
        configured_window_ms=configured_window_ms,
        elapsed_ms=elapsed_ms,
        expected_operator_key=_planning_depth_rate_key(
            steps["operator_principal"]["subject"]
        ),
    )
    if "operator_rate_key" in rate_accounting:
        rate_accounting["elapsed_ms"] = elapsed_ms
    steps["rate_accounting"] = rate_accounting
    steps["aws_actions"] = False
    return steps


def _assert_operator_refresh_reuse_rejected(client, refresh_token: str) -> dict:
    """Prove the logout actually revoked the session.

    Central auth revokes rather than deletes the refresh token, so the only
    observable proof that the session is gone is that reusing the token now
    fails. Any other status -- including a fresh 200 -- fails the stage.
    """
    response = client.request(
        "POST",
        "http://127.0.0.1:3005/api/v1/auth/refresh",
        payload={"refreshToken": refresh_token},
    )
    if response.status != 401:
        raise StageGateError("write_ui_refresh_reuse_not_rejected")
    return {"refresh_reuse_status": 401, "revoked": True}


def _write_local_write_ui_manifest(
    context: StageContext,
    steps: dict[str, Any],
    *,
    diagnostic: bool,
) -> dict:
    stage = WRITE_UI_DIAGNOSTIC_STAGE if diagnostic else "LOCAL-WRITE-UI-1"
    manifest = {
        "stage": stage,
        "verdict": "DIAGNOSTIC_PASS" if diagnostic else "PASS",
        "release_sha": context.release_sha,
        "frontend_sha": context.frontend_sha,
        "completed_at": _utc_timestamp(),
        "steps": steps,
    }
    if diagnostic:
        manifest["acceptance_evidence"] = False
    validate_evidence_payload(manifest)
    target = context.evidence_root / f"{stage}.json"
    clear_failure_manifest(context.evidence_root, stage)
    write_stage_manifest(target, manifest)
    _checksum_manifest(target)
    if not diagnostic:
        _save_state(context, list(STAGE_ORDER[:8]))
    print(f"PASS {stage}")
    return manifest


def _verify_write_ui_diagnostic_isolation(context: StageContext) -> None:
    if os.uname().nodename == ACCEPTANCE_MACHINE_NAME:
        raise StageGateError("write_ui_diagnostic_machine_not_isolated")
    if (
        context.evidence_root.resolve() == DEFAULT_ACCEPTANCE_EVIDENCE_ROOT.resolve()
        or (context.evidence_root / "stage-state.json").exists()
    ):
        raise StageGateError("write_ui_diagnostic_evidence_not_isolated")


def _run_local_write_ui_authenticated(
    context: StageContext, client, token: str, login_evidence: dict
) -> dict[str, Any]:
    week_date, week_key = _write_ui_rid_week(context.as_of_date)
    steps: dict[str, Any] = {
        "login": login_evidence,
        "target_week": {"week_date": week_date, "week_key": week_key},
    }

    steps["write_flag_dark"] = validate_write_flag_is_dark(
        _load_env_file(context.runtime_env_dir / "bff.env").get(
            "PLANNING_DEPTH_WRITES_ENABLED", ""
        )
    )

    dark_probe = client.request(
        "POST",
        W2_V2_BASE,
        payload=_build_dark_probe_request_v2(
            week_date=week_date,
            week_key=week_key,
            client_submission_id=_write_ui_client_submission_id(
                context.release_sha, week_key, "dark-gate"
            ),
        ),
        bearer=token,
    )
    steps["w2_v2_dark_gate"] = validate_w2_write_disabled_result(
        dark_probe.status, dark_probe.body, dark_probe.headers
    )

    frontend_restored = False
    bff_restored = False
    try:
        _restart_bff_with_flag(context, enabled=True)

        _build_frontend(
            context,
            control_plan_reads=False,
            water_planning_v2=True,
            water_planning_submit=True,
            run_tests=False,
            build_label="write-ui-armed",
        )

        with _frontend_server(
            context,
            control_plan_reads=False,
            water_planning_v2=True,
            water_planning_submit=True,
            server_label="write-ui-armed",
        ):
            steps["write_browser"] = _run_write_browser(
                context,
                week_key=week_key,
                week_date=week_date,
            )
    finally:
        try:
            _build_frontend(
                context,
                control_plan_reads=False,
                run_tests=False,
                build_label="write-ui-restored",
            )
            frontend_restored = True
        except Exception:
            pass
        try:
            _restart_bff_with_flag(context, enabled=False)
            bff_restored = True
        except Exception:
            pass

    if not frontend_restored or not bff_restored:
        raise StageGateError("write_ui_restoration_failed")

    steps["restored_write_flag"] = validate_write_flag_is_dark(
        _load_env_file(context.runtime_env_dir / "bff.env").get(
            "PLANNING_DEPTH_WRITES_ENABLED", ""
        )
    )

    restored_dark_probe = client.request(
        "POST",
        W2_V2_BASE,
        payload=_build_dark_probe_request_v2(
            week_date=week_date,
            week_key=week_key,
            client_submission_id=_write_ui_client_submission_id(
                context.release_sha, week_key, "restored-gate"
            ),
        ),
        bearer=token,
    )
    steps["w2_v2_restored_gate"] = validate_w2_write_disabled_result(
        restored_dark_probe.status,
        restored_dark_probe.body,
        restored_dark_probe.headers,
    )

    steps["aws_actions"] = False
    return steps


def run_local_write_ui(context: StageContext, *, diagnostic: bool = False) -> dict:
    if diagnostic:
        _verify_write_ui_diagnostic_isolation(context)
        _clear_checksum_artifact(
            context.evidence_root,
            f"{WRITE_UI_DIAGNOSTIC_STAGE}.json",
        )
        _clear_checksum_artifact(
            context.evidence_root,
            "LOCAL-WRITE-UI-1-browser-result.json",
        )
        _verify_source_checkouts(context)
    else:
        state = _load_state(context)
        validate_stage_transition(tuple(state["completed"]), "LOCAL-WRITE-UI-1")
        _clear_checksum_artifact(
            context.evidence_root,
            "LOCAL-WRITE-UI-1-browser-result.json",
        )

    _verify_frontend_source(context)
    verifier = _load_harness_module(
        context,
        "verify_bearer.py",
        "local_write_ui_bearer_verifier",
    )
    client = LocalHttpClient()
    token, refresh_cookie, login_evidence = _login_operator(
        context,
        client,
        verifier,
    )
    try:
        steps = _run_local_write_ui_authenticated(
            context,
            client,
            token,
            login_evidence,
        )
    except BaseException:
        _operator_logout(
            client,
            refresh_cookie,
            strict=False,
            error_code="write_ui_operator_logout_failed",
        )
        raise
    _operator_logout(
        client,
        refresh_cookie,
        strict=True,
        error_code="write_ui_operator_logout_failed",
    )
    steps["refresh_revoked"] = _assert_operator_refresh_reuse_rejected(
        client, refresh_cookie
    )
    return _write_local_write_ui_manifest(context, steps, diagnostic=diagnostic)


# --- LOCAL-PERSIST-ONLY-1 helpers ---


# The submit path writes ONLY water_planning.planning_depth_{submissions,values}
# (the only two tables in that schema). Persist-only therefore proves EVERY base
# table in ros_gis + scheduler is byte-identical before and after -- dynamically
# enumerated so a newly-migrated table cannot slip past a hand-picked list.
PERSIST_ONLY_EXPECTED_NON_W2_TABLES = frozenset(
    {
        "ros_gis.daily_water_requirements",
        "ros_gis.dataset_versions",
        "ros_gis.gate_mapping_history",
        "ros_gis.section_crop_settings",
        "ros_gis.section_master_history",
        "ros_gis.water_requirement_contributions",
        "ros_gis.water_requirement_runs",
        "scheduler.control_active_gate_authority",
        "scheduler.control_authority_grant_events",
        "scheduler.control_authority_grants",
        "scheduler.control_command_execution_events",
        "scheduler.control_command_execution_receipts",
        "scheduler.control_command_outbox",
        "scheduler.control_command_validation_receipts",
        "scheduler.control_gate_readback_observations",
        "scheduler.control_plan_campaign_versions",
        "scheduler.control_plan_requirements",
        "scheduler.control_plan_runs",
        "scheduler.control_state_transitions",
        "scheduler.gate_plan_events",
        "scheduler.section_delivery_ledger",
    }
)

_QUALIFIED_TABLE_RE = re.compile(r"[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*")

PERSIST_ONLY_EXPECTED_VALUE_COUNT = 41

RATE_KEY_PATTERN = "bff-water-planning:rate:planning_depth.submit:*"
_RATE_KEY_RE = re.compile(
    r"bff-water-planning:rate:planning_depth\.submit:[0-9a-f]{64}"
)
# Allow only a small boundary-measurement margin when proving that an old
# Redis window could have expired between the two atomic snapshots.
_RATE_ELAPSED_MEASUREMENT_TOLERANCE_MS = 100.0


def _planning_depth_rate_key(subject: str) -> str:
    if not isinstance(subject, str) or not subject:
        raise StageGateError("persist_only_rate_subject_invalid")
    try:
        digest = hashlib.sha256(subject.encode("utf-8")).hexdigest()
    except (UnicodeEncodeError, TypeError) as exc:
        raise StageGateError("persist_only_rate_subject_invalid") from exc
    return "bff-water-planning:rate:planning_depth.submit:" + digest


# One EVAL == one atomic Redis read. Each triple is emitted as key<TAB>value<TAB>
# pttl on its own line so an integer counter can never be confused for a blank
# line, and a missing/nil value is impossible for these keys.
_RATE_SNAPSHOT_LUA = (
    "local out = {} "
    "local keys = redis.call('KEYS', ARGV[1]) "
    "for i, k in ipairs(keys) do "
    "local v = redis.call('GET', k) "
    "local t = redis.call('PTTL', k) "
    "out[#out+1] = k .. '\\t' .. tostring(v) .. '\\t' .. tostring(t) "
    "end "
    "return table.concat(out, '\\n')"
)


def _rate_snapshot_elapsed_ms(started_at: float, ended_at: float) -> float:
    return max(0.0, (ended_at - started_at) * 1000.0)


def _sql_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _persist_snapshot_table_digest_sql(table: str) -> str:
    if not _QUALIFIED_TABLE_RE.fullmatch(table):
        raise StageGateError("persist_only_table_name_invalid")
    # Deterministic full-row digest: md5 over the per-row md5 of the row's
    # canonical jsonb text, ordered by that same text. to_jsonb captures EVERY
    # column (incl. mutable status/hash fields), jsonb text is normalized, and
    # ordering by the row text is a total order needing no per-table primary key.
    # An empty table collapses to md5('').
    return (
        "(SELECT md5(coalesce(string_agg(md5(to_jsonb(t)::text), '' "
        f"ORDER BY to_jsonb(t)::text), '')) FROM {table} t)"
    )


def _build_persist_snapshot_sql(tables: list[str]) -> str:
    digest_pairs = ", ".join(
        f"{_sql_string_literal(table)}, {_persist_snapshot_table_digest_sql(table)}"
        for table in tables
    )
    # One statement == one MVCC snapshot: the non-W2 digests and the full W2 rows
    # are all read from a single consistent view of the database.
    return (
        "SELECT json_build_object("
        f"'non_w2_digests', json_build_object({digest_pairs}), "
        "'w2_submissions', (SELECT coalesce("
        "json_agg(to_jsonb(s) ORDER BY s.submission_id), '[]'::json) "
        "FROM water_planning.planning_depth_submissions s), "
        "'w2_values', (SELECT coalesce("
        "json_agg(to_jsonb(v) ORDER BY v.submission_id, v.section_id), '[]'::json) "
        "FROM water_planning.planning_depth_values v))::text"
    )


def _persist_only_enumerate_tables(context: StageContext) -> list[str]:
    raw = _psql(
        context,
        "SELECT table_schema || '.' || table_name "
        "FROM information_schema.tables "
        "WHERE table_schema IN ('ros_gis', 'scheduler') "
        "AND table_type = 'BASE TABLE' "
        "ORDER BY 1",
    )
    tables = [line.strip() for line in raw.splitlines() if line.strip()]
    if not PERSIST_ONLY_EXPECTED_NON_W2_TABLES.issubset(tables):
        raise StageGateError("persist_only_table_missing")
    for table in tables:
        if not _QUALIFIED_TABLE_RE.fullmatch(table):
            raise StageGateError("persist_only_table_name_invalid")
    return tables


def _persist_snapshot_psql(context: StageContext, sql: str) -> Any:
    postgres_url = _load_env_file(context.runtime_env_dir / "bff.env")["POSTGRES_URL"]
    env = _postgres_process_env(postgres_url)
    # Pin timezone so any timestamptz column serializes identically across reads.
    env["PGOPTIONS"] = env["PGOPTIONS"] + " -c timezone=UTC -c extra_float_digits=3"
    raw = _run_checked(
        "persist_only_snapshot",
        ["psql", "--no-psqlrc", "-X", "-At", "-c", sql],
        env=env,
        timeout=30,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StageGateError("persist_only_snapshot_unparseable") from exc


def _take_persist_snapshot(context: StageContext) -> dict:
    tables = _persist_only_enumerate_tables(context)
    document = _persist_snapshot_psql(context, _build_persist_snapshot_sql(tables))
    if (
        not isinstance(document, dict)
        or not isinstance(document.get("non_w2_digests"), dict)
        or not isinstance(document.get("w2_submissions"), list)
        or not isinstance(document.get("w2_values"), list)
    ):
        raise StageGateError("persist_only_snapshot_malformed")
    return document


def _zone_depths_from_request(request: dict) -> dict[str, float]:
    return {
        str(level["area_id"]): float(level["planning_depth_mm"])
        for level in request["levels"]
    }


def _assert_receipt_bound_submission(
    row: dict,
    receipt: dict,
    *,
    week_key: str,
    week_date: str,
    expected_supersedes: str | None,
) -> None:
    roster_id = row.get("roster_dataset_version_id")
    roster_hash = row.get("roster_source_hash")
    expanded = row.get("expanded_sha256")
    ok = (
        row.get("submission_id") == receipt["submission_id"]
        and row.get("client_submission_id") == receipt["client_submission_id"]
        and row.get("request_sha256") == receipt["request_sha256"]
        and row.get("submitted_by") == receipt["submitted_by"]
        and row.get("project_key") == "mun-bon"
        and row.get("calendar_system") == "rid-irrigation-v1"
        and row.get("week_key") == week_key
        and row.get("week_date") == week_date
        and row.get("schema_version") == 2
        and row.get("supersedes_submission_id") == expected_supersedes
        and isinstance(roster_id, int)
        and roster_id > 0
        and isinstance(roster_hash, str)
        and bool(re.fullmatch(r"[0-9a-f]{64}", roster_hash))
        and isinstance(expanded, str)
        and bool(re.fullmatch(r"[0-9a-f]{64}", expanded))
        # the receipt itself must agree with the same target + supersede chain
        and receipt.get("week_key") == week_key
        and receipt.get("week_date") == week_date
        and receipt.get("calendar_system") == "rid-irrigation-v1"
        and receipt.get("supersedes_submission_id") == expected_supersedes
    )
    if not ok:
        raise StageGateError("persist_only_w2_shape_unexpected")


def _assert_expanded_values(rows: list[dict], zone_depths: dict[str, float]) -> None:
    zones_seen = set()
    for row in rows:
        zone_id = row.get("zone_id")
        section_id = row.get("section_id")
        depth = row.get("planning_depth_mm")
        if (
            zone_id not in zone_depths
            or not isinstance(section_id, str)
            or not section_id.startswith(f"{zone_id}-")
            or row.get("source_kind") != "zone_default"
            or row.get("source_area_id") != zone_id
            or depth is None
            or abs(float(depth) - zone_depths[zone_id]) > 1e-6
        ):
            raise StageGateError("persist_only_w2_shape_unexpected")
        zones_seen.add(zone_id)
    if zones_seen != set(zone_depths):
        raise StageGateError("persist_only_w2_shape_unexpected")


def validate_persist_only_diff(
    before: dict,
    after: dict,
    *,
    create_receipt: dict,
    correct_receipt: dict,
    target_week_key: str,
    target_week_date: str,
    create_zone_depths: dict[str, float],
    correct_zone_depths: dict[str, float],
) -> dict:
    # 1. NON-W2: every enumerated table digest must be identical. In the isolated
    #    guest ANY add/remove/mutation is a real side effect, not tolerated.
    before_digests = before["non_w2_digests"]
    after_digests = after["non_w2_digests"]
    if set(before_digests) != set(after_digests):
        raise StageGateError("persist_only_side_effect_detected")
    for table in sorted(before_digests):
        if before_digests[table] != after_digests[table]:
            raise StageGateError("persist_only_side_effect_detected")

    # 2. W2 SUBMISSIONS: pre-existing rows byte-identical; the new set is exactly
    #    the two receipts; each new row is bound to its receipt + scope + chain.
    before_subs = {row["submission_id"]: row for row in before["w2_submissions"]}
    after_subs = {row["submission_id"]: row for row in after["w2_submissions"]}
    if set(before_subs) - set(after_subs):
        raise StageGateError("persist_only_w2_existing_mutated")
    for sid, row in before_subs.items():
        if after_subs[sid] != row:
            raise StageGateError("persist_only_w2_existing_mutated")
    create_id = create_receipt["submission_id"]
    correct_id = correct_receipt["submission_id"]
    new_sub_ids = set(after_subs) - set(before_subs)
    if new_sub_ids != {create_id, correct_id} or create_id == correct_id:
        raise StageGateError("persist_only_w2_shape_unexpected")
    _assert_receipt_bound_submission(
        after_subs[create_id],
        create_receipt,
        week_key=target_week_key,
        week_date=target_week_date,
        expected_supersedes=None,
    )
    _assert_receipt_bound_submission(
        after_subs[correct_id],
        correct_receipt,
        week_key=target_week_key,
        week_date=target_week_date,
        expected_supersedes=create_id,
    )
    if (
        after_subs[create_id]["expanded_sha256"]
        == after_subs[correct_id]["expanded_sha256"]
    ):
        raise StageGateError("persist_only_w2_shape_unexpected")

    # 3. W2 VALUES: pre-existing rows byte-identical; exactly 41 new rows per new
    #    submission (82 total), each expanded value bound to its zone's depth.
    def value_key(row: dict) -> tuple:
        return (row["submission_id"], row["section_id"])

    before_vals = {value_key(row): row for row in before["w2_values"]}
    after_vals = {value_key(row): row for row in after["w2_values"]}
    if set(before_vals) - set(after_vals):
        raise StageGateError("persist_only_w2_existing_mutated")
    for key, row in before_vals.items():
        if after_vals[key] != row:
            raise StageGateError("persist_only_w2_existing_mutated")
    new_value_keys = set(after_vals) - set(before_vals)
    grouped: dict[str, list[dict]] = {create_id: [], correct_id: []}
    for key in new_value_keys:
        submission_id = key[0]
        if submission_id not in grouped:
            raise StageGateError("persist_only_w2_shape_unexpected")
        grouped[submission_id].append(after_vals[key])
    if (
        len(new_value_keys) != 2 * PERSIST_ONLY_EXPECTED_VALUE_COUNT
        or len(grouped[create_id]) != PERSIST_ONLY_EXPECTED_VALUE_COUNT
        or len(grouped[correct_id]) != PERSIST_ONLY_EXPECTED_VALUE_COUNT
    ):
        raise StageGateError("persist_only_w2_shape_unexpected")
    _assert_expanded_values(grouped[create_id], create_zone_depths)
    _assert_expanded_values(grouped[correct_id], correct_zone_depths)

    return {
        "non_w2_tables_unchanged": len(after_digests),
        "w2_submissions_added": sorted(new_sub_ids),
        "w2_values_added": len(new_value_keys),
        "supersedes_chain": {create_id: None, correct_id: create_id},
    }


def _canonical_write_request_document(request: dict) -> tuple[str, str]:
    levels = []
    for level in sorted(
        request["levels"],
        key=lambda item: (item["area_type"], item["area_id"]),
    ):
        levels.append(
            {
                "area_id": level["area_id"],
                "area_type": level["area_type"],
                "planning_depth_mm": f'{float(level["planning_depth_mm"]):.3f}',
            }
        )
    text = json.dumps(
        {
            "calendar_system": request["calendar_system"],
            "levels": levels,
            "project_key": request["project_key"],
            "schema_version": request["schema_version"],
            "week_date": request["week_date"],
            "week_key": request["week_key"],
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_write_expanded_sha256(rows: list[dict]) -> str:
    value = [
        {
            "planning_depth_mm": f'{float(row["planning_depth_mm"]):.3f}',
            "section_id": row["section_id"],
            "source_area_id": row["source_area_id"],
            "source_kind": row["source_kind"],
            "zone_id": row["zone_id"],
        }
        for row in sorted(rows, key=lambda row: row["section_id"])
    ]
    text = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_write_activation_diff(
    before: dict,
    after: dict,
    *,
    browser_result: dict,
    target_week_key: str,
    target_week_date: str,
    expected_submitted_by: str,
) -> dict:
    before_digests = before["non_w2_digests"]
    after_digests = after["non_w2_digests"]
    if before_digests != after_digests:
        raise StageGateError("write_activation_side_effect_detected")

    before_submissions = {row["submission_id"]: row for row in before["w2_submissions"]}
    after_submissions = {row["submission_id"]: row for row in after["w2_submissions"]}
    if any(
        after_submissions.get(key) != row for key, row in before_submissions.items()
    ):
        raise StageGateError("write_activation_w2_existing_mutated")

    try:
        create_id = str(UUID(str(browser_result["create_result"]["submission_id"])))
        correct_id = str(UUID(str(browser_result["correct_result"]["submission_id"])))
        create_request = browser_result["request_identity"]["create"]
        correct_request = browser_result["request_identity"]["correct"]
        roster_provenance = browser_result["roster_provenance"]
        roster_dataset_version_id = roster_provenance["dataset_version_id"]
        roster_source_hash = roster_provenance["source_hash"]
        create_document, create_request_sha256 = _canonical_write_request_document(
            create_request
        )
        correct_document, correct_request_sha256 = _canonical_write_request_document(
            correct_request
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise StageGateError("write_activation_w2_shape_unexpected") from exc
    if (
        not _write_browser_request_matches(
            create_request,
            base_depth=250.0,
            expected_active_submission_id=None,
        )
        or not _write_browser_request_matches(
            correct_request,
            base_depth=260.0,
            expected_active_submission_id=create_id,
        )
        or create_request["week_key"] != target_week_key
        or correct_request["week_key"] != target_week_key
        or create_request["week_date"] != target_week_date
        or correct_request["week_date"] != target_week_date
        or create_request["client_submission_id"]
        == correct_request["client_submission_id"]
        or type(roster_dataset_version_id) is not int
        or roster_dataset_version_id < 1
        or not isinstance(roster_source_hash, str)
        or not re.fullmatch(r"[0-9a-f]{64}", roster_source_hash)
        or not isinstance(expected_submitted_by, str)
        or not expected_submitted_by
    ):
        raise StageGateError("write_activation_w2_shape_unexpected")
    new_submission_ids = set(after_submissions) - set(before_submissions)
    if create_id == correct_id or new_submission_ids != {create_id, correct_id}:
        raise StageGateError("write_activation_w2_shape_unexpected")

    for submission_id, supersedes, request, request_document, request_sha256 in (
        (
            create_id,
            None,
            create_request,
            create_document,
            create_request_sha256,
        ),
        (
            correct_id,
            create_id,
            correct_request,
            correct_document,
            correct_request_sha256,
        ),
    ):
        row = after_submissions[submission_id]
        client_submission_id = row.get("client_submission_id")
        try:
            canonical_client_id = str(UUID(str(client_submission_id)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise StageGateError("write_activation_w2_shape_unexpected") from exc
        if (
            canonical_client_id != client_submission_id
            or client_submission_id != request["client_submission_id"]
            or row.get("project_key") != "mun-bon"
            or row.get("calendar_system") != "rid-irrigation-v1"
            or row.get("week_key") != target_week_key
            or row.get("week_date") != target_week_date
            or row.get("schema_version") != 2
            or row.get("supersedes_submission_id") != supersedes
            or row.get("submitted_by") != expected_submitted_by
            or row.get("roster_dataset_version_id") != roster_dataset_version_id
            or row.get("roster_source_hash") != roster_source_hash
            or row.get("request_document_text") != request_document
            or row.get("request_sha256") != request_sha256
            or not isinstance(row.get("expanded_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", row["expanded_sha256"])
        ):
            raise StageGateError("write_activation_w2_shape_unexpected")
    if (
        after_submissions[create_id]["expanded_sha256"]
        == after_submissions[correct_id]["expanded_sha256"]
    ):
        raise StageGateError("write_activation_w2_shape_unexpected")

    def value_key(row: dict) -> tuple:
        return (row["submission_id"], row["section_id"])

    before_values = {value_key(row): row for row in before["w2_values"]}
    after_values = {value_key(row): row for row in after["w2_values"]}
    if any(after_values.get(key) != row for key, row in before_values.items()):
        raise StageGateError("write_activation_w2_existing_mutated")
    new_value_keys = set(after_values) - set(before_values)
    grouped: dict[str, list[dict]] = {create_id: [], correct_id: []}
    for key in new_value_keys:
        if key[0] not in grouped:
            raise StageGateError("write_activation_w2_shape_unexpected")
        grouped[key[0]].append(after_values[key])
    if len(new_value_keys) != 2 * PERSIST_ONLY_EXPECTED_VALUE_COUNT or any(
        len(rows) != PERSIST_ONLY_EXPECTED_VALUE_COUNT for rows in grouped.values()
    ):
        raise StageGateError("write_activation_w2_shape_unexpected")

    expected_depths = (
        {f"01-{zone:02d}": 250.0 + 10.0 * (zone - 1) for zone in range(1, 7)},
        {f"01-{zone:02d}": 260.0 + 10.0 * (zone - 1) for zone in range(1, 7)},
    )
    try:
        _assert_expanded_values(grouped[create_id], expected_depths[0])
        _assert_expanded_values(grouped[correct_id], expected_depths[1])
        if after_submissions[create_id][
            "expanded_sha256"
        ] != _canonical_write_expanded_sha256(grouped[create_id]) or after_submissions[
            correct_id
        ][
            "expanded_sha256"
        ] != _canonical_write_expanded_sha256(
            grouped[correct_id]
        ):
            raise StageGateError("write_activation_w2_shape_unexpected")
    except StageGateError as exc:
        raise StageGateError("write_activation_w2_shape_unexpected") from exc
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise StageGateError("write_activation_w2_shape_unexpected") from exc

    return {
        "non_w2_tables_unchanged": len(after_digests),
        "w2_submissions_added": sorted(new_submission_ids),
        "w2_values_added": len(new_value_keys),
        "supersedes_chain": {create_id: None, correct_id: create_id},
    }


def _parse_rate_key_snapshot(raw: str) -> dict:
    snapshot: dict[str, dict[str, int]] = {}
    for line in raw.split("\n"):
        line = line.strip("\r")
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise StageGateError("persist_only_rate_snapshot_unparseable")
        key, value, pttl = parts
        try:
            snapshot[key] = {"value": int(value), "ttl_ms": int(pttl)}
        except ValueError as exc:
            raise StageGateError("persist_only_rate_snapshot_unparseable") from exc
    return snapshot


def _snapshot_planning_depth_rate_keys(context: StageContext) -> dict:
    redis_url = _load_env_file(context.runtime_env_dir / "bff.env")["REDIS_URL"]
    parsed = urlsplit(redis_url)
    database = parsed.path.lstrip("/") or "0"
    if (
        parsed.scheme not in {"redis", "rediss"}
        or parsed.hostname != "127.0.0.1"
        or not database.isdigit()
    ):
        raise StageGateError("persist_only_rate_url_invalid")
    # Select the db explicitly and pass the password via REDISCLI_AUTH -- never on
    # the argv (process listing) -- mirroring how _psql keeps PGPASSWORD in env.
    from urllib.parse import unquote

    env = {**os.environ}
    if parsed.password:
        env["REDISCLI_AUTH"] = unquote(parsed.password)
    raw = _run_checked(
        "persist_only_rate_snapshot",
        [
            "redis-cli",
            "-h",
            parsed.hostname,
            "-p",
            str(parsed.port or 6379),
            "-n",
            database,
            "--raw",
            "EVAL",
            _RATE_SNAPSHOT_LUA,
            "0",
            RATE_KEY_PATTERN,
        ],
        env=env,
        timeout=30,
    )
    return _parse_rate_key_snapshot(raw)


def _rc_database_clean(context: StageContext) -> bool:
    query = """
SELECT (
    to_regnamespace('scheduler') IS NULL
    AND to_regnamespace('ros_gis') IS NULL
    AND to_regnamespace('water_planning') IS NULL
    AND to_regnamespace('gis') IS NULL
)::text;
"""
    try:
        result = _psql(context, query)
    except Exception as exc:
        raise StageGateError("rc_database_not_clean") from exc
    if result.strip() != "t":
        raise StageGateError("rc_database_not_clean")
    return True


def _rc_configured_dark(context: StageContext) -> bool:
    try:
        environments = {
            name: _load_env_file(context.runtime_env_dir / f"{name}.env")
            for name in ("flow", "scheduler", "ros", "bff")
        }
        scheduler = environments["scheduler"]
        ros = environments["ros"]
        if any(
            scheduler.get(name)
            for name in (
                "SCHEDULER_SCADA_BASE_URL",
                "SCHEDULER_SERVICE_JWT_SECRET",
                "SCHEDULER_DEVICE_CAPABILITY_SNAPSHOT_PATH",
            )
        ) or ros.get("REQUIREMENT_SOURCE_POSTGRES_URL"):
            raise ValueError
        if any(
            values.get("ALLOW_MACHINE_COMMANDS") not in (None, "false")
            for values in environments.values()
        ):
            raise ValueError
        sanitized = []
        for name, service in (
            ("flow-monitoring", "flow"),
            ("scheduler", "scheduler"),
            ("ros-gis-integration", "ros"),
            ("bff-water-planning", "bff"),
        ):
            source = environments[service]
            selected = {
                key: source[key]
                for key in GATE_ENV_NAMES
                - {
                    "REQUIREMENT_SOURCE_POSTGRES_URL",
                    "SCHEDULER_SCADA_BASE_URL",
                    "SCHEDULER_SERVICE_JWT_SECRET",
                    "SCHEDULER_DEVICE_CAPABILITY_SNAPSHOT_PATH",
                }
                if key in source
            }
            sanitized.append({"name": name, "pm2_env": {"env": selected, **selected}})
        collect_dark_runtime_contract(
            json.dumps(sanitized, separators=(",", ":")),
            _read_json(
                context.repo_root / "services/flow-monitoring/data/model-releases/"
                "engineering-prior-v5-v1.json"
            ),
        )
        return True
    except (KeyError, TypeError, ValueError, StageGateError) as exc:
        raise StageGateError("rc_runtime_not_dark") from exc


def _rc_preflight_snapshot(context: StageContext) -> dict[str, Any]:
    _verify_source_checkouts(context)
    if _rc_database_clean(context) is not True:
        raise StageGateError("rc_database_not_clean")
    try:
        rate_state = _snapshot_planning_depth_rate_keys(context)
    except Exception as exc:
        raise StageGateError("rc_rate_state_not_clean") from exc
    if rate_state != {}:
        raise StageGateError("rc_rate_state_not_clean")
    try:
        raw_pm2 = json.loads(_pm2_json())
        if not isinstance(raw_pm2, list) or raw_pm2:
            raise ValueError
    except Exception as exc:
        raise StageGateError("rc_runtime_not_clean") from exc
    try:
        listeners = _listener_snapshot()
        if application_port_conflicts(listeners) or unexpected_non_loopback_listeners(
            listeners
        ):
            raise ValueError
    except Exception as exc:
        raise StageGateError("rc_listener_state_not_clean") from exc
    if _rc_configured_dark(context) is not True:
        raise StageGateError("rc_runtime_not_dark")
    return {
        "evidence_root_empty": True,
        "database_clean": True,
        "rate_state_clean": True,
        "actionable_commands": 0,
        "sources_clean": True,
        "runtime_dark": True,
    }


def _rc_preflight_path(context: StageContext) -> Path:
    return context.evidence_root.parent / "LOCAL-RC-1-preflight.json"


def _rc_internal_preflight_attempt(
    context: StageContext,
) -> tuple[dict[str, Any], str] | None:
    path = context.evidence_root / "RC-PREFLIGHT.json"
    if not path.exists():
        return None
    try:
        _verify_checksum_entry(path)
        raw = path.read_bytes()
        if len(raw) > 1024 * 1024:
            raise ValueError
        record = json.loads(raw.decode("utf-8"))
        expected = {
            "schema_version": 1,
            "phase": "preflight",
            "verdict": "PASS",
            "release_sha": context.release_sha,
            "frontend_sha": context.frontend_sha,
            "dependency_sha256": None,
            "guest": None,
            "as_of_date": None,
            "checks": _rc_expected_preflight_checks(),
        }
        if not isinstance(record, dict):
            raise ValueError
        dependency_sha256 = record.get("dependency_sha256")
        guest = record.get("guest")
        as_of_date = record.get("as_of_date")
        captured_at = record.get("captured_at")
        expected["dependency_sha256"] = dependency_sha256
        expected["guest"] = guest
        expected["as_of_date"] = as_of_date
        if (
            set(record) != {*expected, "captured_at"}
            or not isinstance(dependency_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", dependency_sha256)
            or not isinstance(guest, dict)
            or set(guest) != {"name", "id", "architecture", "machine_id"}
            or guest.get("name") != ACCEPTANCE_MACHINE_NAME
            or not isinstance(guest.get("id"), str)
            or not re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{26}", guest["id"])
            or guest.get("architecture") != "arm64"
            or not isinstance(guest.get("machine_id"), str)
            or not re.fullmatch(r"[0-9a-f]{32}", guest["machine_id"])
            or not isinstance(as_of_date, str)
            or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", as_of_date)
            or not isinstance(captured_at, str)
            or not re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
                captured_at,
            )
            or record != {**expected, "captured_at": captured_at}
            or raw
            != (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8")
        ):
            raise ValueError
        if (
            datetime.strptime(captured_at, "%Y-%m-%dT%H:%M:%SZ").strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            != captured_at
        ):
            raise ValueError
        validate_evidence_payload(record)
        return record, hashlib.sha256(raw).hexdigest()
    except (
        OSError,
        UnicodeDecodeError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        StageGateError,
    ) as exc:
        raise StageGateError("rc_stage_attempt_identity_mismatch") from exc


def _rc_stage_attempt_from_record(
    record: dict[str, Any], preflight_sha256: str, as_of_date: str
) -> dict[str, Any]:
    return {
        "preflight_sha256": preflight_sha256,
        "dependency_sha256": record["dependency_sha256"],
        "guest": record["guest"],
        "as_of_date": as_of_date,
    }


def _rc_stage_attempt(
    context: StageContext, expected_machine_id: str | None
) -> dict[str, Any] | None:
    internal = _rc_internal_preflight_attempt(context)
    if internal is None:
        if expected_machine_id is not None:
            raise StageGateError("rc_stage_attempt_identity_mismatch")
        return None
    record, preflight_sha256 = internal
    attempt = _rc_stage_attempt_from_record(
        record, preflight_sha256, context.as_of_date.isoformat()
    )
    error = None
    if context.execution_kind != "canonical":
        error = StageGateError("rc_stage_attempt_identity_mismatch")
    elif not isinstance(expected_machine_id, str) or not re.fullmatch(
        r"[0-9a-f]{32}", expected_machine_id
    ):
        error = StageGateError("rc_stage_attempt_identity_mismatch")
    elif record["as_of_date"] != context.as_of_date.isoformat():
        error = StageGateError("rc_stage_attempt_identity_mismatch")
    elif record["guest"].get("machine_id") != expected_machine_id:
        error = StageGateError("rc_stage_attempt_identity_mismatch")
    if error is not None:
        error.rc_attempt = attempt
        raise error
    return attempt


def _bind_rc_stage_attempt(
    context: StageContext, stage: str, attempt: dict[str, Any]
) -> None:
    path = context.evidence_root / f"{stage}.json"
    try:
        _verify_checksum_entry(path)
        manifest = _read_json(path)
        if (
            manifest.get("stage") != stage
            or manifest.get("verdict") != "PASS"
            or manifest.get("release_sha", manifest.get("backend_sha"))
            != context.release_sha
            or manifest.get("frontend_sha") != context.frontend_sha
        ):
            raise ValueError
        manifest["rc_attempt"] = attempt
        write_stage_manifest(path, manifest)
        _checksum_manifest(path)
    except BaseException as exc:
        try:
            _discard_rc_stage_artifact(context, stage)
        except (KeyboardInterrupt, SystemExit):
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise exc
            raise
        except BaseException:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise exc
            raise
        if isinstance(exc, (OSError, TypeError, ValueError, StageGateError)):
            raise StageGateError("rc_stage_attempt_identity_mismatch") from exc
        raise


def _cleanup_rc_preflight_publication(
    internal_paths: tuple[Path, ...],
    external_path: Path | None = None,
) -> None:
    try:
        paths = internal_paths
        if external_path is not None and external_path.exists():
            paths = (*paths, external_path)
        for path in paths:
            path.unlink(missing_ok=True)
            if path.exists():
                raise OSError(f"RC preflight artifact remained: {path.name}")
        if external_path is not None and external_path.exists():
            raise OSError("RC external preflight artifact remained")
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as exc:
        raise StageGateError("rc_preflight_publication_rollback_failed") from exc


def run_local_rc_preflight(
    context: StageContext,
    *,
    dependency_sha256: str,
    guest_id: str,
    expected_machine_id: str,
) -> dict[str, Any]:
    try:
        if any(context.evidence_root.iterdir()):
            raise StageGateError("rc_evidence_not_clean")
    except OSError as exc:
        raise StageGateError("rc_evidence_not_clean") from exc
    preflight_path = _rc_preflight_path(context)
    if preflight_path.exists():
        raise StageGateError("rc_preflight_artifact_exists")
    if context.execution_kind != "canonical":
        raise StageGateError("rc_execution_kind_not_accepted")
    if not isinstance(expected_machine_id, str) or not re.fullmatch(
        r"[0-9a-f]{32}", expected_machine_id
    ):
        raise StageGateError("rc_guest_machine_identity_mismatch")
    if not re.fullmatch(r"[0-9a-f]{64}", dependency_sha256):
        raise StageGateError("rc_dependency_identity_not_accepted")
    if not re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{26}", guest_id):
        raise StageGateError("rc_guest_identity_not_accepted")
    owner = _read_json(context.owner_path)
    _validate_execution_owner(context, owner)
    if owner.get("dependency_sha256") != dependency_sha256:
        raise StageGateError("rc_dependency_identity_mismatch")
    checks = _rc_preflight_snapshot(context)
    manifest = {
        "schema_version": 1,
        "phase": "preflight",
        "verdict": "PASS",
        "release_sha": context.release_sha,
        "frontend_sha": context.frontend_sha,
        "dependency_sha256": dependency_sha256,
        "guest": {
            "name": ACCEPTANCE_MACHINE_NAME,
            "id": guest_id,
            "architecture": owner["architecture"],
            "machine_id": expected_machine_id,
        },
        "as_of_date": context.as_of_date.isoformat(),
        "checks": checks,
        "captured_at": _utc_timestamp_seconds(),
    }
    validate_evidence_payload(manifest)
    internal_paths = (
        context.evidence_root / "RC-PREFLIGHT.json",
        context.evidence_root / "stage-state.json",
        context.evidence_root / "SHA256SUMS",
    )
    try:
        write_stage_manifest(internal_paths[0], manifest)
        _checksum_manifest(internal_paths[0])
        _save_state(context, [])
        write_stage_manifest(preflight_path, manifest)
    except (KeyboardInterrupt, SystemExit):
        try:
            _cleanup_rc_preflight_publication(internal_paths, preflight_path)
        except BaseException:
            pass
        raise
    except BaseException:
        try:
            _cleanup_rc_preflight_publication(internal_paths, preflight_path)
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException:
            raise
        raise
    return manifest


def _rc_load_stage_manifests(
    context: StageContext,
    *,
    expected_attempt: dict[str, Any] | None = None,
    require_internal: bool = False,
) -> dict[str, dict[str, Any]]:
    internal_path = context.evidence_root / "RC-PREFLIGHT.json"
    if require_internal or internal_path.exists():
        try:
            internal = _rc_internal_preflight_attempt(context)
            if internal is None:
                raise StageGateError("rc_finalize_stage_attempt_invalid")
            record, preflight_sha256 = internal
            internal_attempt = _rc_stage_attempt_from_record(
                record, preflight_sha256, context.as_of_date.isoformat()
            )
            if expected_attempt is not None and internal_attempt != expected_attempt:
                raise StageGateError("rc_finalize_stage_attempt_invalid")
            expected_attempt = internal_attempt
        except StageGateError as exc:
            if str(exc) == "rc_finalize_stage_attempt_invalid":
                raise
            raise StageGateError("rc_finalize_stage_attempt_invalid") from exc
    try:
        state = _load_state(context)
    except Exception as exc:
        raise StageGateError("rc_finalize_stage_state_incomplete") from exc
    if state.get("completed") != list(STAGE_ORDER):
        raise StageGateError("rc_finalize_stage_state_incomplete")
    manifests: dict[str, dict[str, Any]] = {}
    for stage in STAGE_ORDER:
        path = context.evidence_root / f"{stage}.json"
        try:
            _verify_checksum_entry(path)
            manifest = _read_json(path)
        except Exception as exc:
            raise StageGateError("rc_finalize_stage_manifest_invalid") from exc
        if (
            manifest.get("stage") != stage
            or manifest.get("verdict") != "PASS"
            or manifest.get("release_sha", manifest.get("backend_sha"))
            != context.release_sha
            or manifest.get("frontend_sha") != context.frontend_sha
        ):
            raise StageGateError("rc_finalize_stage_manifest_invalid")
        if (
            expected_attempt is not None
            and manifest.get("rc_attempt") != expected_attempt
        ):
            raise StageGateError("rc_finalize_stage_attempt_invalid")
        manifests[stage] = manifest
    return manifests


def _rc_expected_preflight_checks() -> dict[str, Any]:
    return {
        "evidence_root_empty": True,
        "database_clean": True,
        "rate_state_clean": True,
        "actionable_commands": 0,
        "sources_clean": True,
        "runtime_dark": True,
    }


def _rc_load_preflight_record(
    context: StageContext,
    *,
    dependency_sha256: str,
    guest_id: str,
    expected_machine_id: str,
) -> tuple[dict[str, Any], str]:
    if (
        context.execution_kind != "canonical"
        or not re.fullmatch(r"[0-9a-f]{64}", dependency_sha256)
        or not re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{26}", guest_id)
        or not isinstance(expected_machine_id, str)
        or not re.fullmatch(r"[0-9a-f]{32}", expected_machine_id)
    ):
        raise StageGateError("rc_finalize_preflight_invalid")
    try:
        owner = _read_json(context.owner_path)
        _validate_execution_owner(context, owner)
        if owner.get("dependency_sha256") != dependency_sha256:
            raise ValueError
        path = _rc_preflight_path(context)
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            descriptor_stat = os.fstat(descriptor)
            if (
                not stat.S_ISREG(descriptor_stat.st_mode)
                or descriptor_stat.st_size > 1024 * 1024
            ):
                raise ValueError
            with os.fdopen(descriptor, "rb") as stream:
                descriptor = -1
                raw = stream.read(1024 * 1024 + 1)
            if len(raw) != descriptor_stat.st_size or len(raw) > 1024 * 1024:
                raise ValueError
        finally:
            if descriptor != -1:
                os.close(descriptor)
        record = json.loads(raw.decode("utf-8"))
    except (
        OSError,
        UnicodeDecodeError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        StageGateError,
    ) as exc:
        raise StageGateError("rc_finalize_preflight_invalid") from exc
    if not isinstance(record, dict):
        raise StageGateError("rc_finalize_preflight_invalid")
    expected_guest = {
        "name": ACCEPTANCE_MACHINE_NAME,
        "id": guest_id,
        "architecture": "arm64",
        "machine_id": expected_machine_id,
    }
    expected = {
        "schema_version": 1,
        "phase": "preflight",
        "verdict": "PASS",
        "release_sha": context.release_sha,
        "frontend_sha": context.frontend_sha,
        "dependency_sha256": dependency_sha256,
        "guest": expected_guest,
        "as_of_date": context.as_of_date.isoformat(),
        "checks": _rc_expected_preflight_checks(),
    }
    captured_at = record.get("captured_at")
    if (
        set(record) != {*expected, "captured_at"}
        or not isinstance(captured_at, str)
        or not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
            captured_at,
        )
    ):
        raise StageGateError("rc_finalize_preflight_invalid")
    try:
        if (
            datetime.strptime(captured_at, "%Y-%m-%dT%H:%M:%SZ").strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            != captured_at
        ):
            raise ValueError
    except ValueError as exc:
        raise StageGateError("rc_finalize_preflight_invalid") from exc
    expected["captured_at"] = captured_at
    if record != expected:
        raise StageGateError("rc_finalize_preflight_invalid")
    try:
        validate_evidence_payload(record)
        canonical = (json.dumps(record, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        if raw != canonical:
            raise ValueError
        record_sha256 = hashlib.sha256(raw).hexdigest()
    except (StageGateError, TypeError, ValueError) as exc:
        raise StageGateError("rc_finalize_preflight_invalid") from exc
    return record, record_sha256


def _rc_process_identity(processes: object) -> list[tuple[Any, ...]]:
    if not isinstance(processes, list) or len(processes) != len(PROCESS_NAMES):
        raise StageGateError("rc_finalize_process_stability_invalid")
    identity = []
    for item in processes:
        if (
            type(item) is not dict
            or set(item)
            != {"name", "status", "restarts", "pid", "memory_bytes", "cpu_percent"}
            or type(item.get("name")) is not str
            or type(item.get("status")) is not str
            or item.get("status") != "online"
            or type(item.get("restarts")) is not int
            or item.get("restarts") < 0
            or type(item.get("pid")) is not int
            or item.get("pid") <= 0
            or type(item.get("memory_bytes")) is not int
            or item.get("memory_bytes") < 0
            or type(item.get("cpu_percent")) not in {int, float}
            or isinstance(item.get("cpu_percent"), bool)
            or not math.isfinite(item.get("cpu_percent"))
            or item.get("cpu_percent") < 0
        ):
            raise StageGateError("rc_finalize_process_stability_invalid")
        identity.append((item["name"], item["status"], item["restarts"], item["pid"]))
    if sorted(name for name, *_rest in identity) != sorted(PROCESS_NAMES):
        raise StageGateError("rc_finalize_process_stability_invalid")
    return sorted(identity)


def _rc_final_snapshot(
    context: StageContext, stage_manifests: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    try:
        persist_steps = stage_manifests["LOCAL-PERSIST-ONLY-1"]["steps"]
        write_steps = stage_manifests["LOCAL-WRITE-ACT-1"]["steps"]
        persist_principal = persist_steps["operator_principal"]["subject"]
        write_principal = write_steps["operator_principal"]["subject"]
        runtime_baseline = write_steps["runtime_restoration"]
        expected_persist_digest = write_steps["persist_snapshot_sha256"]
        if (
            not isinstance(persist_principal, str)
            or not persist_principal
            or not isinstance(write_principal, str)
            or not write_principal
            or not isinstance(runtime_baseline, dict)
            or not isinstance(expected_persist_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_persist_digest)
        ):
            raise ValueError
        baseline_processes = runtime_baseline["processes"]
        baseline_dark = runtime_baseline["dark_contract_after"]
        baseline_listeners = runtime_baseline["listeners"]
        if not isinstance(baseline_dark, dict) or not isinstance(
            baseline_listeners, list
        ):
            raise ValueError
        baseline_identity = _rc_process_identity(baseline_processes)
    except (KeyError, TypeError, ValueError, StageGateError) as exc:
        if isinstance(exc, StageGateError):
            raise
        raise StageGateError("rc_finalize_immutable_history_invalid") from exc

    try:
        model_release = _read_json(
            context.repo_root / "services/flow-monitoring/data/model-releases/"
            "engineering-prior-v5-v1.json"
        )
        runtime = _verify_write_activation_restoration(
            context,
            before_dark=baseline_dark,
            model_release=model_release,
            before_listeners=baseline_listeners,
        )
        fresh_identity = _rc_process_identity(runtime.get("processes"))
    except Exception as exc:
        if isinstance(exc, StageGateError) and str(exc) == (
            "rc_finalize_process_stability_invalid"
        ):
            raise
        raise StageGateError("rc_finalize_process_stability_invalid") from exc
    if fresh_identity != baseline_identity:
        raise StageGateError("rc_finalize_process_stability_invalid")
    if runtime.get("verified") is not True:
        raise StageGateError("rc_finalize_process_stability_invalid")

    try:
        fresh_snapshot = _take_persist_snapshot(context)
        fresh_digest = _canonical_json_sha256(fresh_snapshot)
    except Exception as exc:
        raise StageGateError("rc_finalize_immutable_history_invalid") from exc
    if fresh_digest != expected_persist_digest:
        raise StageGateError("rc_finalize_immutable_history_invalid")

    allowed_rate_keys = {
        _planning_depth_rate_key(persist_principal),
        _planning_depth_rate_key(write_principal),
    }
    write_rate_key = _planning_depth_rate_key(write_principal)
    try:
        rate_reference = write_steps["rate_state_after_browser"]
        if (
            type(rate_reference) is not dict
            or set(rate_reference)
            != {
                "configured_window_ms",
                "minimum_elapsed_ms",
                "snapshot_completed_monotonic_ms",
                "snapshot",
            }
            or type(rate_reference["configured_window_ms"]) is not int
            or isinstance(rate_reference["configured_window_ms"], bool)
            or rate_reference["configured_window_ms"] <= 0
            or type(rate_reference["minimum_elapsed_ms"]) is not int
            or isinstance(rate_reference["minimum_elapsed_ms"], bool)
            or rate_reference["minimum_elapsed_ms"] < 0
            or type(rate_reference["snapshot_completed_monotonic_ms"]) is not int
            or isinstance(rate_reference["snapshot_completed_monotonic_ms"], bool)
            or rate_reference["snapshot_completed_monotonic_ms"] < 0
            or type(rate_reference["snapshot"]) is not dict
            or not set(rate_reference["snapshot"]).issubset(allowed_rate_keys)
            or write_rate_key not in rate_reference["snapshot"]
        ):
            raise ValueError
        configured_window_ms = rate_reference["configured_window_ms"]
        minimum_elapsed_ms = rate_reference["minimum_elapsed_ms"]
        snapshot_completed_monotonic_ms = rate_reference[
            "snapshot_completed_monotonic_ms"
        ]
        reference_rate_state = rate_reference["snapshot"]
        for key, row in reference_rate_state.items():
            if (
                type(key) is not str
                or key not in allowed_rate_keys
                or type(row) is not dict
                or set(row) != {"value", "ttl_ms"}
                or type(row["value"]) is not int
                or row["value"] <= 0
                or type(row["ttl_ms"]) is not int
                or row["ttl_ms"] <= 0
                or row["ttl_ms"] > configured_window_ms
            ):
                raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        raise StageGateError("rc_finalize_rate_state_invalid") from exc
    try:
        final_rate_snapshot_started_at = time.monotonic()
        if (
            type(final_rate_snapshot_started_at) not in {int, float}
            or isinstance(final_rate_snapshot_started_at, bool)
            or not math.isfinite(final_rate_snapshot_started_at)
            or final_rate_snapshot_started_at < 0
        ):
            raise ValueError
        final_rate_snapshot_started_ms = math.floor(
            final_rate_snapshot_started_at * 1000.0
        )
        if final_rate_snapshot_started_ms < snapshot_completed_monotonic_ms:
            raise ValueError
        rate_state = _snapshot_planning_depth_rate_keys(context)
        final_rate_snapshot_completed_at = time.monotonic()
        if (
            type(final_rate_snapshot_completed_at) not in {int, float}
            or isinstance(final_rate_snapshot_completed_at, bool)
            or not math.isfinite(final_rate_snapshot_completed_at)
            or final_rate_snapshot_completed_at < 0
        ):
            raise ValueError
        final_rate_snapshot_completed_ms = math.ceil(
            final_rate_snapshot_completed_at * 1000.0
        )
        if final_rate_snapshot_completed_ms < final_rate_snapshot_started_ms:
            raise ValueError
        full_elapsed_ms = max(
            minimum_elapsed_ms,
            final_rate_snapshot_started_ms - snapshot_completed_monotonic_ms,
        )
        if full_elapsed_ms < 0:
            raise ValueError
        if type(rate_state) is not dict:
            raise ValueError
        for key, reference_row in reference_rate_state.items():
            if key not in rate_state and reference_row["ttl_ms"] > full_elapsed_ms:
                raise ValueError
        for key, row in rate_state.items():
            if (
                key not in allowed_rate_keys
                or type(row) is not dict
                or set(row) != {"value", "ttl_ms"}
                or type(row["value"]) is not int
                or row["value"] <= 0
                or type(row["ttl_ms"]) is not int
                or row["ttl_ms"] <= 0
                or key not in reference_rate_state
                or row["value"] != reference_rate_state[key]["value"]
                or row["ttl_ms"] > configured_window_ms
                or row["ttl_ms"]
                > max(0, reference_rate_state[key]["ttl_ms"] - full_elapsed_ms)
            ):
                raise ValueError
    except Exception as exc:
        raise StageGateError("rc_finalize_rate_state_invalid") from exc

    try:
        write_manifest_path = context.evidence_root / "LOCAL-WRITE-ACT-1.json"
        _verify_checksum_entry(write_manifest_path)
        write_manifest_sha256 = hashlib.sha256(
            write_manifest_path.read_bytes()
        ).hexdigest()
        proof = {
            "processes": runtime["processes"],
            "dark_contract": runtime["dark_contract_after"],
            "frontend_activation_gates": runtime["final_activation_gates"],
            "readiness": runtime["readiness"],
            "listeners": runtime["listeners"],
            "persist_snapshot_sha256": fresh_digest,
            "rate_state": rate_state,
            "rate_minimum_elapsed_ms": full_elapsed_ms,
            "rate_snapshot_started_monotonic_ms": final_rate_snapshot_started_ms,
            "rate_snapshot_completed_monotonic_ms": final_rate_snapshot_completed_ms,
            "write_activation_manifest_sha256": write_manifest_sha256,
        }
        result = {
            "verdict": "PASS",
            "completed": list(STAGE_ORDER),
            "runtime_dark": True,
            "processes_stable": True,
            "readiness_green": True,
            "listeners_accepted": True,
            "immutable_history": True,
            "proof": proof,
        }
        validate_evidence_payload(result)
        return result
    except (OSError, StageGateError, TypeError, ValueError) as exc:
        if isinstance(exc, StageGateError) and str(exc).startswith("rc_finalize_"):
            raise
        raise StageGateError("rc_finalize_immutable_history_invalid") from exc


def _rollback_rc_finalize_publication(
    context: StageContext,
    success_paths: tuple[Path, ...],
    primary: BaseException,
) -> None:
    try:
        for path in success_paths:
            _clear_checksum_artifact(context.evidence_root, path.name)
            if path.exists():
                raise OSError(f"RC success artifact remained: {path.name}")
        index_entries = _read_checksum_index(context.evidence_root / "SHA256SUMS")
        if any(path.name in index_entries for path in success_paths):
            raise OSError("RC success checksum remained after rollback")
    except (KeyboardInterrupt, SystemExit) as cleanup:
        if isinstance(primary, (KeyboardInterrupt, SystemExit)):
            if cleanup is primary:
                raise
            raise primary from cleanup
        raise cleanup from primary
    except BaseException as cleanup_exc:
        if isinstance(primary, (KeyboardInterrupt, SystemExit)):
            raise primary from cleanup_exc
        raise StageGateError("rc_finalize_publication_rollback_failed") from cleanup_exc


def run_local_rc_finalize(
    context: StageContext,
    *,
    dependency_sha256: str,
    guest_id: str,
    expected_machine_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(expected_machine_id, str) or not re.fullmatch(
        r"[0-9a-f]{32}", expected_machine_id
    ):
        raise StageGateError("rc_guest_machine_identity_mismatch")
    record, record_sha256 = _rc_load_preflight_record(
        context,
        dependency_sha256=dependency_sha256,
        guest_id=guest_id,
        expected_machine_id=expected_machine_id,
    )
    expected_attempt = _rc_stage_attempt_from_record(
        record, record_sha256, context.as_of_date.isoformat()
    )
    stage_manifests = _rc_load_stage_manifests(
        context,
        expected_attempt=expected_attempt,
        require_internal=False,
    )
    final = _rc_final_snapshot(context, stage_manifests)
    expected_guest = {
        "name": ACCEPTANCE_MACHINE_NAME,
        "id": guest_id,
        "architecture": "arm64",
        "machine_id": expected_machine_id,
    }
    manifest = {
        "schema_version": 1,
        "stage": "LOCAL-RC-1",
        "verdict": "PASS",
        "release_sha": context.release_sha,
        "frontend_sha": context.frontend_sha,
        "dependency_sha256": dependency_sha256,
        "guest": expected_guest,
        "as_of_date": context.as_of_date.isoformat(),
        "preflight": {
            "verdict": record["verdict"],
            **record["checks"],
            "record": record,
            "record_sha256": record_sha256,
        },
        "final": final,
    }
    summary = {
        "schema_version": 1,
        "evidence_kind": "local_release_candidate",
        "acceptance": "LOCAL-RC-1",
        "acceptance_evidence": True,
        "campaign_ledger_eligible": False,
        "aws_actions_authorized": False,
        "release_sha": context.release_sha,
        "frontend_sha": context.frontend_sha,
        "dependency_sha256": dependency_sha256,
        "guest": expected_guest,
        "as_of_date": context.as_of_date.isoformat(),
        "passed": [*STAGE_ORDER, "LOCAL-RC-1"],
        "failed": [],
        "unreached": [],
        "verdict": "PASS",
    }
    validate_evidence_payload(manifest)
    validate_evidence_payload(summary)
    rc_manifest_path = context.evidence_root / "LOCAL-RC-1.json"
    summary_path = context.evidence_root / "RC-SUMMARY.json"
    success_paths = (rc_manifest_path, summary_path)
    preflight_path = _rc_preflight_path(context)
    failure_path = context.evidence_root / "LOCAL-RC-1-failure.json"
    if failure_path.exists():
        _clear_checksum_artifact(context.evidence_root, failure_path.name)
    try:
        write_stage_manifest(rc_manifest_path, manifest)
        _checksum_manifest(rc_manifest_path)
        write_stage_manifest(summary_path, summary)
        _checksum_manifest(summary_path)
        preflight_path.unlink()
        if preflight_path.exists():
            raise OSError("external preflight artifact remained")
    except (KeyboardInterrupt, SystemExit) as primary:
        _rollback_rc_finalize_publication(context, success_paths, primary)
        raise
    except BaseException as primary:
        _rollback_rc_finalize_publication(context, success_paths, primary)
        raise
    return manifest


def assert_persist_target_week_clean(before_snapshot: dict, week_key: str) -> dict:
    """Require the persist-only target week to hold no existing submission.

    persist-only creates a fresh root (active=None), which the BFF REPLAYS to 200
    -- not 201 -- if a prior (possibly failed) run already wrote this week; the
    stage would otherwise fail with an opaque submission-rejected code. Migration
    010 makes submissions immutable, so a used week can never be cleaned: fail
    early and clearly. Remedy: re-run with --as-of-date on a different week.
    """
    for row in before_snapshot.get("w2_submissions", []):
        if (
            row.get("project_key") == "mun-bon"
            and row.get("calendar_system") == "rid-irrigation-v1"
            and row.get("week_key") == week_key
        ):
            raise StageGateError("persist_only_target_week_not_clean")
    return {"clean": True, "week_key": week_key}


def _planning_depth_write_window_ms(context: StageContext) -> int:
    try:
        configured = _load_env_file(context.runtime_env_dir / "bff.env").get(
            "PLANNING_DEPTH_WRITE_WINDOW_SECONDS"
        )
    except StageGateError as exc:
        raise StageGateError("planning_depth_write_window_invalid") from exc
    raw = "300" if configured is None else configured.strip()
    try:
        if not re.fullmatch(r"[+-]?[0-9]+", raw):
            raise ValueError
        seconds = int(raw, 10)
        if seconds <= 0:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise StageGateError("planning_depth_write_window_invalid") from exc
    return seconds * 1000


def validate_persist_only_rate_accounting(
    before: dict,
    after: dict,
    *,
    expected_increment: int = 2,
    configured_window_ms: int = 300000,
    elapsed_ms: int | float = 0,
    expected_operator_key: str | None = None,
) -> dict:
    error = "persist_only_rate_side_effect_detected"
    if (
        isinstance(configured_window_ms, bool)
        or not isinstance(configured_window_ms, int)
        or configured_window_ms <= 0
    ):
        raise StageGateError(error)
    if isinstance(elapsed_ms, bool) or not isinstance(elapsed_ms, (int, float)):
        raise StageGateError("persist_only_rate_elapsed_invalid")
    try:
        elapsed_value = float(elapsed_ms)
    except (OverflowError, TypeError, ValueError) as exc:
        raise StageGateError("persist_only_rate_elapsed_invalid") from exc
    if not math.isfinite(elapsed_value) or elapsed_value < 0:
        raise StageGateError("persist_only_rate_elapsed_invalid")
    if expected_operator_key is not None and (
        not isinstance(expected_operator_key, str)
        or _RATE_KEY_RE.fullmatch(expected_operator_key) is None
    ):
        raise StageGateError(error)

    def positive_ttl(entry: Any) -> int:
        ttl_ms = entry.get("ttl_ms") if isinstance(entry, dict) else None
        if isinstance(ttl_ms, bool) or not isinstance(ttl_ms, int) or ttl_ms <= 0:
            raise StageGateError(error)
        return ttl_ms

    def current_ttl(entry: Any) -> int:
        ttl_ms = positive_ttl(entry)
        if ttl_ms > configured_window_ms:
            raise StageGateError(error)
        return ttl_ms

    def rate_value(entry: Any) -> int:
        value = entry.get("value") if isinstance(entry, dict) else None
        if isinstance(value, bool) or not isinstance(value, int):
            raise StageGateError(error)
        return value

    keys = set(before) | set(after)
    if any(
        not isinstance(key, str) or _RATE_KEY_RE.fullmatch(key) is None for key in keys
    ):
        raise StageGateError(error)

    current_ttls = {key: current_ttl(entry) for key, entry in after.items()}
    operator_keys = []
    for key in keys:
        prior = before.get(key)
        current = after.get(key)
        if current is None:
            # A key present only before must have had an expiring window; a
            # persistent or missing TTL cannot prove that it naturally expired.
            prior_ttl_ms = positive_ttl(prior)
            if prior_ttl_ms > elapsed_value + _RATE_ELAPSED_MEASUREMENT_TOLERANCE_MS:
                raise StageGateError(error)
            continue

        current_value = rate_value(current)
        ttl_ms = current_ttls[key]
        if prior is None:
            if current_value != expected_increment:
                raise StageGateError(error)
            operator_keys.append(key)
            continue

        prior_value = rate_value(prior)
        prior_ttl_ms = positive_ttl(prior)
        if current_value == prior_value:
            if (
                ttl_ms
                > max(0.0, prior_ttl_ms - elapsed_value)
                + _RATE_ELAPSED_MEASUREMENT_TOLERANCE_MS
            ):
                raise StageGateError(error)
            if ttl_ms > prior_ttl_ms:
                raise StageGateError(error)
            continue

        if current_value == prior_value + expected_increment:
            if (
                ttl_ms
                > max(0.0, prior_ttl_ms - elapsed_value)
                + _RATE_ELAPSED_MEASUREMENT_TOLERANCE_MS
            ):
                raise StageGateError(error)
            if ttl_ms > prior_ttl_ms:
                raise StageGateError(error)
            operator_keys.append(key)
            continue

        # A reset is only credible when the old window had a finite positive
        # TTL that could have elapsed between the atomic snapshots, and the
        # new counter starts at exactly the expected increment.
        if current_value == expected_increment:
            if prior_ttl_ms > elapsed_value + _RATE_ELAPSED_MEASUREMENT_TOLERANCE_MS:
                raise StageGateError(error)
            operator_keys.append(key)
            continue
        raise StageGateError(error)

    if len(operator_keys) != 1 or (
        expected_operator_key is not None and operator_keys[0] != expected_operator_key
    ):
        raise StageGateError(error)
    return {"operator_rate_key": operator_keys[0], "increment": expected_increment}


def _operator_logout(
    client, refresh_cookie: str, *, strict: bool, error_code: str
) -> bool | BaseException:
    try:
        logout = client.request(
            "POST",
            "http://127.0.0.1:3005/api/v1/auth/logout",
            payload={"refreshToken": refresh_cookie},
        )
    except BaseException as exc:
        if not strict:
            return exc
        if not isinstance(exc, Exception):
            raise
        raise StageGateError(error_code) from exc
    if strict and logout.status not in {200, 204}:
        raise StageGateError(error_code)
    return logout.status in {200, 204}


def _persist_only_logout(
    client, refresh_cookie: str, *, strict: bool
) -> bool | BaseException:
    return _operator_logout(
        client,
        refresh_cookie,
        strict=strict,
        error_code="persist_only_operator_logout_failed",
    )


def _cleanup_initial_operator_session(
    client,
    refresh_cookie: str,
    *,
    logout: Callable[[], Any],
    primary: BaseException,
    error_code: str,
) -> None:
    cleanup_errors: list[BaseException] = []
    try:
        logout_result = logout()
        if isinstance(logout_result, BaseException):
            cleanup_errors.append(logout_result)
        elif logout_result is False:
            cleanup_errors.append(StageGateError(error_code))
    except BaseException as exc:
        cleanup_errors.append(exc)

    try:
        reuse_evidence = _assert_operator_refresh_reuse_rejected(
            client,
            refresh_cookie,
        )
        if not isinstance(reuse_evidence, dict):
            cleanup_errors.append(StageGateError(error_code))
    except BaseException as exc:
        cleanup_errors.append(exc)

    primary_interrupt = (
        primary if isinstance(primary, (KeyboardInterrupt, SystemExit)) else None
    )
    cleanup_interrupt = next(
        (
            error
            for error in cleanup_errors
            if isinstance(error, (KeyboardInterrupt, SystemExit))
        ),
        None,
    )
    interrupt = primary_interrupt or cleanup_interrupt
    if interrupt is not None:
        if cleanup_errors:
            setattr(
                interrupt,
                "session_cleanup",
                {
                    "logout_attempted": True,
                    "refresh_reuse_attempted": True,
                    "proved": False,
                },
            )
        raise interrupt
    if cleanup_errors:
        cleanup_error = StageGateError(error_code)
        raise cleanup_error from primary


def _persist_only_body(
    context: StageContext, client, token: str, login_evidence: dict
) -> dict:
    week_date, week_key = _persist_only_rid_week(context.as_of_date)
    steps: dict[str, Any] = {
        "login": login_evidence,
        "target_week": {"week_date": week_date, "week_key": week_key},
    }
    steps["write_flag_dark"] = validate_write_flag_is_dark(
        _load_env_file(context.runtime_env_dir / "bff.env").get(
            "PLANNING_DEPTH_WRITES_ENABLED", ""
        )
    )
    principal = client.request(
        "GET",
        "http://127.0.0.1:3021/api/v1/auth/principal",
        bearer=token,
    )
    steps["operator_principal"] = validate_w1_principal_result(
        principal.status,
        principal.body,
        principal.headers,
    )

    before_snapshot = _take_persist_snapshot(context)
    steps["target_week_clean"] = assert_persist_target_week_clean(
        before_snapshot, week_key
    )
    before_rate = _snapshot_planning_depth_rate_keys(context)
    before_rate_completed_at = time.monotonic()

    bff_restored = False
    try:
        _restart_bff_with_flag(context, enabled=True)
        create_request = _build_planning_depth_request_v2(
            week_date=week_date,
            week_key=week_key,
            client_submission_id=_write_ui_client_submission_id(
                context.release_sha, week_key, "persist-only"
            ),
            active_submission_id=None,
            depth_offset="0.100",
        )
        create = client.request(
            "POST", W2_V2_BASE, payload=create_request, bearer=token
        )
        create_receipt = validate_w2_submission_result(
            create.status, create.body, create.headers, expected_status=201
        )
        steps["w2_submit"] = create_receipt

        correct_request = _build_planning_depth_request_v2(
            week_date=week_date,
            week_key=week_key,
            client_submission_id=_write_ui_client_submission_id(
                context.release_sha, week_key, "persist-only-correct"
            ),
            active_submission_id=create.body["submission_id"],
            depth_offset="0.200",
        )
        correct = client.request(
            "POST", W2_V2_BASE, payload=correct_request, bearer=token
        )
        correct_receipt = validate_w2_submission_result(
            correct.status, correct.body, correct.headers, expected_status=201
        )
        steps["w2_correct"] = correct_receipt
    finally:
        try:
            _restart_bff_with_flag(context, enabled=False)
            bff_restored = True
        except Exception:
            pass

    if not bff_restored:
        raise StageGateError("persist_only_restoration_failed")

    steps["restored_write_flag"] = validate_write_flag_is_dark(
        _load_env_file(context.runtime_env_dir / "bff.env").get(
            "PLANNING_DEPTH_WRITES_ENABLED", ""
        )
    )

    after_snapshot = _take_persist_snapshot(context)
    after_rate_started_at = time.monotonic()
    after_rate = _snapshot_planning_depth_rate_keys(context)
    elapsed_ms = _rate_snapshot_elapsed_ms(
        before_rate_completed_at, after_rate_started_at
    )

    steps["persist_only_diff"] = validate_persist_only_diff(
        before_snapshot,
        after_snapshot,
        create_receipt=create_receipt,
        correct_receipt=correct_receipt,
        target_week_key=week_key,
        target_week_date=week_date,
        create_zone_depths=_zone_depths_from_request(create_request),
        correct_zone_depths=_zone_depths_from_request(correct_request),
    )
    steps["rate_accounting"] = validate_persist_only_rate_accounting(
        before_rate,
        after_rate,
        configured_window_ms=_planning_depth_write_window_ms(context),
        elapsed_ms=elapsed_ms,
        expected_operator_key=_planning_depth_rate_key(
            steps["operator_principal"]["subject"]
        ),
    )
    steps["rate_accounting"]["elapsed_ms"] = elapsed_ms
    steps["aws_actions"] = False

    return {
        "stage": "LOCAL-PERSIST-ONLY-1",
        "verdict": "PASS",
        "release_sha": context.release_sha,
        "frontend_sha": context.frontend_sha,
        "completed_at": _utc_timestamp(),
        "steps": steps,
    }


def run_local_persist_only(context: StageContext) -> dict:
    state = _load_state(context)
    validate_stage_transition(tuple(state["completed"]), "LOCAL-PERSIST-ONLY-1")

    verifier = _load_harness_module(
        context,
        "verify_bearer.py",
        "local_persist_only_bearer_verifier",
    )
    client = LocalHttpClient()
    try:
        token, refresh_cookie, login_evidence = _login_operator(
            context, client, verifier
        )
    except BaseException as primary:
        try:
            recovered_refresh_cookie = client.refresh_cookie()
        except BaseException:
            recovered_refresh_cookie = None
        if isinstance(recovered_refresh_cookie, str) and recovered_refresh_cookie:
            _cleanup_initial_operator_session(
                client,
                recovered_refresh_cookie,
                logout=lambda: _persist_only_logout(
                    client,
                    recovered_refresh_cookie,
                    strict=False,
                ),
                primary=primary,
                error_code="persist_only_initial_operator_cleanup_unproved",
            )
        raise
    # Outer boundary starting right after login: any failure downstream still
    # logs out (best-effort, no masking); a clean run logs out strictly.
    try:
        manifest = _persist_only_body(context, client, token, login_evidence)
    except BaseException as primary:
        _cleanup_initial_operator_session(
            client,
            refresh_cookie,
            logout=lambda: _persist_only_logout(
                client,
                refresh_cookie,
                strict=False,
            ),
            primary=primary,
            error_code="persist_only_initial_operator_cleanup_unproved",
        )
        raise
    _persist_only_logout(client, refresh_cookie, strict=True)

    validate_evidence_payload(manifest)
    target = context.evidence_root / "LOCAL-PERSIST-ONLY-1.json"
    clear_failure_manifest(context.evidence_root, "LOCAL-PERSIST-ONLY-1")
    write_stage_manifest(target, manifest)
    _checksum_manifest(target)
    _save_state(context, list(STAGE_ORDER[:9]))
    print("PASS LOCAL-PERSIST-ONLY-1")
    return manifest


def run_local_write_activation(context: StageContext) -> dict:
    state = _load_state(context)
    validate_stage_transition(tuple(state["completed"]), "LOCAL-WRITE-ACT-1")
    _clear_checksum_artifact(
        context.evidence_root,
        "LOCAL-WRITE-ACT-1-browser-result.json",
    )
    _verify_frontend_source(context)

    verifier = _load_harness_module(
        context,
        "verify_bearer.py",
        "local_write_activation_bearer_verifier",
    )
    client = LocalHttpClient()
    try:
        token, refresh_cookie, login_evidence = _login_operator(
            context,
            client,
            verifier,
        )
    except BaseException as primary:
        try:
            recovered_refresh_cookie = client.refresh_cookie()
        except BaseException:
            recovered_refresh_cookie = None
        if isinstance(recovered_refresh_cookie, str) and recovered_refresh_cookie:
            _cleanup_initial_operator_session(
                client,
                recovered_refresh_cookie,
                logout=lambda: _operator_logout(
                    client,
                    recovered_refresh_cookie,
                    strict=False,
                    error_code="write_activation_operator_logout_failed",
                ),
                primary=primary,
                error_code="write_activation_initial_operator_cleanup_unproved",
            )
        raise
    try:
        steps = _run_local_write_activation_authenticated(
            context,
            client,
            token,
            login_evidence,
            verifier=verifier,
        )
    except BaseException as primary:
        _cleanup_initial_operator_session(
            client,
            refresh_cookie,
            logout=lambda: _operator_logout(
                client,
                refresh_cookie,
                strict=False,
                error_code="write_activation_operator_logout_failed",
            ),
            primary=primary,
            error_code="write_activation_initial_operator_cleanup_unproved",
        )
        raise
    _operator_logout(
        client,
        refresh_cookie,
        strict=True,
        error_code="write_activation_operator_logout_failed",
    )
    steps["refresh_revoked"] = _assert_operator_refresh_reuse_rejected(
        client,
        refresh_cookie,
    )

    manifest = {
        "stage": "LOCAL-WRITE-ACT-1",
        "verdict": "PASS",
        "release_sha": context.release_sha,
        "frontend_sha": context.frontend_sha,
        "completed_at": _utc_timestamp(),
        "steps": steps,
    }
    validate_evidence_payload(manifest)
    target = context.evidence_root / "LOCAL-WRITE-ACT-1.json"
    clear_failure_manifest(context.evidence_root, "LOCAL-WRITE-ACT-1")
    write_stage_manifest(target, manifest)
    _checksum_manifest(target)
    _save_state(context, list(STAGE_ORDER))
    print("PASS LOCAL-WRITE-ACT-1")
    return manifest


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=(*STAGE_ORDER, "LOCAL-RC-1"))
    parser.add_argument("--release-sha", required=True)
    parser.add_argument("--frontend-sha", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("/opt/munbon/repo"))
    parser.add_argument(
        "--frontend-root",
        type=Path,
        default=Path("/opt/munbon/frontend"),
    )
    parser.add_argument(
        "--harness-root", type=Path, default=Path("/opt/munbon/harness")
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_ACCEPTANCE_EVIDENCE_ROOT,
    )
    parser.add_argument(
        "--runtime-env-dir",
        type=Path,
        default=Path("/etc/munbon/control-plan-read-runtime"),
    )
    parser.add_argument("--as-of-date", type=date.fromisoformat)
    parser.add_argument(
        "--execution-kind", choices=("canonical", "rehearsal"), required=True
    )
    parser.add_argument("--rc-phase", choices=("preflight", "finalize"))
    parser.add_argument("--dependency-sha256")
    parser.add_argument("--guest-id")
    parser.add_argument("--expected-machine-id")
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args(argv)
    if args.stage == "LOCAL-RC-1":
        if args.execution_kind != "canonical":
            parser.error("LOCAL-RC-1 requires canonical execution")
        if args.rc_phase is None:
            parser.error("LOCAL-RC-1 requires --rc-phase")
        if args.dependency_sha256 is None or args.guest_id is None:
            parser.error("LOCAL-RC-1 requires dependency and guest identity")
        if args.expected_machine_id is None or not re.fullmatch(
            r"[0-9a-f]{32}", args.expected_machine_id
        ):
            parser.error("LOCAL-RC-1 requires expected machine identity")
        if args.as_of_date is None:
            parser.error("LOCAL-RC-1 requires --as-of-date")
    elif any(
        value is not None
        for value in (
            args.rc_phase,
            args.dependency_sha256,
            args.guest_id,
        )
    ):
        parser.error("RC options are supported only for LOCAL-RC-1")
    elif args.expected_machine_id is not None:
        if args.execution_kind != "canonical":
            parser.error("expected machine identity requires canonical execution")
        if not re.fullmatch(r"[0-9a-f]{32}", args.expected_machine_id):
            parser.error("expected machine identity is invalid")
    if args.diagnostic:
        if args.stage != "LOCAL-WRITE-UI-1":
            parser.error("--diagnostic is supported only for LOCAL-WRITE-UI-1")
        if (
            args.evidence_root.resolve() == DEFAULT_ACCEPTANCE_EVIDENCE_ROOT.resolve()
            or (args.evidence_root / "stage-state.json").exists()
        ):
            parser.error("--diagnostic requires an isolated evidence root")
    if args.execution_kind == "rehearsal" and args.stage not in STAGE_ORDER[:3]:
        parser.error(
            "rehearsal execution supports only LOCAL-BASE-0 through LOCAL-AC-1"
        )
    if args.execution_kind == "rehearsal" and args.as_of_date is None:
        parser.error("rehearsal execution requires --as-of-date")
    if args.as_of_date is None:
        args.as_of_date = date.today()
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    execution_kind = getattr(args, "execution_kind", "canonical")
    context = StageContext(
        release_sha=args.release_sha,
        frontend_sha=args.frontend_sha,
        repo_root=args.repo_root,
        frontend_root=args.frontend_root,
        harness_root=args.harness_root,
        evidence_root=args.evidence_root,
        runtime_env_dir=args.runtime_env_dir,
        as_of_date=args.as_of_date,
        execution_kind=execution_kind,
    )
    expected_machine_id = getattr(args, "expected_machine_id", None)
    if expected_machine_id is not None and _actual_machine_id() != expected_machine_id:
        raise StageGateError("rc_guest_machine_identity_mismatch")
    if any(context.evidence_root.glob("*-failure.json")):
        print("FAIL stage_failure_terminal")
        return 1
    rc_attempt: dict[str, Any] | None = None
    try:
        if args.stage in STAGE_ORDER:
            rc_attempt = _rc_stage_attempt(context, expected_machine_id)
            if rc_attempt is not None:
                context = replace(context, rc_attempt=rc_attempt)
        if args.stage == "LOCAL-RC-1":
            if args.rc_phase == "preflight":
                run_local_rc_preflight(
                    context,
                    dependency_sha256=args.dependency_sha256,
                    guest_id=args.guest_id,
                    expected_machine_id=expected_machine_id,
                )
            else:
                run_local_rc_finalize(
                    context,
                    dependency_sha256=args.dependency_sha256,
                    guest_id=args.guest_id,
                    expected_machine_id=expected_machine_id,
                )
        elif args.stage == "LOCAL-BASE-0":
            run_local_base(context)
        elif args.stage == "LOCAL-RTA-1":
            run_local_rta(context)
        elif args.stage == "LOCAL-AC-1":
            run_local_ac(context)
        elif args.stage == "LOCAL-READ-ACT-1":
            run_local_read_activation(context)
        elif args.stage == "LOCAL-EVIDENCE-1":
            run_local_evidence_activation(context)
        elif args.stage == "LOCAL-GO-READ-1":
            run_local_go_read(context)
        elif args.stage == "LOCAL-WRITE-FOUNDATION-1":
            run_local_write_foundation(context)
        elif args.stage == "LOCAL-WRITE-UI-1":
            if getattr(args, "diagnostic", False):
                run_local_write_ui(context, diagnostic=True)
            else:
                run_local_write_ui(context)
        elif args.stage == "LOCAL-PERSIST-ONLY-1":
            run_local_persist_only(context)
        elif args.stage == "LOCAL-WRITE-ACT-1":
            run_local_write_activation(context)
        else:
            raise StageGateError("stage_dispatch_invalid")
        if rc_attempt is not None:
            _verify_rc_post_stage_state(context, args.stage, rc_attempt)
    except (KeyboardInterrupt, SystemExit) as primary:
        if rc_attempt is not None and args.stage in STAGE_ORDER:
            try:
                _discard_rc_stage_artifact(context, args.stage)
            except (KeyboardInterrupt, SystemExit) as cleanup:
                if cleanup is primary:
                    raise
                raise primary from cleanup
            except BaseException as cleanup_exc:
                raise primary from cleanup_exc
        raise
    except Exception as exc:
        # Only Exception is a stage verdict. An operator interrupt
        # (KeyboardInterrupt/SystemExit) is NOT: it propagates with standard
        # process semantics and writes no manifest — writing one here would
        # stamp a FAIL beside an already-written PASS if the abort lands after
        # a stage completed, permanently contradicting the evidence.
        # DRY with _safe_error_code: same unexpected_<Type> fallback as the
        # restoration guard, so non-StageGateError codes never diverge.
        if isinstance(exc, StageGateError) and str(exc) in {
            "rc_stage_publication_rollback_failed",
            "rc_preflight_publication_rollback_failed",
            "rc_finalize_publication_rollback_failed",
        }:
            print(f"FAIL {exc}", file=sys.stderr)
            return FAILURE_MANIFEST_EXIT_CODE
        if rc_attempt is not None and args.stage in STAGE_ORDER:
            pass_path = args.evidence_root / f"{args.stage}.json"
            if pass_path.exists():
                try:
                    _discard_rc_stage_artifact(context, args.stage)
                except (KeyboardInterrupt, SystemExit):
                    raise
                except BaseException:
                    pass
                print(
                    "FAIL rc_stage_publication_rollback_failed",
                    file=sys.stderr,
                )
                return FAILURE_MANIFEST_EXIT_CODE
        safe_error = (
            exc
            if isinstance(exc, StageGateError)
            else StageGateError(_safe_error_code(exc))
        )
        if safe_error is not exc:
            primary_restoration = getattr(exc, "restoration", None)
            if isinstance(primary_restoration, dict):
                safe_error.restoration = primary_restoration
        teardown_error = None
        if args.stage == "LOCAL-RTA-1":
            # Contain teardown failure so it cannot mask the primary finding —
            # but RECORD it, so orphaned runtime processes are explained rather
            # than silently swallowed.
            try:
                _stop_runtime()
            except Exception as exc_teardown:
                teardown_error = _safe_error_code(exc_teardown)
        diagnostic = getattr(args, "diagnostic", False)
        stage = WRITE_UI_DIAGNOSTIC_STAGE if diagnostic else args.stage
        failure = {
            "stage": stage,
            "verdict": "FAIL",
            "release_sha": args.release_sha,
            "frontend_sha": args.frontend_sha,
            "failed_gate": str(safe_error),
            "failed_at": (
                _utc_timestamp_seconds()
                if args.stage == "LOCAL-RC-1"
                else _utc_timestamp()
            ),
        }
        if args.stage == "LOCAL-RC-1":
            failure.update(
                {
                    "rc_phase": args.rc_phase,
                    "dependency_sha256": args.dependency_sha256,
                    "guest": {
                        "name": ACCEPTANCE_MACHINE_NAME,
                        "id": args.guest_id,
                        "architecture": "arm64",
                        "machine_id": expected_machine_id,
                    },
                    "as_of_date": context.as_of_date.isoformat(),
                }
            )
            if args.rc_phase == "preflight":
                try:
                    failure["harness_hashes"] = {
                        name: _hash_file(context.harness_root / name)
                        for name in HARNESS_ARTIFACTS
                    }
                except Exception:
                    print(
                        "FAIL rc_preflight_failure_harness_identity_unavailable",
                        file=sys.stderr,
                    )
                    return FAILURE_MANIFEST_EXIT_CODE
        if diagnostic:
            failure["acceptance_evidence"] = False
        if execution_kind == "rehearsal":
            failure["acceptance_evidence"] = False
            failure["as_of_date"] = context.as_of_date.isoformat()
        if teardown_error is not None:
            failure["teardown_error"] = teardown_error
        if rc_attempt is None:
            attached_attempt = getattr(safe_error, "rc_attempt", None)
            if isinstance(attached_attempt, dict):
                rc_attempt = attached_attempt
        if rc_attempt is not None and args.stage in STAGE_ORDER:
            failure["rc_attempt"] = rc_attempt
        restoration = getattr(safe_error, "restoration", None)
        if isinstance(restoration, dict):
            failure["restoration"] = restoration
        predicate_codes = getattr(safe_error, "predicate_codes", None)
        if (
            isinstance(predicate_codes, (list, tuple))
            and predicate_codes
            and all(
                isinstance(code, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,127}", code)
                for code in predicate_codes
            )
        ):
            failure["predicate_codes"] = list(predicate_codes)
        try:
            target = args.evidence_root / f"{stage}-failure.json"
            write_stage_manifest(target, failure)
        except Exception:
            print("FAIL failure_manifest_write_failed", file=sys.stderr)
            return FAILURE_MANIFEST_EXIT_CODE
        try:
            _checksum_manifest(target)
        except Exception:
            print("FAIL failure_manifest_checksum_failed", file=sys.stderr)
            return FAILURE_MANIFEST_EXIT_CODE
        print(f"FAIL {stage}: {safe_error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
