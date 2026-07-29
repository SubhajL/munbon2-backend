# RID calendar v1 correctness

Created: 2026-07-30 15:50:43 +0700
Branch: `feat/rid-calendar-v1`
Starting HEAD: `8c2c3570d2c66470ba186a0945b666c5f479f39b`
Base: `origin/main` at `f6584acca6ab5fb4f8f5560f0cb07bb9c38d14b2`

## Exploration and confirmed decisions

Auggie semantic search could not be given the required real two-second deadline, so it was
skipped. Planning is based on direct inspection plus exact-identifier searches of:

- `AGENTS.md`, `CLAUDE.md`, `CONTEXT.md`
- `services/bff-water-planning/CLAUDE.md`
- `contracts/rid-calendar/v1/*`
- `services/bff-water-planning/src/core/rid_calendar.py`
- `services/bff-water-planning/src/services/daily_demand_calculator.py`
- BFF RID-calendar and daily-demand tests
- `services/ros/src/utils/rid-calendar.js`
- `services/ros/src/services/{excelService,queueService}.js`
- ROS RID-calendar and Excel tests
- Smart CMS `water_planning.zone_planting_dates` write path
- ROS-GIS requirement-source loading and daily requirement production

Two read-only `terra_support` explorations were reused: one reconstructed the contract/history
and one independently traced crop-demand and Excel risks. The primary agent verified the
runtime call sites and owns all decisions below.

The user confirmed:

- Administrative irrigation year/week remains fixed from 1 November through 31 October.
- It uses an ending-year label: 2024-11-01 belongs to irrigation year 2025 CE / 2568 BE.
- Crop activity is not a fixed rainy/dry calendar. It is driven by actual per-zone planting
  dates supplied by Smart CMS and the resolved expected harvest date.
- No public `season(date)` operation may infer rainy/dry state from a month boundary.
- Crop activity is inclusive at both planting and expected harvest.
- Existing legacy `calendar_week` / `calendar_year` keys are not reinterpreted in place.
- The speculative ROS Excel consumer changes are removed from this PR.

## Plan Draft A — pure crop gate in the calculator

### Overview

Publish a corrected RID calendar v1 with four public operations and explicit CE/BE identities,
then evaluate crop activity once per plot before ROS, AquaCrop, AWD, or persistence. Remove the
dormant Excel parser integration while retaining the independently tested JavaScript contract
implementation.

### Files to change

- `contracts/rid-calendar/v1/README.md` — authoritative rules, four-operation API, source-driven
  crop activity, and corrected legacy-key wording.
- `contracts/rid-calendar/v1/{irrigation-week,crop-activity}.schema.json` — renamed public
  vocabulary and bounded crop-state schema.
- `contracts/rid-calendar/v1/{irrigation-week,crop-activity}.vectors.json` — ending-year,
  CE/BE, week-span, and crop-window boundary witnesses.
- `contracts/rid-calendar/v1/manifest.json` — renamed inventory and refreshed hashes.
- Delete the superseded `rid-week.*` and `crop-week.*` contract files.
- `services/bff-water-planning/src/core/rid_calendar.py` — `IrrigationYear`,
  `IrrigationWeek`, `DateSpan`, `CropActivity`, and the four public operations.
- `services/bff-water-planning/src/core/__init__.py` — publish only the agreed vocabulary.
- BFF RID-calendar tests — replay renamed vectors, integrity witnesses, era invariants, and
  pure-function properties.
- `services/bff-water-planning/src/services/daily_demand_calculator.py` — gate inactive plots
  before demand engines and pass the already-resolved crop week to ROS.
- `services/bff-water-planning/tests/unit/test_daily_demand_crop_activity.py` — calculator-level
  positive AquaCrop fixtures before planting and after harvest.
- `services/bff-water-planning/tests/unit/test_daily_demand_crop_week.py` — active-window ROS
  request coverage using the new public vocabulary.
- `services/ros/src/utils/rid-calendar.js` and its test — mirror the corrected contract.
- `services/ros/src/services/excelService.js`, `services/ros/jest.config.js` — remove only the
  speculative Excel/calendar consumer and its test-only alias wiring.
- Delete `services/ros/tests/unit/excel-planting-schedule.test.js`.
- Prior and current Coding Logs plus `.codex/coding-log.current` — preserve review evidence and
  record lifecycle proof.

### Implementation steps and TDD sequence

1. Replace test imports and expectations with the four-operation vocabulary and bounded crop
   activity; run focused Python and Jest suites to obtain RED failures for missing symbols and
   old vector fields.
2. Add calculator-level tests with positive inactive-window AquaCrop fixtures; run them RED and
   confirm ROS/AquaCrop are currently called or positive demand is produced.
3. Implement the smallest pure domain types/functions and replay the shared vectors.
4. Gate `calculate_daily_demands` before either demand engine; skip inactive rows and skip empty
   persistence. Pass `CropActivity.crop_week` into `_calculate_ros_demand`.
5. Remove the Excel consumer delta and its tests; no RED applies because this is an explicit
   deletion/reversion of dormant speculative wiring.
6. Refresh manifest hashes and embedded contract-set pins.
7. Format, run focused tests, then full per-service gates and three-run reliability checks.

Functions:

- `irrigation_year(day)` — return ending-year `IrrigationYear` with explicit CE/BE values.
- `irrigation_week(day)` — return an atomic `IrrigationWeek` identity and unambiguous key.
- `irrigation_week_span(week)` — return the inclusive seven-day span or short week 53.
- `crop_activity(planting_date, expected_harvest_date, on)` — return
  `not_planted|active|harvested` and an optional crop week.
- `_calculate_ros_demand(plot, date, crop_week)` — price only an already-active crop and never
  reload a competing planting date from ROS.

### Test coverage

- `test_irrigation_year_uses_ending_year_and_explicit_eras` — ending label and 543-year invariant.
- `test_irrigation_week_matches_every_contract_vector` — shared date-to-identity conformance.
- `test_contract_retains_named_boundary_witnesses` — prevents weakening by vector count alone.
- `test_crop_activity_matches_every_contract_vector` — both inactive bounds and active weeks.
- `test_crop_activity_rejects_reversed_window` — invalid harvest fails closed.
- `test_inactive_crop_skips_both_engines_and_persistence` — positive fixtures cannot leak demand.
- `test_planting_and_harvest_dates_are_active` — inclusive endpoints price exactly once.
- Jest mirrors each cross-language contract and integrity assertion.

### Decision completeness

- Goal: publish correct unpushed contract v1 and prevent all out-of-window pricing.
- Non-goals: named rainy/dry inference, FE schema changes, workbook-family repair, ROS upload
  activation, legacy key migration, or ROS-GIS producer rewiring.
- Success: both languages replay identical contract bytes; inactive plots call neither demand
  engine nor persistence; active endpoints pass their exact crop week; Excel delta is absent.
- Public interfaces: four pure operations and four immutable identity/result types. No endpoint,
  environment variable, migration, queue payload, or message-topic change.
- Failure modes: wrong types/ranges and reversed crop windows raise; missing plot dates fail
  closed by skipping pricing; no compatibility aliases are published.
- Rollout/backout: contract is unpushed, so amend in place. Reverting the PR restores the prior
  behavior; no data migration exists.
- Monitoring: existing calculator warning/error logs identify invalid plot inputs. Watch for
  unexpected inactive counts after later deployment; no activation is part of this PR.
- Acceptance: BFF bare pytest, ROS Jest in multiple timezones, formatting/lint where configured,
  manifest/hash verification, and exact runtime call-site search.

### Dependencies

No new packages, services, secrets, database schemas, or external runtime dependencies.

### Validation

- `services/bff-water-planning/venv/bin/python -m pytest -q tests/unit/...`
- `services/bff-water-planning/venv/bin/python -m pytest -q`
- `npm test -- --runInBand` from `services/ros`
- `npm run lint` from `services/ros`
- timezone replay for the ROS contract suite
- contract manifest and embedded set-hash checks in both languages

### Wiring verification

| Component | Entry point | Registration | Schema/table |
|---|---|---|---|
| Python RID calendar | `DailyDemandCalculator.calculate_daily_demands` | `from core import crop_activity` | contract JSON only |
| Crop gate | daily scheduler and REST-triggered calculator call | existing `main.py` scheduler/router wiring | source plot planting/harvest fields; no schema change |
| JavaScript RID calendar | contract conformance suite only by explicit scope | Jest `testMatch` | contract JSON only |
| Excel removal | none after removal | dormant unmounted ROS upload path unchanged | none |

The JavaScript implementation deliberately has no speculative production caller after Excel
removal. It remains because the user approved contract-data plus language-local conformance; a
future real ROS consumer must wire it in its own vertical slice.

### Cross-language schema verification

No DB migration is planned. Exact searches confirm Smart CMS persists `planting_date` in
`water_planning.zone_planting_dates`, ROS-GIS maps it by zone, and the BFF calculator already
loads `planting_date` plus `expected_harvest_date` on each plot. This PR changes no table name or
column semantics.

## Plan Draft B — filter crop activity in SQL

### Overview

Publish the same corrected contract, but push planting/harvest filtering into
`_get_active_plots` so inactive plots never enter the calculator loop. Keep a bounded pure
`crop_activity` function for contract conformance and active crop-week calculation.

### Files to change

The contract, language implementations, tests, Excel removals, and logs match Draft A.
`daily_demand_calculator.py` additionally changes `_get_active_plots(zones, date)` and its SQL
date predicates; calculator tests pin the query arguments and mock behavior.

### Implementation steps and TDD sequence

1. Add contract and SQL-filter tests first; confirm missing vocabulary and absent predicates RED.
2. Implement identities, four operations, and contract vectors.
3. Add `planting_date <= calculation_date <= expected_harvest_date` to plot selection.
4. Keep a defensive pure crop-activity assertion before ROS and pass the resulting week.
5. Remove Excel delta, refresh hashes, format, and run all gates three times.

Functions:

- The four contract operations match Draft A.
- `_get_active_plots(zones, date)` — return only database rows inside their crop window.
- `_calculate_ros_demand(plot, date, crop_week)` — active-only ROS request.

### Test coverage

Contract tests match Draft A. Additional query tests assert both bounds and parameter numbering;
mock-profile tests assert the same filter is applied outside SQL.

### Decision completeness

- Goal/non-goals/public interfaces: same as Draft A.
- Success additionally requires SQL and mock profiles to filter identically.
- Failure modes: null dates are excluded by SQL; malformed values fail in the defensive domain
  call. This fails closed.
- Rollout/backout/monitoring/acceptance: same as Draft A, with query-shape regression coverage.

### Dependencies

No new packages or migrations. It assumes every supported DB uses the same plot date columns.

### Validation

Draft A commands plus focused `_get_active_plots` query tests.

### Wiring verification

| Component | Entry point | Registration | Schema/table |
|---|---|---|---|
| Python RID calendar | calculator loop | existing core import | contract JSON |
| SQL crop filter | `_get_active_plots(zones, date)` | existing calculator call | `ros_gis.plots.planting_date`, `expected_harvest_date` |
| JavaScript mirror | Jest conformance | Jest `testMatch` | contract JSON |
| Excel removal | none | dormant path unchanged | none |

### Cross-language schema verification

No migration. Both date column names already appear in the BFF query and ROS-GIS inputs.

## Comparative analysis

- Draft A centralizes one crop-activity decision in the pure contract, works identically for mock
  and real inputs, and makes engine non-invocation directly testable.
- Draft B reduces rows returned by SQL but duplicates the date-window rule between SQL and Python,
  risks mock/DB divergence, and treats null/malformed dates differently across profiles.
- Draft A may iterate over inactive rows, but correctness dominates this small scheduler batch and
  future query optimization can be added without changing domain semantics.
- Both preserve the FE/ROS-GIS authority boundary and avoid inventing a fixed rainy/dry season.
- Draft A better follows the repo preference for pure, testable domain logic and minimal changes.

## Unified Execution Plan

### Overview

Use Draft A. Publish four precise administrative-calendar/crop-activity operations, with explicit
ending-year CE/BE identities, and make crop activity the sole gate before any BFF demand engine.
Remove the speculative Excel integration and leave existing legacy calendar keys untouched.

### Files to change

Use the Draft A file list exactly. Do not add migrations, FE changes, queue plumbing, routes,
flags, or compatibility aliases.

### Implementation steps

1. **RED contract tests:** rename schemas/vectors in test expectations; add ending-year, era,
   integrity, and bounded crop-activity assertions; confirm failures against current code.
2. **RED calculator tests:** add positive inactive-window AquaCrop/ROS fixtures at day-before and
   day-after boundaries; confirm current calculator invokes engines or emits demand.
3. **GREEN domain implementation:** add `IrrigationYear`, `IrrigationWeek`, `DateSpan`,
   `CropActivity`; implement the four public operations and private validation/helpers.
4. **GREEN runtime integration:** evaluate `crop_activity` from source-provided plot dates before
   ROS/AquaCrop/AWD, skip inactive/invalid plots, skip empty persistence, and pass the crop week
   into ROS without retrieving a competing crop calendar.
5. **Remove speculative Excel wiring:** restore `excelService.js` and Jest alias config to base,
   delete its planting-schedule test, retain only the language-local calendar mirror.
6. **Contract publication:** rename contract files, refresh file hashes/set hash, and update both
   embedded pins.
7. **Fast gates:** format touched files, run focused Python/Jest tests, lint the ROS service.
8. **Full gates:** bare BFF pytest and ROS Jest; replay relevant suites three consecutive times
   and replay JS contract tests across Bangkok, UTC, Los Angeles, and Chatham.
9. **Wiring/QCHECK/g-check:** verify exact call sites, run an independent read-only QCHECK, stage
   intended files, run formal `g-check`, disposition findings, and rerun affected gates.
10. **Lifecycle:** amend the unpushed commit with a conventional message and no prohibited
    attribution, push, open PR, inspect checks, admin-merge if allowed, synchronize local main,
    and run exact-merged-SHA post-merge verification.

### Test coverage

- Contract pinning and renamed-file inventory.
- Ending-year CE/BE identity at 31 October / 1 November.
- Week 53 leap/non-leap spans and supported limits.
- Required named witnesses cannot be deleted silently.
- Crop activity before, planting day, intermediate weeks, harvest day, and after harvest.
- Reversed crop windows and invalid date types fail closed.
- Calculator-level inactive dates with positive engine fixtures call neither engine.
- Planting/harvest endpoints pass exact crop weeks to ROS and may persist.
- JavaScript mirrors all shared vectors and era invariants.

### Decision completeness

- Goal: correct contract v1 and eliminate out-of-window demand pricing before first push.
- Non-goals: fixed rainy/dry labels, FE schema work, Excel workbook repair, upload activation,
  legacy calendar-key cutover, or canonical ROS-GIS producer redesign.
- Success criteria:
  - no `rid_year`, `rid_week`, `RidWeek`, `rid_week_of`, or unbounded `crop_week_of` remains in
    the v1 public contract/implementations/tests;
  - four operations agree across Python/JS vectors;
  - 2024-11-01 is 2025 CE / 2568 BE irrigation week 1;
  - inactive calculator paths invoke neither ROS nor AquaCrop and write no demand;
  - Excel consumer delta and vacuous real-workbook test are absent;
  - all gates and reviews pass before push.
- Public interfaces: the four pure operations/types only; no endpoint/env/topic/migration change.
- Edge/failure modes: strict civil dates; explicit range checks; reversed crop window raises;
  null/malformed plot windows fail closed without pricing; short week 53 stays bounded.
- Rollout/backout: dark contract/code publication only; amend before push; PR revert is complete
  backout because no state migration occurs.
- Observability: calculator warnings for invalid source windows; existing scheduler logs and
  demand row counts are the later runtime signals.
- Acceptance checks: exact commands in Draft A plus diff/wiring inspection, QCHECK, g-check, PR
  checks, merged-SHA identity, and post-merge focused tests.

### Dependencies

Existing Python/Jest/jsonschema/xlsx installations only. No new dependency.

### Validation

Use Draft A commands, three-run reliability, timezone matrix, secret-shaped ignore probes,
contract manifest recomputation, commit-message inspection, and GitHub PR/check inspection.

### Wiring verification

| Component | Entry point | Registration location | Schema/table |
|---|---|---|---|
| `crop_activity` | `DailyDemandCalculator.calculate_daily_demands` | `core/__init__.py` import | source-provided plot date fields |
| `irrigation_year` / `irrigation_week` | contract conformance and future administrative callers | `core/__init__.py`; JS exports | contract JSON |
| `irrigation_week_span` | shared vector conformance | Python/JS module exports | contract JSON |
| JavaScript mirror | ROS Jest conformance | existing `jest.config.js:testMatch` | contract JSON |
| Excel reversion | no calendar call remains | dormant unmounted upload route unchanged | no schema change |

### Cross-language schema verification

No DB migration. Current exact evidence:

- Smart CMS physical column: `water_planning.zone_planting_dates.planting_date`.
- API aggregate: `plantingDates` / `planting_dates`.
- ROS-GIS maps zone planting dates into section inputs and resolves expected harvest dates.
- BFF plot query already selects `planting_date` and `expected_harvest_date`.
- Existing legacy `calendar_week` / `calendar_year` writers remain unchanged.

### Decision-complete checklist

- [x] No open implementation decisions remain.
- [x] Every public name and result type is fixed.
- [x] Every behavior change has a defect-sensitive test.
- [x] Validation commands are service-scoped and specific.
- [x] Wiring table covers every changed component and explicit no-runtime JS exception.
- [x] Rollout/backout and no-migration boundary are explicit.

## Implementation (2026-07-30)

Implemented Draft A after the user confirmed that crop cycles are zone/source-driven rather than
derivable from a fixed rainy/dry calendar.

- Replaced the public `rid_*` / unbounded crop-week vocabulary with:
  - `irrigation_year(date) -> IrrigationYear`
  - `irrigation_week(date) -> IrrigationWeek`
  - `irrigation_week_span(IrrigationWeek) -> DateSpan`
  - `crop_activity(planting_date, expected_harvest_date, date) -> CropActivity`
- Defined irrigation year as 1 November through 31 October with the ending-year label. The
  canonical boundary witness is `2024-11-01 -> 2025 CE / 2568 BE, week 1`.
- Made CE and BE a paired identity with the invariant `be = ce + 543`; Python construction
  supports conversion from either era, and both language implementations reject mismatched
  pairs.
- Added bounded crop activity: before planting is `not_planted`, planting through expected
  harvest is `active`, and after harvest is `harvested`.
- Moved the crop-activity decision ahead of ROS, AquaCrop, AWD, and demand-row persistence in the
  BFF calculator. Active plots pass the source-derived crop week into ROS without fetching a
  second crop calendar.
- Reverted the speculative Excel consumer and Jest-alias changes to `origin/main` bytes and
  removed the vacuous workbook test.
- Left the existing legacy `calendar_week` / `calendar_year` calculation unchanged.

No new dependency, migration, endpoint, environment variable, queue payload, feature flag, or
runtime activation was added.

### TDD evidence

RED was recorded before implementation:

- Focused Python: `29 failed, 2 passed`; failures covered missing renamed contract files,
  `NotImplemented` domain operations, the old ROS signature, engine calls, and persistence.
- Focused Jest: failed with `ENOENT` for `irrigation-week.vectors.json`.

GREEN after implementation and final era-identity coverage:

- Focused Python: `33 passed`.
- Focused Jest: `50 passed`.
- The calculator tests use positive ROS and AquaCrop fixtures before planting and after expected
  harvest, and assert that neither engine, AWD, nor persistence is called.

### Validation evidence

- BFF bare suite: `280 passed, 8 skipped, 59 warnings`.
  - The eight skipped integration cases are pre-existing and environment-gated.
- BFF unit suite: `279 passed` on each of three consecutive runs.
- ROS Jest: `50 passed` on each of three consecutive runs.
- ROS contract timezone replay: `50 passed` under `Asia/Bangkok`, `UTC`,
  `America/Los_Angeles`, and `Pacific/Chatham`.
- Python Black check on the changed calendar modules/tests: passed.
- Targeted ROS ESLint on both changed JavaScript files: passed.
- Targeted Prettier on JavaScript, Markdown, and contract JSON: passed.
- `git diff --check`: passed.
- Exact combined diff from `origin/main` for `excelService.js` and `jest.config.js`: empty.
- Exact search found no deprecated public `rid_year`, `rid_week`, `RidWeek`, `ridWeek`,
  `crop_week_of`, or `cropWeekOf` name in the v1 contract/implementations/conformance tests.
- Exact search confirmed the existing legacy `date.isocalendar()` writers remain unchanged.

The service-wide `npm run lint` remains a repository baseline failure with `6,874 problems`
(`6,861 errors`, `13 warnings`) across existing generated/unformatted ROS files. No error occurs
in either changed JavaScript file, as proven by the targeted ESLint gate above.

## QCHECK and formal review (2026-07-31)

An independent read-only Terra QCHECK and the primary `g-check` review examined the exact staged
candidate against `origin/main`.

### Findings and dispositions

1. **MEDIUM — crop-activity schema did not enforce the state/week invariant.**
   - Before remediation, schema validation accepted `active + null` and inactive states with a
     positive crop week even though the contract prose prohibited both.
   - RED: three negative schema cases failed because no `ValidationError` was raised.
   - Fixed with conditional schema branches for active and inactive states; refreshed the
     per-file and contract-set hashes in both implementations.
   - GREEN: all three negative cases pass and the contract hash suites pass.
2. **MEDIUM — CE/BE conversion was public only in Python.**
   - The four calendar operations stay unchanged.
   - Fixed by exposing `IrrigationYear.fromCe` / `fromBe` constructors in JavaScript, mirroring
     Python `IrrigationYear.from_ce` / `from_be`, and documenting that result-type constructors
     are not extra calendar operations.
   - RED: the new JavaScript conversion test failed because `IrrigationYear` was undefined.
   - GREEN: both era constructors produce `{ce: 2025, be: 2568}` and the full Jest suite passes.
3. **MEDIUM — calculator-level invalid-window behavior lacked defect-sensitive coverage.**
   - Added missing/non-date and reversed-window cases with positive ROS/AquaCrop doubles.
   - Both prove fail-closed behavior before ROS, AquaCrop, AWD, and persistence.

No high-severity or remaining actionable findings were found. The primary function/test
checklists found the functions composable and low-complexity, the boundary expectations
independent and defect-sensitive, and the runtime gate wired at the correct outer-calculator
boundary.

### Post-remediation gates

- Focused Python contract/calculator suite: `38 passed`.
- BFF unit suite: `284 passed`.
- ROS Jest: `51 passed`.
- Targeted Black, ESLint, and Prettier: passed.
- Current contract-set hash:
  `987006c64402e79b9cb7af29358283f4cb368203cbd46935490a7ff453115539`.

## Hosted lifecycle (2026-07-31)

- Opened PR #144 from `feat/rid-calendar-v1` to `main`.
- The first hosted attempt marked all nine checks failed within two to eight seconds.
- GitHub job metadata shows `steps: []`, `runner_id: 0`, and no runner name for every sampled job.
- Both sampled check annotations state exactly:
  `The job was not started because your account is locked due to a billing issue.`
- Classification: GitHub account/billing infrastructure blocker, not a code-test failure.
- The user explicitly authorized an admin merge if possible. The merge decision therefore relies
  on the complete local gates, three-run reliability evidence, timezone replay, independent
  QCHECK, formal g-check, and exact staged-index audit recorded above.
