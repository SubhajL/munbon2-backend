# LOCAL-WRITE-FOUNDATION-1 Coding Log

Created: 2026-07-28 19:00:00 +07
Authoritative baseline: `origin/main` at `469553cc2ae4da2c0ddaf88cb558d2970793517d`

## Planning context

This is the LOCAL-WRITE-FOUNDATION-1 acceptance stage — the combined local
backend-only gate that exercises W1 (effective principal) and W2 (planning-depth
submissions) as a live integration before any frontend or activation work begins.

W1 landed as PR #122 and W2 as PR #123 + #124 (compatibility fix). Both are on
current `origin/main`. The stage runner (`ops/control-plan-read-local/run-stage-suite.py`)
currently contains six stages through LOCAL-GO-READ-1. This PR adds the seventh
stage, LOCAL-WRITE-FOUNDATION-1.

Planning uses the g2-planning lifecycle. Implementation uses g2-coding.

---

# DREP: LOCAL-WRITE-FOUNDATION-1

## §0 Repo Profile

- **Repo root**: `/Users/subhajlimanond/dev/munbon2-backend`
- **Language(s)**: Python 3.11 (FastAPI, pytest)
- **Baseline**: `origin/main` at `469553cc2ae4da2c0ddaf88cb558d2970793517d`
- **Test command (ops)**: `cd ops/control-plan-read-local && python -m pytest tests/ -v`
- **Test command (BFF)**: `cd services/bff-water-planning && pytest -v`
- **Test command (Scheduler)**: `cd services/scheduler && PYTHONPATH=src pytest -q`
- **Lint**: Black 23.11, Isort 5.12 (Black profile), Ruff
- **Typecheck**: N/A (Python — type hints on public functions)
- **Build**: N/A (no root build; per-service)
- **Migration policy**: Ordered manifest with SHA-256 checksums; `owned_migration_number_min=9`
- **Coding-log**: `coding-logs/2026-07-28-19-00-00 Coding Log (local-write-foundation-1).md`
- **Repo ownership**: ours
- **Runtime ownership**: ours
- **Disposition**: production

### MUST NOT list (from root CLAUDE.md)

- MUST NOT commit secrets, API keys, DB passwords, tokens, or production hostnames
- MUST NOT push directly to `main`
- MUST NOT introduce a second copy of an existing algorithm
- MUST NOT silently hardcode operational constants
- MUST NOT add mock data for integration paths
- MUST NOT skip tests or substitute simpler tests

---

## §1 Goal / Non-Goals

**Goal**: Add the seventh acceptance stage `LOCAL-WRITE-FOUNDATION-1` to the
local stage suite. This stage exercises W1 effective-principal and W2
planning-depth write/read-back end-to-end against the real local runtime,
proving the dark-flag gate, migration integrity, principal auth, rate limiter,
immutable ledger, replay/conflict semantics, and active read-back before any
frontend or activation work begins.

**Non-Goals**:
- No frontend (FE-5/FE-6/FE-7/FE-8) work
- No browser automation (backend-only HTTP stage)
- No production activation, AWS work, or deployment
- No changes to W1 or W2 production code — only the stage harness
- No ROS recomputation, machine command, authority, or SCADA changes
- No migration changes — migration 009/010 exist and are exercised as-is
- No changes to the body of existing six stage functions

---

## §2 Requirements — R1..R10

- **R1**: `STAGE_ORDER` includes `"LOCAL-WRITE-FOUNDATION-1"` after `"LOCAL-GO-READ-1"`, `validate_stage_transition` enforces all prior stages completed, and `_parse_args` accepts it.
- **R2**: GO-READ-1's `_save_state` call saves `list(STAGE_ORDER[:6])` (not the full tuple), so it does not falsely mark stage 7 complete.
- **R3**: `orchestrate.py`'s `STAGE_ORDER` includes the new stage, so `run-all` and the host CLI accept it.
- **R4**: The stage proves W1 `GET /api/v1/auth/principal` returns `200` with sorted `effective_roles` containing `"operator"`, and `Cache-Control: no-store`.
- **R5**: The stage proves W2 POST returns `503` with `planning_depth_writes_disabled` when `PLANNING_DEPTH_WRITES_ENABLED` is not `"true"`.
- **R6**: With the flag temporarily enabled (BFF restarted), the stage proves create (`201`), replay of the same client-id/content (`200` with same submission_id), conflict on stale active-id (`409`), active GET (`200` with 41 expanded values matching the submission), and missing-week GET (`404`).
- **R7**: The stage verifies migration 010 is applied and manifest checksum matches.
- **R8**: The stage restores `PLANNING_DEPTH_WRITES_ENABLED=false`, restarts BFF, and confirms POST returns `503` again — even if a drill failed mid-sequence (try/finally guard).
- **R9**: The stage emits `LOCAL-WRITE-FOUNDATION-1.json` evidence manifest with verdict, SHAs, timestamps, and drill results.
- **R10**: `bootstrap-linux.sh` seeds `PLANNING_DEPTH_WRITES_ENABLED=false` in `bff.env` so the flag state is explicit, not implicit.

---

## §3 Change Contract — F1..F8

| ID | Path | Action | Anchor | New exports | Purpose |
|----|------|--------|--------|-------------|---------|
| F1 | `ops/control-plan-read-local/run-stage-suite.py` | MODIFY | `STAGE_ORDER` tuple L45–51 | — | Add `"LOCAL-WRITE-FOUNDATION-1"` |
| F2 | `ops/control-plan-read-local/run-stage-suite.py` | MODIFY | `run_local_go_read()` `_save_state` call L3819 | — | Change `list(STAGE_ORDER)` to `list(STAGE_ORDER[:6])` |
| F3 | `ops/control-plan-read-local/run-stage-suite.py` | MODIFY | `main()` dispatch L3865–3876 | — | Add dispatch case for stage 7 |
| F4 | `ops/control-plan-read-local/run-stage-suite.py` | MODIFY | after `run_local_go_read()` | `run_local_write_foundation()`, validation helpers | New stage + helpers |
| F5 | `ops/control-plan-read-local/orchestrate.py` | MODIFY | `STAGE_ORDER` tuple L16–23 | — | Add `"LOCAL-WRITE-FOUNDATION-1"` |
| F6 | `ops/control-plan-read-local/tests/test_stage_suite.py` | MODIFY | end of file | — | Add tests for new validation helpers |
| F7 | `ops/control-plan-read-local/tests/test_local_artifacts.py` | MODIFY | L80 count + L83 assertion | — | Update `_checksum_manifest` count from 6→7, update `_save_state` assertion |
| F8 | `ops/control-plan-read-local/bootstrap-linux.sh` | MODIFY | `bff.env` heredoc L296–299 | — | Add `PLANNING_DEPTH_WRITES_ENABLED=false` |

---

## §4 Function Contracts — FN1..FN10

```
FN1  run_local_write_foundation(context: StageContext) -> dict
     File:        F4
     Does:        Orchestrates LOCAL-WRITE-FOUNDATION-1: verifies migration 010
                  status, W1 principal, W2 dark-flag gate, temporarily enables
                  writes by modifying bff.env and restarting BFF via PM2, exercises
                  create/replay/conflict/active/not-found, restores the flag
                  (try/finally), and emits the stage manifest.
     Pre:         All six prior stages completed. Local runtime running.
     Post:        Evidence manifest written. PLANNING_DEPTH_WRITES_ENABLED restored
                  to false. BFF restarted with false. Returns manifest dict.
     Errors:      Raises StageGateError on any drill failure. Flag is still
                  restored on exception via the finally block.
     Invariants:  Never issues a machine command, authority grant, or SCADA request.
```

```
FN2  validate_w1_principal_result(status: int, body: Any, headers: dict) -> dict
     File:        F4
     Does:        Validates W1 principal: status 200, exactly "subject" and
                  "effective_roles" keys, effective_roles is sorted and contains
                  "operator", Cache-Control includes "no-store".
     Pre:         body is parsed JSON; headers is the response headers dict.
     Post:        Returns {"subject": str, "effective_roles": list[str]}.
     Errors:      Raises StageGateError with descriptive code.
     Invariants:  Rejects extra fields, unsorted roles, missing no-store.
```

```
FN3  validate_w2_write_disabled_result(status: int, body: Any, headers: dict) -> dict
     File:        F4
     Does:        Validates W2 POST returns 503 with detail
                  "planning_depth_writes_disabled" and no-store header.
     Pre:         body is parsed JSON from W2 POST.
     Post:        Returns {"status": 503, "detail": str}.
     Errors:      Raises StageGateError if status != 503 or detail wrong.
```

```
FN4  validate_w2_submission_result(status: int, body: Any, headers: dict, *, expected_status: int) -> dict
     File:        F4
     Does:        Validates W2 POST create (201) or replay (200). Checks
                  submission_id, client_submission_id, content_hash, replayed,
                  week_key, and no-store header. For replay, additionally checks
                  submission_id matches the original create receipt.
     Pre:         body is parsed JSON from W2 POST.
     Post:        Returns the validated receipt dict.
     Errors:      Raises StageGateError if status/fields wrong.
```

```
FN5  validate_w2_active_result(status: int, body: Any, headers: dict, *, submission_id: str, expected_count: int) -> dict
     File:        F4
     Does:        Validates W2 active GET returns 200 with matching submission_id
                  and expanded_values list of expected_count (41) entries, plus
                  no-store header.
     Pre:         body is parsed JSON from W2 GET /active.
     Post:        Returns {"submission_id": str, "expanded_values_count": int}.
     Errors:      Raises StageGateError if status/count wrong.
```

```
FN6  validate_w2_conflict_result(status: int, body: Any, headers: dict) -> dict
     File:        F4
     Does:        Validates stale-active-id POST returns 409 with no-store.
     Pre:         body is parsed JSON.
     Post:        Returns {"status": 409, "detail": str}.
     Errors:      Raises StageGateError if status != 409.
```

```
FN7  validate_w2_not_found_result(status: int, body: Any, headers: dict) -> dict
     File:        F4
     Does:        Validates GET /active for non-existent week returns 404 with
                  no-store.
     Pre:         body is parsed JSON.
     Post:        Returns {"status": 404}.
     Errors:      Raises StageGateError if status != 404.
```

```
FN8  _build_planning_depth_request(*, week_date: str, client_submission_id: str, active_submission_id: str | None, depth_offset: str) -> dict
     File:        F4
     Does:        Builds a valid PlanningDepthSubmissionRequest body with six
                  zone-level defaults. depth_offset shifts depths to create a
                  canonically distinct payload for successor/conflict testing
                  (e.g., "0.100" vs "0.200").
     Pre:         week_date is an ISO date for a Monday.
     Post:        Returns a dict matching PlanningDepthSubmissionRequest schema.
     Errors:      None — pure builder.
     Invariants:  Uses synthetic but structurally valid depth values.
```

```
FN9  _restart_bff_with_flag(context: StageContext, enabled: bool) -> None
     File:        F4
     Does:        Appends/replaces PLANNING_DEPTH_WRITES_ENABLED in bff.env,
                  restarts BFF via pm2 restart, waits for /ready.
     Pre:         PM2 running; BFF process registered.
     Post:        BFF running with updated flag. /ready returns 200.
     Errors:      Raises StageGateError on timeout or ready failure.
```

```
FN10 _verify_bff_write_flag(context: StageContext, expected: str) -> dict
     File:        F4
     Does:        Reads the actual PM2 process environment for bff-water-planning
                  and confirms PLANNING_DEPTH_WRITES_ENABLED matches expected.
     Pre:         BFF running.
     Post:        Returns {"flag": str, "matches": bool}.
     Errors:      Raises StageGateError if mismatch.
```

---

## §5 Test Plan — T1..T12

```
T1   test_stage_order_includes_local_write_foundation_after_go_read
     File:      ops/control-plan-read-local/tests/test_stage_suite.py
     Covers:    R1
     Type:      unit (pure data)
     Arrange:   import STAGE_ORDER
     Act:       check position
     Assert:    STAGE_ORDER[-1] == "LOCAL-WRITE-FOUNDATION-1" and
                STAGE_ORDER[-2] == "LOCAL-GO-READ-1"
     RED-proof: fails with AssertionError because the stage is not in the tuple
```

```
T2   test_go_read_saves_six_stage_prefix_not_full_order
     File:      ops/control-plan-read-local/tests/test_local_artifacts.py
     Covers:    R2
     Type:      unit (source inspection)
     Arrange:   read run-stage-suite.py source
     Act:       search for the _save_state call in run_local_go_read
     Assert:    contains "_save_state(context, list(STAGE_ORDER[:6]))" and does NOT
                contain "_save_state(context, list(STAGE_ORDER))" in go_read body
     RED-proof: fails because the current code has list(STAGE_ORDER) — this is the
                bug Codex caught; after fix, passes
```

```
T3   test_orchestrate_stage_order_includes_write_foundation
     File:      ops/control-plan-read-local/tests/test_orchestrate.py
     Covers:    R3
     Type:      unit (pure data)
     Arrange:   import orchestrate.STAGE_ORDER
     Act:       check membership
     Assert:    "LOCAL-WRITE-FOUNDATION-1" in orchestrate.STAGE_ORDER
     RED-proof: fails because orchestrate.py doesn't have the stage yet
```

```
T4   test_validate_w1_principal_result_accepts_valid_operator
     File:      ops/control-plan-read-local/tests/test_stage_suite.py
     Covers:    R4
     Type:      unit (pure function)
     Arrange:   status=200, body={"subject":"op1","effective_roles":["operator"]},
                headers={"cache-control":"no-store"}
     Act:       validate_w1_principal_result(200, body, headers)
     Assert:    returns dict with subject="op1"
     RED-proof: fails with ImportError before FN2 exists
```

```
T5   test_validate_w1_principal_rejects_missing_operator_role
     File:      ops/control-plan-read-local/tests/test_stage_suite.py
     Covers:    R4
     Type:      unit (pure function)
     Arrange:   body with effective_roles=["field_team"]
     Act:       validate_w1_principal_result(200, body, headers)
     Assert:    raises StageGateError
     RED-proof: fails before FN2; after naive impl that skips role check, fails
                with "StageGateError not raised"
```

```
T6   test_validate_w1_principal_rejects_missing_no_store
     File:      ops/control-plan-read-local/tests/test_stage_suite.py
     Covers:    R4
     Type:      unit (pure function)
     Arrange:   valid body but headers={"cache-control":"max-age=60"}
     Act:       validate_w1_principal_result(200, body, headers)
     Assert:    raises StageGateError
     RED-proof: fails before FN2 exists; after impl without header check, fails
```

```
T7   test_validate_w2_write_disabled_accepts_503
     File:      ops/control-plan-read-local/tests/test_stage_suite.py
     Covers:    R5
     Type:      unit (pure function)
     Arrange:   status=503, body={"detail":"planning_depth_writes_disabled"},
                headers={"cache-control":"no-store"}
     Act:       validate_w2_write_disabled_result(503, body, headers)
     Assert:    returns without error
     RED-proof: fails with ImportError before FN3 exists
```

```
T8   test_validate_w2_submission_result_accepts_201
     File:      ops/control-plan-read-local/tests/test_stage_suite.py
     Covers:    R6
     Type:      unit (pure function)
     Arrange:   status=201, body with all receipt fields, replayed=False
     Act:       validate_w2_submission_result(201, body, headers, expected_status=201)
     Assert:    returns validated receipt
     RED-proof: fails with ImportError before FN4 exists
```

```
T9   test_validate_w2_active_accepts_41_values
     File:      ops/control-plan-read-local/tests/test_stage_suite.py
     Covers:    R6
     Type:      unit (pure function)
     Arrange:   status=200, body with submission_id and 41 expanded_values
     Act:       validate_w2_active_result(200, body, headers, submission_id="s1",
                expected_count=41)
     Assert:    returns dict with expanded_values_count=41
     RED-proof: fails with ImportError before FN5 exists
```

```
T10  test_validate_w2_conflict_accepts_409
     File:      ops/control-plan-read-local/tests/test_stage_suite.py
     Covers:    R6
     Type:      unit (pure function)
     Arrange:   status=409, body={"detail":"stale_active_submission"}
     Act:       validate_w2_conflict_result(409, body, headers)
     Assert:    returns without error
     RED-proof: fails with ImportError before FN6 exists
```

```
T11  test_validate_w2_not_found_accepts_404
     File:      ops/control-plan-read-local/tests/test_stage_suite.py
     Covers:    R6
     Type:      unit (pure function)
     Arrange:   status=404, body={"detail":"planning_depth_submission_not_found"}
     Act:       validate_w2_not_found_result(404, body, headers)
     Assert:    returns without error
     RED-proof: fails with ImportError before FN7 exists
```

```
T12  test_build_planning_depth_request_produces_distinct_canonical_payloads
     File:      ops/control-plan-read-local/tests/test_stage_suite.py
     Covers:    R6
     Type:      unit (pure function)
     Arrange:   build two requests with different depth_offset values
     Act:       _build_planning_depth_request with "0.100" and "0.200"
     Assert:    the two requests have different levels values (canonically distinct)
     RED-proof: fails with ImportError before FN8 exists
```

---

## §6 Traceability Matrix

| Req  | Tests      | Files    | Slice |
|------|-----------|----------|-------|
| R1   | T1        | F1,F3    | S1    |
| R2   | T2        | F2,F7    | S1    |
| R3   | T3        | F5       | S1    |
| R4   | T4,T5,T6  | F4       | S1    |
| R5   | T7        | F4       | S1    |
| R6   | T8–T12    | F4       | S1    |
| R7   | —*        | F4       | S1    |
| R8   | —*        | F4       | S1    |
| R9   | —*        | F4       | S1    |
| R10  | —*        | F8       | S1    |

*R7/R8/R9/R10 are runtime-integration behaviors verified by the stage function itself;
they cannot be unit-tested without the full local runtime stack.

---

## §7 Wiring Verification

| New component | Entry point (runtime caller) | Registration site | Schema/table |
|---|---|---|---|
| `"LOCAL-WRITE-FOUNDATION-1"` in `run-stage-suite.py` | `_parse_args()` choices | `STAGE_ORDER` tuple L45 | — |
| `"LOCAL-WRITE-FOUNDATION-1"` in `orchestrate.py` | `run_all_stages()` + CLI parser | `orchestrate.STAGE_ORDER` L16 | — |
| `run_local_write_foundation()` | `main()` dispatch L3865 | `elif args.stage == "LOCAL-WRITE-FOUNDATION-1":` | — |
| `validate_w1_principal_result()` | `run_local_write_foundation()` | direct call | W1 `GET /api/v1/auth/principal` |
| `validate_w2_write_disabled_result()` | `run_local_write_foundation()` | direct call | — |
| `validate_w2_submission_result()` | `run_local_write_foundation()` | direct call | `water_planning.planning_depth_submissions` |
| `validate_w2_active_result()` | `run_local_write_foundation()` | direct call | `water_planning.planning_depth_values` |
| `validate_w2_conflict_result()` | `run_local_write_foundation()` | direct call | — |
| `validate_w2_not_found_result()` | `run_local_write_foundation()` | direct call | — |
| `_restart_bff_with_flag()` | `run_local_write_foundation()` | direct call | `bff.env` |
| `_verify_bff_write_flag()` | `run_local_write_foundation()` | direct call | PM2 env |
| `PLANNING_DEPTH_WRITES_ENABLED=false` | `bootstrap-linux.sh` `bff.env` | heredoc L296 | — |

---

## §8 Slice Plan — S1

| ID | Scope | Owner | Stop line | Oracle | Done when |
|----|-------|-------|-----------|--------|-----------|
| S1 | F1–F8, T1–T12 | Claude | — | T1–T12 + ops pytest green + existing tests unbroken | All tests green, stage wired, no regression |

**Owner rationale**: Single acceptance-harness PR. Touches only ops code (not
production code). Validation helpers are judgment-heavy. No delegation.

---

## §9 Risks, Rollout, Rollback

| Risk | Trigger | Blast radius | Gate | Rollback |
|------|---------|-------------|------|----------|
| Stage runner regression | New code breaks existing stages | All 6 prior stages | Existing ops pytest must remain green | Revert PR |
| Flag restoration failure | Exception during write drills | BFF stays write-enabled | try/finally ensures restoration + verify | Manual env reset |
| Settings singleton reload | Flag written to env but not reloaded | Drills see stale value | PM2 restart + readiness wait + env verify | N/A |
| GO-READ state clobber | `_save_state(list(STAGE_ORDER))` marks stage 7 complete | Stage 7 unreachable | T2 catches this; fix in F2 | Revert PR |

The stage itself is inert — no runtime code, no migration, no deployment artifact.

---

## §10 Do-Not-Touch List

- `services/scheduler/` — all files
- `services/bff-water-planning/` — all files
- `contracts/` — all files
- Existing stage function bodies: `run_local_base`, `run_local_rta`,
  `run_local_ac`, `run_local_read_activation`, `run_local_evidence_activation`,
  `run_local_go_read` — EXCEPT the single `_save_state` call fix in
  `run_local_go_read` (F2)
- Existing test functions in `test_stage_suite.py`, `test_orchestrate.py`,
  `test_local_artifacts.py` — EXCEPT the artifact count/assertion updates (F7)
- `ops/control-plan-read-local/tests/test_stage_suite.py` existing tests — must
  not be modified

---

## Codex Adversarial Findings — Disposition

| # | Finding | Disposition | Action |
|---|---------|-------------|--------|
| 1 | GO-READ saves `list(STAGE_ORDER)` — stage 7 falsely marked complete | **ACCEPTED** — Critical blocker. | Added F2 + R2 + T2 |
| 2 | `orchestrate.py` has independent `STAGE_ORDER` — CLI rejects stage 7 | **ACCEPTED** — Wiring gap. | Added F5 + R3 + T3 |
| 3 | `test_local_artifacts.py` has hardcoded 6-stage counts | **ACCEPTED** — Would break existing tests. | Added F7 |
| 4 | `bootstrap-linux.sh` bff.env missing explicit write flag | **ACCEPTED** — Ambiguous config. | Added F8 + R10 |
| 5 | `_build_planning_depth_request` lacks level variant for conflict testing | **ACCEPTED** — Replay vs successor are content-identical; changing active_submission_id alone is insufficient for successor. | Added `depth_offset` param to FN8 + T12 |
| 6 | Validators omit `Cache-Control: no-store` header check | **ACCEPTED** — Important W1/W2 contract. | Added `headers` param to all validators |
| 7 | Settings singleton means flag toggle requires BFF restart | **ACCEPTED** — Must restart BFF, not just write env. | Added FN9 `_restart_bff_with_flag` + FN10 `_verify_bff_write_flag` |
| 8 | `main()` generic exception handler does no flag restoration | **ACCEPTED** — Flag restoration must be in `run_local_write_foundation` try/finally, not in `main()`. | R8 specifies try/finally guard |
| 9 | T1 vacuous if GO-READ state bug exists | **ACCEPTED** — T2 catches the root cause independently. | T2 added |
| 10 | `docs/operations/` references six stages | **REJECTED** — docs/ is git-ignored; out of scope for this PR. | No action |
| 11 | `test_orchestrate.py` needs parser coverage for stage 7 | **PARTIALLY ACCEPTED** — The existing `run_all` test already iterates `orchestrate.STAGE_ORDER` dynamically, so adding the stage to the tuple is sufficient. | T3 covers membership; existing tests cover run-all |
