# Coding Log - RT-3 RT-4 OPS-1 runtime hardening

Started: 2026-07-21 15:34:09 +0700

## Authoritative task

Implement the three ordered follow-ups from the supplied runtime-closure brief:

1. RT-3 canonical DSN handling in bff-water-planning and ros-gis-integration.
2. RT-4 truthful ROS liveness/readiness and BFF propagation.
3. OPS-1 reproducible control-plan read deployment derived from runtime commit `c352fdd6`, without its host compensations.

Deliver each item as an independent standard GitHub PR from refreshed `main`, merge it, fast-forward local `main`, and verify the merged commit before starting the next item. Planning and review artifacts are not product changes: archive them on a separate `ops/archive-rt3-rt4-ops1-20260721` branch and leave product `main` clean. Preserve the existing archive branches `ops/archive-backend-main-plans-20260721` and `ops/archive-control-plan-runtime-roadmap-20260721`; after the new archive is durable, remove the obsolete `ops/control-plan-read-runtime-20260721` worktree/branch because its evidence is already preserved.

## Exploration evidence

- Root guidance: `CLAUDE.md` is canonical; `AGENTS.md` adds TDD and QCHECK detail; `CONTEXT.md` identifies these services as irrigation-canal scope.
- Service guidance: `services/bff-water-planning/CLAUDE.md` and `services/ros-gis-integration/CLAUDE.md` require fail-closed behavior and service-local pytest gates.
- Auggie semantic search was attempted with a real two-second deadline and timed out. Planning therefore uses direct file inspection plus exact-string searches.
- Inspected RT-3 files: both `src/db/database_manager.py` implementations, ROS `migrations/migrate.py`, service requirements, settings tests, and existing migration DSN parsers.
- Inspected RT-4 files: ROS `src/main.py` and `src/db/database_manager.py`; BFF `src/services/readiness_service.py`, `src/main.py`, and `tests/unit/test_readiness_service.py`.
- Inspected OPS-1 evidence: commit `c352fdd6689b85206bfc482f8a83a8ca38d08d93`, its four wrappers/ecosystem/log, existing PM2 patterns, migration runners, and archive branches.
- Current base: `main == origin/main == 44703c3d5804bb79f390f68cf73b6e68314077d7` when planning started.

## Plan Draft A - service-focused, three sequential PRs

### Overview

Implement the smallest service-local hardening for each named item and land the items in dependency order. RT-3 owns database connection construction, RT-4 owns readiness contracts, and OPS-1 owns only deploy orchestration and verification.

### Files to change

RT-3:

- `services/bff-water-planning/src/db/postgres_dsn.py` - parse a PostgreSQL URL once into redaction-safe structured connection values.
- `services/bff-water-planning/src/db/database_manager.py` - pass asyncpg kwargs and a SQLAlchemy `URL.create` object.
- `services/bff-water-planning/tests/unit/test_postgres_dsn.py` - reserved characters, IPv6, ports, query, malformed input, redaction, and wiring.
- `services/ros-gis-integration/src/db/postgres_dsn.py` - equivalent service-local parser; no cross-service shared package.
- `services/ros-gis-integration/src/db/database_manager.py` - use the helper for main and optional source pools plus ORM URL.
- `services/ros-gis-integration/tests/unit/test_postgres_dsn.py` - the same contract plus source URL coverage.

RT-4:

- `services/ros-gis-integration/src/main.py` - process-only `/health`, dependency-backed `/ready` with 503, safe check labels, and root endpoint discovery.
- `services/ros-gis-integration/tests/unit/test_readiness.py` - health isolation; main Postgres/Redis/source Postgres readiness; fail/recover on the same process; redaction.
- `services/bff-water-planning/src/services/readiness_service.py` - probe ROS `/ready` and require exact `ready` status.
- `services/bff-water-planning/tests/unit/test_readiness_service.py` - update route/status contract and add same-client failure/recovery proof.
- Service `CLAUDE.md` files - replace stale health debt notes with the shipped contracts.

OPS-1:

- `ops/control-plan-read-runtime/README.md` - secret-file contract, setup, activation, verification, backout, ports, and capacity limits.
- `ops/control-plan-read-runtime/ecosystem.config.cjs` - four loopback-only PM2 applications using repo-owned wrappers.
- `ops/control-plan-read-runtime/run-{flow,scheduler,ros,bff}.sh` - source per-service mode-600 env files, run tracked migrations where owned, and exec exact service-local virtualenvs; no package installs or alternate DSNs.
- `ops/control-plan-read-runtime/activate.sh` - capacity preflight, PM2 update, five-minute stability gate, stop-on-failure, save-on-success.
- `ops/control-plan-read-runtime/runtime_gate.py` - parse `/proc/meminfo`, project safe PM2 state, probe readiness, detect restart deltas, and enforce the 300-second window.
- `ops/control-plan-read-runtime/verify_bearer.py` - secret-safe central login and real Scheduler/BFF list/detail verification without printing or retaining credentials/tokens.
- `ops/control-plan-read-runtime/tests/test_runtime_gate.py` - boundaries, restarts, readiness transitions, redaction, and manifest/wrapper invariants.

### TDD implementation steps

For every PR: add the named tests first; run them and record the expected RED; make the smallest production change; refactor only for readability/reuse; run focused tests, full affected-service tests, formatting/lint/type gates where configured, shell/Node validation for OPS, three full reliability runs, wiring checks, QCHECK, formal g-check, then commit/PR/merge/post-merge verification.

Functions:

- `parse_postgres_dsn(raw_url)` - validate scheme/authority/database, split userinfo at the final authority separator so raw reserved characters remain usable, percent-decode each credential exactly once, parse IPv6/port/query, and raise fixed redacted errors.
- `PostgresDsn.asyncpg_kwargs()` - return host/user/password/database/port plus supported asyncpg query settings without a DSN string.
- `PostgresDsn.sqlalchemy_url()` - build `postgresql+asyncpg` using `URL.create`, retaining query parameters while its display remains password-hidden.
- `health_check()` - return process liveness only and never query dependencies.
- `readiness_check()` - call `DatabaseManager.check_health`, expose safe `ok|unhealthy` values, and return 503 unless every required DB is healthy.
- `build_required_targets()` - require Scheduler `/ready`, Flow `/ready`, and ROS `/ready`, all with exact `ready` status.
- `parse_meminfo()` / `check_capacity()` - block below 512 MiB MemAvailable or above 1 GiB used swap, including boundary tests.
- `project_pm2_state()` / `verify_pm2_state()` - keep only names/status/restart counts and fail on missing, offline, duplicate, or incremented processes.
- `probe_readiness()` / `run_stability_gate()` - require all four loopback endpoints to stay 200 with the exact ready status for the whole default 300 seconds.
- `verify_bearer_reads()` - authenticate through central auth and prove protected Scheduler/BFF reads without logging secrets.

### Test coverage

RT-3 tests:

- `test_raw_reserved_password_round_trips_once` - raw at percent colon slash credentials preserved.
- `test_percent_encoded_password_decodes_exactly_once` - encoded percent sequences are not double-decoded.
- `test_ipv6_port_and_database_are_structured` - bracketed IPv6 and explicit port survive.
- `test_query_parameters_reach_both_drivers` - SSL/session settings survive structured construction.
- `test_malformed_urls_raise_redacted_error` - invalid input never echoes secret or host.
- `test_database_manager_uses_kwargs_and_url_object` - production wiring avoids reconstructed DSN strings.
- `test_real_encoded_credential_connects` - opt-in read-only `SELECT 1` through actual configured URL.

RT-4 tests:

- `test_health_is_process_only` - liveness stays 200 without dependency calls.
- `test_ready_requires_main_postgres_and_redis` - either failure yields ROS 503.
- `test_ready_requires_source_postgres_when_enabled` - producer source failure yields ROS 503.
- `test_ready_omits_source_when_producer_disabled` - disabled producer has no false dependency.
- `test_ready_failure_then_recovery_without_restart` - same process returns 503 then 200.
- `test_ready_body_never_leaks_dependency_details` - host URL secret text never appears.
- `test_bff_targets_ros_ready` - exact `/ready` route and status contract.
- `test_bff_recovers_with_same_client` - upstream ROS 503 then 200 propagates.

OPS-1 tests:

- `test_capacity_allows_exact_thresholds` - 512 MiB and 1 GiB boundaries pass.
- `test_capacity_blocks_low_available_memory` - below memory floor fails closed.
- `test_capacity_blocks_high_used_swap` - over swap ceiling fails closed.
- `test_pm2_restart_increment_fails_gate` - any unexpected restart blocks save.
- `test_missing_or_offline_process_fails_gate` - incomplete PM2 set blocks activation.
- `test_readiness_transition_fails_continuous_window` - any non-ready sample fails.
- `test_safe_projection_excludes_pm2_environment` - PM2 secrets never enter reports.
- `test_manifest_uses_exact_loopback_ports` - ports 3011/3021/3047/3022 are fixed.
- `test_wrappers_have_no_package_or_dsn_overlays` - no runtime installs or decoded aliases.
- `test_bearer_verifier_redacts_failures` - errors never contain password or token.

### Decision completeness

- Goal: eliminate the three runtime compensations/debts and make the dark read stack reproducibly deployable.
- Non-goals: enable FE-3, create a control plan, enable execution/readback/SCADA, enable the ROS producer schedule, change schemas, rotate secrets, or merge planning logs to product main.
- Success: all named tests/gates pass three times; real encoded DB credential reaches `SELECT 1`; ROS and BFF both show 503 then 200 without restart; OPS default window is 300 seconds with no PM2 restart increments; each PR is merged and local main matches origin/main.
- Public interfaces: new ROS `GET /ready`; ROS `GET /health` becomes liveness-only; BFF internal probe path changes to ROS `/ready`; OPS adds CLI/scripts and per-service env-file names. No DB migration or API request schema changes.
- Failures: malformed DSN fails closed with fixed safe text; readiness fails closed 503; missing/closed dependencies fail closed; capacity or PM2 instability stops applications and does not `pm2 save`; bearer mismatch exits nonzero without secrets.
- Rollout: RT-3 before RT-4; RT-4 before OPS. Each PR independently reversible. OPS activation leaves current saved PM2 state untouched unless the full stability gate succeeds.
- Monitoring: readiness status classes only, PM2 status/restart deltas, MemAvailable, used swap; never raw env, URL, exception, token, or credential.
- Acceptance commands: service pytest; `black --check`/configured lint where available; `bash -n`; Node ecosystem load; OPS pytest; three repetitions; live DB `SELECT 1`; live ROS/BFF failure-recovery exercise; `git rev-parse HEAD` equals `origin/main` after each merge.

### Dependencies

- Python 3.11 service virtualenvs with tracked requirements.
- Reachable configured PostgreSQL/Redis for live verification; no synthetic integration data.
- Standard GitHub CLI/auth for PRs.
- Host PM2 and `/proc/meminfo` only for OPS runtime activation.

### Validation and wiring

| Component | Entry point | Registration | Schema/table |
| --- | --- | --- | --- |
| BFF DSN helper | `DatabaseManager.initialize()` | relative import in BFF DB manager | connection-only; `POSTGRES_URL` |
| ROS DSN helper | `DatabaseManager.initialize()` | relative import in ROS DB manager | connection-only; `POSTGRES_URL`, optional source URL |
| ROS readiness | HTTP `GET /ready` | FastAPI decorator in `src/main.py` | main PostgreSQL, Redis, optional source PostgreSQL |
| BFF ROS probe | BFF HTTP `GET /ready` | `build_required_targets()` called by BFF main | none |
| PM2 ecosystem | `pm2 start ecosystem.config.cjs` | four wrapper paths in manifest | none |
| Runtime gate | `activate.sh` then Python CLI | called before `pm2 save` | `/proc/meminfo`, `pm2 jlist`, four HTTP endpoints |
| Bearer verifier | Python CLI after activation | operator-invoked per README | auth token in memory only; Scheduler/BFF reads |

Cross-language schema verification: no migration or schema/table edit is planned. RT-3 preserves existing databases; RT-4 reads existing connection health; OPS invokes existing tracked migration runners without introducing DDL.

## Plan Draft B - one integrated runtime-hardening PR

### Overview

Implement RT-3, RT-4, and OPS-1 together so the deployment scripts and readiness verifier are written against the final source in one atomic branch. This reduces repeated branch setup and permits one end-to-end runtime proof before merge.

### Files to change

The same RT-3, RT-4, and OPS-1 file set as Draft A, but committed and reviewed together. Tests remain service-local plus the OPS suite.

### Implementation steps

Write all RT-3 RED tests, implement DSNs, then all RT-4 RED tests, implement readiness, then OPS RED tests and scripts. Run all affected suites and one combined runtime verification before one QCHECK/g-check/PR.

### Test coverage

Identical named tests to Draft A; add one combined smoke proving canonical DSN boot, ROS readiness, BFF propagation, and OPS gate in a single deployed tree.

### Decision completeness

- Goal/non-goals/interfaces/failures are identical to Draft A.
- Success differs: one PR contains all three items and one post-merge proof.
- Rollout/backout is coarser: any regression requires reverting the entire runtime-hardening change.
- Monitoring and acceptance commands are identical.

### Dependencies, validation, and wiring

Identical to Draft A. The wiring table is unchanged because runtime entry points do not depend on PR boundaries.

## Comparative analysis

- Draft A strengths: matches the brief's explicit isolated RT-3 PR and ordered sessions; bounds review risk; preserves one-PR-at-a-time repo workflow; lets OPS depend only on merged source truth.
- Draft A cost: repeated branch/PR/gate cycles and careful carry-forward of the unmerged Coding Log into the archive branch.
- Draft B strengths: fewer Git operations and one integrated deployed-tree smoke.
- Draft B gap: violates the brief's isolation requirement for RT-3, couples two service contracts to operational tooling, and makes rollback unnecessarily broad.
- Both plans follow TDD, fail-closed readiness, no-secret logging, no schema changes, and explicit wiring verification.

## Unified Execution Plan

Use Draft A's three sequential PRs. Reuse Draft B's combined final runtime smoke only after OPS-1 lands.

### Ordered execution

1. RT-3 on `fix/rt3-canonical-dsn`: create service-local helpers/tests, prove RED/GREEN, run both complete service suites three times, run a real encoded credential `SELECT 1` without printing it, QCHECK/g-check, PR, merge, update local main, post-merge rerun.
2. RT-4 on fresh `fix/rt4-readiness-truth`: add ROS liveness/readiness tests first, implement the endpoint split, update BFF target/tests, prove 503 then 200 on unchanged processes, run both service suites three times, QCHECK/g-check, PR, merge, update local main, post-merge rerun.
3. OPS-1 on fresh `feat/ops1-reproducible-control-plan-runtime`: add gate/verifier tests first, create secret-free wrappers/manifest/README, assert no runtime package/DSN compensation, run shell/Node/Python gates three times, QCHECK/g-check, PR, merge, update local main, post-merge verify the default five-minute contract and, when capacity permits, the live window.
4. Final combined audit: prove every supplied bullet against current files, tests, PR/merge state, runtime state, and exact local-main SHA.
5. Archive: copy this Coding Log and any non-product plans/reviews into `ops/archive-rt3-rt4-ops1-20260721`, commit/push that branch without merging it, preserve prior archive branches, remove completed feature/runtime worktrees, delete obsolete non-archive local branches only after ancestry/archive checks, and confirm the primary backend worktree is clean on local main.

### Unified decision-complete checklist

- No open implementation decisions remain.
- Every public surface is named and has a defect-sensitive test.
- Validation is scoped per service plus final combined runtime proof.
- Every new component has a production/operator call path.
- No migration is added; existing migration runners are invoked before start.
- Rollout and backout are fail-closed and secret-safe.
- Product main excludes Coding Logs and planning artifacts; separate archive branch retains them.

## Implementation (2026-07-21 15:44:35 +0700) - RT-3 canonical DSN handling

### Goal

Remove runtime DSN compensation by accepting raw or percent-encoded PostgreSQL credentials, decoding credentials exactly once, and constructing asyncpg and SQLAlchemy connections without rebuilding a URL string.

### What changed

- Added identical service-local `db/postgres_dsn.py` helpers to bff-water-planning and ros-gis-integration. Each validates with a fixed redacted error, supports raw reserved characters and encoded credentials, handles IPv6/ports, maps `sslmode`/`target_session_attrs`, routes remaining query parameters to `server_settings`, returns structured asyncpg kwargs, and creates the ORM URL through SQLAlchemy `URL.create`.
- Rewired BFF `DatabaseManager.initialize()` to pass only keyword connection arguments to asyncpg and the `URL` object plus safe driver options to SQLAlchemy.
- Rewired ROS `DatabaseManager.initialize()` for both `POSTGRES_URL` and conditionally required `REQUIREMENT_SOURCE_POSTGRES_URL`, plus its SQLAlchemy engine.
- Added defect-sensitive unit tests in both services and opt-in real-PostgreSQL integration tests.
- Kept Coding Log/pointer artifacts untracked so they cannot enter the product PR; they will be copied to the separate ops archive branch after all three items land.

### TDD evidence

- RED commands:
  - `/Users/subhajlimanond/dev/munbon2-backend/services/bff-water-planning/venv/bin/python -m pytest -q tests/unit/test_postgres_dsn.py`
  - `/Users/subhajlimanond/dev/munbon2-backend/services/ros-gis-integration/venv/bin/python -m pytest -q tests/unit/test_postgres_dsn.py`
- RED result: both commands failed 11 tests. Helper calls raised `NotImplementedError`; the BFF production wiring still passed a positional reconstructed DSN whose observed password bytes were double-encoded; ROS production calls had no structured password keyword.
- GREEN focused result: both commands passed 11 tests.
- Real DB command: both integration tests ran with `POSTGRES_DSN_TEST_URL` containing the encoded reserved-character password `p%40ss%25%3A%2Freal` against an ephemeral PostgreSQL 15 container and passed `SELECT 1`; no source/runtime DSN rewrite was used.
- Reliability GREEN:
  - BFF full suite with real integration URL: 203 passed on each of three consecutive runs.
  - ROS full suite with real integration URL: 176 passed, 1 unrelated configured integration skip on each of three consecutive runs.

### Other validation

- BFF manifest-sync prerequisite fixed in the local test environment only: installed the already tracked `strawberry-graphql[fastapi]==0.322.2` and `python-multipart==0.0.32`; this changed no tracked file.
- Black check passed for both new helpers, both unit tests, both integration tests, and the already-formatted ROS manager. The legacy BFF manager is not globally Black-formatted on `main`; its new block is formatted and unrelated whole-file rewrite noise was removed.
- `git diff --cached --check` passed.
- Targeted scan found no production hostname, decoded-DSN alias, or runtime package overlay in the intended files.
- The prior EC2 alias timed out. The real PostgreSQL 15 container is therefore the current real-connection proof; live-host rollout proof remains part of OPS-1, subject to capacity and host reachability.

### Wiring verification

| Component | Non-test call site | Registration | Schema match |
| --- | --- | --- | --- |
| BFF `parse_postgres_dsn` | `DatabaseManager.initialize()` | relative import in `src/db/database_manager.py` | `POSTGRES_URL`; no schema edit |
| ROS `parse_postgres_dsn` | `DatabaseManager.initialize()` for main and source | relative import in `src/db/database_manager.py` | `POSTGRES_URL`, optional `REQUIREMENT_SOURCE_POSTGRES_URL`; no schema edit |
| asyncpg structured args | both manager pool constructors | direct `asyncpg.create_pool(**kwargs)` | real PostgreSQL `SELECT 1` passed |
| SQLAlchemy URL | both manager engine constructors | direct `create_async_engine(URL.create(...))` | ORM connection metadata preserved |

### Behavior and risk notes

- Malformed URLs fail closed as `Invalid PostgreSQL URL`; no URL, host, password, or parser exception is reflected.
- Identity-bearing query parameters and certificate-path query parameters are rejected instead of ambiguously overriding the structured authority. `sslmode`, `ssl`, `target_session_attrs`, and PostgreSQL server settings remain supported.
- Percent decoding is exactly once. An encoded literal such as `%252F` becomes `%2F`, not `/`.
- No migration, schema, env name, port, or API contract changed.

### Follow-ups

- RT-4 must branch from refreshed merged main and may rely on ROS booting with canonical DSN handling.
- OPS-1 must not reintroduce `LEGACY_POSTGRES_URL` or any decoded/runtime-only DSN alias.

## Review (2026-07-21 15:44:35 +0700) - working-tree

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-rt3-canonical-dsn-20260721`
- Branch: `fix/rt3-canonical-dsn`
- Scope: staged RT-3 product files; untracked Coding Log/pointer explicitly excluded from the product review set.
- Commands Run: staged name/stat/targeted diff inspection; line-numbered helper/manager/test inspection; `git diff --cached --check`; focused pytest; both full service suites three times with real PostgreSQL integration; Black checks; exact helper-file comparison; secret/overlay scan.
- Auggie semantic review timed out at the required two-second ceiling; direct inspection fallback was used.

### Findings

CRITICAL

- No findings.

HIGH

- No findings.

MEDIUM

- No findings.

LOW

- No findings. An initial unrelated whole-file Black rewrite in the BFF manager was removed before this formal review.

### Open Questions / Assumptions

- Raw `?` and `#` inside credentials are intentionally unsupported because they delimit query/fragment syntax; the requested raw/encoded `@`, `%`, `:`, and `/` cases are covered.
- Live EC2 proof could not run because the configured SSH endpoint timed out. The opt-in integration test provides real PostgreSQL protocol/authentication proof without mocks.

### Recommended Tests / Validation

- Keep the opt-in encoded-credential integration test in CI whenever a disposable PostgreSQL URL is available.
- Rerun both service suites after merge and exercise the live encoded host URL during OPS-1 activation if the host passes capacity gating.

### Rollout Notes

- RT-3 has no schema or API rollout. Revert restores the old URL reconstruction, but that would again require the forbidden decoded runtime overlay for encoded credentials.
- The new parser never logs or returns the input URL on failure.

### RT-3 merge and post-merge verification

- PR: `#111` (`https://github.com/SubhajL/munbon2-backend/pull/111`).
- GitHub Actions infrastructure: all jobs ended with zero steps; annotations reported the account was locked due to a billing issue. Main had no branch protection/ruleset. The exact annotation and all local evidence were posted on the PR before the repository-documented merge path was used, matching the immediately preceding PR #110 precedent.
- Merged commit: `5f69e2f0c4a405450c228bc873ba4df9e2464a39`; local `main == origin/main` in the isolated worktree.
- Exact merged-commit post-merge tests: BFF 202 passed with the opt-in DB test skipped because its disposable URL was absent; ROS 175 passed with its two opt-in DB tests skipped. The same product bytes had already passed the real PostgreSQL encoded-credential tests and three full reliability runs before merge.
- The original backend checkout was concurrently moved by separate work onto dirty branch `feat/7-3a-dark-commandability-d6-validation`. It was not switched, staged, edited, or cleaned; subsequent work remains isolated.

## Implementation (2026-07-21 16:04:47 +07) - RT-4 readiness truth

### Goal

Separate ROS process liveness from dependency readiness, make the BFF consume ROS dependency truth, and prove dependency failure/recovery without process restarts or secret-bearing output.

### What changed

- ROS `/health` is process-only and never calls a dependency.
- ROS `/ready` checks main PostgreSQL and Redis, plus requirement-source PostgreSQL only when the daily requirement producer is enabled. Any missing, false, malformed, or exceptional result fails closed with HTTP 503 and fixed safe labels.
- Removed ROS's fabricated Flow/Scheduler/ROS/GIS health booleans.
- BFF readiness now probes ROS `/ready` and requires the exact `status: ready` contract; a liveness response cannot satisfy readiness.
- ROS dependency-health logs now emit only exception class names, never raw PostgreSQL/Redis exception text.
- Service documentation reflects the liveness/readiness split.

### TDD and recovery evidence

- Initial RED: the BFF target-builder test failed because production still selected ROS `/health`; seven ROS readiness tests failed because `/health` still called dependencies and `/ready` did not exist.
- Focused GREEN: BFF readiness tests passed 28; ROS readiness tests passed 12 before formal review additions.
- The same in-process ROS ASGI app and the same pooled BFF client each observed a 503 dependency failure and a later 200 recovery after only dependency state changed; neither app/client was restarted.
- Formal review found a log-only leakage path in `DatabaseManager.check_health()`. The new regression test first failed while exposing credential-bearing DB/Redis exceptions, then passed after production logging was reduced to exception types.
- Final reliability GREEN, three consecutive runs each:
  - BFF: 204 passed, 1 opt-in integration skip.
  - ROS: 188 passed, 2 opt-in integration skips.

### Wiring verification

| Component | Non-test call site | Registration | Contract proof |
| --- | --- | --- | --- |
| ROS process liveness | `GET /health` | FastAPI decorator in `src/main.py` | Test proves zero dependency calls |
| ROS dependency readiness | `GET /ready` | FastAPI decorator and `app.state.db_manager` | PG/Redis/source failure matrix plus same-app recovery |
| ROS DB/source health | `DatabaseManager.check_health()` | Lifespan-owned manager | Source included only with producer enabled; safe log regression |
| BFF ROS probe | `build_required_targets()` | BFF `/ready` route's pooled probe service | Exact `/ready`, exact `ready`, same-client failure/recovery |

### Validation

- Black check passed for all changed Python implementation/test files.
- `git diff --cached --check` passed.
- Targeted scans confirmed no readiness hardcoded external-service booleans, no ROS `/health` BFF target, and no raw exception value in the ROS dependency-health checks.
- No migration, schema, env name, service port, or package manifest changed.

## Review (2026-07-21 16:04:47 +07) - working-tree

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-rt3-canonical-dsn-20260721`
- Branch: `fix/rt4-readiness-truth`
- Scope: eight staged RT-4 product files; untracked Coding Log/pointer excluded from the product review set.
- Commands Run: staged status/stat/diff inspection; ROS manager/main/readiness test inspection; BFF readiness implementation/test inspection; focused RED/GREEN pytest; both full suites three times on final bytes; Black checks; whitespace, endpoint-wiring, hardcoded-claim, and leakage scans.
- Auggie semantic review timed out at the required two-second ceiling; direct inspection fallback was used.

### Findings

CRITICAL

- No findings.

HIGH

- Fixed before final review: raw connection exception strings were logged by ROS dependency checks even though the HTTP body was safe. A failing regression now covers main PostgreSQL, source PostgreSQL, and Redis logs; production emits only `error_type`.

MEDIUM

- Fixed before final review: a malformed non-dictionary health result could have raised while constructing readiness. It now follows the same fixed safe 503 response.

LOW

- No findings.

### Open Questions / Assumptions

- `DAILY_REQUIREMENT_ENABLED` is the existing source-pool/producer enablement boundary, so it is also the readiness boundary for requirement-source PostgreSQL.
- Historical raw exception logging outside the dependency-readiness method is not exercised by `/ready` and remains outside RT-4.

### Recommended Tests / Validation

- Preserve the same-app and same-client failure/recovery tests; they specifically prevent a cached readiness result or restart-only recovery regression.
- Run one post-merge full suite per affected service before starting OPS-1.

### Rollout Notes

- BFF and ROS must roll together: an old ROS without `/ready` correctly makes the new BFF return 503.
- No migration is required. Rollback restores the old liveness probe and therefore restores the known false-positive risk.

### RT-4 merge and post-merge verification

- PR: `#112` (`https://github.com/SubhajL/munbon2-backend/pull/112`).
- GitHub Actions again created zero-step jobs only; the exact annotation reported the account was locked due to a billing issue. The local three-run evidence, formal review, empty-step proof, and annotation were posted on the PR. Main remained unprotected with no rulesets, so the repository's normal squash-merge path was used.
- Merged commit: `f6c624472b946e0ec6fc161870f3baa1e25ccf0f`; local `main == origin/main` after preserving a concurrent local commit on its existing feature branch.
- Exact merged-commit post-merge tests: BFF 204 passed, 1 opt-in integration skip; ROS 188 passed, 2 opt-in integration skips.
- OPS-1 branch `feat/ops1-reproducible-control-plan-runtime` was created directly from merged `origin/main`.

## Implementation (2026-07-21 16:21:22 +07) - OPS-1 reproducible runtime

### Goal

Replace the machine-specific wrappers in runtime commit `c352fdd6` with source-controlled, secret-free deployment assets that use only tracked dependencies and canonical DSNs, fail closed on capacity/restart/readiness defects, and provide a real central-auth bearer verifier.

### What changed

- Added repo-relative PM2 wrappers for Flow, Scheduler, ROS-GIS, and BFF at exact loopback ports 3011, 3021, 3047, and 3022.
- Added a shared mode-600 environment loader. Each service receives canonical settings directly; there is no legacy/decoded DSN alias, host path, embedded credential, or runtime package install.
- Added migration-before-start: Flow/Scheduler `apply-all`, every tracked ROS migration in order, and an idempotent BFF SQL applier that imports the RT-3 canonical DSN parser and logs only a safe exception type on failure.
- Added a repo-relative PM2 ecosystem and fail-closed activation script. Capacity gates before PM2 changes; after the intentional manifest load it snapshots restart counters, permits a bounded two-minute dependency startup only if capacity/restart state stays safe, requires a subsequent 300-second all-ready window, and saves PM2 only on success.
- Added a standard-library bearer verifier that checks missing/malformed credentials, real central login and strict claims, Scheduler/BFF v2 list reads, missing-detail 404 preservation, BFF no-store headers, logout, and refresh-token reuse rejection without printing credentials/tokens/cookies/bodies.
- Added operator README instructions for environment ownership, exact commands, capacity behavior, dark posture, safe diagnostics, and backout.

### TDD evidence

- Initial RED: OPS tests stopped at collection because `runtime_gate` and `verify_bearer` did not exist; artifact tests also named the absent manifest/wrappers/README.
- Initial GREEN: 25 focused tests passed after the first implementation.
- Review-driven RED/GREEN:
  - Activation-order test failed until the restart baseline moved after the intentional PM2 manifest load, preventing an expected reload from being called an unexpected restart.
  - Startup-monitor tests failed until a bounded transient startup phase was added; capacity and restart defects remain immediate failures and the 300-second stability clock starts only after first full readiness.
  - Safe BFF migration failure regression confirms credential-bearing invalid URLs produce only the exception class.
  - Prior-host capacity case (330 MiB available, 873 MiB swap used) explicitly fails on the memory floor.
- Final reliability GREEN: 29 tests passed on each of three consecutive runs.

### Real migration proof

- Started an ephemeral PostgreSQL 15 container on loopback with synthetic reserved-character password `p@ss%:/real`.
- Passed the encoded canonical URL to `apply_bff_migration.py`; it authenticated without a decoded overlay, created `gis.crop_registry`, and passed a second idempotent application.
- The container was removed immediately after proof.

### Wiring verification

| Component | Non-test call site | Registration | Contract proof |
| --- | --- | --- | --- |
| Four wrappers | PM2 ecosystem app entries | repo-relative `path.join(__dirname, wrapper)` | exact names/paths/ports and `bash -n` tests |
| Env loader | every wrapper before settings use | `runtime-lib.sh` | mode 600 and required-name checks; no value output |
| Migrations | each wrapper before Uvicorn | tracked runners plus BFF SQL helper | static order tests plus real encoded BFF DB proof |
| Capacity/restart/readiness gate | `activate.sh` | capacity -> PM2 -> baseline -> startup -> 300s -> save | boundary, prior-host, PM2 projection, startup, recovery, and duration tests |
| Bearer verifier | operator CLI | direct auth/Scheduler/BFF loopback URLs | strict claim/page/no-store/logout checks with safe reporting |

### Validation

- Focused suite: 29 passed, three consecutive runs.
- Black check passed for all Python scripts/tests.
- Every shell script passed `bash -n`; the Node-loaded ecosystem registered exactly the four intended process names.
- `git diff --cached --check` passed; executable modes are staged for every command/wrapper.
- Secret/overlay scan found no legacy/decoded DSN alias, runtime package install, machine-specific path, embedded PostgreSQL credential, private key, or GitHub token.
- Live-host activation remains pending until after merge; the last known host state correctly fails the new memory gate, and the configured SSH endpoint previously timed out.

## Review (2026-07-21 16:21:22 +07) - working-tree

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-rt3-canonical-dsn-20260721`
- Branch: `feat/ops1-reproducible-control-plan-runtime`
- Scope: 16 staged OPS-1 runtime/readme/test files; untracked Coding Log/pointer excluded from product review.
- Commands Run: complete line-by-line script/README/test inspection; staged stat/mode/whitespace checks; focused RED/GREEN and three final runs; Black; shell syntax; Node manifest load; overlay/secret scan; real PostgreSQL encoded-credential BFF migration twice.
- Auggie semantic review timed out at the required two-second ceiling earlier in this item; direct inspection fallback was used.

### Findings

CRITICAL

- No findings.

HIGH

- Fixed before formal review: a baseline captured before PM2 updated an existing entry could reject the intentional deployment reload. The baseline is now captured immediately after that load, and every later increment is blocked.
- Fixed before formal review: immediate stability sampling could stop healthy services while their migrations/pools were still initializing. A bounded startup phase now allows only transient state, then requires the full independent five-minute green window.

MEDIUM

- Fixed before formal review: the repository's blanket `tests/` ignore rule initially excluded the new OPS test directory from staging. All five test files are now explicitly tracked in the product change.

LOW

- No findings.

### Open Questions / Assumptions

- The live host must first satisfy `MemAvailable >= 512 MiB`; the last measured 330 MiB is an intentional activation blocker, not a bypass candidate.
- Central auth on loopback 3005 and operator credentials remain prerequisites owned outside this secret-free repository directory.

### Recommended Tests / Validation

- After merge, run the capacity gate on the live host. Activate only if it passes, then allow the script's full startup plus 300-second stable window and run the bearer verifier.
- If SSH remains unreachable or capacity remains below threshold, record the exact blocker and do not mutate/suppress the gate.

### Rollout Notes

- Activation remains read-only/dark: Scheduler execution disabled, readback off, no SCADA/service secret/capability snapshot; ROS producer/schedules disabled.
- Failed activation stops exactly the four runtime processes and does not save PM2. It never rolls back data migrations; database correction stays forward-only or restore-based.

### OPS-1 merge, post-merge verification, and live blocker

- PR: `#113` (`https://github.com/SubhajL/munbon2-backend/pull/113`).
- GitHub Actions secret-scan jobs again had zero steps and the exact account-billing-lock annotation. Local evidence and the infrastructure failure were posted on the PR; main had no rulesets/protection and the normal squash-merge path was used.
- Merged commit: `e364d17fd38bc520195e9cfde06f659508e02b42`; local `main == origin/main`.
- Exact merged-commit post-merge proof: 29 OPS tests passed; shell syntax and four-app Node manifest load passed.
- Live SSH attempt to `ec2-43-209-12-182.ap-southeast-7.compute.amazonaws.com:22` timed out before authentication, so the live capacity command, activation, 300-second window, and bearer verifier could not execute.
- Read-only AWS EC2 API fallback also failed because the locally configured AWS credentials returned `AuthFailure`. No host, PM2, database, security-group, or deployment state was mutated. Live activation remains fail-closed pending restored host reachability and valid operator access.

## Archive and cleanup (2026-07-21)

- Product `main` and `origin/main` both resolve to `e364d17fd38bc520195e9cfde06f659508e02b42`, containing merged PRs #111, #112, and #113 without Coding Log/plan artifacts.
- This log and `.codex/coding-log.current` are committed only on `ops/archive-rt3-rt4-ops1-20260721`, based on that product main.
- Verified `c352fdd6` is an ancestor of `ops/archive-control-plan-runtime-roadmap-20260721` and verified its runtime ecosystem and coding log are readable from that archive branch.
- Removed clean worktree `/Users/subhajlimanond/dev/munbon2-backend-control-plan-runtime-20260721` and deleted its obsolete local `ops/control-plan-read-runtime-20260721` branch. Its material remains recoverable from the verified archive branch.
- Concurrent/unrelated feature worktrees and branches were not switched, edited, cleaned, or removed. The primary checkout remains owned by concurrent work on `feat/7-3b-dark-deployment-observability`.
- The temporary RT-3/RT-4/OPS-1 worktree will be removed only after this archive branch is pushed and its remote commit/content are verified; that final filesystem audit is reported in the session handoff.

## Live-host recovery and bearer-audience correction (2026-07-21)

- Recovered the current authorized host from the same-day central-auth operator log after the old `AWS-Lab01` alias timed out. Direct SSH to the current host succeeded without changing host state.
- Live capacity was `MemAvailable=262064 kB`, below the required 512 MiB floor. The exact merged `runtime_gate.py` returned `FAIL capacity: mem_available_below_512_mib`, so activation and its five-minute window were correctly not started.
- The live PM2 projection still showed the four pre-OPS runtime services online; restart counts were 1 (BFF), 1 (flow-monitoring), 43 (ROS), and 16 (Scheduler). BFF, flow-monitoring, and Scheduler readiness returned 200; the old ROS runtime returned 200 on `/health` and 404 on `/ready`, confirming that the new runtime manifest is not live.
- A loopback SSH tunnel allowed the exact merged bearer verifier to exercise central auth, Scheduler, and BFF without exposing credentials. Missing and malformed bearer checks passed, then strict access-claim validation failed only on `audience`.
- Safe claim-key/type inspection and the same-day auth deployment record established the live non-secret contract as issuer `munbon-auth`, audience `munbon-services`, and role `operator`. The verifier's hidden `munbon-api` audience default was therefore a real OPS-1 defect.
- Follow-up branch: `fix/ops1-bearer-audience-contract`; commit `d3262cbf7eea9bdcac81f739044b2e7986f4c916`.

### Follow-up TDD and validation

- RED: a parameterized test for missing, empty, and whitespace-only `MUNBON_EXPECTED_JWT_AUDIENCE` failed because `Config` silently supplied the wrong default.
- GREEN: the verifier now requires and trims an explicit audience, raising the fixed safe code `expected_audience_missing` when absent.
- RED: the runtime-artifact test failed while the README used a placeholder audience that was not directly runnable.
- GREEN: the README now gives `MUNBON_EXPECTED_JWT_AUDIENCE='munbon-services'` and states that the value must match central auth and Scheduler `JWT_AUDIENCE`.
- Final OPS suite: 33 passed; the preceding reliability gate also passed the same 33 tests on each of three consecutive runs.
- Black check, staged whitespace check, and bounded secret/host scan passed.
- Live corrected verifier passed all six fixed-code steps: missing bearer rejection, malformed bearer rejection, central login plus strict claims, operator Scheduler/BFF list reads, preserved missing-detail 404s, and logout plus rejected refresh-token reuse.
- Auggie semantic search was skipped after its bounded calls repeatedly timed out earlier in the item; exact-file and exact-string inspection was used as the documented fallback.

## Review (2026-07-21 16:38:00 +07) - commit `d3262cbf`

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-ops1-bearer-fix-20260721`.
- Scope: four-file OPS verifier contract correction in commit `d3262cbf`.
- Commands Run: full diff inspection; call-site search; 33 focused tests; Black check; staged whitespace check; secret/host scan; live tunnel verification against central auth, Scheduler, and BFF.

### Findings

CRITICAL

- No findings.

HIGH

- Fixed before formal review: the hidden `munbon-api` default made a correctly configured live deployment fail strict verification. The expected audience is now mandatory and deployment-owned.

MEDIUM

- Fixed before formal review: the first README correction used a placeholder instead of an exact runnable value. An artifact test now pins the current `munbon-services` command.

LOW

- No findings.

### Open Questions / Assumptions

- `munbon-services` is the current deployment contract, not a universal product default; future environments must pass their own exact configured value.
- Activation remains intentionally blocked until the live host satisfies `MemAvailable >= 512 MiB`; no capacity bypass is authorized.

### Recommended Tests / Validation

- Re-run the bearer verifier from the exact merged commit with the explicit live audience after merge.
- Re-run the capacity gate before any future activation attempt and start the 300-second stability window only after the gate passes.

### Wiring verification

| Source | Consumer | Contract | Evidence |
| --- | --- | --- | --- |
| `MUNBON_EXPECTED_JWT_AUDIENCE` | `Config.from_environment()` | required, trimmed, non-empty | parameterized fail-closed tests |
| `Config.audience` | `run_verification()` -> `claim_errors()` | exact scalar or list membership | unit claim tests plus live success |
| README command | operator CLI | current explicit `munbon-services` value | artifact assertion plus live invocation |

## Bearer follow-up merge and completion (2026-07-21 16:42:18 +07)

- PR: `#114` (`https://github.com/SubhajL/munbon2-backend/pull/114`).
- Both GitHub Actions secret-scan jobs again had zero steps and the exact annotation `The job was not started because your account is locked due to a billing issue.` Local test, review, scan, and live evidence were posted on the PR. `main` had no branch protection or rulesets, so the normal squash-merge path was used.
- Remote merge commit: `80f3060f3bce0de721d20c9e1408fe9305502d32`.
- `gh pr merge --squash --delete-branch` completed the GitHub merge but could not update the checkout because local `main` was already in the primary worktree. The remote result was verified directly; no reset or force-update was used.
- The primary local `main` was clean and already contained four separate 7.3a/7.3b commits. Merging `origin/main` preserved them and landed the OPS correction at local merge commit `efbdf5cfdc06f6e82e9560af40af5a49d9f54915`; local `main` is now five commits ahead and zero behind `origin/main`.
- Exact post-merge local-main validation: 33 OPS tests passed and Black check passed.
- The first post-merge live-verifier attempt hit a stale SSH tunnel whose diagnostic was `Broken pipe`. A fresh loopback-only tunnel returned 200 readiness for auth, Scheduler, and BFF; the verifier loaded from exact `origin/main` then passed all six fixed-code steps.
- The replacement tunnel was stopped after proof and local ports 33005, 33021, and 33022 were verified free.
- Deployment/activation was not attempted because the live host remains below the mandatory 512 MiB available-memory floor. This is the intended fail-closed OPS-1 result; the five-minute stability window begins only after capacity and startup readiness pass.
