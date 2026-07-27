from __future__ import annotations

from decimal import Decimal, InvalidOperation
from uuid import uuid4

import asyncpg
from schemas.planning_depth import (
    EffectivePrincipalProjection,
    PlanningDepthActiveSubmission,
    PlanningDepthExpandedValue,
    PlanningDepthSubmissionReceipt,
    PlanningDepthSubmissionRequest,
)
from services.planning_depth_submission import (
    PlanningDepthValidationError,
    RosterSection,
    canonicalize_expanded_planning_depth_values,
    canonicalize_planning_depth_request,
    expand_planning_depth_values,
    validate_canonical_roster,
)


class PlanningDepthConflictError(RuntimeError):
    pass


class PlanningDepthRosterUnavailableError(RuntimeError):
    pass


class PlanningDepthStoredDataError(RuntimeError):
    pass


def _zone_id(value) -> str:
    text = str(value)
    if text.startswith("Zone"):
        text = text[4:]
    try:
        zone_number = int(text)
    except ValueError as exc:
        raise PlanningDepthRosterUnavailableError(
            "canonical roster is invalid"
        ) from exc
    if not 1 <= zone_number <= 6:
        raise PlanningDepthRosterUnavailableError("canonical roster is invalid")
    return f"01-{zone_number:02d}"


async def load_planning_depth_roster(connection) -> list[RosterSection]:
    try:
        rows = await connection.fetch(
            """
            SELECT section_id, zone, area_rai
            FROM ros_gis.sections_current
            ORDER BY section_id
            """
        )
        roster = [
            RosterSection(
                section_id=str(row["section_id"]),
                zone_id=_zone_id(row["zone"]),
                area_rai=Decimal(str(row["area_rai"])),
            )
            for row in rows
        ]
        validate_canonical_roster(roster)
        return roster
    except (
        asyncpg.PostgresError,
        InvalidOperation,
        PlanningDepthValidationError,
        TypeError,
        ValueError,
    ) as exc:
        raise PlanningDepthRosterUnavailableError(
            "canonical roster is unavailable"
        ) from exc


def _receipt(row, *, replayed: bool) -> PlanningDepthSubmissionReceipt:
    return PlanningDepthSubmissionReceipt(
        schema_version=row["schema_version"],
        submission_id=row["submission_id"],
        client_submission_id=row["client_submission_id"],
        project_key=row["project_key"],
        week_key=row["week_key"],
        week_date=row["week_date"],
        submitted_at=row["submitted_at"],
        submitted_by=row["submitted_by"],
        supersedes_submission_id=row["supersedes_submission_id"],
        request_sha256=row["request_sha256"],
        replayed=replayed,
    )


async def _load_active_row(connection, project_key: str, week_key: str):
    return await connection.fetchrow(
        """
        SELECT current.*
        FROM water_planning.planning_depth_submissions AS current
        WHERE current.project_key = $1
          AND current.week_key = $2
          AND NOT EXISTS (
              SELECT 1
              FROM water_planning.planning_depth_submissions AS successor
              WHERE successor.supersedes_submission_id = current.submission_id
          )
        ORDER BY current.submitted_at DESC, current.submission_id DESC
        LIMIT 1
        """,
        project_key,
        week_key,
    )


async def create_planning_depth_submission(
    connection,
    request: PlanningDepthSubmissionRequest,
    principal: EffectivePrincipalProjection,
    roster: list[RosterSection],
) -> PlanningDepthSubmissionReceipt:
    request_document = canonicalize_planning_depth_request(request)
    expanded = expand_planning_depth_values(request.levels, roster)
    expanded_document = canonicalize_expanded_planning_depth_values(expanded)
    try:
        async with connection.transaction():
            await connection.fetchval(
                "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
                f"planning-depth:{request.project_key}:{request.week_key}",
            )
            existing = await connection.fetchrow(
                """
                SELECT *
                FROM water_planning.planning_depth_submissions
                WHERE client_submission_id = $1
                """,
                request.client_submission_id,
            )
            if existing is not None:
                if (
                    existing["submitted_by"] == principal.subject
                    and existing["request_sha256"] == request_document.sha256
                ):
                    return _receipt(existing, replayed=True)
                raise PlanningDepthConflictError("client_submission_id_conflict")

            active = await _load_active_row(
                connection,
                request.project_key,
                request.week_key,
            )
            if (
                active is not None
                and active["request_sha256"] == request_document.sha256
            ):
                return _receipt(active, replayed=True)

            active_id = None if active is None else active["submission_id"]
            if request.expected_active_submission_id != active_id:
                raise PlanningDepthConflictError("stale_active_submission")

            submission_id = uuid4()
            inserted = await connection.fetchrow(
                """
                INSERT INTO water_planning.planning_depth_submissions (
                    submission_id,
                    schema_version,
                    client_submission_id,
                    project_key,
                    week_key,
                    week_date,
                    submitted_by,
                    supersedes_submission_id,
                    request_document_text,
                    request_sha256,
                    expanded_sha256
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING *
                """,
                submission_id,
                request.schema_version,
                request.client_submission_id,
                request.project_key,
                request.week_key,
                request.week_date,
                principal.subject,
                active_id,
                request_document.text,
                request_document.sha256,
                expanded_document.sha256,
            )
            await connection.executemany(
                """
                INSERT INTO water_planning.planning_depth_values (
                    submission_id,
                    section_id,
                    zone_id,
                    planning_depth_mm,
                    source_kind,
                    source_area_id
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                [
                    (
                        submission_id,
                        item.section_id,
                        item.zone_id,
                        item.planning_depth_mm,
                        item.source_kind,
                        item.source_area_id,
                    )
                    for item in expanded
                ],
            )
            return _receipt(inserted, replayed=False)
    except asyncpg.UniqueViolationError as exc:
        raise PlanningDepthConflictError("concurrent_successor_conflict") from exc


async def get_active_planning_depth_submission(
    connection,
    project_key: str,
    week_key: str,
) -> PlanningDepthActiveSubmission | None:
    active = await _load_active_row(connection, project_key, week_key)
    if active is None:
        return None
    rows = await connection.fetch(
        """
        SELECT section_id,
               zone_id,
               planning_depth_mm,
               source_kind,
               source_area_id
        FROM water_planning.planning_depth_values
        WHERE submission_id = $1
        ORDER BY section_id
        """,
        active["submission_id"],
    )
    levels = [
        PlanningDepthExpandedValue(
            section_id=row["section_id"],
            zone_id=row["zone_id"],
            planning_depth_mm=row["planning_depth_mm"],
            source_kind=row["source_kind"],
            source_area_id=row["source_area_id"],
        )
        for row in rows
    ]
    if (
        len(levels) != 41
        or canonicalize_expanded_planning_depth_values(levels).sha256
        != active["expanded_sha256"]
    ):
        raise PlanningDepthStoredDataError(
            "stored planning-depth projection is inconsistent"
        )
    return PlanningDepthActiveSubmission(
        schema_version=active["schema_version"],
        submission_id=active["submission_id"],
        client_submission_id=active["client_submission_id"],
        project_key=active["project_key"],
        week_key=active["week_key"],
        week_date=active["week_date"],
        submitted_at=active["submitted_at"],
        submitted_by=active["submitted_by"],
        supersedes_submission_id=active["supersedes_submission_id"],
        request_sha256=active["request_sha256"],
        levels=levels,
    )
