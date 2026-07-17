"""Migration-owned control-domain metadata seam (PR 4.2).

Control-domain tables (control_plan_runs, gate_plan_events, command_intents,
...) attach to ControlBase ONLY, are created exclusively by
`python migrations/migrate.py apply <id>`, and ship with the PR that consumes
them (4.3a onward). ControlBase is deliberately NOT imported by
models/__init__.py, main.py, or core/database.py — the legacy
`Base.metadata.create_all()` path must never see these tables
(locked by tests/unit/test_create_all_isolation.py)."""

from sqlalchemy.orm import declarative_base

ControlBase = declarative_base()
