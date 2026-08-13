# ROS Daily Requirement Temporal Qualification Planning

Date: 2026-08-12 (Asia/Bangkok)

Disposition: NO-GO remains in force. This planning pass does not implement code, qualify a commit/PR, mutate the preserved guest, replay acceptance, deploy, activate, or authorize another canonical campaign.

## Scope and evidence boundary

The current `main` checkout is dirty with 12 modified and 3 untracked files. The formal review at lines 1386 onward of the prior Coding Log is the governing input. The live source confirms the stale HTTP doubles, unrestricted manual date, provenance-only cutoff, superseded dedup conflict, v2/Flow lineage ambiguity, incomplete boundary/hash/coexistence coverage, and weak success validator.

Only the acceptance harness result `305 passed` is established. No ROS behavioral pass is claimed because the prior run stopped collection on missing `strawberry` and `structlog`.

### Locked decisions for this plan

1. The existing manual canonical endpoint accepts only the current operational date derived from the job's configured cron and timezone. Future dates and historical backfill are rejected. Historical backfill is a separate future feature, not silently added here.
2. `source_effective_date` equals the calculation/publication `as_of_date`. Divergence is an internal configuration error, not incomplete authoritative data.
3. `input_cutoff_at` is an upper eligibility bound: no selected source row may have a timestamp after it. It is not an atomic cross-database snapshot and cannot reconstruct overwritten values from mutable current tables.
4. An exact match to a current `published` run is a valid deduplicated transport retry. An exact match to `superseded` history is rejected and never republished as current. Abandoned `calculating` rows are failed before a new run.
5. Flow `method="ros_daily_requirement_v1"` remains the adapter/payload contract identity. The calculation identity `daily-requirement-v2` is propagated separately as `input_versions.requirement_method`.
6. Manual date and superseded conflicts use bounded, sanitized HTTP 409 envelopes. Unexpected configuration/programming failures remain 500 and are not mislabeled as incomplete sources.
7. No schema migration is required for the minimal fix. `water_requirement_runs.as_of_date` persists the effective/calculation date, and existing `input_cutoff_at`, `method_version`, and `content_hash` persist the remaining identity.

## Runtime path

`POST /api/v1/water-requirements/runs`
→ `trigger_daily_requirement_run`
→ `operational_date(now, job.cron, job.timezone_name)` authorization
→ `DailyRequirementJob.run_once(as_of_date, now)`
→ `AuthoritativeRequirementSourceLoader.load(source_effective_date, input_cutoff_at)`
→ `RequirementSnapshot`
→ v2 content hash and status-aware lookup
→ calculation/persistence/publication
→ `SELECT_FLOW_RECORDS_FOR_RUN`
→ Flow publisher
→ LOCAL-AC exact response validation
→ published database-lineage lookup.

---

# Plan Draft A — Minimal upper-bound remediation

## Overview

Keep the current schema and architecture. Complete the temporal separation by enforcing current-operational-date authorization at the manual API boundary, adding timestamp upper bounds to every source query, making dedup status-aware, and carrying the calculation method into Flow lineage.

## Files to change

- `services/ros-gis-integration/src/api/routes/water_requirements.py` — strict manual request/response models, date authorization, sanitized conflict mappings.
- `services/ros-gis-integration/src/services/daily_requirement_job.py` — effective-date invariant and superseded-match stop line.
- `services/ros-gis-integration/src/services/daily_requirement_producer.py` — distinguish configuration errors, lock v2 identity/invariant.
- `services/ros-gis-integration/src/services/requirement_source_loader.py` — timestamp upper-bound query predicates.
- `services/ros-gis-integration/src/db/daily_requirement_run_store.py` — status-truthful matching contract.
- `services/ros-gis-integration/src/db/water_requirement_repository.py` — select persisted method for Flow projection.
- `services/ros-gis-integration/src/services/flow_monitoring_publisher.py` — propagate calculation method separately from adapter method.
- `ops/control-plan-read-local/seed-approved-sources.py` — deterministic Bangkok-midnight capture and crop-setting `created_at`.
- `ops/control-plan-read-local/run-stage-suite.py` — exact success types/keys and bounded new conflict classifications.
- Focused unit/integration tests listed in the Unified Plan.
- `.github/workflows/control-plane-hardening-tests.yml` — run the complete ROS unit suite in the pinned dependency environment.
- `services/ros-gis-integration/CLAUDE.md` — precise effective-date/cutoff/version semantics after GREEN.

## TDD sequence

1. Repair stale HTTP doubles and write failing date/schema/serialization tests.
2. Write failing loader SQL cutoff and post-cutoff rejection tests.
3. Write failing dedup state-matrix, Flow lineage, hash, and strict harness tests.
4. Add the composed four-instant route-to-producer test and confirm expected RED causes.
5. Implement the smallest route/job/loader/store/repository/publisher/harness changes.
6. Refactor names only where current names are false, then run focused and full gates.

## Test coverage

- `test_manual_run_passes_injected_time_to_two_argument_job` — repairs stale serialized HTTP path.
- `test_manual_run_rejects_noncurrent_operational_date` — blocks future and historical canonical dates.
- `test_manual_run_openapi_locks_exact_conflict_envelopes` — locks literals and forbidden extras.
- `test_authoritative_loader_bounds_every_timestamped_source` — proves all query cutoff predicates.
- `test_authoritative_loader_fails_when_only_post_cutoff_rows_exist` — fails closed without eligible inputs.
- `test_daily_requirement_temporal_path_at_bangkok_boundaries` — composes four required UTC instants.
- `test_requirement_hash_matches_reviewed_v2_golden` — freezes independent v2 identity.
- `test_requirement_hash_changes_with_source_effective_date_only` — proves effective-date sensitivity.
- `test_daily_requirement_job_reuses_only_current_published_match` — accepts safe idempotent retry.
- `test_daily_requirement_job_rejects_superseded_match_without_publication` — blocks stale historical replay.
- `test_v1_and_v2_runs_coexist_without_cross_deduplication` — proves real PostgreSQL transition.
- `test_flow_record_keeps_adapter_method_and_adds_requirement_method` — disambiguates downstream lineage.
- `test_validate_manual_requirement_run_rejects_inexact_success` — rejects floats, booleans, extras, omissions.

## Decision completeness

- Goal: qualify the temporal boundary and lineage contract without broad redesign.
- Non-goals: backfill API, historical source reconstruction, cross-database atomic snapshots, canonical replay, deployment.
- Public interfaces: manual endpoint becomes current-operational-date only and adds two bounded 409 reasons; success shape is unchanged.
- Failure mode: post-cutoff or missing source inputs fail closed before persistence/publication.
- Rollout: no flag or migration; deploy only after full ROS, PostGIS, harness, QCHECK, and g-check gates.
- Backout: revert the cohesive source commit before deployment; no data migration rollback is needed.

## Dependencies and validation

Use the pinned Python 3.11 service dependencies. Run the complete ROS unit suite, harness tests, disposable PostGIS migrations/integration, static gates, then repository `make test`. No campaign command belongs to this source-qualification plan.

## Wiring verification

| Component | Entry point | Registration | Schema/table |
|---|---|---|---|
| Manual date authorization | `POST /api/v1/water-requirements/runs` | existing router in `src/main.py` | none |
| Source cutoff predicates | `DailyRequirementJob.run_once` | existing loader injected in lifespan | source `gis.zone`, `water_planning.zone_planting_dates`; local `ros_gis.section_crop_settings`, `ros.eto_monthly`, `ros.kc_weekly`, `ros.effective_rainfall_monthly` |
| Status-aware dedup | job hash lookup | existing `PostgresDailyRequirementRunStore` | `ros_gis.water_requirement_runs` and migration 0003 unique index |
| Calculation method lineage | Flow records for run | existing repository query and publisher | `water_requirement_runs.method_version`, requirement `input_versions` JSON |
| Strict LOCAL-AC envelope | `run_local_ac` | existing manual-run validators | published lineage query |

## Cross-language schema verification

Python loader reads the six source tables above. Node ROS writers use upsert/update semantics for ETo and Kc, and the acceptance seeder upserts GIS, planting, ETo, Kc, and rainfall. Therefore cutoff predicates guarantee “no future row selected” but not historical reconstruction after an overwrite. The plan must document that limitation and must not call the result an atomic reproducible snapshot.

---

# Plan Draft B — Versioned historical snapshot remediation

## Overview

Introduce append-only history/version tables for every mutable source and persist a distinct source snapshot/version identity. This makes `input_cutoff_at` a reconstructable historical snapshot boundary and can support bounded backfill later.

## Files to change

Draft A files, plus new ROS-GIS migrations, ROS writer changes for append-only history, source-database migration/writer changes for GIS and planting history, expanded repository models, and operational migration/runbook documentation.

## TDD sequence

1. Write cross-language migration and writer tests for immutable history rows.
2. Confirm current upserts destroy pre-cutoff reconstruction and tests RED.
3. Add history schema/writers and as-of queries in each database.
4. Persist snapshot/version lineage on requirement runs.
5. Run migration rollback/reapply, writer, loader, and replay tests.

## Test coverage

- `test_source_history_preserves_pre_update_value` — retains overwritten agronomic source state.
- `test_loader_reconstructs_all_sources_at_cutoff` — proves historical as-of snapshot.
- `test_backfill_uses_persisted_source_snapshot_identity` — locks reproducible replay identity.
- `test_cross_database_snapshot_versions_are_auditable` — records both database boundaries.

## Decision completeness

- Goal: reconstruct source state at an arbitrary historical cutoff.
- Non-goals: a distributed ACID transaction across both databases.
- Public interfaces: potentially supports a later bounded backfill endpoint; not enabled in this change.
- Migrations: required in both source and local databases with writer rollout ordering and rollback constraints.
- Failure mode: fail closed when any source lacks history at the requested cutoff.
- Rollout: dual-write/backfill/read-switch sequencing is required.
- Backout: switch reads to current tables before reversing writers; history data remains append-only.

## Dependencies and validation

Requires coordinated ownership of the ROS writers, GIS/planting source database, schema migrations, backfill policy, and operational rollout. This exceeds the reviewed dirty change and cannot be qualified as a small repair.

## Wiring verification

| Component | Entry point | Registration | Schema/table |
|---|---|---|---|
| Source history writers | ROS/GIS upload paths | each existing upsert service | new history tables in both databases |
| Historical loader | daily requirement job | existing loader injection | history views/tables plus snapshot versions |
| Snapshot lineage | run persistence | repository/store | new run lineage columns/table |

## Cross-language schema verification

Every Node/Python writer and SQL consumer must be updated and proven against the same history table/column names. Current evidence shows mutable upserts, so this alternative cannot be implemented only inside ROS-GIS integration.

---

# Comparative analysis

Draft A is the smallest cohesive repair. It closes future leakage, prevents arbitrary manual dates and stale superseded replay, preserves current schema compatibility, and makes the provenance claim honest. Its limitation is explicit: it cannot reconstruct values already overwritten after the cutoff.

Draft B provides stronger historical reproducibility and a credible future backfill foundation. It is materially larger, crosses database/service ownership, requires migrations and writer rollout, and is unsuitable for repairing the current NO-GO work without a new architecture decision and scope authorization.

Both drafts preserve fail-closed behavior and separate Bangkok operational dates from UTC instants. Draft A is selected because the immediate requirement is current-day canonical publication at the UTC/Bangkok boundary, not historical replay.

---

# Unified Execution Plan

## Overview

Implement Draft A. Complete the existing direction with strict API authorization, an honest timestamp upper-bound contract, status-aware dedup, explicit calculation lineage, composed boundary evidence, and complete dependency-environment tests. Keep campaign/runbook work separate.

## Files to change

### Production and runtime

1. `services/ros-gis-integration/src/api/routes/water_requirements.py`
   - Add `ConfigDict(extra="forbid")` to manual request/success/failure models.
   - Import and use `operational_date` with the injected aware `now`, job cron, and job timezone.
   - Reject any manual `asOfDate` not equal to the current operational date before loading sources.
   - Declare exact bounded 409 unions for incomplete source, unauthorized date, and superseded-match conflicts.
   - Construct detail through typed models so runtime output matches OpenAPI.

2. `services/ros-gis-integration/src/services/daily_requirement_producer.py`
   - Add `RequirementConfigurationError` for invalid function parameters and effective-date divergence.
   - Enforce `snapshot.source_effective_date == as_of_date` inside `requirement_run_content_hash`, before dedup.
   - Keep authoritative missing/inconsistent source rows as `RequirementInputError`.
   - Retain `METHOD_VERSION = "daily-requirement-v2"` and the effective date in the hash.

3. `services/ros-gis-integration/src/services/requirement_source_loader.py`
   - `gis.zone`: add `create_date <= cutoff`.
   - planting dates: add `updated_at <= cutoff` alongside project key.
   - crop settings: require both `as_of_date <= source_effective_date` and `created_at <= cutoff`.
   - ETo, Kc, rainfall: add `updated_at <= cutoff`.
   - Pass the normalized UTC cutoff as explicit query arguments.
   - Keep the planting lower-age check. A row exactly at cutoff is eligible; null/post-cutoff rows are ineligible and missing required data fails closed.

4. `services/ros-gis-integration/src/db/daily_requirement_run_store.py`
   - Rename `find_published` to `find_matching_nonfailed` because it returns status-bearing matches.
   - Keep abandoned `calculating` recovery.
   - Return `published` or `superseded` with status; do not hide state.

5. `services/ros-gis-integration/src/services/daily_requirement_job.py`
   - Add `RequirementRunSupersededError`.
   - Reuse/repost only an exact current `published` match.
   - Reject an exact `superseded` match before loading Flow records or publishing.
   - Keep a failed abandoned `calculating` match eligible for a new run.

6. `services/ros-gis-integration/src/db/water_requirement_repository.py`
   - Include `run.method_version` in `SELECT_FLOW_RECORDS_FOR_RUN`.
   - Keep migration 0003 status/uniqueness semantics unchanged.

7. `services/ros-gis-integration/src/services/flow_monitoring_publisher.py`
   - Name the stable adapter constant `FLOW_DEMAND_METHOD = "ros_daily_requirement_v1"`.
   - Add `input_versions["requirement_method"] = row["method_version"]`.
   - Preserve byte-equivalent retries for the same current run.

8. `ops/control-plan-read-local/seed-approved-sources.py`
   - Set scenario `captured_at` to Bangkok midnight for `as_of_date`, converted to UTC.
   - Include deterministic crop-setting `created_at` and insert it explicitly.
   - This fixes the existing Aug 12 seed value (`00:00Z`) being 44 seconds after the original `23:59:16Z` request cutoff; the correct Bangkok-midnight instant is Aug 11 `17:00Z`.

9. `ops/control-plan-read-local/run-stage-suite.py`
   - Require an exact dict/key set for success.
   - Require exact scalar types; `type(requirementCount) is int` rejects `287.0` and booleans.
   - Keep success statuses limited to `published|deduplicated`.
   - Extend exact failure validation only for `manual_date_not_current` and `requirement_run_superseded`; arbitrary 409 bodies remain rejected.
   - Keep lineage restricted to a published run.

10. `.github/workflows/control-plane-hardening-tests.yml`
    - Replace the narrow ROS loader-only command with `python -m pytest -q tests/unit` in the pinned Python 3.11 dependency job, or add an equivalent complete ROS unit job.
    - Keep the disposable PostGIS integration job and migration order.

11. `services/ros-gis-integration/CLAUDE.md`
    - After GREEN, document current-date-only manual runs, effective date equality, cutoff upper-bound limitation, and adapter/calculation version distinction.

### Tests

1. `services/ros-gis-integration/tests/unit/test_water_requirement_read_api.py`
   - Update `_ManualJob` and `_FailingJob` to accept `(as_of_date, now)` and expose cron/timezone.
   - Inject deterministic time in `_manual_run_client`.
   - Replace raw error text with exact sanitized bodies.
   - Test current/future/past dates, unexpected 500, forbidden extras, and exact OpenAPI enums/unions.

2. `services/ros-gis-integration/tests/unit/test_water_requirements_route.py`
   - Retain direct dispatch tests but add date authorization and configuration-error nonclassification.

3. `services/ros-gis-integration/tests/unit/test_requirement_source_loader.py`
   - Assert every SQL query contains its timestamp predicate and receives cutoff.
   - Test exactly-at-cutoff eligibility and post-cutoff fail-closed behavior for each source family.

4. `services/ros-gis-integration/tests/unit/test_daily_requirement_temporal_path.py` (new)
   - Parameterize `16:59:59Z`, `17:00:00Z`, `23:59:16Z`, and `00:00:00Z`.
   - Use FastAPI dependency overrides, a real job, real loader, real producer/hash, focused fake source/local connections, a recording store, and recording publisher.
   - Prove correct operational date, effective/cutoff preservation, successful Bangkok-today publication, future-date rejection before load, post-cutoff source rejection, and zero publication on failure.

5. `services/ros-gis-integration/tests/unit/test_daily_requirement_producer.py`
   - Add a reviewed literal v2 golden SHA-256.
   - Add deterministic-ordering and effective-date-only sensitivity cases.
   - Test effective/calculation date mismatch as configuration error.

6. `services/ros-gis-integration/tests/unit/test_daily_requirement_run_store.py`
   - Cover published, superseded, calculating, failed, and no-match status behavior.

7. `services/ros-gis-integration/tests/unit/test_daily_requirement_job.py`
   - Prove only current published matches deduplicate/repost.
   - Prove superseded matches never call Flow or start a new run.

8. `services/ros-gis-integration/tests/unit/test_flow_monitoring_publisher.py`
   - Lock adapter method and calculation method lineage separately.

9. `services/ros-gis-integration/tests/unit/test_water_requirement_publication.py`
   - Lock SQL projection of persisted `method_version`.

10. `services/ros-gis-integration/tests/integration/test_water_requirement_repository_postgres.py`
    - Create/publish v1, then v2 for one date; prove v1 superseded, v2 published, both retained, no cross-version dedup, and duplicate v2 nonfailed identity rejected.

11. `ops/control-plan-read-local/tests/test_seed_approved_sources.py`
    - Lock Bangkok-midnight UTC capture and explicit crop-setting timestamp.

12. `ops/control-plan-read-local/tests/test_stage_suite.py`
    - Add null/list/string, missing/extra key, invalid UUID, float count, boolean count, wrong scalar type, bounded date conflict, and bounded superseded conflict cases.

## RED → GREEN → REFACTOR order

1. Repair the stale HTTP doubles first and confirm the existing serialized success and 409 tests fail for the expected call-signature/body reasons.
2. Add manual-date policy and exact OpenAPI/response tests; confirm unrestricted dates and default extra handling fail them.
3. Add query-shape and post-cutoff loader tests; confirm absent predicates are the RED cause.
4. Add status-matrix tests; confirm superseded content is republished and accepted as deduplicated today.
5. Add Flow lineage and v2 golden/coexistence tests; confirm calculation method is absent downstream and transition coverage is missing.
6. Add strict harness cases; confirm extra keys and `287.0` are accepted today.
7. Add the four-instant composed test; confirm it crosses route/job/loader/producer rather than merely constructing a snapshot.
8. Implement production changes in the same order, with no unrelated refactor.
9. Run focused GREEN tests after each slice, then the complete unit/PostGIS/harness/static gates.
10. Only after all GREEN gates, perform naming/docs cleanup and rerun all gates.

## Expected failure modes

- Unauthorized manual date: sanitized 409, job/source loader not called.
- Incomplete/invalid authoritative source: existing bounded sanitized 409, no persistence/publication.
- Post-cutoff current row with no historical eligible row: fail closed as incomplete source; never use the newer value.
- Internal date mismatch or invalid horizon: 500/configuration failure, not a sanitized source-data 409.
- Published exact match: `deduplicated`, same run UUID/date/count, Flow repost allowed, lineage remains published.
- Superseded exact match: sanitized 409, no Flow call, no new run.
- Abandoned calculating match: mark failed, then calculate a new run.

## Acceptance commands

Run in an isolated worktree with the complete pinned dependency environment:

```bash
cd services/ros-gis-integration
python3.11 -m pip install -r requirements.txt
CORS_ORIGINS=http://localhost:3000 python3.11 -m pytest -q tests/unit
```

```bash
cd /Users/subhajlimanond/dev/munbon2-backend
python3.11 -m pytest -q \
  ops/control-plan-read-local/tests/test_stage_suite.py \
  ops/control-plan-read-local/tests/test_seed_approved_sources.py
```

Disposable PostGIS, after applying migrations in exact order 0001 → 0002 → 0003:

```bash
cd services/ros-gis-integration
WATER_REQUIREMENT_TEST_POSTGRES_URL="$TEST_POSTGRES_URL" \
  python3.11 -m pytest -q tests/integration/test_water_requirement_repository_postgres.py
```

Static/repository gates:

```bash
python3.11 -m black --check <changed-python-files>
python3.11 -m ruff check <changed-python-files>
python3.11 -m compileall -q services/ros-gis-integration/src services/ros-gis-integration/tests ops/control-plan-read-local
git diff --check
make test
```

Do not claim qualification from AST/Black/harness-only evidence. The complete ROS unit suite and real PostGIS transition test are mandatory.

## Wiring verification

| Component | Runtime entry | Registration/caller | Schema/table verification |
|---|---|---|---|
| Manual operational-date guard | `POST /api/v1/water-requirements/runs` | existing router included by `src/main.py` | no schema |
| Typed manual conflicts | same route | FastAPI response models and exception mapping | exact HTTP/OpenAPI shape |
| Effective-date invariant | job hash before lookup | `DailyRequirementJob.run_once` | persisted as `water_requirement_runs.as_of_date` |
| Timestamp-bound loader | job source load | existing lifespan-injected loader | `gis.zone.create_date`; planting/ETo/Kc/rainfall `updated_at`; crop `created_at` |
| Status-aware dedup | content-hash lookup | job → run store | migration 0003 `(as_of_date, content_hash)` partial unique index |
| Calculation lineage | Flow records query | repository → publisher | `water_requirement_runs.method_version`; Flow `input_versions` |
| Deterministic acceptance seed | LOCAL-AC seeding | `_seed_approved_sources` | exact six source tables |
| Strict evidence validation | LOCAL-AC manual request | `run_local_ac` validators | published-only lineage SQL |
| Complete dependency gate | GitHub Actions | ROS unit job | service `requirements.txt` includes Strawberry and structlog |

## Rollout, monitoring, and backout

- No feature flag or migration is added.
- Before deployment, monitor/inspect sanitized conflict counts by reason, source-incomplete errors, abandoned calculating recovery, superseded-match rejection, and Flow publication failures.
- Backout is a normal source rollback before any new canonical run; no schema/data rollback is required.
- Do not mutate or retry the preserved guest. A fresh non-authoritative pristine BASE → RTA → LOCAL-AC rehearsal is a later qualification action requiring explicit authorization after implementation, full gates, QCHECK, and g-check.
- A new canonical campaign requires separate authorization because the three-attempt ceiling is exhausted.

## Decision-complete checklist

- [x] Goal/non-goals and success criteria are locked.
- [x] Manual date, cutoff, dedup, Flow version, and effective-date semantics are locked.
- [x] Every public response change has serialized HTTP and OpenAPI tests.
- [x] Every behavior change has a defect-sensitive RED test.
- [x] Runtime entry points, registration, and schema/table names are identified.
- [x] No unnecessary migration is proposed.
- [x] Exact focused/full validation commands are listed.
- [x] Campaign, deployment, and guest actions remain explicitly unauthorized.

## Review (2026-08-13 04:00:28 +0700) - system

### Reviewed
- Repo: `/Users/subhajlimanond/dev/munbon2-backend`
- Branch: `main` at `5cfdb2a05b4ea4c2742250845ae55a76816700bd`; `HEAD == origin/main`
- Scope: canonical OrbStack worker; historical frozen 7/9 versus later 2 passed / 1 failed / 6 unreached; live guest/evidence truth; current dirty temporal remediation
- Commands Run: repository identity/status/log; RepoPrompt context-builder and focused reads; uncommitted/historical diff summaries; read-only OrbStack inventory/guest state; attempt-3 inner/outer SHA-256 verification; focused harness/ROS pytest; independent Terra QCHECK
- Sources: root guidance; acceptance runbook; frozen `0228f495` evidence; attempt-3 `5cfdb2a0` archive; orchestration/bootstrap/runtime/stage code; ROS route/job/loader/producer/store/tests; prior/current Coding Logs

### High-Level Assessment
- Disposition remains **NO-GO**. Neither campaign is 9/9 acceptance; this review authorizes no guest mutation, reprovisioning, fourth attempt, deployment, or activation.
- The pasted `dd81b687` / `63ed11aa...` / `01KZP2DG...` handoff is historical. Live `munbon-control-plan-local` is `01KZSKQ6FY4EVCCY94XGWZ9NDS`, owner/ready-bound to backend `5cfdb2a0`, frontend `067b3e22`, and bundle `65b08e34...`, with BASE/RTA complete and AC failed.
- “2/9” means **2 passed, 1 failed, 6 unreached**. Stages 4-9 were not evaluated, so this is not evidence of seven regressions.
- Historical 7/9 used a warm/mutable guest with live dependencies, retained state/secrets, and ambient PM2. The later fresh, content-addressed, offline contract removed those accidental supports and exposed latent seams.
- The actual stage regression is AC: unchanged ROS code passed when UTC/Bangkok shared a civil date and failed at the midnight boundary when they did not.
- The dirty remediation separates Bangkok operational date from UTC provenance in the right direction, but current tests prove it is not qualification-ready.

### As-Is Pipeline Diagram
- Exact host identities/date -> fresh offline Debian ARM64 provisioning and owner publication -> BASE identity/dark-state gate -> RTA migrations, PostGIS, monitoring, auth, pinned PM2/Node, four-service five-minute stability -> AC seeds 41 Bangkok-date settings and POSTs the manual ROS run -> loader/producer validate source time and publish 287 records plus lineage -> stages 4-9 only after AC. Attempt 3 stopped inside AC at the UTC/Bangkok boundary.

### Strengths
- Strict stage prerequisites preserve PASS/FAIL/unreached truth.
- Owner, provisioning, candidate, dependency, harness, and stage identities are explicit.
- Attempt-3 failure evidence has verified inner/outer checksum indexes and containment evidence.
- Later RTA evidence is stronger than historical RTA: pristine offline closure, PostGIS parity, non-root Prometheus, pinned PM2/Node, bearer lifecycle, dark flags, zero restart drift, five-minute stability.
- The three-attempt ceiling was honored; no in-place repair/replay manufactured acceptance.

### Key Risks / Gaps (severity ordered)

CRITICAL
- No additional critical product defect is proven. Acceptance remains blocked because no candidate has 9/9 evidence.

HIGH
- **Stale handoff can target the wrong lifecycle boundary.** Old guest `01KZP2DG...` is not the live canonical guest. Any future authorization must use current live identity and campaign state; old deletion wording must not be reused.
- **Score language overstates regression.** Frozen `0228f495` proves seven passes; attempt 3 proves BASE/RTA passes and AC failure for `5cfdb2a0`. Later stages are unknown, not failed or healthy.
- **UTC instant and Bangkok civil date were conflated.** Attempt 3 seeded/requested August 12 but ran `2026-08-11T23:59:16Z`; all 41 Bangkok-current settings were rejected as UTC-future. The ROS path is unchanged between campaign SHAs, so this was latent and timing-dependent.
- **Qualifications were too narrow for three attempts.** PostGIS, Prometheus, and PM2 were proven one seam at a time; no fresh exact non-authoritative BASE -> RTA -> AC rehearsal composed the next real path.
- **Current remediation lacks a valid RED/GREEN baseline.** The dirty tree has 17 changed/untracked files on `main`. The intended boundary test at `test_daily_requirement_producer.py:75-87` fails because July fixtures omit August ETo/Kc/rainfall, not because of the time contract. Focused ROS run: `65 passed, 1 failed`; serialized HTTP run: `18 passed, 2 failed` due stale one-argument doubles/raw-error expectations. Wrong-reason failures are not valid RED.

MEDIUM
- **`input_cutoff_at` is not a real upper bound.** `requirement_source_loader.py:42-87` does not constrain every timestamped source at/before cutoff, so post-cutoff data can enter a cutoff-labelled run.
- **Dedup and lineage disagree.** Store can return `superseded`; job republishes it as `deduplicated`; dirty harness accepts it; lineage still requires `published`.
- **Manual endpoint accepts unrestricted dates.** Boundary correction does not authorize arbitrary future publication or historical backfill.
- **Calculation identity is partially propagated.** Run/store use `daily-requirement-v2`; Flow still emits `ros_daily_requirement_v1` without a separate tested calculation-method lineage.
- **Domain error mapping is overbroad.** Every `RequirementInputError` becomes incomplete-source 409, including internal argument/configuration failures that should remain 500-class.
- **Partial failure collection is manual.** Strict 9/9 finalization is correct, but stopped-prefix archiving lacks a first-class non-acceptance collector.
- **Runbook is stale.** `CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md:384-401` still calls historical 7/9 the latest result.

LOW
- `StageContext.as_of_date = date.today()` is evaluated at import time; canonical pinning avoids it, diagnostics may not.
- Success validation permits extra keys and `287.0`, unlike the exact failure envelope.
- Frozen WRITE-UI evidence omitted the rejected browser JSON, so its exact failed predicate is unprovable.

### Drift Matrix

| Intended | Implemented / observed | Impact | Fix direction |
| --- | --- | --- | --- |
| Handoff identifies live guest | Pasted ID is a deleted predecessor | Wrong authorization boundary | Generate handoff from live inventory plus owner/stage state |
| Pinned date makes AC deterministic | Live UTC still affected civil eligibility | Wall-clock-dependent result | Separate Bangkok date from UTC instant/cutoff |
| 2/9 means seven failures | Six stages were unreached | False regression narrative | Always report pass/fail/unreached |
| Historical 7/9 predicts pristine readiness | Warm guest had ambient/retained supports | Masked reproducibility gaps | Bind evidence to candidate plus guest contract |
| Qualification protects attempts | Each stopped at latest fixed seam | One latent defect per attempt | Rehearse full next prefix non-authoritatively |
| Cutoff guarantees lineage | Queries are not fully upper-bounded | Post-cutoff data can enter run | Enforce predicates or weaken/rename claim |
| Deduplicated means safe current retry | Superseded match can republish | Stale Flow then lineage fail | Reuse current published only |
| TDD proves temporal change | Boundary test fails on missing fixtures | False RED/confidence | Require named expected failure reason |
| Runbook states current truth | Historical 7/9 still called latest | Operator drift | Append-only ledger/generated current view |

### Nit-Picks / Nitty Gritty
- Same frontend SHA does not provide new WRITE-UI evidence because attempt 3 never reached stage 8.
- Scheduling away from midnight hides rather than fixes the temporal defect.
- Old `63ed11aa...` failure bundle remains valid only for `dd81b687`; it cannot qualify `5cfdb2a0`/`65b08e34...`.
- The plan is ahead of implementation: cutoff predicates, status-aware dedup, date authorization, strict success schema, Flow lineage, composed temporal tests, and CI coverage are not yet present.

### Tactical Improvements (1-3 days)
1. Restore test integrity. Done when boundary RED fails on the old date comparison, HTTP doubles accept/invariant-check `(as_of_date, now)`, and no failure is caused by missing August fixtures or accidental `TypeError`.
2. Lock current-Bangkok-date-only manual policy. Done when four UTC boundary instants compose route -> real job -> real loader -> producer and explicitly accept/reject dates.
3. Make cutoff honest. Done when each timestamped source is bounded at/before cutoff, exactly-at-cutoff passes, and post-cutoff-only data fails closed.
4. Make dedup status-aware. Done when only current `published` matches repost; `superseded` rejects before Flow; calculating/failed/absent paths are tested.
5. Complete response/lineage contracts. Done when data errors vs configuration errors, exact success types/keys, and Flow adapter vs calculation method agree across API/harness/store/publisher tests.
6. Run full gates from an isolated worktree: complete ROS unit, real PostGIS v1/v2 coexistence, all harness tests, Black, Ruff, compilation, diff check, repository tests, QCHECK, and `g-check`.
7. Add first-class partial evidence and an append-only campaign ledger without weakening the strict 9/9 finalizer.

### Strategic Improvements (1-6 weeks)
1. Version a campaign manifest with candidate/dependency/harness hashes, guest contract/ID, timezone/date/instant policy, stage order, ceiling, evidence schema, and authorization state.
2. Build a qualification ladder: artifact schema -> offline validation -> pristine provisioning -> consumer-identity preflight -> non-authoritative full stage prefix -> canonical attempt.
3. Introduce explicit UTC-instant and Bangkok-civil-date domain types/functions, with hash/version compatibility tests.
4. Generate current operator status from append-only machine-readable campaign entries while keeping frozen evidence immutable.

### Big Architectural Changes (only if justified)
- Proposal: separate qualification orchestration from authoritative acceptance while sharing immutable stage implementations and identity checks.
  - Pros: discovers composed failures without consuming authoritative attempts; structurally labels evidence non-authoritative; protects canonical targeting.
  - Cons: adds a second machine/evidence profile and risk of promoting qualification output.
  - Migration Plan: fixed qualification guest/profile -> isolated evidence root with `acceptance=false` -> strict finalizer rejects qualification artifacts -> require clean BASE -> RTA -> AC qualification before seeking new campaign authorization.
  - Tests/Rollout: target-crossing refusal, canonical-guest refusal, evidence-root separation, finalizer rejection, full-prefix rehearsal, then explicit human authorization.

### Open Questions / Assumptions
- Safest minimal manual policy is current Bangkok operational date only; backfill and future simulation should be separate.
- Confirm Flow `method` is adapter identity and a separate field carries calculation identity.
- OrbStack reports the guest machine running, while archived containment says four application PM2 processes were stopped. Machine state is not application acceptance; this review made no process mutation.
- Fresh qualification and any new canonical campaign each require separate explicit authorization; this report grants neither.

## G2 DREP (2026-08-13 08:23:19 +0700) - ROS temporal qualification and partial evidence

### 0. Repository profile

- Root: `/Users/subhajlimanond/dev/munbon2-backend-ros-temporal-qualification-g2`
- Branch/base: `fix/ros-temporal-qualification-g2` at `5cfdb2a05b4ea4c2742250845ae55a76816700bd`, tracking the refreshed identical `origin/main`.
- Protected source state: stash commit `9c499ddb2e0be7b0316c291b1876ba230ec6dbec` was applied without dropping it. The primary checkout remains clean on `main` at the same SHA.
- Candidate baseline: 13 modified and 4 untracked files from the preserved remediation. They are evidence to audit, not accepted implementation.
- Policy: root `AGENTS.md`, root `CLAUDE.md`, root `CONTEXT.md`, and `services/ros-gis-integration/CLAUDE.md`. TDD, Python 3.11, exact tests, conventional commits, branch/PR/admin merge, and no direct push to `main` apply.
- Runtime: Python 3.11.12. The usable existing dependency environment is `/Users/subhajlimanond/dev/munbon2-backend/services/ros-gis-integration/venv`; bare `python3.11` lacks pytest.
- Coding Log pointer resolves to this file. It is primary-owned and excluded from any delegate allowlist.
- RepoPrompt was bound to the exact isolated root and one focused context build covered route, job, loader, producer, store/repository, Flow adapter, harness, orchestrator, seed path, migrations, tests, CI, and documentation.
- External model: the user explicitly selected g2, which authorizes the opt-in route, but the live primary permission profile is unrestricted and cannot prove the required child `workspace-write` containment with no extra writable roots. Q0 therefore fails closed. No repository content will be delegated to DeepSeek; all production slices are `PRIMARY`.
- No `g2-check` package is installed. The g2 lifecycle's required review sequence is independent non-DeepSeek QCHECK followed by the existing formal `g-check`.
- Scoped gates: focused pytest commands listed in each test contract. Full affected gates: ROS unit suite; real PostGIS repository suite when a disposable migrated URL is available; harness stage/orchestrator/seeder suites; Black; Ruff; compileall; `git diff --check`.
- Repository-wide gate: `make test`, interpreted per root guidance as additional evidence rather than a replacement for service-specific gates.
- Migrations: no schema migration is planned. Existing 0001-0004 schema supports the required status/version behavior; real-DB tests must apply all four in order.

### 1. Goal, non-goals, and success

Goal: finish the preserved temporal remediation so canonical manual publication uses the Bangkok operational civil date while every source row is bounded by the UTC cutoff, run reuse is status-safe, and calculation lineage is explicit through Flow. Harden source and harness contracts, add checksum-bound non-acceptance partial collection plus an append-only campaign ledger, and deliver through reviewed PR, authorized admin merge, exact-SHA local-main landing, and worktree cleanup.

Non-goals:

- No guest mutation, provisioning, process restart, canonical retry, fourth campaign attempt, rehearsal, deployment, activation, or deletion.
- No historical/future publication through the canonical manual endpoint; backfill/simulation remain separate and unimplemented.
- No weakening of the strict exact 9/9 acceptance finalizer.
- No migration or change to the stable Flow adapter identity `ros_daily_requirement_v1`.
- No claim that stages 4-9 regressed or passed in attempt 3.

Success criteria:

- Manual publication accepts only `operational_date(now, job.cron, job.timezone_name)` and rejects other dates before loading or publishing.
- All six timestamp-bearing authoritative queries apply inclusive `<= input_cutoff_at` predicates with exact argument-order tests.
- Four specified UTC instants exercise the composed route -> real job -> real loader -> real producer path and prove accepted/rejected dates plus no side effects on rejection.
- Exact published matches deduplicate/repost; calculating matches are failed then retried; superseded matches return typed conflict before Flow.
- Missing/inconsistent authoritative data maps to sanitized 409; manifest/config/programming errors remain 500.
- Persisted calculation method `daily-requirement-v2` appears separately in Flow `input_versions.requirement_method`, while adapter `method` remains `ros_daily_requirement_v1`.
- API and harness success/failure envelopes require exact keys and scalar types.
- A separately named partial collector validates a checksum-bound stopped prefix and emits `acceptance=false`; strict acceptance continues to reject it.
- A validated hash-chained JSONL campaign ledger preserves frozen 7/9 and current 2 passed / 1 failed / 6 unreached truth without implying authorization or deployment.
- Relevant gates, three repeated affected suites, QCHECK, and formal `g-check` pass; PR is merged, local `main` equals exact `origin/main`, and the session worktree is removed.

Public interface decisions:

- `POST /api/v1/water-requirements/runs` retains its request and success fields but adds bounded 409 reasons `operational_date_mismatch` and `superseded_lineage`; it no longer exposes raw source details.
- No new environment variable, table, column, migration, message topic, or deployment flag.
- Host CLI adds `collect-partial-failure`; normal `collect` retains strict acceptance semantics.
- New tracked machine-readable ledger: `docs/operations/control-plan-acceptance-campaign-ledger.jsonl`, force-added because blanket `docs/` ignore applies.
- Rollback: revert the landed commit/PR. Because there is no migration, rollback is source-only; dark-by-default flags remain unchanged.

### 2. Requirements

- `R1` Repair every existing wrong-reason temporal/HTTP test before using it as RED evidence.
- `R2` Authorize manual publication only for the current Bangkok operational date and reject mismatch before job execution.
- `R3` Preserve Bangkok civil `source_effective_date` separately from aware UTC `input_cutoff_at`.
- `R4` Apply an inclusive cutoff to GIS zones, planting dates, crop settings, ETo, Kc, and rainfall queries.
- `R5` Fail closed when no eligible authoritative row remains after the cutoff.
- `R6` Reuse/repost only an exact `published` run; recover `calculating`; reject `superseded` before Flow.
- `R7` Separate authoritative-data errors from manifest/configuration/programming errors at the API boundary.
- `R8` Persist and propagate calculation method `daily-requirement-v2` separately from Flow adapter identity.
- `R9` Enforce exact manual success and conflict envelope keys and exact scalar types in the harness.
- `R10` Seed source timestamps deterministically at Bangkok midnight converted to UTC and explicitly seed crop-setting `created_at`.
- `R11` Collect a checksum-bound partial stopped prefix as explicitly non-acceptance evidence without changing strict 9/9 finalization.
- `R12` Maintain a validated append-only hash-chained campaign ledger for historical 7/9 and current 2/1/6 evidence.
- `R13` Update service/runbook/CI documentation and ensure CI runs complete ROS unit and 0001-0004 PostGIS contracts.
- `R14` Preserve all qualification/deployment actions outside this source-only lifecycle.

### 3. File contract

| ID | Path | Action / anchor | Contract and purpose |
| --- | --- | --- | --- |
| `F1` | `services/ros-gis-integration/tests/unit/test_daily_requirement_producer.py` | MODIFY fixtures/hash tests | Correct August fixtures; lock error taxonomy and independent v2 hash. |
| `F2` | `services/ros-gis-integration/tests/unit/test_water_requirement_read_api.py` | MODIFY manual doubles/TestClient cases | Two-argument job, deterministic clock, exact serialized envelopes/OpenAPI. |
| `F3` | `services/ros-gis-integration/tests/unit/test_water_requirements_route.py` | MODIFY route contract | Date mismatch and typed conflict before side effects. |
| `F4` | `services/ros-gis-integration/tests/unit/test_requirement_source_loader.py` | MODIFY loader contract | Exact cutoff SQL/arguments and eligible-row behavior. |
| `F5` | `services/ros-gis-integration/tests/unit/test_daily_requirement_job.py` | MODIFY job contract | Effective-date invariant and status-aware match behavior. |
| `F6` | `services/ros-gis-integration/tests/unit/test_daily_requirement_run_store.py` | MODIFY store contract | Published/calculating/superseded classification. |
| `F7` | `services/ros-gis-integration/tests/unit/test_flow_monitoring_publisher.py` | MODIFY payload contract | Separate calculation and adapter versions. |
| `F8` | `services/ros-gis-integration/tests/unit/test_water_requirement_publication.py` | MODIFY repository query contract | Project method version into Flow rows. |
| `F9` | `services/ros-gis-integration/tests/unit/test_daily_requirement_temporal_route.py` | CREATE composed test | Four UTC instants through real route/job/loader/producer. |
| `F10` | `services/ros-gis-integration/tests/integration/test_water_requirement_repository_postgres.py` | MODIFY real DB contract | v1/v2 coexistence, supersession, reads, Flow version. |
| `F11` | `services/ros-gis-integration/src/api/routes/water_requirements.py` | MODIFY `trigger_daily_requirement_run` | Date authorization and bounded typed 409s. |
| `F12` | `services/ros-gis-integration/src/services/daily_requirement_producer.py` | MODIFY errors/hash/snapshot | Separate config error; preserve v2 identity. |
| `F13` | `services/ros-gis-integration/src/services/requirement_source_loader.py` | MODIFY `load`/manifest errors/SQL | Normalize and enforce cutoff; typed configuration error. |
| `F14` | `services/ros-gis-integration/src/services/daily_requirement_job.py` | MODIFY `run_once` | Snapshot invariant and status-aware reuse. |
| `F15` | `services/ros-gis-integration/src/db/daily_requirement_run_store.py` | MODIFY matching lookup | Typed superseded conflict and abandoned recovery. |
| `F16` | `services/ros-gis-integration/src/db/water_requirement_repository.py` | MODIFY `SELECT_FLOW_RECORDS_FOR_RUN` | Project persisted calculation method. |
| `F17` | `services/ros-gis-integration/src/services/flow_monitoring_publisher.py` | MODIFY `build_flow_demand_records` | Add `requirement_method` input version. |
| `F18` | `ops/control-plan-read-local/tests/test_stage_suite.py` | MODIFY validators/failure manifest tests | Exact API types/keys and frontend SHA. |
| `F19` | `ops/control-plan-read-local/tests/test_seed_approved_sources.py` | MODIFY seed contract | Bangkok-midnight UTC and crop created_at. |
| `F20` | `ops/control-plan-read-local/tests/test_orchestrate.py` | MODIFY partial/ledger/finalizer tests | Non-acceptance partial collection and ledger validation. |
| `F21` | `ops/control-plan-read-local/run-stage-suite.py` | MODIFY validators/failure manifest | Exact success/conflict and full identity. |
| `F22` | `ops/control-plan-read-local/seed-approved-sources.py` | MODIFY `build_seed_plan`/writes | Deterministic eligible timestamps. |
| `F23` | `ops/control-plan-read-local/orchestrate.py` | MODIFY CLI/finalizer/collector | Separate strict partial evidence path and ledger validation. |
| `F24` | `docs/operations/control-plan-acceptance-campaign-ledger.jsonl` | CREATE | Two evidence-derived hash-chained entries. |
| `F25` | `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md` | MODIFY current-result section | Preserve history; state current 2/1/6 truth and collector usage. |
| `F26` | `services/ros-gis-integration/CLAUDE.md` | MODIFY canonical producer section | Current-date, cutoff, conflict, and version contracts. |
| `F27` | `.github/workflows/control-plane-hardening-tests.yml` | MODIFY ROS jobs | Full unit suite and migration 0004 parity. |
| `F28` | active Coding Log and `.codex/coding-log.current` | MODIFY/retain | Primary-owned DREP and lifecycle evidence. |

No DeepSeek production allowlist exists because Q0 containment fails. All test, production, documentation, CI, and lifecycle files are primary-owned.

### 4. Function contract

- `FN1 trigger_daily_requirement_run(request, job, now)`: compute expected operational date before `run_once`; return exact success; map only bounded domain conflicts to sanitized 409. Unexpected/configuration errors propagate as 500. Caller: FastAPI router registered in `src/main.py`.
- `FN2 requirement_run_content_hash(snapshot, as_of_date, horizon_days)`: validate programming arguments with `RequirementConfigurationError`; hash method and source effective date deterministically. Caller: `DailyRequirementJob.run_once` and producer calculation.
- `FN3 AuthoritativeRequirementSourceLoader.load(..., source_effective_date, input_cutoff_at)`: require aware cutoff, normalize once to UTC, bind inclusive cutoff into all timestamped queries, and fail closed on missing/inconsistent eligible data. Caller: `DailyRequirementJob.run_once`.
- `FN4 DailyRequirementJob.run_once(as_of_date, now)`: require aware time, require snapshot effective date equals request, classify matching run status, publish only new/current-published results, and never publish superseded lineage. Callers: manual route, catch-up, schedule loop.
- `FN5 PostgresDailyRequirementRunStore.find_matching_run(...)`: return published row, fail abandoned calculating and return none, raise `SupersededRequirementRunError` for superseded, ignore failed/absent. Caller: `FN4` under advisory lock.
- `FN6 build_flow_demand_records(records)`: retain adapter `method=ros_daily_requirement_v1`; copy persisted `requirement_method_version` to `input_versions.requirement_method`. Caller: Flow publisher `publish`.
- `FN7 validate_manual_requirement_run(...)`: accept only exact mapping/key set, strict integer count 287, valid UUID/date/status. Caller: `run_local_ac`.
- `FN8 validate_manual_requirement_failure(...)`: accept only exact bounded conflict envelope then raise a stable stage gate. Caller: `run_local_ac`.
- `FN9 build_seed_plan(...)`: use Bangkok midnight converted to UTC for timestamped source rows and explicitly include crop-setting created_at. Caller: seeder CLI.
- `FN10 finalize_partial_failure_collection(destination)`: validate regular-file exact inventory/checksums/identity/completed prefix/next failure and write separate outer index plus `acceptance=false` summary. It never calls or weakens the acceptance finalizer.
- `FN11 collect_partial_failure(destination)`: extract/copy using the existing safe archive path, then invoke `FN10`. Caller: CLI `collect-partial-failure`.
- `FN12 validate_campaign_ledger(path)`: stream JSONL, require exact schema/types/outcomes, recompute canonical entry hashes and previous-link chain, and reject mutation/truncation/invented acceptance. Caller: tests and partial collection/CLI verification path.

### 5. Test contract and RED sequence

- `T1` `test_calculate...before_utc_date_boundary`: repair August ETo/Kc/rain fixture first; old UTC-date comparison mutation must then fail on the named effective-date assertion. RED: focused producer pytest.
- `T2` serialized manual endpoint tests: doubles expose cron/timezone and accept `(date, now)`; deterministic clock; exact sanitized JSON/OpenAPI. Current observed RED is wrong-reason `TypeError`/500, so repair test seams before contract RED.
- `T3` route date policy cases: four instants plus wrong dates; assert mismatch 409 and zero job calls. RED: route accepts mismatch/calls job.
- `T4` composed temporal route cases: real job/loader/producer with focused fake connections/store/publisher; assert exact accepted date, cutoff, output, and zero rejected side effects. RED: unrestricted route/missing cutoff SQL.
- `T5` loader cutoff SQL: assert all six `<=` predicates, normalized cutoff, exact bind order, at-cutoff eligible and after-cutoff unavailable. RED: current queries omit predicates.
- `T6` status-aware match tests: published reuse, calculating recovery, superseded typed conflict, no Flow on superseded. RED: current store returns superseded and job republishes.
- `T7` configuration taxonomy: invalid arguments/manifest/config stay 500 while authoritative missing rows return sanitized 409. RED: current broad catches return 409.
- `T8` v2 lineage tests: independent hard-coded hash golden and effective-date sensitivity; repository projection and Flow payload assert separate identities. RED: Flow rows lack calculation method.
- `T9` exact harness response tests: extra keys, bool, float 287.0, unknown reason/status fail. RED: current success validator accepts extra/equality-compatible values.
- `T10` deterministic seed tests: Aug 12 timestamps equal `2026-08-11T17:00:00+00:00`, including crop `created_at`. RED: current UTC midnight/implicit created_at.
- `T11` partial finalizer tests: valid 2-pass/next-failure prefix succeeds as `acceptance=false`; missing/unindexed/symlink/wrong identity/later artifacts fail; strict finalizer rejects same inventory. RED: function/action absent.
- `T12` ledger tests: both evidence-derived entries validate; altered byte/hash/link/status/acceptance fails. RED: ledger and validator absent.
- `T13` real PostGIS version test: v1/v2 same-day content coexist, v2 supersedes v1, current returns v2, history returns both, Flow carries v2. RED: projection lacks calculation version; schema collision assumptions verified on real DB.
- `T14` CI structural tests or exact workflow inspection: ROS unit job covers `tests/unit`; integration applies 0001-0004. RED: current workflow scope is narrower/stale.

For every slice: author/repair tests -> run exact test -> confirm named RED -> lock/hash tests -> implement minimum code -> GREEN -> focused formatter/lint -> wiring trace. A setup/import/fixture failure never counts as RED.

### 6. Traceability

| Requirement | Runtime realization | Tests | Files | Slice |
| --- | --- | --- | --- | --- |
| `R1` | corrected fixtures/doubles | `T1,T2` | `F1,F2` | `S1` |
| `R2,R3` | `FN1 -> FN4 -> FN3` | `T3,T4` | `F3,F9,F11,F14` | `S1,S2` |
| `R4,R5` | `FN3` query predicates and validation | `T4,T5` | `F4,F9,F13` | `S2` |
| `R6` | `FN4 -> FN5` | `T6,T13` | `F5,F6,F10,F14,F15` | `S3` |
| `R7` | `FN1,FN2,FN3` typed errors | `T2,T7` | `F1-F4,F11-F13` | `S1,S2` |
| `R8` | repository SQL -> `FN6` | `T8,T13` | `F7,F8,F10,F12,F15-F17` | `S3` |
| `R9` | `FN7,FN8` | `T9` | `F18,F21` | `S4` |
| `R10` | `FN9` | `T10` | `F19,F22` | `S4` |
| `R11` | `FN10,FN11` | `T11` | `F20,F23` | `S5` |
| `R12` | `FN12` and ledger rows | `T12` | `F20,F23,F24` | `S5` |
| `R13` | workflow and docs | `T14` plus gate inspection | `F25-F27` | `S6` |
| `R14` | no runtime/guest commands; explicit docs | audit | `F25,F28` | all |

### 7. Wiring verification plan

| Component | Non-test runtime caller | Registration/config load | Schema/contract evidence |
| --- | --- | --- | --- |
| Manual date policy | FastAPI request to `trigger_daily_requirement_run` | router included in `src/main.py`; job exposes cron/timezone | exact 409/success TestClient contracts |
| Cutoff loader | `DailyRequirementJob.run_once` | loader constructed in `src/main.py` from local/source DB managers | source timestamps: `gis.zone.create_date`, planting `updated_at`, crop `created_at`, ETo/Kc/rain `updated_at` |
| Matching run | `DailyRequirementJob.run_once` under advisory lock | `PostgresDailyRequirementRunStore` constructed in lifespan | 0002 statuses + 0003 nonfailed unique index |
| Calculation method lineage | job -> repository `get_flow_records_for_run` -> Flow publisher | publisher constructed in lifespan | `water_requirement_runs.method_version` -> Flow `input_versions.requirement_method` |
| Partial collector | orchestrator CLI `collect-partial-failure` | argparse action dispatch | stage order/state/failure manifest/SHA256SUMS schema; acceptance finalizer remains separate |
| Campaign ledger | partial collector/explicit validation plus tests | fixed repo path | canonical JSON hash chain; external/frozen evidence checksums referenced, not copied or rewritten |

### 8. Slice plan and delegation classification

| ID | Requirements/files/tests | Owner | Q0-Q3 / stop line | Oracle | Done when |
| --- | --- | --- | --- | --- | --- |
| `S1` | `R1,R2,R7`; `F1-F3,F11,F12`; `T1-T3,T7` | `PRIMARY` | Q0 fails: unrestricted child containment; `PRIMARY` | focused producer/route/TestClient pytest | correct RED then GREEN |
| `S2` | `R3-R5`; `F4,F9,F13,F14`; `T4,T5` | `PRIMARY` | Q0 fails; cross-DB temporal semantics also judgment-bound | composed temporal + loader pytest | all four instants/cutoffs prove behavior |
| `S3` | `R6,R8`; `F5-F8,F10,F14-F17`; `T6,T8,T13` | `PRIMARY` | Q0 fails; distributed lineage/real DB stays primary | job/store/Flow/unit + real PG | status and versions verified |
| `S4` | `R9,R10`; `F18,F19,F21,F22`; `T9,T10` | `PRIMARY` | Q0 fails; acceptance harness semantics stay primary | harness/seeder pytest | exact envelopes and timestamps green |
| `S5` | `R11,R12`; `F20,F23,F24`; `T11,T12` | `PRIMARY` | Q0 fails; evidence/acceptance boundaries stay primary | orchestrator pytest and checksum mutations | partial evidence cannot qualify |
| `S6` | `R13,R14`; `F25-F28`; `T14` | `PRIMARY` | lifecycle/docs/CI cannot delegate | structural inspection + full gates | docs/CI/log truthful |

Stop conditions: stop product editing if a migration, guest mutation, campaign retry, deployment, new public backfill interface, weakening of strict 9/9, or unverifiable evidence value becomes necessary. Ask for authority rather than improvise.

### 9. Gates, review, rollout, and rollback

- Baseline diagnostic: focused ROS candidate currently `83 passed, 3 failed`; all three failures match the reviewed wrong-reason fixture/double problems. Harness baseline `368 passed`.
- Run each focused test at RED and GREEN, then complete ROS `tests/unit`.
- Run harness `test_stage_suite.py`, `test_orchestrate.py`, and `test_seed_approved_sources.py`.
- Run real PostGIS suite only with an explicit disposable migrated URL; do not fabricate or point at acceptance/production state.
- Run Black check, Ruff, compileall, `git diff --check`, and `make test`; distinguish infrastructure skips/failures from source passes.
- Repeat the affected ROS and harness scopes three consecutive times.
- Independent non-DeepSeek QCHECK, then formal `g-check`; primary dispositions and remediates every finding.
- Rollout is source delivery only. Dark flags stay false. Admin merge is authorized by the user after PR readiness; no deployment or campaign execution.
- Rollback is PR revert; no schema/data rollback.

### 10. Do-not-touch and baseline audit

- Do not mutate guests, OrbStack, acceptance evidence, external archives, deployment state, `.env`, credentials, existing stashes other than the named backup after final verified landing, or pre-existing worktrees.
- Do not rewrite frozen evidence. Ledger rows cite verified checksums and exact outcomes.
- Tests, fixtures, docs, Coding Log, Git state, and all files are primary-owned because no delegate is eligible.
- Before commit, compare every changed path with base `5cfdb2a05b4ea4c2742250845ae55a76816700bd`; confirm no secrets, generated dependency files, or unrelated historical log edits enter the PR.

### Adversarial challenge disposition

- Accepted: stale one-argument TestClient doubles/raw-response assertions; unrestricted manual backfill; missing cutoff predicates; superseded republish; missing Flow calculation lineage; overbroad 409 mapping; absent partial collector/ledger; stale docs/version tests.
- Accepted refinement: manifest parsing/configuration errors are not authoritative data gaps and must remain 500-class.
- Accepted refinement: composed tests must prove authorization before load and no run/Flow side effects, not merely construct snapshots.
- Rejected: none. No adversarial finding conflicted with source evidence.

### Decision-complete checklist

- All `R`, `F`, `FN`, `T`, and `S` references resolve.
- Every requirement maps to a runtime realization and defect-sensitive test.
- Every new component has a caller/registration/schema contract.
- Exact RED commands are the focused pytest files named by each `T`; predicted failures are recorded above.
- No DeepSeek slice is claimed eligible; Q0 failure is explicit and preserves the full g2 lifecycle on primary.
- Architecture, public contracts, tests, seams, reviews, lifecycle artifacts, Git, PR/merge, and rollback remain primary-owned.
- No open implementation decision remains. No guest/campaign/deployment authority is inferred.

## Implementation (2026-08-13 08:31:00 +0700) - S1 test integrity, date policy, and error taxonomy

- Goal: remove wrong-reason failures, introduce configuration-versus-authoritative-data errors, and lock current-Bangkok-operational-date-only manual publication.
- Test repairs: August producer fixture now includes August ETo/Kc/rainfall. Serialized HTTP doubles accept `(as_of_date, now)`, expose cron/timezone, use deterministic `NOW`, and expect sanitized errors.
- Baseline after test repair: focused producer/route/TestClient scope `32 passed`.
- RED: focused producer/loader/route pytest failed during collection because planned `RequirementConfigurationError` did not exist. This is the intended new export, not an unrelated failure.
- GREEN: `/Users/subhajlimanond/dev/munbon2-backend/services/ros-gis-integration/venv/bin/python -m pytest -q tests/unit/test_daily_requirement_producer.py tests/unit/test_requirement_source_loader.py tests/unit/test_water_requirements_route.py tests/unit/test_water_requirement_read_api.py` -> `73 passed`.
- Production: invalid producer arguments and manifest/runtime-loader configuration now raise `RequirementConfigurationError`; authoritative data defects retain `RequirementInputError`/`RequirementSourceError`. The manual route computes `operational_date(now, job.cron, job.timezone_name)` before calling the job and returns a sanitized `operational_date_mismatch` 409 on mismatch.
- Wiring: `src/main.py` registers this router and constructs the job with configured cron/timezone. Manual mismatch is rejected before loader/store/Flow side effects; catch-up and schedule retain their existing operational-date call sites.
- Risk: no backfill/future endpoint was introduced. Invalid cron/timezone propagates as 500-class configuration failure. No guest/runtime action occurred.

## Implementation (2026-08-13 08:42:00 +0700) - S2 cutoff, effective-date, and composed boundary

- Goal: enforce the inclusive UTC cutoff on every authoritative timestamp source and prove the four Bangkok-boundary instants through the real route/job/loader/producer path.
- RED: focused loader/job/route tests failed because source queries lacked cutoff predicates and because loaded `source_effective_date` was not compared with the requested civil date.
- GREEN: focused `test_requirement_source_loader.py`, `test_daily_requirement_job.py`, and `test_water_requirements_route.py` scope -> `65 passed`.
- Production: loader queries now bind `create_date`/`updated_at`/`created_at <= input_cutoff_at`; the job rejects an effective-date mismatch as configuration failure before run creation or publication.
- Composed evidence: the four-instant test uses `2026-08-11T16:59:59Z`, `2026-08-11T17:00:00Z`, `2026-08-11T23:59:16Z`, and `2026-08-12T00:00:00Z`; only the current Bangkok operational date publishes 287 requirements and the rejected date creates no store or Flow side effect.
- Risk: comparisons are inclusive by contract. All cutoff parameters are normalized to aware UTC values. No runtime or guest was mutated.

## Implementation (2026-08-13 08:50:00 +0700) - S3 lineage, deduplication, and golden sensitivity

- Goal: make only `published` runs deduplicable, reject superseded lineage deterministically, and keep requirement calculation lineage distinct from the stable Flow adapter method.
- RED: focused store/job/Flow/repository tests failed because superseded rows were returned as reusable matches and Flow input versions did not carry the requirement calculation method.
- GREEN: combined store/job/Flow/publication/route/loader scope -> `105 passed`.
- Production: `find_matching_run` returns only published rows, treats calculating rows as non-reusable, and raises typed `SupersededRequirementRunError` for superseded rows. The route maps only that typed error to `superseded_lineage` 409. Flow keeps adapter method `ros_daily_requirement_v1` while recording the requirement run's method separately.
- Golden sensitivity: expected v2 content hash is `83cb6891781c27f970c0513595bca5c2b9663c78c53edafa18d63f0033b8fe47`. A temporary test-only mutation from `daily-requirement-v2` to `daily-requirement-v1` failed with `9cd349...`; after restoration, the golden test passed (`1 passed`).
- Risk: unknown exceptions remain 500-class; the route does not collapse configuration, programming, or storage failures into a 409.

## Implementation (2026-08-13 09:02:50 +0700) - S4 strict harness contract and Bangkok seeding

- Goal: make LOCAL-AC-1 accept only the exact publication/rejection response contracts and seed timestamped sources at the represented Bangkok civil day's midnight.
- RED: `/Users/subhajlimanond/dev/munbon2-backend/services/ros-gis-integration/venv/bin/python -m pytest -q ops/control-plan-read-local/tests/test_stage_suite.py -k 'manual_requirement or failure_manifest_preserves' ops/control-plan-read-local/tests/test_seed_approved_sources.py` -> `6 failed, 13 passed, 301 deselected`; failures were the intended extra-key/type acceptance, missing stable rejection mappings, missing frontend failure-manifest identity, and UTC-midnight seed defects.
- GREEN: the identical command -> `19 passed, 301 deselected`.
- Production: success requires exactly four response keys and an actual integer count of 287. Failure validation recognizes exact incomplete-source, superseded-lineage, and operational-date-mismatch schemas; all unknown or malformed responses remain `manual_requirement_run_not_accepted`. Failure manifests now include `frontend_sha`.
- Seeding: all timestamped approved sources, including crop-setting `created_at`, use Bangkok midnight converted to UTC (`17:00:00+00:00` on the prior UTC date).
- Wiring: `run-stage-suite.py` calls these validators in LOCAL-AC-1 and emits the failure manifest in the common stage exception path; `seed-approved-sources.py` writes the scenario directly to the six authoritative tables.
- Risk: the schema checks intentionally reject additive response fields and Python `bool`/`float` values. No acceptance guest or database was touched.

## Implementation (2026-08-13 09:38:00 +0700) - S5 partial evidence, ledger, docs, CI, and gates

- Goal: preserve stopped-prefix failure evidence without weakening strict 9/9 acceptance, record campaign history as a hash chain, and align delivery surfaces with the implemented ROS contract.
- Partial collector RED: focused `test_orchestrate.py -k 'partial_failure or partial_evidence'` -> `6 failed` because the finalizer/action did not exist. GREEN -> `6 passed, 54 deselected`; later exact pass-manifest frontend identity RED failed as expected and the complete harness rerun passed `375` tests after remediation.
- Ledger RED: focused `test_orchestrate.py -k campaign_ledger` -> `2 failed` because no validator existed. GREEN -> `2 passed, 60 deselected`; checked-in two-entry ledger validation then passed with terminal entry hash `fe2cb916578a1c6ded0c4087f99be832639b3f72af74fcf35ae5f98c9b03f810`.
- Production: `collect-partial-failure` accepts only regular checksum-indexed files, an ordered completed prefix, exactly the next failure, exact backend/frontend/harness identity, and emits `acceptance_evidence=false` plus `PARTIAL-OUTER-SHA256SUMS`. Existing `collect` remains strict 9/9 and now also requires frontend identity on every manifest.
- Campaign truth: ledger row 1 records historical `7 passed / 1 failed / 1 unreached`; row 2 records current `2 passed / 1 failed / 6 unreached`, guest `01KZSKQ6FY4EVCCY94XGWZ9NDS`, and exhausted `3/3` authority. Historical unknown dependency/guest identity is explicit `null`, never fabricated.
- Delivery surfaces: runbook now identifies the current attempt accurately; service guidance documents current-date-only manual publication, inclusive UTC cutoff, superseded conflict, Flow calculation lineage, and migration `0004`; CI runs the complete ROS source suite and applies `0004` in PostGIS.
- Full source gates: ROS `267 passed, 14 skipped`; harness `383 passed`; scoped Black `21 files unchanged`; scoped Ruff `All checks passed`; compileall and `git diff --check` passed.
- Real DB gate: disposable local `postgis/postgis:16-3.4` container, migrations `0001` through `0004` all `applied`, repository plus dataset-immutability integrations `13 passed`; exact session container removed afterward.
- Stability: affected ROS plus harness scope passed three consecutive times at `519 passed` each. After the exact frontend-manifest refinement, harness route/orchestrator scope passed `375` tests.
- Repository gate caveat: `make test` encountered `Missing script: test` in `services/sensor-data/vercel-deployment`; its Makefile uses `|| true`, so the command returned zero. This is not counted as a passing gate and is outside the changed ROS/harness surface.
- Wiring: FastAPI lifespan builds/stores the job (`src/main.py:104-106`) and registers the route (`src/main.py:156-158`); route authorizes the Bangkok date before `run_once` (`water_requirements.py:178-219`); job passes effective date/cutoff and performs status-aware matching (`daily_requirement_job.py:48-81`); loader applies six timestamp upper bounds (`requirement_source_loader.py:34-113`); Flow publishes distinct adapter/calculation lineage (`flow_monitoring_publisher.py:8-35`); the orchestrator CLI dispatches the separate partial collector and both finalizers validate exact inventories.
- Risk/authorization: no preserved guest, acceptance evidence, canonical campaign, deployment, activation, AWS resource, or external database was mutated. The disposable PostGIS instance was test-only and removed.

## Review (2026-08-13 09:51:16 +0700) - working-tree

### Reviewed
- Repo: `/Users/subhajlimanond/dev/munbon2-backend-ros-temporal-qualification-g2`
- Branch: `fix/ros-temporal-qualification-g2`
- Scope: staged working tree based on `5cfdb2a05b4ea4c2742250845ae55a76816700bd`
- Commands Run: staged/unstaged status and diff artifacts; RepoPrompt focused formal review; full ROS/harness pytest; disposable PostGIS migrations/integration; scoped Black, Ruff, compileall, and `git diff --check`

### Findings
CRITICAL
- No findings.

HIGH
- No findings.

MEDIUM
- `requirement_run_content_hash` omitted section and gate dataset-version lineage, allowing a version change with equal projected crop inputs to deduplicate stale lineage. Fix: include both immutable dataset IDs and prove sensitivity.
- Deterministic crop-setting IDs retained `local-ac-1-v5` while insertion used `ON CONFLICT DO NOTHING`; a previously seeded local database could retain the old post-cutoff `created_at`. Fix: bump the local-only deterministic scenario identity and lock the new ID.
- Partial failure validation accepted checksum-indexed artifacts named for unreached stages. Fix: reject any unreached-stage-prefixed artifact, even when indexed.
- Campaign ledger authorization allowed `exhausted` with null attempt data and `historical_closed` with non-null attempt data. Fix: enforce exact state-specific shapes.

LOW
- Real PostGIS coverage did not explicitly assert v1/v2 publication coexistence and Flow calculation-lineage projection. Add this to the existing immutable correction test.
- The OpenAPI 409 description described only incomplete source data despite also declaring operational-date and superseded-lineage conflicts. Expand the description without changing the bounded schemas.

### Open Questions / Assumptions
- Dataset version IDs are immutable lineage identities under migration `0004`; including them in v2 run identity is the intended fail-closed dedup boundary.
- Scenario v6 is local acceptance fixture identity only; no production dataset or frozen evidence is rewritten.

### Recommended Tests / Validation
- Run focused RED/GREEN tests for hash sensitivity, v6 seed convergence, indexed later-stage rejection, and authorization contradictions.
- Re-run complete ROS/harness suites, real PostGIS integrations, three consecutive affected scopes, Black, Ruff, compileall, YAML parsing, and diff checks.

### Rollout Notes
- No rollout, guest mutation, acceptance retry, deployment, or activation is authorized. This review covers source delivery only.
- Formal disposition: all six findings are accepted for remediation before commit; no finding is waived.

## Review (2026-08-13 10:01:54 +0700) - working-tree remediation rerun

### Reviewed
- Repo: `/Users/subhajlimanond/dev/munbon2-backend-ros-temporal-qualification-g2`
- Branch: `fix/ros-temporal-qualification-g2`
- Scope: staged working tree after first formal-review remediation
- Commands Run: staged RepoPrompt diff artifact and continued formal review; ROS/harness/PostGIS pytest; Black; Ruff; compileall; YAML parse; `git diff --check`

### Findings
CRITICAL
- No findings.

HIGH
- No findings.

MEDIUM
- Hash chaining alone did not prevent rewriting all ledger rows and recomputing successors. Fix: add base-versus-current byte-prefix validation in CI and pin existing candidate/guest/evidence identities and entry hashes.
- Success validation coerced `runId` through `str`, permitting non-string or noncanonical UUID input. Fix: require an exact canonical string UUID.

LOW
- Numeric/list ledger identity fields could escape as raw `TypeError`. Fix: explicit string guards keep malformed rows within `campaign_ledger_schema_invalid`.
- Manual Pydantic models did not declare closed envelopes. Fix: shared `ConfigDict(extra="forbid")`, serialized extra-request rejection, and OpenAPI `additionalProperties=false` assertions.

### Open Questions / Assumptions
- The base-prefix CI comparison uses the pull-request base SHA or push `before` SHA and treats a missing historical ledger as an empty prefix for this initial introduction.

### Recommended Tests / Validation
- Focused RED/GREEN for canonical UUID, closed envelopes, bounded malformed identity types, and byte-prefix history.
- Re-run full ROS/harness suites, static gates, and the affected scope three times.

### Rollout Notes
- Formal disposition: all four findings accepted and remediated; none waived.
- GREEN: focused exactness tests passed; ROS `268 passed, 15 skipped`; harness `395 passed`; affected scope `532 passed` three consecutive times; Black, Ruff, compileall, YAML parse, and diff check passed. Prior real PostGIS `14 passed` remains applicable because this slice changed only API/evidence validation and CI.

## Review (2026-08-13 10:18:00 +0700) - final staged remediation rerun

### Reviewed
- Repo: `/Users/subhajlimanond/dev/munbon2-backend-ros-temporal-qualification-g2`
- Branch: `fix/ros-temporal-qualification-g2`
- Scope: staged working tree after second formal-review remediation
- Commands Run: staged RepoPrompt diff artifact and continued formal review; focused RED/GREEN pytest; disposable PostGIS migrations/integration; full ROS/harness pytest; Black, Ruff, YAML parse, and `git diff --check`

### Findings
CRITICAL
- No findings.

HIGH
- CI used the default shallow checkout, so an unavailable base commit was incorrectly treated as a historical ledger without the file. Fix: fetch full history and fail closed unless `BASE_SHA^{commit}` exists.
- A retained local-only v5 crop fixture could sort later than v6 after both became cutoff-eligible. Fix: inside the already validated disposable-local seeding transaction, temporarily disable the append-only row trigger, delete only sources matching `^local-ac-1-v[0-9]+$`, restore the trigger, and insert v6; prove the loaded crop lineage against real PostGIS.

MEDIUM
- No findings.

LOW
- Ledger timestamps were shape-checked but impossible calendar values were accepted. Fix: parse and canonical-round-trip the exact UTC timestamp after the regex guard.

### Open Questions / Assumptions
- The local fixture cleanup is intentionally limited to the isolated local-acceptance database and exact local scenario source prefix; the public seeding entry point validates the loopback database URL and wraps the operation in one transaction.
- A genuinely absent ledger at an available historical commit remains a valid empty prefix for initial introduction; an unavailable commit is now an explicit CI failure.

### Recommended Tests / Validation
- Re-run the newly added focused checks and the full affected suites.
- Re-run the complete real-PostGIS repository and dataset-immutability integrations after migrations `0001` through `0004`.
- Publish a fresh staged-only snapshot and obtain a final formal no-findings review before commit.

### Rollout Notes
- Formal disposition: all three findings accepted and remediated; none waived.
- RED: CI-history and impossible-timestamp scope failed `5` tests for the intended missing guards. GREEN: the same scope plus seeder unit coverage passed `15` tests.
- Real DB GREEN: legacy v5 was inserted, v6 was seeded, the authoritative loader selected only v6 lineage, and the complete repository plus dataset-immutability scope passed `15` tests; the disposable container was removed.
- Full GREEN after remediation: ROS `268 passed, 16 explicitly DB-gated skipped`; complete local harness `473 passed`.

## Review (2026-08-13 10:58:00 +0700) - fresh formal review

### Reviewed
- Repo: `/Users/subhajlimanond/dev/munbon2-backend-ros-temporal-qualification-g2`
- Branch: `fix/ros-temporal-qualification-g2`
- Scope: fresh staged-only snapshot `2026-08-13/1050`, with accumulated review context discarded before the pass
- Commands Run: RepoPrompt formal review; focused RED/GREEN pytest; full harness and three-run affected stability scope; Black, Ruff, compileall, YAML parse, and `git diff --check`

### Findings
CRITICAL
- No findings.

HIGH
- Partial evidence returned `acceptance_evidence=false` only to an ignored CLI call, leaving no persisted machine-readable classification. Fix: generate canonical `PARTIAL-SUMMARY.json` before the outer index, include it in `PARTIAL-OUTER-SHA256SUMS`, and print the exact summary from the CLI.

MEDIUM
- No findings.

LOW
- Ledger `schema_version` accepted JSON `true` through Python boolean/integer equality, and plain JSON parsing accepted duplicate keys recursively. Fix: require the exact integer type and parse every ledger object with a duplicate-rejecting object-pairs hook.

### Open Questions / Assumptions
- Partial summaries are host-generated only. A guest-provided `PARTIAL-SUMMARY.json` or `PARTIAL-OUTER-SHA256SUMS` is rejected before validation rather than trusted or overwritten.
- Duplicate-key rejection applies recursively because `object_pairs_hook` runs for each decoded JSON object.

### Recommended Tests / Validation
- Publish one more complete staged-only snapshot after these remediations and obtain an explicit no-findings formal review.

### Rollout Notes
- Formal disposition: both findings accepted and remediated; none waived.
- RED: five focused tests failed for the intended missing summary/CLI/type/duplicate-key guards. GREEN: the same five passed; `test_orchestrate.py` passed `81` tests after formatting; complete harness passed `477`; affected scope passed `578` three consecutive times.
- The real PostGIS `15 passed` and complete ROS `268 passed, 16 skipped` evidence remain applicable because this final slice changes only host evidence and ledger validation.

## Review (2026-08-13 11:04:00 +0700) - final review disposition

### Findings
CRITICAL
- No findings.

HIGH
- Reported manual-dispatch empty-`BASE_SHA` path: rejected as inapplicable. The workflow declares only `pull_request` and `push`; `workflow_dispatch` is absent. Both declared event types provide the selected base SHA, and the job independently fails closed if the commit is unavailable.

MEDIUM
- No findings.

LOW
- CI omitted `test_local_artifacts.py`, so the full-history/base-commit workflow regression test was local-only. Accepted: add the file to the local-harness pytest job and lock its inclusion in the test itself.

### Rollout Notes
- RED: the focused workflow-contract test failed because `test_local_artifacts.py` was absent from the CI command. GREEN: the same test passed after inclusion; YAML parsing and `git diff --check` passed.
- No guest, campaign, deployment, or activation action occurred.

## Review (2026-08-13 11:08:00 +0700) - final formal gate

### Reviewed
- Repo: `/Users/subhajlimanond/dev/munbon2-backend-ros-temporal-qualification-g2`
- Branch: `fix/ros-temporal-qualification-g2`
- Scope: complete staged-only snapshot `2026-08-13/1101`, 29 intended files
- Commands Run: RepoPrompt formal review continuation after explicit disposition; focused workflow regression; YAML parse; `git diff --check`

### Findings
CRITICAL
- No findings.

HIGH
- No findings.

MEDIUM
- No findings.

LOW
- No findings.

### Open Questions / Assumptions
- None.

### Recommended Tests / Validation
- Proceed to commit and PR. Treat hosted zero-step failures under the known Actions billing lock as infrastructure-blocked, not passing CI; retain all local and real-PostGIS evidence in the PR.

### Rollout Notes
- Formal reviewer result: `No confirmed actionable findings.`
- Scope remains source delivery only. No deployment, guest mutation, acceptance retry, campaign execution, or activation is authorized.
