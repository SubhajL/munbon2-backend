# Coding Log — #155 enforce reverse-order rollback in ros-gis migrate.py

Started: 2026-08-09 05:59 (+07)
Branch: fix/155-rollback-order-guard (worktree ../munbon2-backend-155, base origin/main 3ee709ed)
Issue: #155 — out-of-order rollback can silently drop 0004 protection.

## Scope
Fail-closed guard in `rollback_migration` (services/ros-gis-integration/migrations/migrate.py:112):
refuse to roll back a migration while any higher-id migration remains registered,
before executing any down SQL. Latest-first rollback unaffected.

## Exit gate (from the issue)
- `rollback_migration(..., "0001_...")` raises `MigrationError` while a later
  migration is still registered, before executing any DDL.
- Normal reverse-order rollback (latest first) is unaffected.

## Gates
- pytest (service gate; ruff F courtesy). Local vs hosted evidence kept separate
  (PR #156 precedent: hosted GitHub checks all reported failure on a green-local PR).

## Plan
DREP follows (g2-planning). Q0 fires: migration-runner safety code → never-delegate;
Claude implements the whole slice.

## g2-planning — Codex adversarial pass (gpt-5.6-sol, xhigh) + synthesis

Codex verdict: REJECT-as-execution-ready (spec coverage complete; contract wording
and wiring gaps). Every finding verified at cited file:line. Dispositions:

1. ACCEPT (HIGH) — unit job in `.github/workflows/control-plane-hardening-tests.yml`
   names 3 files and omits `test_dataset_version_schema.py` → new runner tests unwired
   from (dormant-but-correct) CI. Fix: add the file to that job's pytest list (F4).
2. ACCEPT (MED) — incident-level proof missing on real PostgreSQL. Add T3 to
   `tests/integration/test_dataset_version_immutability_postgres.py` (already wired
   into the CI `#150` step, env `DATASET_VERSION_TEST_POSTGRES_URL`): with 0001+0004
   applied, `rollback_migration(conn, 0001)` raises MigrationError; triggers still 2;
   both registry rows intact.
3. PARTIAL (MED) — stale "runner permits out-of-order" comments. `0004.down.sql:5`
   is UNEDITABLE (comments participate in the pair checksum; editing an applied
   migration is forbidden by the runner itself) → staleness documented here + PR body;
   it already calls the runner concern "separate". The editable unit-test comment at
   `test_dataset_version_immutability.py:118` is updated (F6).
4. ACCEPT (HIGH) — "Python bytewise" was false. Contract now: "later" = strictly
   greater by Python str comparison (Unicode code-point lexicographic) over the FULL
   migration id; ordering correctness rests on the repo's zero-padded 4-digit prefix
   convention (all 4 tracked ids conform). Stated in the code comment. No id-grammar
   validator (non-goal; no nonconforming id exists; guard stays fail-closed regardless).
5. ACCEPT (HIGH) — R2 overclaimed "only statement executed". Reworded: no down SQL
   and no registry mutation execute; the sole `execute()` is the advisory lock;
   registry reads go through read-only fetch*/fetchval/fetchrow (unlogged by the stub).
6. ACCEPT-BY-DESIGN (MED) — permissive `_StubConn.fetch`: the production guard query
   is exactly `SELECT migration_id FROM ros_gis.schema_migrations` (no WHERE; filter in
   Python), so the stub's return-all behavior is faithful to real semantics; T3 proves
   the path on real Postgres.
7. ACCEPT (MED) — T2 assertion corrected to project 3-tuples to (sql, args) and
   assert the DELETE pair; registry-state deletion proof lives in the real-DB
   round-trip (existing integration test + T3).
8. ACCEPT (MED) — plural blockers: T1 gains case (c) applied={0001,0002,0004},
   target=0001 → message must name BOTH 0002 and 0004 (R4).
9. ACCEPT-AS-DESIGNED — T2 covers R3 only (overblocking boundary); R1 evidence is
   T1+T3. Traceability says so explicitly.
10. ACCEPT — precedence locked: checksum-drift check stays BEFORE the ordering guard;
    new R5+T4: drifted target with a later migration applied raises the checksum error.
11. ACCEPT — FN1 invariant: the registry read for the guard happens INSIDE the
    transaction after `pg_advisory_xact_lock` (no TOCTOU with a concurrent apply).
12. ACCEPT — §0 corrected: worktree has no venv; gate = main-tree
    `services/ros-gis-integration/venv/bin/pytest` run from the worktree service dir
    (baseline verified: 39 passed schema file, 220 passed full unit suite).
13. ACCEPT — integration gate env var is `DATASET_VERSION_TEST_POSTGRES_URL`.
14. ACCEPT — CI pre-applies 0001–0003 before the immutability suite; locally the
    registry may be 0001+0004 only. T3 therefore asserts only that 0004 appears in
    the error (always a blocker), not an exact blocker list.
15. ACCEPT — blast-radius correction: unit suite itself calls rollback at
    schema-test L382/L393/L401; verified those registries (single id / drift / empty)
    never trip the new guard.
16. OUT-OF-SCOPE / FOLLOW-UP — `ops/control-plan-read-runtime/run-ros.sh:25` applies
    only 0001–0003 (NOT 0004): #150's protection is inactive in that runtime. Not a
    #155 runner change; MUST be checked when freezing the nine-stage acceptance
    (does the acceptance stack apply 0004?) and remediated there or via follow-up issue.

## Final change contract (post-synthesis)
- F1 migrate.py — guard in `rollback_migration` after drift check, before
  `execute(down_sql)` (L134); module docstring gains the ordering-refusal line.
- F2 tests/unit/test_dataset_version_schema.py — T1 (params a: {0001,0004}→0001,
  b: {0001,0002,0004}→0002, c: {0001,0002,0004}→0001 asserting both blockers named;
  executed-projection == [advisory lock] only), T2 (latest-first w/ earlier registered
  → "rolled-back" + DELETE (sql,args) pair), T4 (drift precedence).
- F3 services/ros-gis-integration/CLAUDE.md — migrations para: rollback also refuses
  out-of-order (latest-first enforced).
- F4 workflow unit job — add tests/unit/test_dataset_version_schema.py.
- F5 tests/integration/test_dataset_version_immutability_postgres.py — T3 incident
  test (refusal + triggers/registry intact; best-effort state repair in finally).
- F6 tests/unit/test_dataset_version_immutability.py — comment update (runner now
  refuses out-of-order rollback; SQL guard is defense-in-depth).
Owner: Claude (Q0 — migration-runner safety, never-delegate). Oracle: T1 RED→GREEN,
T2/T4 green, T3 RED→GREEN on disposable postgis:16-3.4 (OrbStack), full service
suite green, ruff F courtesy.

## g2-coding — implementation record
Stop line: NONE — Q0 fires (migration-runner safety = never-delegate). All code
Claude-authored; no delegate, no brief, no diff-audit-vs-delegate. Phase 2c-ter
TDD order followed per unit of behaviour.

RED (before guard):
- unit: exactly the 3 T1 parametrizations FAILED `DID NOT RAISE MigrationError`
  (predicted reason); T2/T4 passed as designed (boundary/precedence pins).
- integration (disposable OrbStack postgis:16-3.4, 127.0.0.1:5497, ros_gis_155_test):
  T3 FAILED `DID NOT RAISE`; finally-repair restored 0001+0004 (siblings 10 passed).

GREEN (after guard in rollback_migration, inserted after drift check, before
`execute(down_sql)`): unit file 44 passed; integration file 11 passed.

Mutation evidence (2c-bis, for the pins written green):
- `>` → `>=`: FAILED exactly test_rollback_latest_first_succeeds_while_earlier_remain
  + pre-existing test_rollback_runs_down_sql_and_deregisters (both pin latest-first);
  T1 still passed. Restored → 44 passed. T2 non-vacuous.
- T4 precedence pin argued structurally: its registry ({0001: drifted, 0004: valid})
  makes the two errors distinguishable by match= ("checksum" vs "latest-first");
  flipping the check order flips the raised error → T4 fails.

Gates (Claude-run): unit suite 225 passed ×3; integration file 11 passed ×3;
ruff --select F clean on all 4 touched .py files; workflow YAML parses (ruby YAML OK).
Diff audit: exactly F1–F6 + coding log + pointer; no strays.

## g2-qcheck round 1 (framing: contract-correctness)
- Tier 1: /code-review high (workflow wf_59df37df-5e0), scoped to the worktree diff.
- Tier 2: codex exec gpt-5.6-sol xhigh read-only, prompt carries R1–R5 + call sites
  + full diff ($SCRATCH/qcheck-prompt.md → qcheck-codex.md). MANDATORY trigger:
  migration-runner/config change.
Results pending; findings + dispositions to follow.

### Round 1 — Tier 2 (codex gpt-5.6-sol xhigh) result
Verdict: R1–R5 satisfied at named call sites; NO CRITICAL/HIGH. Reviewer did real
work (file:line cites throughout; independently ran the expanded CI unit selection,
83 passed). Findings + dispositions:
- MEDIUM "full-ID comparison not pinned" → FIXED: 4th T1 param — synthetic blocker
  `0001_dataset_version_parent_zz_suffix_order` (same 0001 prefix, greater suffix;
  needs no .sql pair since only the target's checksum is read). Mutation-proven:
  `int(id[:4])` comparison regression fails exactly that case (1 failed/44 passed),
  restored → 45 passed.
- MEDIUM "T2 cannot prove earlier registry rows survive" → FIXED: _StubConn.execute
  now applies DELETE semantics to self.applied; T2 asserts the surviving registry is
  exactly {0001: its checksum}.
- LOW "T1 does not pin lock id/tx placement" → FIXED: T1 asserts the full tuple
  ("SELECT pg_advisory_xact_lock($1)", (MIGRATIONS_LOCK_ID,), True).
Codex side notes: T3 not rerun by reviewer (no DB URL in its sandbox — Claude runs
it green locally ×3); ruff unavailable to reviewer (Claude ran it clean); run-ros.sh
omitting 0004 reconfirmed as pre-existing #150 activation concern (follow-up at
acceptance-freeze time, NOT a #155 regression).
Gates after fixes: schema file 45 passed; unit suite 226 passed; integration 11
passed; ruff F clean.

### Round 1 — Tier 1 (/code-review high, workflow wf_59df37df-5e0, 11 agents, 0 errored) result
6 verified findings; dispositions:
1. CONFIRMED "sibling runners (scheduler: 13 migrations, flow-monitoring: 2) keep the
   unguarded rollback_migration copy" → DEFERRED w/ owner: verified by grep (both have
   rollback_migration at :157, zero guard hits); #155 + goal scope pin this PR to
   ros-gis; follow-up GitHub issue to be filed with the PR (sibling-runner guard).
2. CONFIRMED "no --force/escape hatch" → REJECTED by design: #155 proposed fix is
   fail-closed reverse-order enforcement "consistent with the runner's existing
   fail-closed behaviour"; DREP §1 Non-Goal ("no --force escape hatch"). Sanctioned
   path is latest-first rollback.
3. PLAUSIBLE "non-conforming ids defeat the guard ('10000_x' < '9999_x'; '00040_foo'
   < '0004_...')" → FIXED (TDD): T5 (param apply/rollback: nonconforming target id
   refuses with match="convention" BEFORE any statement; RED = wrong-reason
   "unknown migration") + T6 ('00040_foo' registered alongside 0004: rollback 0004
   must fail closed; RED = DID NOT RAISE — the exact under-block predicted).
   Impl: MIGRATION_ID_PATTERN=^\d{4}_ enforced in _read_sql (every target id, before
   any I/O) + malformed-registry fail-closed check in the guard before ordering.
   Rollover '10000_x' now refused at apply (forces explicit convention decision).
4. PLAUSIBLE "'later' = id order, not apply chronology" → REJECTED by design: #155
   defines the guard as "any migration with a higher id"; dependency safety follows
   id order (0004's trigger depends on 0001's table regardless of apply chronology).
5. CONFIRMED "docstring rollback example now always fails" → FIXED: example now rolls
   back 0004 + explicit "Rollback is latest-first only" line.
6. CONFIRMED cleanup "redundant second registry query" → REJECTED w/ reason: manual
   CLI op inside advisory-locked tx; folding into the drift fetchrow churns
   never-delegate code and reduces _StubConn fidelity (no-WHERE query = stub-faithful).
De-dup vs Tier 2 round 1: disjoint sets (Tier 2: test-strength; Tier 1: scope/
convention/docs) — the two-tier rationale held empirically again.
Gates after fixes: schema file 48 passed; unit suite 229 passed ×3; integration 11
passed ×3; ruff F clean.

### Round 2 launched (framing: adversarial) — both tiers on remediated tree
Tier 1: workflow wf_61e754a5-52b. Tier 2: codex gpt-5.6-sol xhigh (qcheck2-prompt.md:
crafted-input attacks on the guard, moved-hole check, apply/rollback interaction,
guard-deleted vacuity probe).

### Round 2 results (adversarial) — Tier 2 codex + Tier 1 workflow wf_61e754a5-52b (17 agents, 0 errored)
De-duplicated across tiers (unicode \d found INDEPENDENTLY by both — two witnesses):
- HIGH (both tiers) unicode digits pass \d but sort above ASCII → guard bypass both
  directions (Codex exercised a live bypass; Tier 1 verified in REPL) → FIXED (TDD):
  pattern now ^[0-9]{4}_; T5 extended with Arabic-Indic/Thai/fullwidth target ids ×
  apply/rollback (8 RED cases), T7 unicode-registry fail-closed. Mutation-locked:
  reverting to \d fails exactly 7 tests; restored 58 pass.
- CONFIRMED (T1) duplicate numeric prefixes ordered by suffix lexicography → FIXED
  (TDD): _orderable_registry_ids also refuses duplicate 4-digit prefixes (both
  suffix orderings tested, T9 parameterized; T10: apply refuses a target that would
  CREATE the collision). NOTE: this consciously SUPERSEDES round-1 fix M1 — under
  the unique-prefix invariant, [:4]-numeric and full-id code-point ordering are
  equivalent, so the M1 pin case (same-prefix blocker expecting "latest-first") was
  removed from T1 and re-homed as a duplicate-prefix refusal case in T9. Recorded
  as an evolution, not a silent drop.
- CONFIRMED (both tiers) malformed-registry check ran only at rollback; apply kept
  stacking onto an unorderable registry → FIXED (TDD): shared
  _orderable_registry_ids(conn, including=target) gate runs in apply after the
  already-applied/drift shortcut and BEFORE up SQL (T8: sqls == [lock, schema DDL,
  registry DDL] only).
- PLAUSIBLE (T1) legacy nonconforming row bricks rollback with no guidance →
  FIXED via the above + explicit remediation wording ("repair
  ros_gis.schema_migrations (reviewed manual surgery) before applying or rolling
  back"). Residual inability to self-heal a foreign row is fail-closed BY DESIGN.
- PLAUSIBLE (T1) integration round-trip fragile to future 0005 → REJECTED for this
  diff: failure mode is a LOUD MigrationError in the suite, owned by whoever adds
  0005; not silent.
- CONFIRMED (T1, LOW) _StubConn INSERT/DELETE asymmetry → FIXED (INSERT now
  registers into self.applied).
- CONFIRMED (T1, LOW) CI unit job hand-enumerates 4/17 files → REJECTED for this
  PR: the dormant workflow's established convention is explicit named suites;
  wholesale globbing risks import-time surprises out of #155 scope.
- LOW (T2 round 2) 0004.down.sql stale comment → REJECTED again: file uneditable
  (checksummed pair; runner itself forbids editing applied migrations).
Gates after round-2 fixes: schema file 58 passed; unit suite 239 passed; integration
11 passed; ruff F clean; \d mutation kill verified.

### Round 3 launched (framing: merged-artifact / final-tree coherence) — both tiers

### Round 3 results (merged-artifact) — Tier 2 codex + Tier 1 workflow wf_c835526f-11c (12 agents, 0 errored)
Tier 2: NOTHING above LOW; independently re-verified every legitimate flow (CI
sequential apply, run-ros.sh, _ensure_schema, idempotent re-apply, 0004 round trip,
incident repair) and ran the suites itself (239/97/58 passed). 2 LOW doc fixes
applied (canonical ASCII-NNNN_/unique-prefix sentence in module docstring +
CLAUDE.md + "ASCII" in error wording; conditional wording in the integration
repair comment).
Tier 1: 5 findings — round NOT dry:
- CONFIRMED apply's already-applied fast path returned before the gate,
  contradicting the (round-3-doc-fix) promise that BOTH directions refuse
  unorderable registries → FIXED (TDD): new RED test
  test_reapply_fails_closed_when_registry_has_corrupt_sibling (was
  "already-applied"/DID NOT RAISE), gate moved before the fetchrow fast path.
  run-ros.sh's boot-time re-applies now surface corruption at the EARLIEST touch.
- CONFIRMED duplicate-prefix error's "renumber" guidance dead-ends for
  registered duplicates → FIXED: message now distinguishes renumbering an
  unapplied migration from reviewed manual registry surgery.
- CONFIRMED cleanup: two copy-pasted bad-registry-id tests → FIXED (merged into
  one parameterized test per repo testing rule 1).
- CONFIRMED cleanup "dead including-dedup branch" → NO CHANGE NEEDED / INVALIDATED:
  after the fast-path fix the branch is load-bearing (without it every idempotent
  re-apply would false-positive as a duplicate); pinned by the existing
  test_apply_is_idempotent_when_checksum_matches.
- CONFIRMED cleanup CI step-name mislabel → FIXED ("dataset-version schema +
  migration runner").
Gates after round-3 fixes: schema file 59 passed; unit suite 240 passed;
integration 11 passed; ruff F clean; workflow YAML parses.

### Round 4 launched (framing: fresh contract-correctness on the final tree) — both tiers

### Round 4 — Tier 2 (fresh contract pass) result
- HIGH "clause 4 not met: file reads/checksums precede the advisory lock" →
  REJECTED as a code defect, with evidence: the ROUND-4 PROMPT's clause-4 wording
  was wrong, not the code. `git show 3ee709ed:...migrate.py` proves the base
  runner already computed down_sql/digest BEFORE the transaction; tracked .sql
  files are local state — the advisory lock serializes REGISTRY access, which is
  (and was) entirely under the lock. The #155 exit gate ("raises before executing
  any DDL") is met; refusing a malformed target before opening a transaction is
  the STRONGER fail-closed property and is the pinned contract (T5).
  Corrected contract wording for later rounds: "all REGISTRY reads and
  ordering/orderability refusals under pg_advisory_xact_lock in one tx; target
  file validation/checksum may precede the tx (local, lock-irrelevant)."
- MEDIUM integration test title overclaims "before any DDL" (a rolled-back tx is
  indistinguishable from never-attempted at the postcondition level) → FIXED:
  renamed to test_out_of_order_rollback_is_refused_with_no_persistent_change with
  an explicit pointer to the unit executed-list assert for the statement-level pin.
- MEDIUM not-applied precedence not mutation-locked → FIXED: new precedence pin
  test_rollback_not_applied_refusal_precedes_ordering_refusal (absent target,
  0004 registered → match "not applied", not "latest-first").
- LOW CLAUDE.md omitted DATASET_VERSION_TEST_POSTGRES_URL → FIXED (both gate env
  vars now documented).
Reviewer independently ran: unit 240, four-file selection 98, schema file 59, ruff
F — all green pre-fix. Gates after fixes: unit 241, integration 11, ruff clean.

### Round 4 — Tier 1 (workflow wf_e37b32f6-d54, 9 agents, 0 errored) result
NO correctness bugs; 2 CONFIRMED cleanups, both FIXED:
- integration refusal now attributed to the ordering guard via match="latest-first"
  (was substring-only, could mis-attribute a future unorderable-registry error);
- malformed check scoped to REGISTRY rows only (target grammar is _read_sql's,
  which always fires first); `including` participates only in the duplicate-prefix
  check, where it is load-bearing; helper docstring says so.
Verifier also REFUTED the "not-applied precedence unpinned" candidate — the round-4
Tier-2 M2 test had already added exactly that pin (independent confirmation).
Gates after cleanups: unit 241, integration 11, ruff F clean.

### Round 5 launched (confirmation round, corrected clause-4 wording) — both tiers

### Round 5 results — DRY (both tiers)
- Tier 1 (workflow wf_5deebd77-ce4, 5 agents, 0 errored): ZERO candidates.
- Tier 2 (codex gpt-5.6-sol xhigh): "No genuinely new defects above LOW. The final
  tree meets the corrected contract." Independent five-clause contract trace passed;
  ruff/AST/YAML/git-diff-check green in its sandbox.
Loop-until-dry satisfied: a full both-tier round surfaced nothing above LOW.

## Final summary (Phase 8)
- Stop line: NONE (Q0 — migration-runner safety, never-delegate). 100% of code
  Claude-authored; delegate fix rounds: n/a; no Claude-tail patches (no delegate).
- TDD: every behaviour RED-proven before implementation; boundary pins
  mutation-verified (>→>=, [0-9]→\d, int-prefix comparison — each killed exactly
  its pinning tests). Layers written before tests: none.
- QCHECK: 5 both-tier rounds (contract → adversarial → merged-artifact →
  fresh-eyes → confirmation). Reviewers: Tier 1 = /code-review high multi-agent
  workflow (session model), Tier 2 = codex gpt-5.6-sol xhigh — both independent of
  the (Claude) implementer per g2-qcheck. Two-tier disjointness held every round.
  27 findings total across rounds; all CRITICAL/HIGH fixed (unicode-digit guard
  bypass — found independently by BOTH tiers; apply fast-path gate bypass;
  duplicate-prefix under-block); all MEDIUMs fixed; rejections carry file:line or
  design citations; one deferral → sibling-runner follow-up issue (filed with PR).
- Final gates (exact tree): unit 241 ×3, integration 11 ×3 (disposable OrbStack
  postgis:16-3.4 @127.0.0.1:5497), ruff F clean, workflow YAML parses.
- Local vs hosted evidence SEPARATED: hosted GitHub checks expected to report
  failure while Actions billing is locked (E6; PR #156 precedent) — recorded
  verbatim on the PR at merge time, never conflated with the local evidence above.
