"""Locks for the migration-owned control domain (PR 4.2, roadmap-named)."""

from core.database import Base
from models.control_base import ControlBase
import models  # noqa: F401  (registers every legacy model on Base)
import models.control_plan  # noqa: F401  (registers control tables on ControlBase)

CONTROL_TABLES = {
    "scheduler.control_plan_runs",
    "scheduler.control_plan_requirements",
    "scheduler.gate_plan_events",
    "scheduler.control_state_transitions",
    "scheduler.section_delivery_ledger",
    "scheduler.control_plan_campaign_versions",
    "scheduler.control_command_outbox",
    "scheduler.control_active_gate_authority",
    "scheduler.control_command_execution_events",
}

LEGACY_TABLES = {
    "adjustment_rules",
    "field_instructions",
    "field_teams",
    "optimization_constraints",
    "schedule_adaptations",
    "scheduled_operations",
    "team_availabilities",
    "team_members",
    "weekly_adjustment_summaries",
    "weekly_schedules",
    "weekly_weather_adjustments",
}


def test_control_models_are_excluded_from_create_all():
    # The durable invariant is DISJOINTNESS, not zero tables — 4.3a will
    # legitimately attach control tables to ControlBase.
    assert ControlBase is not Base
    assert set(ControlBase.metadata.tables).isdisjoint(Base.metadata.tables)


def test_legacy_create_all_table_set_is_pinned():
    # A control table appearing here means it leaked onto the legacy Base
    # and would be created by main.py's create_all, bypassing the runner.
    assert set(Base.metadata.tables) == LEGACY_TABLES


def test_control_base_contains_exactly_the_migration_owned_tables():
    assert set(ControlBase.metadata.tables) == CONTROL_TABLES
