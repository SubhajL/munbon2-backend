# Coding Log — RID canonical week calendar (`rid-calendar` v1)

Started 2026-07-29. Base: `main` @ `f6584acc`.
Lifecycle: g2-planning (DREP) → g2-coding (inline; Claude implements, no delegate).

---

## Phase 0 — Repo profile

- Root `/Users/subhajlimanond/dev/munbon2-backend`, `main` @ `f6584acc`.
- Python gate (`services/bff-water-planning`):
  `source venv/bin/activate && CORS_ORIGINS='["http://localhost"]' python -m pytest tests/unit -q`
  — verified baseline **246 passed**. `pytest.ini`: `testpaths=tests`, `asyncio_mode=strict`.
  **No ruff/flake8 config exists** — there is no Python lint gate; do not invent one.
- JS gate (`services/ros`): `npx jest`. `node_modules` was absent; `npm ci` FAILS (lock
  out of sync), `npm install` succeeds only on retry with
  `--fetch-timeout=120000 --maxsockets=3`, and **mutates `package-lock.json`**
  (restored via `git checkout --`; verified clean).
  **`npx jest --listTests` returns ZERO tests** — the 3 files under `tests/` are `.ts`
  with no ts-jest/babel transform. The ros suite is vacuous today. A plain `.js` test
  in `tests/unit/` was smoke-tested and runs (probe deleted, tree clean).
- Ownership: repo `ours` · runtime `ours` · disposition `production`. No UI slice.
- MUST NOT list (root CLAUDE.md), the load-bearing ones here:
  no second copy of an existing algorithm; no silent hardcoded operational constants
  (fail closed and log); pure domain logic lives in `core/` free of I/O; no skipped or
  substitute tests; Conventional Commits; branch → PR → admin merge.

## Phase 1 — Exploration: four premises from the briefing were wrong

| Briefed premise | Verified truth | Evidence |
|---|---|---|
| `shared/nodejs` is real, 2 services use it | **False.** `auth`+`gis` declare `"@munbon/shared": "file:../../shared/nodejs"` but **zero source imports**. All three `shared/` dirs are decoration. | `rg -n "@munbon/shared" services/auth/src services/gis/src` → no hits |
| `shared/typescript-common` holds compiled output | **Untracked entirely** (0 files in `git ls-files`), only a stray local `dist/`. | `git ls-files shared/` → 28 files, all `nodejs/`+`python/` |
| There is no pipe for shared code | **A working pipe already exists**: repo-root `contracts/<family>/v<n>/` + SHA-256 manifest, consumed by `bff-water-planning` tests and mirrored by `scheduler`. Path-based → works from Node too (empirically verified). | `contracts/planning-depth-submissions/v1/`, `scheduler/src/schemas/machine_boundary.py:35` |
| BUG C = silent data loss under a DB UniqueConstraint | **The DB half is wrong.** `weekly_weather_adjustments` is unique on `(zone_id, adjustment_date)` — no collision. `WeeklyAdjustmentSummary` carries `UniqueConstraint('week_number','year')` but **has no writer**. The real live collision is the **Redis key** `weekly_adjustments:{date.year}:week_{isocalendar()[1]}`. | `weekly_adjustment_accumulator.py:238-240`; verified: 2025-01-02 and 2025-12-29 both → `weekly_adjustments:2025:week_1` |

Also: `shared/python/pyproject.toml` declares `readme = "README.md"` but **no README.md
exists** — a poetry build of it would fail. It is not merely unused, it is unbuildable.

## Phase 3 — Codex adversarial pass (`gpt-5.6-sol`, `xhigh`, read-only)

Verdict: **"reject in its current form."** It was right. Dispositions below; nothing dropped.

### ACCEPTED — findings that changed the plan's shape

| # | Finding | Disposition |
|---|---|---|
| 1.2 | **`calendar_week`/`calendar_year` are persisted shared upsert keys.** `gis.ros_water_demands` has `UNIQUE(parcel_id, calendar_week, calendar_year)`; `ros.weekly_water_levels` keys on the same pair. Reinterpreting them ISO→RID in one service mixes semantics against ISO-keyed rows. | **ACCEPTED — kills draft R10.** Verified: `daily_demand_calculator.py:176-177` feeds exactly this pair into `ros_client.get_weekly_water_level`, which reads `ros.weekly_water_levels`. Flipping it would query the wrong rows. **No wired ISO call site is flipped in this work.** Moved to gated S4 with a discriminator + backfill. |
| 1.1 | S2 fixes the BFF, but the **declared production producer is `ros-gis-integration`** (ADR D5), which boots its own sync loop and keeps ISO. | **ACCEPTED.** I found this independently. Consequence: scope is honestly renamed — this work is *not* repo-wide canonicalisation. |
| 1.3 | Replacing `.isocalendar()[1]` alone leaves `date.year` paired with a RID week; both must come atomically from one `RidWeek`. | **ACCEPTED** — and moot once no call site is flipped. The atomicity requirement is baked into `RidWeek` returning both. |
| 1.4 | Three **more** wired BFF week systems: `%V` + hardcoded 52-rollover (`feedback_manager.py:34`), `%Y-W%V` (`demand_aggregator.py:218`), `%Y-W%U` (`repository.py:119`). | **ACCEPTED, verified** (Codex's line numbers were off by 3–5; the sites are real). `%U` is a *sixth* week convention. Recorded, not fixed here. |
| 2.a | **Timezone boundary absent.** Call sites pass naive `datetime.now()`; the domain uses `Asia/Bangkok` explicitly. | **ACCEPTED.** `rid_calendar` is date-only and pure; the instant→civil-date conversion is named as the caller's job and excluded from the module. |
| 2.b | Week-53 cap is **mathematically bogus** — `offset//7+1` over `0..365` already tops out at 53; capping can only hide an anchor bug. | **ACCEPTED — my draft T5 RED-proof ("yields week 54") was simply false.** Replaced with range *validation*, not capping. |
| 2.c | No contract exposes week end/length, yet vectors assert `week_length_days`. | **ACCEPTED** — added `rid_week_span()` returning `(start, end)`. |
| 2.d | `RidWeek` is not self-validating; `RidWeek(2026, 99)` would be constructible. | **ACCEPTED** — `__post_init__` bounds check. |
| 2.e | `_date_only` raises `ValueError`, not `TypeError` — my "mirrors" claim was wrong. | **ACCEPTED** — module raises `TypeError` for wrong *type* and `ValueError` for out-of-range, and the false "mirrors" claim is dropped. |
| 3.a | **T9 was vacuous.** Its regex `\.isocalendar\(\)\[1\]` does not match the tuple-unpack at `planning_depth.py:118`, so the exemption I claimed was needed was unnecessary — proving the guard too narrow to be a semantic guard. Also `glob` vs `rglob`. | **ACCEPTED — T9 deleted outright.** A guard that cannot fail honestly is worse than none. |
| 3.b | T10 must hash **raw bytes** (`fs.readFileSync`), not `require()`'s parsed object; and shared finite vectors prove only sampled dates. | **ACCEPTED** — JS hashes raw bytes with the same CRLF normalisation; the "cannot drift" claim is downgraded to "cannot drift *on the pinned vectors*", which is what it actually proves. |
| 3.c | T1 doesn't pin `README.md` (inventory is `*.json` only), and it is self-consistency, not immutability. | **ACCEPTED** — manifest pins every file including `.md`, and **each implementation embeds `CONTRACT_SET_SHA256` as a source constant** so vectors+manifest can no longer be changed together silently. This is the repo's own idiom (`machine_boundary.py:35`). |
| 3.e / 5.d | T11 was unlandable: production calls `extractPlantingSchedule(paddySheet)` with **no year**, and the method calls `XLSX.utils.sheet_to_json(sheet)`, so a hand-built array fixture is wrong. `rosController:73` is `parseKcData`, not the planting path. | **ACCEPTED.** Redesigned: the anchor year is derived from the sheet's own `startDate` (already parsed, `fillDataSheet!D7`) and **fails closed** when absent — which also satisfies the repo MUST NOT on hardcoded operational constants. Fixture is a real `XLSX` worksheet built via `XLSX.utils.aoa_to_sheet`. |
| 4 | **Manifest ownership backwards** — T1/T10 trust the adjacent mutable manifest, so vectors+manifest change together stays green; slices aren't independently landable. | **ACCEPTED** — resolved by the embedded `CONTRACT_SET_SHA256` constant above. |
| 5.f | Repo-state claim stale: tree is dirty with user-owned coding-log artifacts and `services/ros/node_modules` now exists. | **ACCEPTED, noted.** Those are pre-existing untracked user files plus gitignored `node_modules`; no tracked file is modified by this work except as listed. |
| 6 | The non-goal is coherent **only** if `planning_depth` is named an explicit ISO compatibility island, and the plan stops claiming repo-wide RID canonicalisation. | **ACCEPTED** — see §1 Goal wording below. |

### REJECTED / DOWNGRADED

| # | Finding | Disposition |
|---|---|---|
| 1.5, 1.6, 1.8 | ~15 further ROS/scheduler/water-simulation/smartfarm week sites; ROS's 168-hour "full week" assumption breaks for a 1–2 day week 53. | **ACCEPTED AS TRUE, REJECTED AS SCOPE.** All real. Fixing them is a multi-service cutover, not this work. They are recorded verbatim in the Deferred Register below. **Since no ISO site is flipped here, none of them break.** The 168-hour conflict becomes live only at S4. |
| 5.c | Jest package-boundary concern. | Codex agrees with my empirical probe: it works. Both verified independently. |
| 5.e | "No orphans / independently landable: false." | **PARTIALLY REJECTED.** True of the draft. In the revised plan every new module has a real runtime caller (see §7) and each slice is landable alone because none changes a shared key. |

---

## Revised plan (what is actually being built)

**Goal.** Publish the RID irrigation calendar once as language-neutral pinned data, and
implement it once per language against those exact bytes, so the two implementations
cannot drift on the pinned vectors. Wire each implementation into a call site where RID
semantics are *already* the intent and no shared persisted key changes meaning.

**This is explicitly NOT repo-wide canonicalisation.** After this work the repo still has
multiple week systems; what it gains is one *authoritative, executable* definition of the
RID calendar plus two conforming implementations — the prerequisite for any later cutover.

**Non-Goals** (each with its reason):
1. **No wired ISO call site is flipped.** `calendar_week`/`calendar_year` are shared
   persisted upsert keys (`gis.ros_water_demands`, `ros.weekly_water_levels`);
   reinterpreting them in one service is silent data corruption. → gated S4.
2. `schemas/planning_depth.py` and the `week_key` wire format are untouched — an explicit
   **ISO compatibility island** pinned by a DB CHECK, a published contract, and two dark
   FE PRs (#22/#23).
3. No `shared/python` / `shared/typescript-common` revival (dead; and `shared/python` is
   unbuildable). Per-service Docker builds use the *service dir* as context
   (`COPY requirements.txt .`), so a `-e ../../shared/python` requirement would break the
   image — verified, this is why code-sharing-by-path is not the mechanism.
4. `services/scheduler`, `ros-gis-integration`, `water-simulation`, `smartfarm` untouched.

### Slices (all owner **Claude**, inline — user specified "g2 inline dev lifecycles")

| ID | Scope | Oracle | Risk |
|----|-------|--------|------|
| S1 | `contracts/rid-calendar/v1/` — 2 schemas, 2 vector sets, README, manifest pinning **every** file | manifest self-pin test | inert data, zero runtime risk |
| S2 | `bff-water-planning/src/core/rid_calendar.py` + `core/__init__.py` re-export + vector & property tests; wired by fixing the pre-planting crop-week bug (`daily_demand_calculator.py:166`) | vector conformance + properties + full suite ≥246 | local, no shared key touched |
| S3 | `ros/src/utils/rid-calendar.js` + jest conformance vs the **same bytes**; wired by replacing the hardcoded `new Date(2024,10,1)` with the sheet's own start date, failing closed | jest vs shared vectors + embedded set hash | local, RID-native path |

### Deferred Register (verified real, NOT fixed here)

- `bff-water-planning`: `%V`+52-rollover `feedback_manager.py:34`; `%Y-W%V`
  `demand_aggregator.py:218`; `%Y-W%U` `repository.py:119`; ISO pairs at
  `ros_sync_service.py:29,180,196`, `integration_client.py:490`,
  `query_optimizer.py:223`, `daily_demand_calculator.py:176,195`.
- `ros-gis-integration` (**the ADR-D5 canonical producer**): same six sites.
- `scheduler`: Redis key collision `weekly_adjustment_accumulator.py:238-240`;
  Monday/January spans `schedule_optimizer.py:182`.
- `ros`: `dayjs .week()` `crop-week-calculator.js:40`; ISO Mon–Sun aggregation +
  **168-hour full-week assumption** `water-level-aggregation.service.js:14,87`;
  `isoWeek()`/SQL `EXTRACT(WEEK)` `weekly-update-scheduler.service.js:50` (started at
  runtime, `index.js:90`); `land-preparation.service.js:136`; `weekly-eto.service.js:33`.
- `water-simulation` `demand_simulator.py:81`; `smartfarm` `waterPlanningService.js:42`.

### Open decisions for the user
1. **RID year label** = anchor year (2026-11-01 → RID **2026**) vs ending year (→ 2027).
   Adopted: **anchor**. Isolated to one constant + the vectors; cheap to flip now.
2. **S4 cutover** — discriminator column + backfill + `week_key` → `YYYY-Rww`, before the
   dark FE PRs go live. Not executed; needs sequencing.


---

## Phase 2 — implementation (all Claude, inline; no delegate)

**Stop line: none — Q0 fired.** The user specified "g2 inline dev lifecycles", and Q1
would have fired independently ("timezone/calendar" is a named hard-part trigger).
Per Phase 2c-ter the full TDD ordering still applied with no delegate to enforce it.

Every unit was RED-proven before implementation:

| Unit | RED evidence (the right reason) |
|---|---|
| `core/rid_calendar.py` | `ModuleNotFoundError: No module named 'core.rid_calendar'` |
| crop-week wiring | `assert 100.0 == 0` — an *unplanted* plot was billed 100 m³ at week-1 demand |
| `ros/src/utils/rid-calendar.js` | `Cannot find module '../../src/utils/rid-calendar'` |
| `excelService` anchor | `Expected "2026-11-01", Received "2024-10-31"` — the hardcode |

One harness repair was needed before the excelService RED was honest: `excelService`
transitively loads a logger via `@config/index`, and `module-alias` registers only in
`src/index.js`. Added `moduleNameMapper` to `jest.config.js` mirroring `_moduleAliases`.
A "cannot resolve" failure is a broken harness, not RED.

### Mutation evidence (Phase 2c-bis)

The manifest-pinning tests went from a collection error straight to green, so they never
had an individual RED. All were mutation-verified; each killed the intended test:

| Mutation | Result |
|---|---|
| Append one byte to `README.md` | manifest test fails — **prose is genuinely pinned** |
| Corrupt `CONTRACT_SET_SHA256` (py) | pin test fails |
| Add an unlisted file to the contract dir | completeness fails |
| Revert crop-week fix to `max(1, …)` | crop-week test fails |
| Corrupt `CONTRACT_SET_SHA256` (js) | 2 tests fail incl. the cross-language pin |
| Remove the week-53 clamp (js) | 16 tests fail |
| Restore the 2024 hardcode (js) | 5 tests fail |
| Revert plantingDate to UTC midnight | TZ regression test fails under `TZ=Asia/Bangkok` |

### Evidence beyond the pinned vectors

- **Exhaustive cross-language differential:** Python and JS produce identical week key
  AND week span for **all 25,933 dates** from 1990-01-01 to 2060-12-31. Codex
  independently ran the same comparison across **182,987** dates and also found
  agreement — two witnesses, disjoint tooling.
- **Hash equivalence:** the JS binary round-trip is byte-identical to Python's CRLF
  replacement on Thai UTF-8, CRLF, and arbitrary high bytes (0xff 0xfe).
- **Canonicalisation equivalence:** JS and Python emit the same 702-byte canonical
  record string and the same set hash.
- **Timezone matrix:** 79 JS tests green under Asia/Bangkok, UTC, America/Los_Angeles,
  Pacific/Kiritimati, and Pacific/Chatham (+12:45).

## Phase 5 — QCHECK

- **Tier 1** — `g2-check` on the staged tree (`/code-review` unavailable in this
  environment; the skill's documented substitute). Reviewer: Claude (implementer) —
  independence is imperfect here and is recorded as such; Tier 2 carried the
  independent load.
- **Tier 2** — Codex `gpt-5.6-sol`, `model_reasoning_effort=xhigh`, read-only.
  **Mandatory**: three triggers fired (domain math, shared contract, data model).

### Tier 1 finding (Claude)

**HIGH — `plantingDate` timezone regression, self-inflicted.** I changed
`extractPlantingSchedule` to emit UTC-midnight `Date`s, but
`calculationService.calculateDaysSincePlanting` (`services/ros/src/services/calculationService.js:158-161`)
subtracts raw epoch ms. In Asia/Bangkok a UTC-midnight value sits 7h later than local
midnight, so `Math.floor(diff/86400000)` drops by one for any run between 00:00 and
07:00 local — an off-by-one crop week on early-morning runs.
**Fixed**: emit local-midnight `Date`s (exactly the prior semantics; only the year was
ever wrong). Regression test added, and it pins `getHours() === 0` TZ-independently.
While fixing, a second-order fact surfaced: raw epoch-ms arithmetic is also DST-fragile
late in the local day. That is pre-existing `calculationService` behaviour, Thailand
observes no DST, and the test now samples early in the day and says so.

### Tier 2 findings (Codex) — all verified against the repo before disposition

| # | Finding | Verified? | Disposition |
|---|---|---|---|
| HIGH-1 | The validated workbook `คบ.มูลบน_ROS_ฤดูฝน(2568).xlsm` has no `fill_data!D7`, so requiring an in-workbook start date hard-fails known-good input | **CONFIRMED, and worse** — D5 is undefined too. (`2568` BE = **2025** CE, so the old 2024 anchor was wrong by a year for this very file.) | **FIXED** — `parseROSExcelFile(buffer, ridYear)`: an explicit season wins, D7 is a fallback, throws only when neither exists. Test replays the real workbook. |
| HIGH-2 | Date cells arrive as numeric Excel serials; `resolveRidYear` accepted only Date/string, so real workbooks would fail | **CONFIRMED** — SheetJS default `cellDates:false`. My fixture only wrote strings: a fake encoding a wrong interface assumption. | **FIXED** — `toCivilDate` handles Date / numeric serial (`XLSX.SSF.parse_date_code`) / string. Test asserts the fixture cell really is type `'n'`. |
| HIGH-3 | `!services/ros/tests/**` re-included secret-shaped files after the credential rules | **CONFIRMED** — `private.key`, `credentials`, `*.pem`, `*.key`, `*.sql`, `config.local.js` all became trackable, in a repo with committed-credential history | **FIXED** — credential guards re-asserted after the negation, mirroring the scheduler block at `.gitignore:358`. Verified both directions: secrets ignored, real tests still trackable. |
| MEDIUM | The `CONTRACT_SET_SHA256` tests are adoption declarations, not behavioural pins; JS never recomputed the set hash | **CONFIRMED** | **FIXED** — JS now recomputes the set hash from records (verified byte-identical to Python: same 702-byte canonical string); the declaration test is relabelled as such in its own docstring. |
| MEDIUM | The broad negation also makes future `*.test.ts` trackable while Jest has no TS transformer | Confirmed | **ACCEPTED, not fixed** — the existing tracked dead `.ts` tests predate this change. Recorded in the Deferred Register. |
| LOW | No century/boundary coverage | Confirmed | **FIXED** — RID 1900 / 2099 / 2100 (non-leap century) / 2399, plus range enforcement at both ends. |

**Codex's verified no-finding areas:** calendar math correct across all supported dates;
byte-identical hashing incl. Thai UTF-8; the pre-planting return shape does not break its
caller (`reason` is discarded before persistence); `moduleNameMapper` is Jest-only; no
prohibited ISO call site or planning-depth island was touched.

### HIGH-1 residual — recorded, not silently dropped

Codex recommended rejecting unsupported workbooks *before enqueue*. I did **not** change
`rosController`/`queueService`, because both are **non-loadable**: `mongoose` and `bull`
are required by 7 files under `services/ros/src/` but declared in **no manifest** and not
installed (`queueService.js` → `Cannot find module 'bull'`; `rosController.js` →
`Cannot find module 'mongoose'`). `excelService.js` itself loads fine, so the new code is
not orphaned — but its two callers cannot currently execute. I wrote a controller
validation test, found it unrunnable for this reason, and **deleted it rather than ship an
untestable change**. Adding the caller-side `ridYear` plumbing belongs with the PR that
fixes those undeclared dependencies.

## Phase 4 — gates (Claude ran each itself)

- Python: **280 passed**, 3× consecutive, stable (baseline was 246).
- JS: **79 passed**, 3× consecutive, and green across 5 timezones.
- Wiring: `crop_week_of` imported at `daily_demand_calculator.py:12`, called `:165`,
  reachable from `main.py:19` (scheduler) and `main.py:132` (route). `ridWeekStart`/
  `ridWeekOf` imported at `excelService.js:40`, called in `extractPlantingSchedule`
  and `resolveRidYear`. Non-test import **and** runtime call site for both — no orphans.
- Lint: **no Python lint gate exists** in this service (verified in Phase 0 — no ruff/
  flake8 config); none was invented. JS: the new `rid-calendar.js` is **0 problems**;
  `excelService.js` went 279 → ~310 because the added block matches the file's 4-space
  transpiled indentation rather than the config's 2-space rule. `npm run lint` was
  **already failing repo-wide** (6,844 pre-existing errors), so this is reported, not
  claimed green.

## Deferred Register additions

- `services/ros`: `mongoose` and `bull` required by 7 src files, declared nowhere,
  not installed → `rosController` and `queueService` cannot load. The Excel upload
  path is structurally dead until fixed.
- `services/ros`: `calculationService.calculateDaysSincePlanting` uses raw epoch-ms
  subtraction and is DST-fragile (harmless in Thailand, which has no DST).
- `services/ros`: the tracked `tests/**/*.ts` files cannot run — no TS transformer.


## Phase 5 — QCHECK round 2 (Codex `gpt-5.6-sol` xhigh, re-run of the raising tier)

Round 2 found four more. All verified against the repo before disposition.

| # | Finding | Verified? | Disposition |
|---|---|---|---|
| R2-1 | **My round-1 real-workbook test was VACUOUS.** `paddy_rain` has ref `B1:AJ82`, so the parser's A-origin column indexes (F=5, G=6) read the wrong cells — the week sits at index 4, the area at 5. The workbook yields **zero** planting rows, so my `forEach` asserted nothing. | **CONFIRMED** — measured 0 rows parsed; row 2 is `[null,null,null,null,1,9820,…]` | **FIXED** — the workbook test now asserts only what it proves (it *parses*), and a separate test **pins the zero-row gap explicitly** as a pre-existing defect with the reason. Fixing the indexes needs ground truth on the workbook family → own PR. |
| R2-2 | 1904-epoch (Mac) workbooks: `XLSX.SSF.parse_date_code` without `date1904` silently shifts the season **four years** | **CONFIRMED** — serial 46327 reads as 2026-11-01 under 1900 and 2030-11-02 under 1904 | **FIXED** — the workbook's `WBProps.date1904` is threaded into `toCivilDate`. Tested at the **decode level**: SheetJS's writer does not re-base serials when `WBProps` is set post-hoc, so a round-tripped "1904 workbook" fixture is internally inconsistent and would prove nothing. Mutation-verified. |
| R2-3 | Credential guards still bypassable: `services/ros/.gitignore`'s `!tests/**/*.test.js` is deeper than the root guards, so `.env.test.js` / `credentials.test.js` / `private.key.test.js` were trackable | **CONFIRMED** — all three were trackable | **FIXED** — guards re-asserted inside the service-level file after the negation. Verified: 6 secret-shaped paths ignored, both real tests still trackable. |
| R2-4 | JS lacked the century/boundary coverage Python gained | Confirmed | **FIXED** — RID 1900/2099/2100/2399 + range enforcement mirrored in JS. |
| R2-5 | My log said `bull` is "declared in no manifest" — inaccurate repo-wide | Correct, my wording was sloppy | **CORRECTED**: neither is in **`services/ros`'s** manifest; other services do declare `bull`. Also noted: `ros.routes` is not mounted (`index.js:58`), so the upload path is doubly dormant. |

**A near-miss worth recording.** After the round-2 edits I read `Tests: 70 passed` as green.
It was not: a splice error left an extra brace, `excel-planting-schedule.test.js` **failed to
parse, and its whole suite silently did not run**. Only checking `Test Suites:` — not the test
count — exposed it. This is exactly the false-negative pattern `g2-qcheck` warns about, and it
came from filtering the jest output on `✕`, which a suite-level failure never emits.

## Final gates

- Python **280 passed** ×3 (baseline 246).
- JS **86 passed, 2 suites** ×4 timezones (Asia/Bangkok, UTC, America/Los_Angeles,
  Pacific/Chatham +12:45).
- Every mutation applied to the new code killed its intended test.
- Zero open CRITICAL/HIGH.

## Attribution

All code, tests, contracts, and prose authored by **Claude, inline** — no delegate
(user specified "g2 inline dev lifecycles"; Q0/Q1 both applied). Reviewers: Tier 1
`g2-check` (Claude — imperfect independence, recorded), Tier 2 Codex `gpt-5.6-sol`
at `xhigh` across **two rounds**. Fix rounds: 2. Delegate token cost: none.

## Review (2026-07-30 11:12:03 +0700) - commit 8c2c3570

### Reviewed
- Repo: `/Users/subhajlimanond/dev/munbon2-backend`
- Branch: `feat/rid-calendar-v1`
- Scope: `8c2c3570d2c66470ba186a0945b666c5f479f39b`
- Base: `f6584acca6ab5fb4f8f5560f0cb07bb9c38d14b2`
- Commands Run: `git status --short --branch`; targeted `git show`; exact-identifier `rg`; workbook inspection with SheetJS; BFF unit suite; ROS Jest suite

### Findings
CRITICAL
- None.

HIGH
- The public crop-week rule contradicts the settled bounded-season domain model and can continue pricing a crop after harvest. `crop_week_of` explicitly returns unbounded values (`services/bff-water-planning/src/core/rid_calendar.py:104-115`), and its property test requires week 61 (`tests/unit/test_rid_calendar_properties.py:123-125`). The live daily scheduler starts from `main.py:58-60`; `_get_active_plots` selects `expected_harvest_date` but filters only `status = 'active'` (`daily_demand_calculator.py:548-578`); every date after planting is then sent to ROS (`:163-211`). Fix direction: make the public crop-activity operation return inactive outside the agreed inclusive season/harvest window, or keep a separately named raw elapsed-week helper and require the live demand path to apply the bounded operation. Add boundary tests for the day before planting, planting day, harvest day, and day after harvest, including proof that ROS is not called outside the window.
- The claimed pre-planting no-billing fix is not end-to-end. `_calculate_ros_demand` returns zero before planting (`daily_demand_calculator.py:163-173`), but `calculate_daily_demands` still loads AquaCrop and combines it (`:83-94`). The default `aquacrop_priority` policy selects any positive AquaCrop row (`:294-303`) and persists the resulting demand. The new test calls only the private ROS method (`tests/unit/test_daily_demand_crop_week.py:62-74`), so it cannot detect this. Fix direction: establish crop activity once before invoking either engine, then suppress both engines and persistence of positive demand outside the crop window. Add a calculator-level test with a positive pre-plant AquaCrop result and assert final demand is zero and neither pricing path runs.
- Contract v1 publishes unresolved and user-contradicted domain identity. The agreed vocabulary is `irrigation_week(date) -> (irrigation_year, 1..53)`, but schemas and APIs publish `rid_year`/`rid_week`, `RidWeek`, and `rid_week_of` (`contracts/rid-calendar/v1/rid-week.schema.json:19-35`; `rid_calendar.py:45-101`; `rid-calendar.js:81-126`). The README also makes the unconfirmed anchor-year convention authoritative (`README.md:16-17`) without a first-class BE/CE type or `season(date)` operation. This is cheap to correct while unpushed and expensive after publishing a versioned contract. Fix direction: settle the year-label example and era boundary, rename the public API and vectors to the agreed vocabulary, add the missing agreed operations/types, regenerate the manifest, and rerun both conformance suites before push.

MEDIUM
- The ROS Excel change has a dormant but deterministic caller break. `parseROSExcelFile(buffer, ridYear)` requires an explicit year for the validated workbook because it has no `fill_data!D7` (`excelService.js:177-212`; `excel-planting-schedule.test.js:190-203`), while `queueService.js:101-109` still calls it with only the buffer and the checked-in declaration still exposes a one-argument method (`excelService.d.ts:33-41`). The HTTP upload path is currently not mounted and its queue/controller dependencies do not load, so this is not a live production regression today; it will fail immediately when that path is repaired. Either remove/defer the Excel wiring from this PR, or carry a typed season through request, queue payload, processor, and declaration with an integration test.
- The ISO compatibility conclusion is directionally correct, but “ISO-keyed and enforced by UNIQUE” is too strong. Existing call sites pair an ISO week number with civil `date.year` (`daily_demand_calculator.py:180-185`), and ROS SQL similarly pairs `EXTRACT(WEEK)` with `EXTRACT(YEAR)` (`weekly-update-scheduler.service.js:151-169`). The uniqueness constraints enforce tuple uniqueness, not calendar semantics. Keep the no-cutover decision, but describe the columns as legacy calendar keys whose historical semantics must be profiled before adding a discriminator/backfill.

LOW
- The commit message includes a `Co-Authored-By: Claude Opus` trailer, which violates repository rule GH-2. Remove it when amending the unpushed commit.
- The schema `minItems` floors do not guarantee that the load-bearing boundary witnesses remain present. Add explicit contract-integrity assertions for named dates around 1 November, leap day, week 53, and supported-range edges rather than relying only on counts.

### Open Questions / Assumptions
- Confirm with one explicit example whether the irrigation year containing `2024-11-01` is labelled 2024 or 2025, and whether Thai display year is a typed BE conversion rather than an interchangeable integer.
- Confirm the exact four-function API and the inclusive/exclusive rule for `season(date)` and crop-window end.
- Confirm whether crop activity ends at the crop's expected harvest date, the configured season end, or the earlier of the two.
- The validated rainy-season 2568 workbook contains no D7 and currently yields zero planting rows; its real planting-week semantics are not evidence for either year-label convention until the workbook-family mapping is established.

### Recommended Tests / Validation
- Add end-to-end BFF calculator tests for positive AquaCrop data before planting and after harvest.
- Add Python and JavaScript contract vectors for the agreed irrigation vocabulary, season identity, BE/CE conversion, and both crop-window bounds.
- Add request-to-queue-to-parser coverage if the ROS Excel wiring remains in this PR.
- Re-run the BFF unit suite and ROS Jest suite in the timezone matrix after regenerating contract hashes.
- Current verification: BFF `280 passed`; ROS `86 passed, 2 suites`. Mutation claims were reviewed in the log but were not independently replayed in this review.

### Rollout Notes
- Do not push or open the PR until the public vocabulary, year label, era typing, and crop-window semantics are settled.
- Keep existing `calendar_week`/`calendar_year` and planning-depth `YYYY-Www` consumers unchanged in this slice; future migration needs a discriminator, historical data audit, and backfill.
- The `contracts/` plus per-language runtime mirror approach is reasonable here because service Docker contexts are isolated and the shared package directories are unused/unbuildable. It provides test-time conformance, not a runtime cross-image version handshake.
