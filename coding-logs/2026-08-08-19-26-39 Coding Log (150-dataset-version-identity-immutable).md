# Coding Log: #150 — make ros_gis.dataset_versions identity immutable

Date: 2026-08-08
Issue: GitHub #150 — "Make ros_gis.dataset_versions.source_hash immutable
(planning-depth provenance drift)"
Repository: `/Users/subhajlimanond/dev/munbon2-backend`  (worktree: `-issue150`)
Base: origin/main @ 6a2510cf
Skill: g2-coding (TDD orchestrator)

## Problem (from the issue)

R0 (PR #149) binds roster provenance `(roster_dataset_version_id,
roster_source_hash)` onto each immutable planning-depth submission. But
`ros_gis.dataset_versions.source_hash` is DB-mutable: only the *history* tables
(`section_master_history`, `gate_mapping_history`) carry immutability triggers
from `0001_dataset_version_parent`; the parent `dataset_versions` row does not.
So a stored provenance pair can drift to identify no row — silently invalidating
the audit identity R0 exists to guarantee. Latent today (no code updates
`source_hash`); nothing enforces the invariant.

## Exit gate (from the issue)

- A ROS migration on `ros_gis.dataset_versions` makes its identity immutable
  (reject UPDATE of `source_hash`, and of `dataset_version_id` / `dataset_kind`).
- A real-Postgres test proving a stored provenance pair cannot be orphaned by an
  ROS update.
- Must be resolved OR formally accepted before the real nine-stage OrbStack run.

## Chosen option: A (immutability trigger), not B (cross-service FK)

Option B (composite unique key + `ON UPDATE RESTRICT` FK from the BFF
`planning_depth_submissions`) requires cross-database migration ordering (ros_gis
must exist before the BFF FK) and a cross-service coordination the issue itself
flags as heavier. Option A is self-contained in ros-gis-integration, mirrors the
existing `reject_immutable_dataset_row_change()` precedent, and fully closes the
UPDATE-orphaning hole. Chosen: A.

## Stop-line decision (g2-coding Q0-Q3)

**Q0 FIRES → do not delegate; Claude implements the whole slice.**
Trigger: this is a database migration / irreversible schema change (an explicit
never-delegate item). No pi/DeepSeek brief, no shim, no diff-audit-of-delegate.
Strict TDD still applies in full (Phase 2c-ter): per behaviour, test -> RED ->
implement -> GREEN. Where a real RED is available (behaviour absent on a DB with
only 0001 applied) it is used; the integration test is RED-proven, not merely
mutation-checked.

## Design (the two subtleties that shape the trigger)

1. **`dataset_versions` is only PARTIALLY immutable under UPDATE.** Unlike the
   history tables, its rows legitimately mutate: `status` transitions draft ->
   active -> superseded and `effective_from/effective_to` are set at activation.
   So the history tables' *blanket* `BEFORE UPDATE OR DELETE` unconditional raise
   would be WRONG here — it would block activation. The trigger uses the same
   `BEFORE UPDATE OR DELETE` event but treats the ops differently: DELETE is
   rejected unconditionally (append-only — see below), while UPDATE is
   **column-selective**, rejected only when an identity column actually changes
   (`source_hash`, `dataset_kind`, `dataset_version_id`), via `IS DISTINCT FROM`.

2. **The `SET col = DEFAULT` hole on the identity PK.** `dataset_version_id` is
   `GENERATED ALWAYS AS IDENTITY`. Postgres already rejects `UPDATE ... SET
   dataset_version_id = <explicit>` natively, BUT it PERMITS `UPDATE ... SET
   dataset_version_id = DEFAULT`, which assigns a fresh sequence value and would
   orphan the provenance pair. So the trigger's `dataset_version_id` branch is
   non-vacuous: it is the only guard against the DEFAULT reassignment. (Verified
   empirically on real Postgres — see Phase 2.)

## DELETE is blocked too (corrected after QCHECK round 1)

My first cut treated DELETE as out of scope, reasoning that a referenced roster
version has `section_master_history` children whose FK
(`dataset_versions(dataset_version_id, dataset_kind)`) plus their own
DELETE-immutability make the parent undeletable. **Both QCHECK tiers independently
falsified that**: the schema does not require an active `section_master` version
to have any child rows, so a CHILDLESS active version — which a stored provenance
pair can still point at — has no FK protection and was deletable. Verified
empirically (`DELETE 1`, pair -> 0 rows). Since the issue's real invariant is that
the provenance pair cannot orphan, and orphaning-by-DELETE is a real vector, the
trigger now rejects DELETE outright (`BEFORE UPDATE OR DELETE`, append-only),
matching 0001's history-table precedent. No ros_gis code deletes these rows
(grep-clean), so nothing legitimate breaks.

**TRUNCATE too (corrected after QCHECK round 2).** I first left TRUNCATE
unguarded (matching 0001's precedent), but both round-2 tiers flagged that a
row-level trigger never fires on TRUNCATE, so `TRUNCATE ... CASCADE` would wipe
the whole ledger and orphan every pair — contradicting the migration's own
"append-only" claim. Since the migration *claims* append-only, it must *enforce*
it: a statement-level `BEFORE TRUNCATE` trigger (sharing the same function via
`TG_OP <> 'UPDATE'`) now rejects it. Verified by real-Postgres test +
mutation.

**created_at made immutable (added in round 2).** Round 2 also caught that the
UPDATE guard left `created_at` mutable, so the creation timestamp of a
published/superseded version could be forged — undermining the same audit
integrity. 0001 freezes `created_at` on the history tables; 0004 now freezes it
on the parent too. This extends beyond the exit gate's literal identity trio,
deliberately, because a mutable creation timestamp defeats the append-only claim.

**Out-of-order rollback → follow-up #155.** Round 2's fourth finding — that
rolling back 0001 before 0004 (which the runner permits) can silently drop 0004's
protection on reapply — is a `migrate.py` *runner* limitation affecting every
migration, not a defect in this trigger. 0004's `down` is guarded against a
missing table (partial mitigation); the root fix (fail-closed reverse-order
rollback) is filed as #155, matching how #150 itself was filed as an R0 follow-up.

## Phase 2 — acceptance tests authored + RED proven (real behaviour, not harness)

Tests (Claude-authored contract; nothing delegated — Q0):
- `tests/unit/test_dataset_version_immutability.py` — SQL-shape regression guards.
- `tests/integration/test_dataset_version_immutability_postgres.py` — the
  load-bearing real-Postgres proof (gated on `DATASET_VERSION_TEST_POSTGRES_URL`).

RED was proven against a disposable postgis DB with a NO-OP `0004` placeholder
(so migrations apply but add no trigger — the acceptance tests stay byte-identical
from RED through GREEN):

- unit: 3 failed / 3 passed — the trigger-content assertions fail (absent); the
  file-exists/tracked + no-harm guards pass.
- integration: 4 failed / 2 passed — `source_hash` update, `dataset_kind` update,
  `SET dataset_version_id=DEFAULT`, and the orphaning capstone all "DID NOT RAISE"
  (behaviour absent); the native GENERATED-ALWAYS explicit-value rejection and the
  activation (status/effective) update pass in both RED and GREEN.

Empirical confirmation from RED: `UPDATE ... SET dataset_version_id = DEFAULT`
succeeded without the trigger (reassigning the id), proving the trigger's
`dataset_version_id` branch is non-vacuous and that the DEFAULT reassignment is a
genuine orphaning vector — not a hypothetical.

## Phase 3-4 — implementation + verification (all gates GREEN, Claude's own hand)

Implemented `migrations/0004_dataset_version_identity_immutable.{up,down}.sql`:
a column-selective `BEFORE UPDATE` trigger `dataset_versions_identity_is_immutable`
backed by `ros_gis.reject_dataset_version_identity_change()`, which RAISEs only
when `dataset_version_id`, `dataset_kind`, or `source_hash` `IS DISTINCT FROM` its
OLD value. Down drops the trigger then the function; nothing else.

- GREEN: unit 6/6 + integration 6/6 = 12 passed.
- Full ros-gis suite: 223 passed, 3 skipped (other integration tests lacking their
  env vars) — no regressions.
- ruff (system, courtesy; not a repo-configured gate here — service gate is pytest)
  `--select F`: all checks passed.
- Down migration verified against real Postgres via the runner:
  `status` (0001+0004 applied) -> `rollback 0004` (trigger gone) -> `apply 0004`
  (trigger restored). The down SQL genuinely executes and is reversible.
- 3x flakiness: 12 passed x3, deterministic.

Wiring (Phase 4b equivalent for a pure-DDL migration): there is no import/call
site; the "wiring" is discovery by the tracked migrate.py runner. Proven live —
`migrate.py status/rollback/apply` finds and drives `0004` by filename, and the
gitignore allowlist (`!*.up.sql`/`!*.down.sql`) keeps both files tracked.

Diff audit (self): change set is exactly 2 new migration SQL files + 2 new test
files. No product code, models, or existing migrations touched; acceptance tests
authored by Claude (no delegate — Q0). No fabricated/mocked data; the proof runs
against real Postgres.

## QCHECK (g2-qcheck) — loop-until-dry

Implementer: Claude, solo (Q0 fired — migration = never-delegate). Tier 2 must be
an independent model family; Codex `gpt-5.6-sol` @ xhigh (read-only) was smoke-
tested live (not assumed quota-blocked) and used each round.

### Round 1 — contract-correctness framing
- Tier 1 `/code-review high` (workflow, multi-agent Claude): 4 CONFIRMED, 0 refuted.
- Tier 2 Codex `gpt-5.6-sol` @ xhigh: 0 CRITICAL/HIGH; 2 MEDIUM + 2 LOW.

| Finding | Tier(s) | Disposition |
|---|---|---|
| DELETE orphans a childless active version | BOTH | FIXED — trigger now `BEFORE UPDATE OR DELETE` (append-only); test + mutation-verified |
| `\nUPDATE` ddl-guard misses indented statements | T1 | FIXED — anchored `(?im)^\s*` regex |
| dead `SCHEMA_MIGRATIONS` branch weakened the down-guard | T1 | FIXED — simplified to `"DELETE FROM" not in upper` |
| per-test reconnect/re-apply | T1 | FIXED — module `_schema_applied` flag |
| activation test omits active→superseded / non-null effective_to | T2 | FIXED — full lifecycle test |
| tracking asserted only via check-ignore, not tracking | T2 | FIXED — `git ls-files --error-unmatch` |
| integration test skips-open without the URL | T2 | ACKNOWLEDGED — matches the repo's per-feature integration env-var convention; local run is the evidence |

### Round 2 — adversarial framing (on the round-1 remediated tree)
- Tier 1 `/code-review high` round 2: 4 CONFIRMED, 2 REFUTED.
- Tier 2 Codex round 2: nothing above LOW; 1 LOW.

Pre-emptive repo probes to settle findings (grep-it-first): bulk UPDATE, writable
CTE, `UPDATE ... FROM`, `INSERT ... ON CONFLICT DO UPDATE`, MERGE — all traverse
the per-row trigger and are rejected; a plain INSERT of a new row is allowed and
cannot collide (GENERATED-ALWAYS unique PK).

| Finding | Tier(s) | Disposition |
|---|---|---|
| TRUNCATE bypasses the row trigger; ledger wipeable | T1 (T2 noted) | FIXED — statement-level `BEFORE TRUNCATE` guard; test + mutation-verified |
| created_at left mutable (timestamp forgery) | T1 | FIXED — created_at added to the immutable guard; test + mutation-verified |
| down never exercised against real Postgres | T1 | FIXED — committed apply→rollback→reapply integration test |
| out-of-order rollback silently drops protection | T1 + T2(LOW) | MEDIUM → follow-up #155 (runner-level, out of trigger scope); 0004 down guarded against a missing table as partial mitigation |
| 2nd env var / bespoke rejection harness | T1 | REFUTED — matches the repo's per-file pattern (`WATER_REQUIREMENT_TEST_POSTGRES_URL`, `POSTGRES_DSN_TEST_URL`) |
| `_schema_applied` reimplements a session fixture | T1 | REFUTED — pytest-asyncio 0.21 session-scoped async fixtures are the known event-loop footgun; the module flag is the safe choice |

Each REFUTED finding cites the file/line that makes it wrong (per g2-qcheck: reject
with the same evidence bar as accept).

Gates re-run green after every round: unit+integration 19 passed, full ros-gis
suite 230 passed / 3 skipped, 3× deterministic, ruff (F) clean. New-behaviour
tests (DELETE, TRUNCATE, created_at) are RED-proven or mutation-verified non-vacuous.

### Round 3 — merged-artifact / cross-file-coherence framing
- Tier 1 `/code-review high` round 3: 2 CONFIRMED correctness + 1 PLAUSIBLE cleanup, 0 refuted.
- Tier 2 Codex round 3: nothing above LOW except the already-filed #155; every
  cross-file check passed (trigger/function names agree up↔down↔tests, `IDENTITY_ERROR`
  / `APPEND_ONLY_ERROR` match the two RAISE messages, `TG_OP <> 'UPDATE'` executes
  before any NEW/OLD access, checksum covers both directions, the round-trip
  `NOT tgisinternal ... == 2` filter correctly excludes the 4 FK triggers).

| Finding | Tier | Disposition |
|---|---|---|
| integration test gates on `DATASET_VERSION_TEST_POSTGRES_URL`, wired into no CI job → always skipped (false-green; also the unit file ran in no CI job) | T1 | FIXED — wired both suites into `control-plane-hardening-tests.yml`: unit into `ros-roster-tests`, integration as a new `ros-postgis-integration` step with the env var. This corrects the round-1 L-3 "skips-open" I had under-dispositioned as convention |
| DDL-only guard missed INSERT and only matched schema-qualified UPDATE | T1 | FIXED — regex now catches INSERT + qualified/unqualified UPDATE; verified non-vacuous (injected statements caught, real 0004 clean) |
| capstone re-lists the 7 attack vectors (drift risk) | T1 (PLAUSIBLE) | NOTED — deliberate independent aggregate; the focused per-vector tests are the primary guard (a new column always gets its own test); clarifying comment added |
| out-of-order ancestor rollback | T2 (MEDIUM) | ACCEPTED — same finding as round 2; runner-level, owned by follow-up #155; Codex confirms the slice is "coherent and complete" under that acceptance |

## Review (g2-check, 2026-08-08 21:53:40 +0700) — last-commit 95933fae (#150 slice)

### Reviewed
- Repo / branch: munbon2-backend (worktree `-issue150`) / `fix/150-dataset-version-identity-immutable`
- Scope: last-commit `95933fae` — 5 files (0004 up/down, unit + integration tests, `control-plane-hardening-tests.yml`)
- Commands run: `git show`/targeted diffs; full ros-gis `pytest` (230 passed / 3 skipped); DELETE/TRUNCATE/created_at mutation checks + identity RED proof; real-PG probes (bulk UPDATE, writable CTE, `UPDATE ... FROM`, `ON CONFLICT DO UPDATE`, MERGE); down apply→rollback→reapply round-trip; **water_requirement integration re-run under the trigger on a full 0001-0004 DB (2 passed)**; DDL-guard regex non-vacuity check; workflow YAML validation.
- Not inspected: 0002/0003 migrations' own correctness (unchanged); the hosted CI run itself (billing-locked — cannot execute remotely); the migrate.py runner's out-of-order-rollback behaviour (accepted; filed #155).

### Findings
**No CRITICAL / HIGH / MEDIUM findings.**

Boundary risk recorded as VERIFIED-CLEAN (not a finding): the append-only + column-selective trigger vs the only production writer of `ros_gis.dataset_versions`, `_activate_section_dataset` (`src/services/requirement_source_loader.py:781-805`). It supersedes the active row with `UPDATE ... SET status='superseded', effective_to=$2` (both mutable) and INSERTs the new active row — neither touches an immutable column, so the trigger allows both. Confirmed by re-running the water_requirement integration suite with the trigger present on a full 0001-0004 database (2 passed). The first water_requirement test (which exercises activation) also passed even on a 0001+0004-only DB.

LOW / noted:
- The integration suite skips without `DATASET_VERSION_TEST_POSTGRES_URL`; now wired into the `ros-postgis-integration` CI job so it runs (round 3). Until hosted-CI billing is restored, the local run at exact SHA is the evidence.
- The capstone re-lists the 7 attack vectors (drift risk); the focused per-vector tests are the primary guard; a clarifying comment was added (round 3).

### Open Questions / Assumptions
- Assumes 0004 is applied AFTER 0001 in every environment (the CI job and the test's `_ensure_schema` both do). Out-of-order apply is not enforced by the runner, but 0004 genuinely depends only on 0001.

### Recommended Tests / Validation
- Once hosted-CI billing is restored, confirm the `ros-postgis-integration` job's new step executes (not skips) and both ros-gis suites are green remotely.

### Rollout Notes
- Additive DDL (a trigger + a function); no feature flag — it is a fail-closed DB constraint. Ordering: 0004 after 0001. Rollback: 0004 down drops both triggers + the function (round-trip tested) and is guarded against a missing table. Backward-compatible: existing rows unaffected; the only production UPDATE path (activation/supersession) stays legal; no ros_gis code performs a DELETE/TRUNCATE of `dataset_versions` (grep-clean).

### Round 4 — final dryness (converged)
- Tier 1 g2-check (formal review; also the task's formal g-check deliverable): no
  CRITICAL/HIGH/MEDIUM. Verified the key boundary — the append-only +
  column-selective trigger vs the only production writer `_activate_section_dataset`
  (supersede via status/effective_to + INSERT a new row) — CLEAN, by re-running the
  water_requirement suite under the trigger on a full 0001-0004 DB (2 passed). Full
  report in the "## Review (g2-check ...)" section above.
- Tier 2 Codex round 4: one LOW — an unquoted `#150` in the new CI step name made
  YAML treat ` #150)` as a comment, truncating the displayed step name (env/command
  intact). FIXED (quoted the name). The Codex job was killed by the harness after
  completing its static analysis (wiring valid, regex non-vacuous); its findings are
  captured here.

Both tiers dry (nothing above LOW). QCHECK converged after 4 rounds.

## Final state (definitive)
- `0004` installs one function used by two triggers on `ros_gis.dataset_versions`:
  `dataset_versions_identity_is_immutable` (BEFORE UPDATE OR DELETE, row-level) and
  `dataset_versions_no_truncate` (BEFORE TRUNCATE, statement-level). Any non-UPDATE
  op is rejected append-only; an UPDATE is rejected only when an immutable column
  (dataset_version_id, dataset_kind, source_hash, created_at) changes.
- Lifecycle columns (status, effective_from/to, source_description) stay mutable; the
  sole production writer (activation/supersession) is unaffected (verified).
- Tests: 9 unit + 10 integration; every rejection behaviour RED- or mutation-verified;
  the down migration apply→rollback→reapply is exercised; both suites are wired into
  the control-plane-hardening CI jobs.
- Follow-up #155: runner-level reverse-order-rollback enforcement (out of trigger scope).
- Delegate: none (Q0 — migration is never-delegate). All code Claude-authored.
  Fix-round count: QCHECK rounds 1-4 (contract → adversarial → merged-artifact → dryness).
