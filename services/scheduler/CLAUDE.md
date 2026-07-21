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

## Review lifecycle (PR 4.3b) — EVENT-SOURCED, append-only
`control_plan_runs` is fully immutable, so the current lifecycle state is DERIVED, fail-closed, from
the append-only `control_state_transitions` history (`core.control_plan_lifecycle.derive_control_plan_state`);
the runs `lifecycle_state` column stays `'draft'` (creation metadata) and the response's
`lifecycle_state` is the derived value. States: draft → under_review → approved_for_shadow, with
cancelled/superseded/invalidated terminal. Migration `0003_control_plan_review_lifecycle` relaxes ONLY
the four narrow 0001 transition CHECKs (never edits 0001) and adds an edge-graph CHECK — **use
`COALESCE(from_state,'__initial__')`: a tuple CHECK containing SQL NULL passes on UNKNOWN.** The down
restores the narrow checks and only succeeds while no seq>1 row exists (once lifecycle rows exist,
forward-fix, never down). Endpoints (POST `/control-plans/{id}/versions/{v}/{review,approve-for-shadow,
cancel,invalidate,supersede}`): each appends ONE transition in a txn; the (plan,version,sequence) PK is
the concurrency backstop (409). `approve_shadow_plan` runs the coverage gate (feasible optimizer +
completed 3-member prediction + no manual_review/invalidated ledger row; `predicted_excess_risk` stays
approvable) and FREEZES the exact requirement/model/prediction/ledger hashes into the shadow_approved
transition document (`machine_authority_granted=false`). Shadow approval grants NO machine authority;
supersede requires an approved successor with the SAME physical `(section_id, gate_id)` scope but NO
safe-handover (activation/4.3c owns that) and NO one-approved-per-scope uniqueness (deferred to 4.3c).

## Tests
- Bare pytest = the gate; discovery confined to tests/ (root EC2 probes moved to
  `scripts/ops/*_probe.py`, non-test filenames — never collected).
- Integration suites are env-gated: `SCHEDULER_TEST_POSTGRES_URL` must name a DISPOSABLE
  LOOPBACK Postgres (non-loopback RAISES); they apply/rollback migration objects and
  create/drop the legacy create_all tables.
- pytest 7.4.3 + pytest-asyncio 0.21.1 (asyncio_mode=strict): do NOT upgrade pytest here
  casually, and prefer inline `@asynccontextmanager` helpers over async fixtures (ratified
  pattern; survives the eventual pytest 8.x jump).

## Control-plan read contract v2 (BE-FE0)

The canonical read-only list/detail/prediction-coverage/ledger/lifecycle-history
contract is pinned under `contracts/control-plans/v2/` with a manifest, per-file
SHA-256 values, valid examples, and invalid drift fixtures. The list response is
`projection_schema_version=2` and includes `shadow_active`; v1 remains immutable
history and is no longer accepted by the runtime response model. Scheduler and
BFF must update their strict mirrors and fixture suites atomically on any future
version bump.

## Execution-authority grants (PR 7.1a) — represent authority, execute NOTHING

Migration `0012_authority_grants`: an IMMUTABLE per-plan-version
`control_authority_grants` row (UNIQUE(plan_id, plan_version); UNIQUE
grant_content_sha256 = replay idempotency; CHECK model_release_commandable IS
TRUE) + append-only `control_authority_grant_events` (granted seq-1 exactly
once → renewed* → revoked terminal, ONE revocation via a partial unique index).
Down REFUSES once any grant exists. TERMINOLOGY:
`control_active_gate_authority` is the SHADOW scope mutex; 0012 is EXECUTION
authority — always qualify. Current status is NEVER stored: fold via
`core.authority_grant.derive_authority_grant_status` (expired iff `now >=
expiry`, matching 5.2 deadline semantics; renewal must strictly extend and is
REFUSED at/after expiry — no resurrection; a lapsed grant needs a NEW grant).
Grant-time `validate_authority_evidence` binds: v2-provenance release triple
(v1 plans are NEVER grantable), commandability evidence that must itself
declare `commandable=true` AND bind the same triple (request evidence cannot
promote — Flow currently pins `commandable=false`, so no positive path exists),
the CURRENTLY CONFIGURED capability pair, EXACT physical scope equality
(requirements' (section, gate, path)), the flow envelope over
`gate_plan_events.source_flow_m3s` in `(lower, upper]`, longest-continuous-open
vs policy (an unclosed gate counts to `horizon_end`), trims ≥ the plan's own
setting, initialization exactly `{"kind":"dry"}` (wet-state ranges need a
future versioned contract), COMPLETE 0010 receipt coverage (every outbox
intent has an accepted receipt), and a strictly-future expiry capped by
`control_authority_lease_hours` (24 = the roadmap's lease checkpoint).
`verify_execution_authority` is the 7.2-consumable WHOLE-BATCH predicate
(partial actuation prevention); in 7.1a its only callers are grant preflight +
`POST /authority-grants/reviews` — it is NOT imported by the worker/dispatcher.
AUTHZ safety valence: review/grant/renew = supervisor + STRICT policy (503 in
compat → issuance impossible in every tracked deployment; the empty capability
snapshot is a second independent gate); revoke = supervisor WITHOUT the strict
gate (idempotent safety brake, mirrors the 5.2b hold precedent) and also works
on an expired grant (audit). Readiness now requires ALL 0001–0012 tables +
migration ids. Metrics: `control_authority_grant_events_total{event_type}` is
OBSERVATIONAL ONLY — never an authorization source. 7.2 obligation
(documented): a safe-close after expiry/revocation needs its own separately
authorized fail-safe path — do NOT bolt a bypass onto the grant predicate.

## Operator authority controls (PR 7.1b)

The Scheduler is the resource-server enforcement boundary for every operator
mutation. `approve-for-shadow`, `activate`, `hold`, `resume`, grant, renew, and
revoke require the byte-exact phrase from `core.operator_confirmation` in
`X-Operator-Confirmation`. Positive actions additionally verify
`X-Operator-Step-Up-Code` directly with Auth and atomically consume that
subject/code pair in Redis for 120 seconds; the same TOTP cannot authorize a
second action in its validity window. Replay-store failure is fail-closed.
`activate`, `resume`, grant, and renew also require live SCADA health plus an exact device-capability
release/hash match with Scheduler startup configuration. Hold and revoke never
call Auth or SCADA after confirmation, preserving the safety brake during an
outage. `/authority-grants/applicability` is a read-only stored-truth
projection; it accepts no evidence from the caller and integrity-checks the
stored command-intent batch before reporting grantability. No 7.1b route writes a
machine command, and tracked noncommandable/empty-capability configuration
keeps authority dark.

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
