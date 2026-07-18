# scheduler — weekly irrigation scheduling & adaptation

**Python 3.11 / FastAPI** · Entry: `src/main.py` · **Extends [../../CLAUDE.md](../../CLAUDE.md)**

## Purpose
Weekly schedule generation/adaptation for Munbon field operations; consumes canonical
requirements and (from PR 4.3a onward) will own the non-commanding control-plan lifecycle.
PR 4.2 established the test/migration foundation; feature surfaces predate remediation —
treat outputs as provisional.

## Commands
```bash
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src ./venv/bin/python -m pytest -q     # THE gate (pytest.ini: testpaths=tests)
python src/main.py                                 # dev server
```
`.env` is load-bearing: `core/config.py` Settings has required fields with no defaults —
bare pytest fails at import without it.

## Migrations (PR 4.2)
`python migrations/migrate.py apply|rollback <id>` and `status` — one transaction per
migration, pair checksums in `scheduler.schema_migrations`, drift refusal both directions,
`POSTGRES_URL` only. **Control-domain tables attach to `models/control_base.ControlBase`
and are migration-owned ONLY** — the legacy `Base.metadata.create_all()` (main.py /
core/database.py) must never see them (locked by tests/unit/test_create_all_isolation.py;
legacy 11-table set pinned). PR 4.3a shipped the first pair (`0001_control_plan_drafts`:
control_plan_runs / control_plan_requirements / gate_plan_events /
control_state_transitions, all in the `scheduler` schema, immutability triggers, TEXT
canonical documents — never JSONB). PR 5.1 added `0002_predicted_delivery_ledger`
(`section_delivery_ledger`, append-only, reuses the 0001 immutability trigger function).
ORM ↔ DDL drift is locked across BOTH pairs by
tests/unit/test_control_models_match_migration_ddl.py; 4.3b relaxes the narrow
transition checks via a NEW migration, never by editing an applied pair.

## Predicted-fulfillment ledger (PR 5.1)
`project_predicted_delivery_ledger` (core/predicted_delivery_ledger.py) is a PURE
projection of a feasible draft's persisted prediction response into per-requirement,
per-checkpoint delivery rows, committed atomically inside `create_draft`. Key semantics:
- Flow attributes NO in-transit to requirements (delivery accounting is delivered-only);
  per-requirement transit is the sum of the requirement's OWN `path_reach_ids` reach
  `in_transit_volume_m3` — path-occupancy CONTEXT, NEVER additive across requirements,
  excluded from safe-close arithmetic.
- Member labels (lower/nominal/upper) are parameter-distribution positions, NOT a delivery
  ordering; raw member values are stored and API bounds are min/max across members.
- Prediction-only status vocabulary (6 values); reconciles to the persisted artifact at
  horizon end (fail-closed on mismatch/misalignment/missing path reach).
- Read-only ledger route: `GET /api/v1/control-plans/{plan_id}/versions/{version}/ledger`
  (min/max bounds + pure `evaluate_safe_handover` verdicts). The draft POST/GET is unchanged;
  BFF (4.4) consumes this route. `evaluate_safe_handover` is a pure predicate — no lifecycle
  transition (4.3b owns supersede).

## Tests
- Bare pytest = the gate; discovery confined to tests/ (root EC2 probes moved to
  `scripts/ops/*_probe.py`, non-test filenames — never collected).
- Integration suites are env-gated: `SCHEDULER_TEST_POSTGRES_URL` must name a DISPOSABLE
  LOOPBACK Postgres (non-loopback RAISES); they apply/rollback migration objects and
  create/drop the legacy create_all tables.
- pytest 7.4.3 + pytest-asyncio 0.21.1 (asyncio_mode=strict): do NOT upgrade pytest here
  casually, and prefer inline `@asynccontextmanager` helpers over async fixtures (ratified
  pattern; survives the eventual pytest 8.x jump).

## Gotchas / Watch-outs (PR 4.2 audit — foundation repaired, features NOT)
- **Removed as generation-drifted (2026-07-17)**: unit suites for MixedIntegerOptimizer +
  RealTimeAdapter (tested nonexistent APIs) and the 3 integration API suites (fake bearer
  vs real JWT decode; nonexistent routes; unimplemented WS subscribe protocol;
  monkeypatches that never took effect). Their honest replacements arrive with the 4.3x
  feature PRs; do NOT resurrect the deleted files.
- **Duplicate FieldTeam classes** (`models/schedule.py` — used by live endpoints — and
  `models/team.py` — used by TeamMember/Availability) merge into ONE `field_teams` table
  via `extend_existing`; team.py relationships bind by class object to dodge registry
  ambiguity. Consolidation is owed to a future PR; never add a third.
- **Known live defects (documented, out of 4.2 scope)**: `RealTimeAdapter.handle_demand_change`
  calls missing `_plan_water_reallocation`; `src/api/schedule.py` imports nonexistent
  `..main.db_manager` (dead module); hardcoded real-path constants throughout services/;
  `DELETE /schedule/{id}` is still broken (async lazy-load on cascade → MissingGreenlet;
  `adaptations` has no ORM cascade/passive_deletes) — the PR 4.2 `ondelete="CASCADE"` FKs
  record intent only, they do NOT make ORM deletes safe.
- **`POST /api/v1/scheduler/demands` has NO server in-tree**: ros-gis-integration and
  bff-water-planning still POST it, their clients swallow the 404 into
  `{"status": "failed"}` envelopes, and the deployed entry point (src/main.py, per PM2)
  never mounted it — pre-existing before PR 4.2 removed the dead alternate entrypoints
  (main_ec2/main_minimal) that once carried it. The demands intake gets its real,
  strict-contract home in the 4.3x scheduler lifecycle PRs; do NOT resurrect the deleted
  entrypoints for it.
- PR 4.2 fixed three never-worked schema landmines: btree index on JSON
  (`idx_team_zones`, removed), missing FKs behind `WeeklySchedule` relationships (added,
  `ondelete="CASCADE"`), ambiguous `"FieldTeam"` registry strings (class-object binding).
  `create_all` provisions a fresh real Postgres for the first time.
