# Coding Log: Campaign ledger success closure

## Session summary

- Started: 2026-08-15 10:20:54 +07
- Repository: `/Users/subhajlimanond/dev/munbon2-backend-campaign-ledger-success-closure`
- Branch: `fix/campaign-ledger-success-closure`
- Baseline: `4ac0c2b0a76151909020cd02c7001c566f209855`
- Upstream baseline: `origin/main@4ac0c2b0a76151909020cd02c7001c566f209855`
- Baseline status: clean after removing the session-generated RepoPrompt export; no user product changes were present
- Objective: close only the source harness/governance gap required before a future nine-stage campaign
- Protected state: the primary checkout, all pre-existing worktrees, historical campaign ledger bytes, frozen evidence, guests, campaign authority, deployments, activation, credentials, and AWS state

## DREP MUNBON-CAMPAIGN-LEDGER-SUCCESS-CLOSURE-V1

### Section 0: Repository profile

- Root: `/Users/subhajlimanond/dev/munbon2-backend-campaign-ledger-success-closure`
- Branch and HEAD: `fix/campaign-ledger-success-closure` at `4ac0c2b0a76151909020cd02c7001c566f209855`
- Applicable policy: root `AGENTS.md`, root `CLAUDE.md`, and root `CONTEXT.md`
- Required policy: TDD with a defect-specific RED; Python 3.11; preserve unrelated state; use an isolated worktree; primary owns contracts, tests, integration, gates, reviews, Coding Logs, Git, PR, merge, landing, and cleanup; no subagent edits product code outside the explicitly allowed implementer roles
- Scope language: Python 3.11, Markdown, and existing GitHub Actions YAML wiring
- Scoped gates:
  - `python3 -m pytest -q ops/control-plan-read-local/tests/test_orchestrate.py -k campaign_ledger`
  - `python3 -m pytest -q ops/control-plan-read-local/tests/test_orchestrate.py -k 'frontend_sha or partial_failure_cli'`
  - `python3 -m pytest -q ops/control-plan-read-local/tests/test_local_artifacts.py -k 'campaign_ledger or runbook'`
- Full affected gate:
  - `python3 -m pytest -q ops/control-plan-read-local/tests/test_stage_suite.py ops/control-plan-read-local/tests/test_orchestrate.py ops/control-plan-read-local/tests/test_seed_approved_sources.py ops/control-plan-read-local/tests/test_local_artifacts.py`
- Static gates:
  - `python3 -m black --check ops/control-plan-read-local/orchestrate.py ops/control-plan-read-local/tests/test_orchestrate.py ops/control-plan-read-local/tests/test_local_artifacts.py`
  - `python3 -m ruff check ops/control-plan-read-local/orchestrate.py ops/control-plan-read-local/tests/test_orchestrate.py ops/control-plan-read-local/tests/test_local_artifacts.py`
  - `python3 -m compileall -q ops/control-plan-read-local/orchestrate.py ops/control-plan-read-local/tests/test_orchestrate.py ops/control-plan-read-local/tests/test_local_artifacts.py`
  - `CODEX_ALLOW_LARGE_OUTPUT=1 git diff --check`
- Root Turbo gate: not applicable because canonical `CLAUDE.md` states this repository has no root workspace or Turborepo; the affected Python harness CI job is authoritative for this surface
- Migration policy: no database or data migration is permitted or required
- Previous Coding Log pointer: resolved to the completed PR #186 remediation log; this focused lifecycle creates and selects this new log rather than modifying the completed log
- External-model mode: g2 stateless DREP-only proposal was considered; Q1 prohibits delegation for this authorization/public-contract change, so no external packet is authorized or sent

### Section 1: Goal, non-goals, and success

The validator must be able to represent a genuine terminal nine-stage success without weakening either existing hash-chained failure record. The same PR removes reusable stale frontend-SHA guidance, records truthful next-step boundaries, and keeps operational acceptance separate from source delivery.

Non-goals:

- Do not append a synthetic or fabricated successful campaign row.
- Do not alter either existing ledger line, hash, candidate, evidence identity, or outcome.
- Do not refresh the Smart CMS candidate, run State A/B gates, provision or replace a guest, authorize a rehearsal/campaign, run stages, collect runtime evidence, deploy, activate, or touch AWS.
- Do not add a parallel JSON Schema, refactor the validator architecture, or modify the CI workflow unless a failing wiring test proves it necessary.

Locked public contract:

- New serialized authorization state: `successful_closed`.
- A successful entry is valid only when `outcome.acceptance is True`, `passed == list(STAGE_ORDER)`, `failed == []`, `unreached == []`, `evidence.index_name == "OUTER-SHA256SUMS"`, and authorization is `successful_closed` with exact positive integer `attempt` and `ceiling` satisfying `attempt <= ceiling`.
- Existing failure entries remain valid only under their current ordered single-failure partition and `historical_closed` or `exhausted` authorization rules.
- A success/failure outcome paired with the other authorization family fails with `campaign_ledger_schema_invalid`.
- `--frontend-sha` has no reusable historical default. Source-resolving actions without a lowercase 40-hex value fail with `frontend_sha_not_accepted` before repository SHA inspection. `validate-campaign-ledger` and `collect-bootstrap-failure` keep their early independent behavior.
- The runbook uses an explicit accepted-SHA placeholder and labels historical SHAs as evidence identities, not defaults.

Measurable success:

- A synthetic valid success entry passes the validator and append-only extension check.
- Near-success hybrids, partial evidence indexes, invalid attempt metadata, reordered/duplicate/partial stage sets, and crossed authorization states fail closed.
- The checked-in ledger still contains exactly the same two validated failure entries and terminal hash.
- The stale CLI default and active runbook assignment are absent; historical SHA evidence remains documented.
- Focused, full affected, static, three-repeat, QCHECK, and formal `g-check` gates pass before delivery.

Compatibility and rollback:

- The validator change is additive for future rows and preserves all current bytes. Older code will reject a future `successful_closed` row, but this PR appends no row.
- Operational CLI callers that omitted `--frontend-sha` must now pass the explicitly accepted frontend `origin/main` SHA.
- Source rollback is a normal revert of the delivered commit before any future successful row is appended. No runtime or data rollback is needed for this PR.

### Section 2: Requirements

- `R1`: Accept exactly a complete nine-stage successful outcome with no failed or unreached stages.
- `R2`: Couple a successful outcome to `successful_closed` authorization with positive exact integer attempt metadata satisfying `attempt <= ceiling`.
- `R3`: Require successful evidence to reference `OUTER-SHA256SUMS`; reject partial or inner-only evidence indexes for success.
- `R4`: Preserve the exact validation, hashes, identities, outcomes, and byte order of both existing failure records.
- `R5`: Preserve existing failure semantics: one ordered failed stage plus ordered passed/unreached partition, with `historical_closed` or `exhausted` authorization only.
- `R6`: Remove the stale frontend SHA default and reject missing/malformed frontend SHAs before repository inspection for source-resolving actions.
- `R7`: Preserve frontend-independent CLI actions without requiring a frontend repository or SHA.
- `R8`: Correct active runbook frontend-SHA guidance without deleting legitimate historical evidence identities.
- `R9`: Replace stale next-work prose with the truthful boundary: all nine current acceptance stages are implemented, no current 9/9 evidence exists, and rehearsal/campaign/guest/deployment/activation actions require separate authority.
- `R10`: Preserve CI path triggers, affected pytest invocation, full-history checkout, base-commit guard, and append-only validator invocation.
- `R11`: Do not append successful evidence or mutate operational state in this source PR.

### Section 3: File contract

| ID | Path | Action | Anchor | Exports/contracts | Purpose |
| --- | --- | --- | --- | --- | --- |
| `F1` | `ops/control-plan-read-local/orchestrate.py` | MODIFY | `validate_campaign_ledger()`, `_parse_args()`, `main()` | signatures unchanged; serialized state gains `successful_closed`; CLI default removed | enforce exact success/failure variants and explicit frontend identity |
| `F2` | `ops/control-plan-read-local/tests/test_orchestrate.py` | MODIFY | `_campaign_ledger_entry()` and campaign/CLI tests | test-only helpers | lock RED, anti-weakening cases, immutable ledger, and CLI behavior |
| `F3` | `ops/control-plan-read-local/tests/test_local_artifacts.py` | MODIFY | `test_all_stages_runbook_locks_local_before_aws_and_documents_current_commands()` | test contract only | lock durable runbook guidance and authority boundaries |
| `F4` | `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md` | MODIFY | Provision and Next local work sections | operator guidance | remove stale reusable SHA and stale implementation instruction |
| `F5` | `coding-logs/2026-08-15-10-20-54 Coding Log (campaign-ledger-success-closure).md` | CREATE | whole file | lifecycle artifact | preserve DREP, RED/GREEN, gates, reviews, and landing evidence |
| `F6` | `.codex/coding-log.current` | MODIFY | one-line pointer | lifecycle pointer | direct formal review to this lifecycle |

Explicitly unchanged: `docs/operations/control-plan-campaign-ledger.jsonl`, `.github/workflows/control-plane-hardening-tests.yml`, migrations, fixtures outside `F2`, services, contracts, deployment files, and evidence archives.

### Section 4: Function contract

`FN1 validate_campaign_ledger(path: Path) -> list[dict]`

- File: `F1`
- Does: parse exact JSONL objects, validate either the existing ordered failure variant or the new complete success variant, then verify hash chaining and canonical entry hashes.
- Pre: caller supplies a readable UTF-8 ledger path.
- Post: returns entries unchanged and ordered only when every row satisfies its exact variant and chain.
- Errors: retains `campaign_ledger_invalid`, `campaign_ledger_schema_invalid`, `campaign_ledger_chain_invalid`, and `campaign_ledger_entry_hash_invalid` distinctions.
- Invariants: campaign IDs are unique; schema keys are exact; success and failure variants cannot mix; every current historical row remains valid.
- Callers: `validate_campaign_ledger_append_only()` and CLI `main()` action `validate-campaign-ledger`.

`FN2 _parse_args(argv: list[str] | None = None) -> argparse.Namespace`

- File: `F1`
- Does: parse existing actions and flags while leaving `frontend_sha` unset when omitted.
- Pre: argv follows the existing CLI vocabulary.
- Post: no historical frontend SHA is synthesized.
- Errors: argparse behavior remains unchanged for invalid flags/actions.
- Invariants: frontend-independent actions remain parseable without `--frontend-sha`.
- Callers: `main()` and direct parser tests.

`FN3 main(argv: list[str] | None = None) -> int`

- File: `F1`
- Does: preserve early frontend-independent actions, then validate frontend SHA syntax before backend/frontend repository inspection and exact origin comparison.
- Pre: argv was accepted by `_parse_args()`.
- Post: source-resolving actions use one explicit accepted frontend SHA; missing or malformed values return 1 and print `FAIL orchestration: frontend_sha_not_accepted`.
- Errors: existing `OrchestrationError` mapping to machine-readable failure output remains unchanged.
- Invariants: no operational action proceeds with a missing, malformed, or stale frontend identity.
- Callers: module `__main__` and tests.

### Section 5: Test contract

`T1 test_validate_campaign_ledger_accepts_complete_successful_closed_entry`

- File: `F2`
- Covers: `R1`, `R2`, `R3`
- Type: unit
- Arrange: one synthetic canonical entry using all nine `STAGE_ORDER` values, empty failed/unreached lists, `acceptance=True`, `OUTER-SHA256SUMS`, and `successful_closed` attempt 1 of 3.
- Act: call `validate_campaign_ledger()`.
- Assert: returned structure equals the independently built entry.
- RED command: `python3 -m pytest -q ops/control-plan-read-local/tests/test_orchestrate.py -k successful_closed`
- RED proof: current validator raises `campaign_ledger_schema_invalid` because it accepts only `acceptance=False` and failure authorization states.
- GREEN command: same.
- Edge cases: exact boolean identity, complete order, and positive attempt below ceiling.

`T2 test_validate_campaign_ledger_rejects_invalid_successful_closed_entry`

- File: `F2`
- Covers: `R1`, `R2`, `R3`, `R5`
- Type: parameterized unit
- Arrange: rehashed mutations covering acceptance false, partial/reordered/duplicate stages, failed/unreached members, crossed authorization state, null/boolean/zero/negative/excess attempt metadata, and partial/inner-only evidence index.
- Act: validate each ledger.
- Assert: exact `campaign_ledger_schema_invalid`.
- RED command: included in the `successful_closed` selector.
- RED proof: anti-weakening cases already fail before implementation; they become regression guards when the positive behavior is added.
- GREEN command: same.
- Edge cases: JSON booleans are not integers; attempt may be below ceiling but never exceed it.

`T3 test_validate_campaign_ledger_append_only_accepts_success_after_failure_history`

- File: `F2`
- Covers: `R1`, `R4`, `R10`
- Type: unit
- Arrange: two failure entries as base bytes plus a chained synthetic success row in current bytes.
- Act: call `validate_campaign_ledger_append_only()`.
- Assert: all three entries return and base bytes remain the exact prefix.
- RED command: campaign-ledger selector.
- RED proof: current schema rejects the success row.
- GREEN command: campaign-ledger selector.
- Edge cases: existing rewrite rejection remains unchanged.

`T4 test_checked_in_campaign_ledger_is_valid`

- File: `F2`
- Covers: `R4`, `R5`, `R11`
- Type: repository contract
- Arrange: checked-in two-line ledger.
- Act: validate it and project exact identities/outcomes.
- Assert: exact two entries and terminal hashes already pinned; add an explicit entry-count/authorization projection only if it strengthens, never weakens, current assertions.
- RED command: campaign-ledger selector.
- RED proof: existing GREEN preservation test; it must stay GREEN throughout.
- GREEN command: campaign-ledger selector.
- Edge cases: no third synthetic repository row.

`T5 test_main_requires_explicit_frontend_sha_before_repo_inspection`

- File: `F2`
- Covers: `R6`
- Type: unit/CLI
- Arrange: a source-resolving action without `--frontend-sha` and repository lookup doubles that must not be called.
- Act: call `main()`.
- Assert: return 1, exact failure output, zero repository lookup calls.
- RED command: `python3 -m pytest -q ops/control-plan-read-local/tests/test_orchestrate.py -k 'frontend_sha or partial_failure_cli'`
- RED proof: current parser injects a historical SHA and `main()` performs repository lookup.
- GREEN command: same.
- Edge cases: malformed string fails through the same early contract.

`T6 existing frontend-independent CLI tests`

- File: `F2`
- Covers: `R7`
- Type: unit/CLI regression
- Arrange: `validate-campaign-ledger` and `collect-bootstrap-failure` without frontend flags; update partial-failure source-resolving test to pass an explicit SHA.
- Act: call `main()`.
- Assert: independent actions retain current results; partial failure receives its explicit identity.
- RED command: relevant focused selectors.
- RED proof: preservation/update coverage; current independent tests remain GREEN.
- GREEN command: relevant focused selectors.
- Edge cases: missing action-specific paths keep their existing errors.

`T7 test_all_stages_runbook_locks_local_before_aws_and_documents_current_commands`

- File: `F3`
- Covers: `R8`, `R9`, `R11`
- Type: static contract
- Arrange: read the tracked runbook.
- Act: inspect bounded active guidance and command counts.
- Assert: explicit accepted frontend placeholder and authority separation exist; obsolete active assignment and stale `implement LOCAL-WRITE-UI-1` instruction are absent; historical evidence SHA remains allowed; 12 command references remain.
- RED command: `python3 -m pytest -q ops/control-plan-read-local/tests/test_local_artifacts.py -k runbook`
- RED proof: current active assignment and stale next-work sentence violate the new assertions.
- GREEN command: same.
- Edge cases: do not globally ban historical SHA text.

`T8 test_campaign_ledger_ci_fetches_and_requires_the_base_commit`

- File: existing `F3` test
- Covers: `R10`
- Type: static wiring contract
- Arrange/Act: inspect the exact harness workflow job.
- Assert: existing fetch-depth, base guard, test invocation, and append-only command remain wired.
- RED proof: existing GREEN preservation test.
- GREEN command: local-artifacts campaign selector.
- Edge cases: workflow stays unchanged.

### Section 6: Traceability

| Requirement | Realized by function and call/statement | Tests | Files | Slice |
| --- | --- | --- | --- | --- |
| `R1` | `validate_campaign_ledger()` exact success outcome predicate | `T1,T2,T3` | `F1,F2` | `S1,S2` |
| `R2` | `validate_campaign_ledger()` coupled `successful_closed` authorization predicate | `T1,T2` | `F1,F2` | `S1,S2` |
| `R3` | `validate_campaign_ledger()` success evidence-index predicate | `T1,T2` | `F1,F2` | `S1,S2` |
| `R4` | unchanged chain/hash validation and checked-in ledger bytes | `T3,T4` | `F1,F2` | `S1,S2` |
| `R5` | unchanged failure partition and authorization predicates | `T2,T4` | `F1,F2` | `S1,S2` |
| `R6` | `_parse_args()` unset default and `main()` pre-lookup syntax guard | `T5` | `F1,F2` | `S1,S2` |
| `R7` | `main()` early action branches | `T6` | `F1,F2` | `S1,S2` |
| `R8` | runbook Provision assignment/guidance | `T7` | `F3,F4` | `S3` |
| `R9` | runbook Current result and Next local work boundary | `T7` | `F3,F4` | `S3` |
| `R10` | workflow path filters, full-history checkout, pytest and append-only steps | `T3,T8` | `F2,F3` plus unchanged workflow | `S1,S3` |
| `R11` | unchanged checked-in ledger plus explicit runbook/log non-goal | `T4,T7` | `F2,F4,F5` | `S1,S3` |

### Section 7: Wiring

| Component | Non-test runtime caller | Registration/config load | Schema/contract evidence |
| --- | --- | --- | --- |
| `validate_campaign_ledger()` | CLI `main()` and `validate_campaign_ledger_append_only()` | same module; workflow invokes CLI | `T1-T4`, exact checked-in rows, workflow append-only gate |
| `_parse_args()` frontend identity | module `__main__` to `main()` | argparse flag `--frontend-sha` | `T5,T6`, all 12 runbook commands |
| runbook frontend variable | operator command sequence | shell variable passed to every source-resolving command | `T7` and exact command-count assertions |
| existing CI harness | GitHub pull-request/push path filters | `control-plan-local-harness-tests` | `T8`, full-history checkout, base-ledger comparison |

No component is created or moved. The workflow already covers every changed source/doc/test path and runs both affected test files.

### Section 8: Slice plan

DeepSeek budget: `0`

Selected DeepSeek slice: `NONE`

| ID | Requirements/files/tests | Mode | Q0-Q3 result | Stop line | Production allowlist | Oracle | Done when |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `S1` | acceptance tests and immutable-history guards; `R1-R7,R10,R11`; `F2`; `T1-T6` | `PRIMARY` | Q1: tests, public serialized contract, and authorization semantics are primary-owned | `PRIMARY` | none | exact RED/GREEN commands | expected RED is proven and assertions locked |
| `S2` | validator and CLI implementation; `R1-R7`; `F1`; `T1-T6` | `PRIMARY` | Q1: authorization/governance validator and public state are prohibited for DeepSeek | `PRIMARY` | none | `T1-T6` | focused GREEN and complete primary diff audit pass |
| `S3` | runbook/tests/lifecycle; `R8-R11`; `F3-F6`; `T7,T8` | `PRIMARY` | Q1: documentation, lifecycle artifacts, authority boundaries, and Git are primary-only | `PRIMARY` | none | static contracts and formal review | runbook, wiring, Coding Log, reviews, and delivery are complete |

Q0 evidence: explicit g2 invocation and isolated primary-owned worktree exist; local route health will be checked. Q1 is decisive before any proposal: the change defines authorization/governance semantics and a public serialized state. Therefore no proposal bundle, egress manifest, durable receipt, or DeepSeek request is permitted for this DREP/PR.

### Section 9: Gates, review, rollout, and rollback

1. Run local-only `g2-doctor` and record route status without external probe.
2. Author `T1-T8` changes on the primary and prove the exact REDs.
3. Implement `F1` and `F4` minimally on the primary.
4. Run all scoped GREEN commands.
5. Run the full affected four-file harness gate.
6. Run Black check, Ruff, compileall, and diff check.
7. Run the combined affected campaign/parser/runbook scope three consecutive times.
8. Verify workflow path filters, test-file invocation, fetch depth, base guard, append-only CLI, unchanged workflow hash, unchanged ledger hash, and exact two-entry validation.
9. Run skeptical QCHECK against the root function, test, and implementation checklists; disposition every concern.
10. Run formal `g-check` on the working-tree/commit scope and append its report here; remediate and rerun when material.
11. Commit with a Conventional Commit, push the branch, create one standard GitHub PR, inspect required checks, and admin-merge only after source/test/review/conflict requirements are satisfied. Hosted billing-lock evidence, if it recurs, remains unavailable rather than passing.
12. Fetch the merge, make local `main == origin/main` at the exact merge SHA, verify the merge tree matches the reviewed candidate, audit retained artifacts, remove this session worktree, prune, and prove the primary checkout remains clean.

Rollout: source-only merge. No flag, guest, campaign, database, deployment, activation, AWS, or production action.

Rollback: revert the source commit/merge before a future successful row is appended. If a successful row is later appended under this schema, validator rollback requires preserving reader compatibility and is outside this PR.

### Adversarial challenge disposition

- Accepted: success must require the complete `OUTER-SHA256SUMS` evidence index, never a partial-failure index.
- Accepted: remove both the runbook's stale active SHA and the parser's stale default; do not replace either with another soon-stale SHA.
- Accepted: add anti-weakening success/failure authorization and stage-partition cases.
- Accepted: preserve the two checked-in historical failure rows and the append-only byte-prefix gate.
- Rejected: append a third checked-in success row during this PR. No genuine 9/9 evidence exists; a synthetic row would fabricate operational acceptance.
- Resolved naming ambiguity: use the literal `successful_closed`, matching the requested successful/closed vocabulary; do not accept aliases.
- Resolved attempt semantics: a successful campaign may close before its ceiling, so require exact positive integers with `attempt <= ceiling`; `exhausted` alone requires equality.

### Section 10: Do-not-touch and baseline

- Do not modify `docs/operations/control-plan-campaign-ledger.jsonl`; baseline SHA-256 `45970d9a2240eb2090a7958d9add373fb5ec4ef6068b38d04ae4ac22ce4f4261`.
- Do not modify `.github/workflows/control-plane-hardening-tests.yml`; baseline SHA-256 `61c26167e169bd327d1f4697197f0675d3f78a3d656e7544227f03fde2a0c336`.
- Acceptance tests become locked after confirmed RED; no later weakening, fixture substitution, skips, or test-only bypasses.
- Do not modify migrations, contracts, services, fixtures outside `F2`, evidence archives, guests, campaign state, deployment state, credentials, AWS state, Git history, primary checkout changes, or any pre-existing worktree.
- Baseline source hashes:
  - `orchestrate.py`: `c52903ebf0d0d8815b93eb03b9a5c66b4aa2eff863e5c0e5c3841a85f929382d`
  - `test_orchestrate.py`: `c26cbb7fca7890601393869acd726869b792a724d696e384553d94ec2e6c0b6e`
  - `test_local_artifacts.py`: `9caef279263474670cfa89f49730851b7f0251df58508123700c46ad03fd1557`
  - runbook: `a88cac0ffb237aa60042aebf5c1ac8e6f673556336698147ac958c818037ccd7`
- Complete changed-file audit after implementation must contain only `F1-F6`; any ledger/workflow/operational file change is a stop condition.

## Planning status

- g2-planning instructions loaded: yes
- RepoPrompt bound root confirmed: `/Users/subhajlimanond/dev/munbon2-backend-campaign-ledger-success-closure`
- RepoPrompt discovery: one focused context build from the exact baseline plus focused primary revalidation
- DeepSeek budget: 0
- DeepSeek request invoked: no
- Standalone g2-check available: no; existing formal `g-check` is selected
- DREP disposition: decision-complete and ready for primary-owned RED

## g2-coding preflight and RED

- Bound RepoPrompt root: `/Users/subhajlimanond/dev/munbon2-backend-campaign-ledger-success-closure`
- DREP baseline and candidate HEAD: both `4ac0c2b0a76151909020cd02c7001c566f209855`
- Discovery path: reused the exact-baseline focused Context Builder evidence, then primary-read `CONTEXT.md`, validator/schema, strict collection, CLI parser/dispatch, campaign tests, runbook contract test, tracked runbook/ledger, and harness workflow wiring
- Local-only g2 doctor: PASS with 0 failures; Codex CLI, Keychain presence, proxy health, model metadata, agent definition, and registration passed; external Native Responses and provider tool-round probes were intentionally skipped because DeepSeek budget is 0
- DeepSeek budget reconfirmed: 0; selected slice NONE; no packet compiled; no external request or durable receipt created
- Single product-code writer: primary only
- Protected baseline ledger SHA-256: `45970d9a2240eb2090a7958d9add373fb5ec4ef6068b38d04ae4ac22ce4f4261`
- Protected workflow SHA-256: `61c26167e169bd327d1f4697197f0675d3f78a3d656e7544227f03fde2a0c336`

### Locked acceptance-test hashes

- `ops/control-plan-read-local/tests/test_orchestrate.py`: `cb9038aa608b5e1364303743a19549b34a4442b863f8781cf52f62b60fd38e88`
- `ops/control-plan-read-local/tests/test_local_artifacts.py`: `23e6a0c3419a867b2cebf27cdea5d65e8b8945da99c7c2e4301dff20eecddf7f`

### RED evidence

1. `python3 -m pytest -q ops/control-plan-read-local/tests/test_orchestrate.py -k successful_closed`
   - Result: 1 failed, 11 passed, 84 deselected.
   - Expected failure: positive success fixture reached `validate_campaign_ledger()` and raised `campaign_ledger_schema_invalid`; no setup/import/hash failure occurred.
2. `python3 -m pytest -q ops/control-plan-read-local/tests/test_orchestrate.py -k campaign_ledger`
   - Result: 2 failed, 28 passed, 66 deselected.
   - Expected failures: direct success validation and append-only success extension both reached the current failure-only schema and raised `campaign_ledger_schema_invalid`; existing history tests passed.
3. `python3 -m pytest -q ops/control-plan-read-local/tests/test_orchestrate.py -k 'frontend_sha or partial_failure_cli'`
   - Result: 2 failed, 2 passed, 92 deselected.
   - Expected failure: missing and malformed frontend values both invoked `_origin_main_sha`; the locked contract requires `frontend_sha_not_accepted` before repository inspection.
4. `python3 -m pytest -q ops/control-plan-read-local/tests/test_local_artifacts.py -k runbook`
   - Result: 1 failed, 42 deselected.
   - Expected failure: active runbook still contains the stale frontend assignment and lacks the locked corrected guidance.

The only warning was the pre-existing pytest-asyncio default-loop-scope deprecation from the machine Python 3.13 environment. It did not affect collection or the expected failures. Production implementation may now begin; the acceptance assertions are locked.

## GREEN and integration evidence

### Implementation

- `validate_campaign_ledger()` now computes exact coupled variants instead of broadening the existing failure predicate:
  - failure: current ordered single-failure partition plus `historical_closed` or `exhausted`;
  - success: exact nine-stage ordered pass, zero failed, zero unreached, `acceptance=True`, complete outer index, and `successful_closed` with exact positive integer attempt metadata.
- `_parse_args()` no longer synthesizes a historical frontend SHA.
- `main()` preserves frontend-independent early actions, then rejects missing/malformed frontend identity before repository inspection.
- The runbook uses a reviewed-SHA placeholder, labels historical SHAs as evidence identities, preserves the truthful current 2/1/6 result, and replaces the stale WRITE-UI instruction with the separate-authority boundary.
- The checked-in campaign ledger and harness workflow were not edited.

### Focused GREEN

- Campaign-ledger scope: 34 passed after QCHECK remediation.
- Frontend-SHA/partial-failure CLI scope: 4 passed.
- Runbook scope: 1 passed.
- Campaign/runbook wiring scope: 2 passed.

### Authoritative Python 3.11 gate

- The machine `python3.11` binary was 3.11.12 but its global environment lacked pytest, so the first direct attempt was correctly classified as setup failure and not gate evidence.
- A disposable `/tmp/munbon-ledger-gate.u3sbnO/venv` was created with Python 3.11.12 and the CI-pinned `services/ros-gis-integration/requirements.txt`.
- Full affected harness command: `/tmp/munbon-ledger-gate.u3sbnO/venv/bin/python -m pytest -q ops/control-plan-read-local/tests/test_stage_suite.py ops/control-plan-read-local/tests/test_orchestrate.py ops/control-plan-read-local/tests/test_seed_approved_sources.py ops/control-plan-read-local/tests/test_local_artifacts.py`.
- Final result after QCHECK remediation: 465 passed in 2.07 seconds.

### Static and stability gates

- Black check on all three changed Python files: PASS.
- Ruff check on all three changed Python files: PASS.
- Python 3.11 compileall on all three changed Python files: PASS.
- `CODEX_ALLOW_LARGE_OUTPUT=1 git diff --check`: PASS.
- Campaign ledger CLI validation: PASS.
- Final affected stability scope: 39 passed, 104 deselected on each of three consecutive Python 3.11 runs.
- The pinned CI requirements do not include Black or Ruff; attempts inside the disposable venv reported those modules unavailable. The installed machine Black and Ruff commands passed and are the formatter/linter evidence.

### Final hashes before formal review

- `test_orchestrate.py`: `99ee978c9fefb0d14c9741cca6f01392946131b38a225f0a7b7f10cacece8e7d`
- `test_local_artifacts.py`: `9dfb7bc916ebf55f521ebd076c4cf980347597b6dbb2718543f031b040f224f7`
- `orchestrate.py`: `9c4b315586c7af06f3414366475b0af0eb2aed9c614ce97db1be44ef893418e3`
- runbook: `3132c6ec9798d4571e21937c5d75d47ec572567d2943a3046fcb425399e47b21`
- protected ledger unchanged: `45970d9a2240eb2090a7958d9add373fb5ec4ef6068b38d04ae4ac22ce4f4261`
- protected workflow unchanged: `61c26167e169bd327d1f4697197f0675d3f78a3d656e7544227f03fde2a0c336`

## Formal g-check report (2026-08-15 10:52 +07)

Scope: staged working tree on `fix/campaign-ledger-success-closure`, based on `4ac0c2b0a76151909020cd02c7001c566f209855`.

Review inputs and commands:

- Published staged-diff snapshots `2026-08-15/1041`, `2026-08-15/1046`, and final `2026-08-15/1049` through RepoPrompt.
- Reviewed validator consumers, CLI dispatch ordering, checked-in ledger invariants, workflow wiring, runbook authority boundaries, and test oracles.
- Ran the focused contract scope, full affected Python 3.11 harness, Black, Ruff, compileall, and diff-check after every accepted functional/test remediation.

Findings by severity:

- CRITICAL: none.
- HIGH: none.
- MEDIUM: none unresolved. The initial runbook authority/ledger contradiction was accepted and remediated.
- LOW: none unresolved. Raw-byte identity, audit-hash freshness, and static closing-language coverage findings were accepted and remediated.

Final disposition: no actionable findings remain.

Residual risks and rollout notes:

- Hosted GitHub Actions is not currently independent acceptance evidence; local Python 3.11 gates are the available source gate unless hosted checks become runnable.
- No genuine successful operational row exists. The success schema is exercised synthetically and grants no campaign, guest replacement, deployment, activation, promotion, AWS, WRITE-ACT, or RC authority.
- Older validator versions reject future `successful_closed` rows; validator delivery must precede any separately authorized successful campaign ledger append.

The post-RED test hash changed only through primary-owned strengthening: explicit crossed authorization, duplicate-stage, negative-attempt and immutable nine-stage literal coverage, followed by the accepted QCHECK regression test. No positive oracle or expected production behavior was weakened.

## QCHECK (2026-08-15 10:35 +07)

### Independent non-DeepSeek review

Finding:

- P2: no direct test proved the workflow's `validate-campaign-ledger` CLI action remained ahead of the new frontend-SHA guard, although the workflow intentionally omits frontend flags.

Disposition: accepted and remediated. Added `test_validate_campaign_ledger_cli_does_not_require_frontend_repo`, which makes repository inspection fail the test, invokes the CLI action without frontend flags, and asserts `PASS campaign_ledger`. Focused campaign scope increased to 34 passed and the full affected gate increased to 465 passed.

No other functional defect was found. The reviewer independently confirmed exact nine-stage ordering, empty failed/unreached lists, complete outer index, positive non-boolean attempt metadata, preserved failure variants, unchanged checked-in rows, and truthful runbook boundaries.

### Primary function checklist

- `validate_campaign_ledger()` remains a linear, readable validation flow. Named booleans make the success/failure alternatives explicit without introducing a new class or a one-use extracted function.
- Exact list equality is the appropriate data structure/algorithm for the nine-stage ordered partition; no nested search or mutable global state was introduced.
- No unused parameters, unnecessary casts, new hidden dependencies, I/O seams, or mocks were added to production code.
- Names considered included `valid_success_outcome`, `is_successful_outcome`, and `successful_outcome_is_valid`; the selected names read consistently with the coupled authorization predicates.
- `_parse_args()` and `main()` retain their existing domain vocabulary and failure code.

### Primary test checklist

- Inputs are parameterized and every case can fail for a real broadening defect.
- The positive assertion compares the complete returned structure to an independently built entry and pins the literal nine-stage order rather than reusing the production constant as the sole oracle.
- Negative cases cover acceptance mismatch, crossed authorization, partial/failed/unreached stages, reorder, duplicate, null/boolean/zero/negative/excess attempts, and partial/inner-only indexes.
- The checked-in test retains exact candidate, guest, evidence, entry-hash, outcome, and authorization projections for both immutable failure entries.
- CLI tests assert exact return/output and prove repository lookups are absent on the relevant early paths.
- Tests do not assert type-checker-only behavior, skip code, weaken existing assertions, or reuse validator output as the oracle.

### Primary implementation checklist

- TDD RED was confirmed for success schema, append-only success, frontend guard order, and runbook guidance before production/doc changes.
- Change scope is limited to the DREP's validator, CLI, tests, runbook, Coding Log, and pointer.
- No new service, shared abstraction, database, migration, runtime mutation, or operational evidence was introduced.
- Canonical Python 3.11 affected tests, formatter, linter, compile, diff, wiring, and three-repeat gates pass.

QCHECK disposition: no unresolved findings. Formal `g-check` may begin.

## Formal review remediation evidence (2026-08-15 10:49 +07)

The first formal staged-diff review found two actionable gaps:

- P1: the runbook's closing sentence incorrectly implied that only successful 9/9 campaigns extend the ledger and did not repeat the separate `LOCAL-RC-1` prerequisite for promotion.
- P2: the checked-in-ledger test pinned semantic fields and canonical entry hashes but not the protected file's exact bytes.

Both were accepted and remediated. The runbook now requires every authorized success or failure outcome to be recorded with its checksum-bound evidence, while promotion separately requires genuine 9/9 evidence, authorized passing `LOCAL-RC-1`, and promotion/AWS authorization. The checked-in-ledger test now pins the exact raw-byte SHA-256 before semantic validation.

The second formal review confirmed those findings resolved and found two further P2 audit-strength gaps: the earlier hashes were pre-remediation, and the static runbook test did not lock the corrected closing authority language. Both were accepted. The test now requires the success/failure ledger clause, `LOCAL-RC-1`, and promotion/AWS separation and forbids the old conflating sentence.

Post-remediation authoritative evidence:

- Focused contract scope: 39 passed, 104 deselected.
- Full affected Python 3.11 harness: 465 passed.
- Black check: PASS.
- Ruff check: PASS.
- Python 3.11 compileall: PASS.
- `CODEX_ALLOW_LARGE_OUTPUT=1 git diff --check`: PASS.
- `test_orchestrate.py`: `8abfdd3d6bd18ba9984ff1e9a54bb3ccde52275ad15d1d26161372a363e356a7`
- `test_local_artifacts.py`: `89b20f161748c979ed86eafefb843620ab2cff8a2cdb2f77e72a1b44e6e93401`
- `orchestrate.py`: `9c4b315586c7af06f3414366475b0af0eb2aed9c614ce97db1be44ef893418e3`
- runbook: `d4786062391be1be776f67c2ccfeef0fce750faeaa22a8773824786accef53ae`
- protected ledger unchanged: `45970d9a2240eb2090a7958d9add373fb5ec4ef6068b38d04ae4ac22ce4f4261`
- protected workflow unchanged: `61c26167e169bd327d1f4697197f0675d3f78a3d656e7544227f03fde2a0c336`
