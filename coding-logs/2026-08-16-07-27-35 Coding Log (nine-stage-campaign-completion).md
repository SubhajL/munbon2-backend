# Coding Log: nine-stage campaign completion

Started: 2026-08-16 07:27:35 +0700
Session worktree: /Users/subhajlimanond/dev/munbon2-backend-9of9-canonical-campaign
Branch: ops/9of9-canonical-campaign
Baseline: 27c5558dda2139ccd2e84f19616c56401fff4427
Goal: complete the remaining path from PR #188 source closure through a structurally non-authoritative three-stage rehearsal, a separately authorized pristine canonical nine-stage campaign, genuine 9/9 collection, one append-only successful_closed ledger row, reviewed delivery, exact local-main landing, and worktree cleanup.

## Reconciliation

- Step 1 of the supplied path is complete. PR #188 merged at 27c5558dda2139ccd2e84f19616c56401fff4427 and added the exact successful_closed ledger variant, explicit frontend SHA handling, regression tests, and corrected runbook language.
- The checked-in ledger remains intentionally unchanged at two failure rows with raw SHA-256 45970d9a2240eb2090a7958d9add373fb5ec4ef6068b38d04ae4ac22ce4f4261.
- The latest historical campaign is exhausted at attempt 3 of ceiling 3. Its preserved canonical guest is not pristine and is bound to the old candidate with two passed stages, one failed stage, and six unreached stages.
- Backend main and origin/main are clean and equal to the PR #188 merge SHA.
- Smart CMS main and origin/main currently resolve locally to 067b3e22401854f8c6d6db42dc0c5c1872fca6f8, but its primary checkout has unrelated Coding Log changes. Candidate gates must run from a new clean detached/isolated worktree after a fresh origin/main fetch.
- No new rehearsal grant or canonical grant exists. Source development and read-only candidate preparation do not imply guest creation, deletion, stage execution, or campaign authority.
- Current source can run canonical stages only on munbon-control-plan-local. It cannot run the required pristine BASE -> RTA -> AC rehearsal on a separate guest and cannot collect a successful three-pass prefix as structurally non-authoritative evidence.

## Plan Draft A: generalized execution profiles

### Overview

Add a general ExecutionSpec carrying execution kind, run ID, campaign identity, attempt, and ceiling through provisioning state, owner state, stage state, every stage manifest, and collectors. Add profile-aware versions of all operational CLI actions and a tested guest-retirement action.

### Files to change

- ops/control-plan-read-local/orchestrate.py: general execution object, profile-aware commands, rehearsal collector, retirement action.
- ops/control-plan-read-local/provisioning_contract.py: execution identity in every state transition.
- ops/control-plan-read-local/bootstrap-linux.sh: execution arguments and owner/state binding.
- ops/control-plan-read-local/run-stage-suite.py: execution identity in state and manifests.
- relevant tests and runbook.

### TDD sequence

1. Add tests for execution identity, two guest names, three-pass rehearsal evidence, cross-profile refusal, and exact-ID retirement.
2. Confirm focused RED failures arise from missing profile behavior.
3. Implement general profiles and identity propagation.
4. Refactor common collector validation only after GREEN.
5. Run the complete affected harness and static gates.

### Strengths

- Strong machine-readable identity across every artifact.
- Extensible to more rehearsal or campaign profiles.
- Automated retirement policy can reduce operator mistakes if OrbStack supports immutable-ID deletion.

### Weaknesses

- Changes stable canonical CLI and ephemeral schemas beyond the stated three-stage need.
- Adds public-contract and migration risk before an operational campaign.
- A wrapper around a name-based orb delete still cannot make the final mutation atomic.
- Larger review and rollback surface delays the required qualification.

### Decision completeness

Goal: general multi-profile orchestration.
Non-goals: stage algorithm changes, deployment, AWS, production.
Failure policy: fail closed on any identity or profile mismatch.
Rollout: source PR before any candidate or guest action.
Rollback: revert before profile guests exist; never resume profile guests with older code.

## Plan Draft B: additive fixed three-stage rehearsal

### Overview

Add exactly one fixed rehearsal execution kind and guest while preserving all canonical commands. Reuse the existing bootstrap and stage implementations for only LOCAL-BASE-0, LOCAL-RTA-1, and LOCAL-AC-1. Add a successful-prefix collector that emits acceptance_evidence=false and REHEARSAL-OUTER-SHA256SUMS and can never satisfy the campaign ledger.

### Files to change

- ops/control-plan-read-local/orchestrate.py
  - Add fixed canonical/rehearsal execution vocabulary and derived guest lookup.
  - Parameterize internal machine, guest, provision, stage, bootstrap-failure, and partial-failure helpers.
  - Add provision-rehearsal, run-rehearsal-stage, collect-rehearsal, collect-rehearsal-partial-failure, and collect-rehearsal-bootstrap-failure actions.
  - Add exact three-pass rehearsal finalization using shared evidence validation.
- ops/control-plan-read-local/bootstrap-linux.sh
  - Accept a closed execution kind, derive the fixed machine name, and add execution_kind plus acceptance_evidence=false to owner.json.
- ops/control-plan-read-local/run-stage-suite.py
  - Add execution_kind to StageContext and the parser.
  - Permit rehearsal dispatch only for BASE, RTA, and AC.
  - Derive the expected owner/machine in LOCAL-BASE-0 without duplicating any stage.
- ops/control-plan-read-local/tests/test_orchestrate.py
  - Lock host commands, profile selection, collection, recovery, anti-promotion, and unchanged canonical behavior.
- ops/control-plan-read-local/tests/test_stage_suite.py
  - Lock rehearsal owner/machine checks and the three-stage dispatch ceiling.
- ops/control-plan-read-local/tests/test_local_artifacts.py
  - Lock the exact rehearsal sequence, non-acceptance evidence, stop rules, and separate grants.
- docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md
  - Add exact rehearsal commands and the exact-ID canonical replacement preflight.
- this Coding Log and .codex/coding-log.current.

### TDD sequence

1. Add host command and parser tests for the fixed rehearsal guest and stage ceiling.
2. Run focused tests and confirm expected missing-behavior RED.
3. Parameterize the smallest shared host helpers and bootstrap owner fields.
4. Confirm focused GREEN before collector work.
5. Add three-pass rehearsal collector tests and confirm expected RED.
6. Implement shared validation plus rehearsal summary/index.
7. Add failure-recovery and ledger anti-promotion tests.
8. Update runbook/static tests.
9. Run affected gates, three repeated focused runs, QCHECK, and formal g-check.

### Test coverage

- test_build_machine_command_uses_exact_rehearsal_guest: fixed isolated rehearsal shape.
- test_build_machine_command_rejects_unknown_execution_kind: closed execution vocabulary.
- test_provision_rehearsal_targets_only_rehearsal_guest: no canonical mutation.
- test_run_rehearsal_stage_accepts_base_rta_ac: exact ordered rehearsal prefix.
- test_run_rehearsal_stage_rejects_later_stages: no accidental canonical continuation.
- test_bootstrap_owner_binds_rehearsal_non_acceptance: owner identity cannot promote.
- test_finalize_rehearsal_collection_accepts_exact_three_pass_prefix: correct successful rehearsal.
- test_finalize_rehearsal_collection_writes_only_rehearsal_outer_index: no canonical acceptance index.
- test_finalize_rehearsal_collection_rejects_later_or_failure_artifacts: exact inventory.
- test_collect_rehearsal_partial_failure_targets_rehearsal_guest: safe first-failure recovery.
- test_campaign_ledger_rejects_rehearsal_evidence_index: no ledger promotion.
- stage-suite rehearsal BASE and dispatch tests: real runtime owner/stage boundary.
- runbook static contract test: commands and separate authority remain exact.

### Decision completeness

Goal: structurally safe three-stage rehearsal using shared stage implementations.
Non-goals: general execution framework, canonical CLI changes, automated deletion, full rehearsal, campaign authority, deployment, AWS, production.
Success: a pristine fixed rehearsal guest can run only BASE/RTA/AC and produce checksum-bound acceptance_evidence=false evidence; canonical 9/9 remains unchanged.
Public interfaces: five additive host CLI actions and one internal guest --execution-kind argument.
Failure policy: fail closed on unknown kind, wrong fixed guest, wrong owner, later rehearsal stage, unexpected artifacts, or identity mismatch.
Rollout: merge source PR before selecting final candidate or requesting runtime authority.
Rollback: safe before a rehearsal guest exists; after creation, preserve its evidence and remove only with separate authority.

## Comparative synthesis

Draft A is stronger only for a future generalized campaign platform. It adds identity and retirement abstractions not required by the user's exact three-stage rehearsal and does not eliminate a name-based OrbStack deletion race. Draft B is smaller, additive, keeps canonical interfaces stable, reuses the existing stages, and creates the structural evidence boundary the goal actually requires.

Unified decision: implement Draft B. Do not add a retirement CLI unless native immutable-ID deletion or concurrent-operator protection becomes an explicit requirement. Canonical replacement remains a separately authorized, serialized procedure that verifies the exact granted guest ID, fixed name, shape, owner, candidate, dependency, stage prefix, failure manifest, and checksums immediately before and after the explicit OrbStack deletion command.

## Unified execution plan

### Phase 1: source enablement

1. Lock the DREP below and author acceptance tests.
2. Confirm RED for fixed rehearsal guest selection, three-stage ceiling, owner classification, and successful three-prefix collection.
3. Implement the minimum additive source changes.
4. Verify canonical commands and strict 9/9 collection are unchanged.
5. Run full affected gates, three repeated focused tests, independent QCHECK, and formal g-check.
6. Create one standard PR, use the standing billing-lock policy without investigation, admin-merge after local acceptance and mergeability checks, and land exact local main.

### Phase 2: candidate refresh

1. Re-fetch backend and frontend origin/main.
2. Create a clean isolated frontend worktree without touching the dirty primary checkout.
3. Require frontend main == origin/main at one full SHA.
4. Run npm run ci:local:all -- --base HEAD^ in the clean frontend worktree. This covers fully dark and V2-visible/write-dark State A/B modes with submit false.
5. Preserve its manifest and SHA256SUMS.
6. Freeze the post-source-PR backend SHA and the same frontend SHA.
7. Build and validate one offline dependency archive and record its SHA-256 and input manifest.

### Phase 3: separate rehearsal authority and execution

Required grant fields:

- scope local-three-stage-rehearsal
- exact backend SHA, frontend SHA, dependency SHA-256
- fixed guest munbon-control-plan-rehearsal
- current Bangkok as_of_date at execution
- permission to create that guest and later remove only its exact observed ID
- unique bootstrap/evidence destinations
- expiry and explicit exclusions for canonical ledger, deployment, activation, AWS, and production

Execution:

1. Provision one fresh rehearsal guest.
2. If provisioning fails, collect sanitized bootstrap evidence and stop.
3. Run BASE, RTA, and AC separately with one pinned as_of_date.
4. On first failure, issue no later stage and collect partial non-acceptance evidence.
5. On three passes, collect REHEARSAL-SUMMARY.json and REHEARSAL-OUTER-SHA256SUMS; require acceptance_evidence=false and no OUTER-SHA256SUMS.
6. Preserve evidence. Remove only the exact rehearsal guest if the grant includes cleanup.

### Phase 4: separate canonical authority and campaign

Required grant fields:

- new campaign ID
- attempt 1, ceiling 1 unless the ledger schema is separately extended
- exact backend/frontend/dependency identities
- rehearsal evidence reference and index hash
- exact current failed canonical guest name and observed immutable ID
- exact old owner/candidate/dependency and 2-pass/1-fail stage state
- permission to remove only that guest and create one replacement
- unique canonical bootstrap/evidence destinations
- current Bangkok as_of_date and clean RID weeks
- expiry and explicit exclusions for LOCAL-RC-1, promotion, deployment, activation, AWS, and production

Execution:

1. Validate ledger and old evidence.
2. Re-read Orb inventory and old guest owner/state/checksums; require exact grant match.
3. Validate Orb deletion syntax and stable ID availability.
4. Under single-operator serialization, re-read inventory immediately before deleting the fixed canonical name.
5. Verify the exact old ID/name is absent, then provision one fresh canonical guest.
6. Record the new canonical guest ID.
7. Dispatch all nine stages individually in STAGE_ORDER on the same guest/database/date.
8. On first failure, stop immediately, collect partial evidence, preserve guest, and close attempt 1/1 as exhausted through a separate closure decision.
9. On 9/9, run strict collect and verify every manifest, browser artifact, identity, checksum index, sanitization rule, dark flag, listener/process state, and no AWS action.

### Phase 5: successful closure PR

1. Freeze the successful evidence directory and OUTER-SHA256SUMS hash.
2. Verify the ledger still has the original two-row raw-byte prefix.
3. Append one canonical successful_closed row with nine passed, zero failed, zero unreached, attempt 1/1, exact new guest ID, and previous hash equal to row 2.
4. Update exact checked-in ledger assertions and the runbook current result.
5. Validate current and append-only ledger history against the candidate commit.
6. Run affected gates, QCHECK, formal g-check, standard PR, authorized admin merge, and exact local-main landing.
7. Preserve the successful canonical guest and evidence. Remove only session worktrees and temporary files.

## G2 DREP: MUNBON-9OF9-REHEARSAL-ENABLEMENT-V1

### 0. Repository profile

- Root: /Users/subhajlimanond/dev/munbon2-backend-9of9-canonical-campaign
- Branch: ops/9of9-canonical-campaign
- HEAD/baseline: 27c5558dda2139ccd2e84f19616c56401fff4427
- Baseline status: clean before this Coding Log and pointer.
- Protected user worktrees: munbon2-backend-pr3-roster-v1, munbon2-backend-pr4-rid-v2, munbon2-backend-write-ui-logout-transport, munbon2-backend-wui.
- Protected runtime: existing munbon-control-plan-local and every unrelated OrbStack guest; no runtime mutation in the source PR.
- Policies: global and repository AGENTS.md delegation/ownership; CLAUDE.md TDD, conventional commits, no secrets, no direct main push; CONTEXT.md irrigation scope.
- Languages: Python 3.11 plus Bash; no migration.
- Scoped gates: focused pytest selectors listed in T1-T12.
- Full affected gate: pytest on test_stage_suite.py, test_orchestrate.py, test_seed_approved_sources.py, and test_local_artifacts.py, plus any provisioning tests touched.
- Static gates: Black, Ruff, compileall, and diff check.
- Coding Log pointer: replaced by g-planning to this file.
- External-model mode: stateless proposal is explicitly permitted by g2 invocation, but DeepSeek budget is zero because the slice changes a public operational CLI, authorization/evidence boundary, and guest targeting. All production work is PRIMARY.

### 1. Goal, non-goals, and success

Goal: safely enable the exact three-stage non-authoritative rehearsal required before a new canonical campaign, without forking stage implementations or weakening canonical acceptance.

Non-goals:

- No full nine-stage rehearsal.
- No canonical guest deletion or runtime action in the source PR.
- No campaign authorization or ledger append in the source PR.
- No deployment, activation, promotion, LOCAL-RC-1, AWS, production, credential, database migration, or unrelated service change.
- No generalized execution framework or automatic guest-retirement API.

Measurable success:

- Only a fixed rehearsal guest can receive rehearsal actions.
- Rehearsal dispatch permits exactly BASE, RTA, and AC.
- Three passes generate checksum-bound acceptance_evidence=false evidence and never OUTER-SHA256SUMS.
- Failure recovery targets the rehearsal guest and stays non-authoritative.
- Existing canonical commands, strict nine-stage finalizer, ledger history, and workflow remain valid and byte-preserved where protected.

Public interface:

- Add provision-rehearsal.
- Add run-rehearsal-stage.
- Add collect-rehearsal.
- Add collect-rehearsal-partial-failure.
- Add collect-rehearsal-bootstrap-failure.
- Add internal guest --execution-kind canonical|rehearsal.
- No API, DB schema, message, env-var, or migration change.

Failure semantics: fail closed. Preserve the guest/evidence on any mismatch, bootstrap failure, stage failure, missing failure manifest, collector mismatch, or cleanup uncertainty.

Rollout: source PR first; then candidate gates; then a separately authorized rehearsal. Rollback before runtime is a normal source revert. After a new rehearsal guest exists, do not run older code against it; preserve evidence and require separate cleanup authority.

### 2. Requirements

- R1: Map only canonical and rehearsal execution kinds to fixed guest names.
- R2: Preserve exact isolated ARM64/Debian 12 machine shape for both kinds.
- R3: Provision rehearsal without reading, writing, or targeting the canonical guest.
- R4: Bind rehearsal execution_kind and acceptance_evidence=false in owner.json.
- R5: Allow rehearsal dispatch only for BASE, RTA, and AC.
- R6: Reuse existing BASE, RTA, and AC implementations.
- R7: Validate rehearsal owner, candidate, dependency, harness, and fixed guest identity.
- R8: Collect an exact successful three-pass prefix.
- R9: Emit REHEARSAL-SUMMARY.json with acceptance_evidence=false.
- R10: Emit REHEARSAL-OUTER-SHA256SUMS and never canonical OUTER-SHA256SUMS.
- R11: Reuse partial and bootstrap failure semantics against the rehearsal guest.
- R12: Reject rehearsal evidence as successful campaign-ledger evidence.
- R13: Keep all canonical command shapes and strict 9/9 behavior valid.
- R14: Document exact commands, separate authority, stop boundaries, and no-AWS/RC scope.

### 3. File contract

| ID | Path | Action | Anchor | Contract | Purpose |
| F1 | ops/control-plan-read-local/orchestrate.py | MODIFY | machine helpers, provision, run_stage, collectors, parser/main | additive rehearsal CLI | host orchestration |
| F2 | ops/control-plan-read-local/bootstrap-linux.sh | MODIFY | argument validation and owner.json | closed execution kind | guest owner binding |
| F3 | ops/control-plan-read-local/run-stage-suite.py | MODIFY | StageContext, run_local_base, parser/main | three-stage rehearsal ceiling | shared guest stages |
| F4 | ops/control-plan-read-local/tests/test_orchestrate.py | MODIFY | machine/provision/stage/collector tests | acceptance tests | host contract |
| F5 | ops/control-plan-read-local/tests/test_stage_suite.py | MODIFY | context/parser/BASE tests | acceptance tests | guest contract |
| F6 | ops/control-plan-read-local/tests/test_local_artifacts.py | MODIFY | runbook contract | static acceptance | operator wiring |
| F7 | docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md | MODIFY | operational sequence | additive commands | operator runbook |
| F8 | coding log and .codex/coding-log.current | MODIFY | lifecycle artifact | primary-owned | evidence |

### 4. Function contract

FN1 _execution_machine_name(execution_kind: str) -> str
File: F1
Does: maps exactly canonical/rehearsal to fixed machine names.
Pre: caller passes a string.
Post: returns only one of two constants.
Errors: execution_kind_not_accepted.
Invariants: arbitrary names never enter Orb commands.
Callers: host machine/guest/provision/stage/collector helpers.

FN2 build_machine_command(spec, execution_kind=canonical) -> list[str]
File: F1
Does: builds the existing exact isolated create command for the derived fixed machine.
Errors: rejects any changed shape/name/kind.
Callers: provision.

FN3 provision(..., execution_kind=canonical) -> None
File: F1
Does: reuses exact candidate/archive/bootstrap flow against the derived fixed guest.
Errors: preserves current fail-closed behavior and collects kind-specific bootstrap failure.
Callers: main canonical and provision-rehearsal actions.

FN4 run_stage(..., execution_kind=canonical) -> None
File: F1
Does: validates and dispatches an existing stage against the derived guest.
Errors: rehearsal stage outside first three is refused before guest command.
Callers: main canonical and run-rehearsal-stage.

FN5 finalize_rehearsal_collection(destination: Path) -> dict
File: F1
Does: validates exact BASE/RTA/AC PASS inventory and writes non-acceptance summary/index.
Errors: exact stable rehearsal evidence errors; no partial acceptance.
Callers: collect_rehearsal and tests.

FN6 collect_rehearsal(destination, release_sha, frontend_sha) -> dict
File: F1
Does: validates rehearsal guest/candidate, streams evidence, finalizes it, and removes stream residue.
Errors: preserves guest and destination on mismatch.
Callers: main collect-rehearsal.

FN7 StageContext plus run_local_base
File: F3
Does: carries closed execution kind and verifies the derived fixed owner/machine.
Errors: rehearsal later-stage or owner mismatch fails closed.
Callers: run-stage-suite main dispatch.

### 5. Test contract

T1 host fixed execution lookup and machine commands
File: F4
Covers: R1,R2,R13
RED: pytest test_orchestrate.py -k rehearsal_machine
Expected RED: rehearsal constants/arguments are absent.
GREEN: same selector passes.

T2 rehearsal provisioning target
File: F4
Covers: R3,R4
RED: pytest test_orchestrate.py -k provision_rehearsal
Expected RED: action/helper does not exist and bootstrap lacks kind.
GREEN: selector passes with exact command assertions.

T3 rehearsal stage ceiling
File: F4,F5
Covers: R5,R6
RED: pytest test_orchestrate.py test_stage_suite.py -k rehearsal_stage
Expected RED: no rehearsal dispatch/profile validation exists.
GREEN: only BASE/RTA/AC pass; later stages reject before execution.

T4 owner identity
File: F4,F5
Covers: R4,R7
RED: pytest test_orchestrate.py test_stage_suite.py -k rehearsal_owner
Expected RED: owner fields are absent/unvalidated.
GREEN: exact kind/machine/non-acceptance required.

T5 successful three-prefix collection
File: F4
Covers: R8,R9,R10
RED: pytest test_orchestrate.py -k rehearsal_collection
Expected RED: finalizer/action absent.
GREEN: exact structure and indexes pass.

T6 malformed rehearsal inventories
File: F4
Covers: R8,R10
RED/GREEN command: selector rehearsal_collection_invalid.
Cases: later stage, failure file, symlink, unindexed file, wrong SHA, missing harness.

T7 failure recovery targeting
File: F4
Covers: R11
RED: pytest test_orchestrate.py -k rehearsal_failure_collection
Expected RED: collectors target canonical guest only.
GREEN: partial/bootstrap collection targets rehearsal and remains false.

T8 ledger anti-promotion
File: F4
Covers: R12,R13
RED: pytest test_orchestrate.py -k rehearsal_ledger
Expected RED: no explicit rehearsal-index regression fixture.
GREEN: rehearsal index is rejected while canonical success fixture remains valid.

T9 canonical regression
File: F4,F5
Covers: R13
Command: existing canonical and full affected suites.
Expected: no behavior drift.

T10 runbook wiring
File: F6,F7
Covers: R14
RED: pytest test_local_artifacts.py -k runbook
Expected RED: exact rehearsal/authority language absent.
GREEN: exact commands and boundaries present.

### 6. Traceability

| Requirement | Runtime realization | Tests | Files | Slice |
| R1,R2 | FN1 -> FN2 -> orb create | T1 | F1,F4 | S1 |
| R3,R4 | main -> FN3 -> bootstrap owner write | T2,T4 | F1,F2,F4,F5 | S1 |
| R5,R6 | main -> FN4 -> run-stage-suite existing dispatch | T3 | F1,F3,F4,F5 | S1 |
| R7 | validate_stage_guest and run_local_base | T4 | F1,F3,F4,F5 | S1 |
| R8-R10 | collect-rehearsal -> FN6 -> FN5 | T5,T6 | F1,F4 | S2 |
| R11 | kind-specific existing collectors | T7 | F1,F4 | S2 |
| R12 | validate_campaign_ledger exact index requirement | T8 | F1,F4 | S2 |
| R13 | unchanged canonical main paths | T1,T8,T9 | F1-F5 | S1,S2 |
| R14 | runbook and static gate | T10 | F6,F7 | S3 |

### 7. Wiring

| Component | Non-test runtime caller | Registration/config load | Contract evidence |
| execution lookup | machine/guest/provision/stage/collect helpers | orchestrate.py main action branches | fixed constants and T1 |
| rehearsal provision | orchestrate.py main provision-rehearsal | argparse action choice | T2 |
| rehearsal stage | orchestrate.py main run-rehearsal-stage -> guest run-stage-suite.py | host and guest parsers | T3,T4 |
| rehearsal finalizer | orchestrate.py main collect-rehearsal | collector dispatch | T5,T6 |
| rehearsal recovery | main rehearsal partial/bootstrap actions | collector dispatch | T7 |
| operator commands | tracked runbook | test_local_artifacts.py | T10 |

No schema/table/migration row applies. Ephemeral owner JSON is the only changed data contract.

### 8. Slice plan

DeepSeek budget: 0
Selected DeepSeek slice: NONE

| ID | Requirements/files/tests | Mode | Q0-Q3 result | Stop line | Allowlist | Oracle | Done when |
| S1 | R1-R7,R13; F1-F5; T1-T4,T9 | PRIMARY | Q1 public CLI and authority/guest identity boundary | PRIMARY | none | T1-T4,T9 | primary gates pass |
| S2 | R8-R13; F1,F4; T5-T9 | PRIMARY | Q1 acceptance-evidence public contract | PRIMARY | none | T5-T9 | exact non-promotion proven |
| S3 | R14; F6,F7; T10 | PRIMARY | Q1 operational authority documentation | PRIMARY | none | T10 | runbook/static gate pass |

No production file is externally allowlisted. No DeepSeek request will be made. g2-coding remains active with usage zero.

### 9. Gates, review, rollout, rollback

- Focused RED/GREEN commands from T1-T10.
- Full affected Python 3.11 pytest gate for stage suite, orchestrator, approved sources, artifacts, and provisioning tests.
- Black check on changed Python.
- Ruff check on changed Python.
- Python 3.11 compileall.
- Bash syntax check for bootstrap-linux.sh.
- Diff whitespace check.
- Affected test scope repeated three times.
- Independent non-DeepSeek QCHECK.
- Formal existing g-check with all findings dispositioned.
- Standard PR and authorized admin merge. Known no-step billing lock is ignored under standing policy and not called passing.
- Exact local main/origin main/tree verification.
- Rollback before rehearsal guest creation is source revert. After creation, preserve evidence and use separate exact guest cleanup authority.

### 10. Do-not-touch and baseline

- Do not alter existing ledger rows or append a row in the source PR.
- Do not modify the CI workflow unless a defect-sensitive wiring test proves necessity.
- Do not modify stage algorithms, order, write flags, services, migrations, credentials, runtime guests, or external evidence during source development.
- Do not touch the dirty Smart CMS primary checkout.
- Do not touch pre-existing backend worktrees.
- Do not let a subagent edit product code, tests, Coding Logs, Git, runtime, PR, or deployment.
- Audit all changes against baseline 27c5558dda2139ccd2e84f19616c56401fff4427.

## Decision-complete checklist

- Every R/F/FN/T/S reference resolves.
- Every requirement maps to a runtime call site and test.
- Every new action is wired in host and guest parsers.
- Every RED command predicts missing behavior, not setup failure.
- DeepSeek budget is exactly zero because Q1 is decisive.
- Public CLI, evidence, and authority decisions stay primary-owned.
- Source PR, candidate preparation, rehearsal grant, canonical grant, campaign execution, ledger closure PR, and deployment/activation are distinct.
- No open implementation decision remains for the source slice.

## 2026-08-16 07:43 ICT — S1/S2 acceptance contract RED

- Created pinned Python 3.11 gate environment at `/tmp/munbon-9of9-gate.jd0ldB/venv` from `services/ros-gis-integration/requirements.txt`.
- Added primary-owned acceptance tests for the fixed rehearsal machine/guest, structural non-acceptance owner marker, exact three-stage checksum-bound rehearsal finalizer, explicit rehearsal actions, host stage ceiling, and guest execution context.
- RED command: `/tmp/munbon-9of9-gate.jd0ldB/venv/bin/python -m pytest -q ops/control-plan-read-local/tests/test_orchestrate.py -k 'rehearsal' ops/control-plan-read-local/tests/test_stage_suite.py -k 'rehearsal'`.
- RED result: 8 failed, 1 passed, 412 deselected. Failures are the expected missing production contracts (`REHEARSAL_STAGE_ORDER`, rehearsal command/owner/finalizer/stage functions, parser actions, and `StageContext.execution_kind`); no setup or unrelated failure occurred.
- The one passing negative parser test raised for the pre-existing absence of `--execution-kind`; it remains part of the GREEN contract but is not counted as independent RED evidence.

## 2026-08-16 08:17 ICT — S1/S2/S3 GREEN

- Added the fixed `munbon-control-plan-rehearsal` Debian 12 ARM64 profile without changing the canonical guest name, canonical stage order, strict 9/9 finalizer, ledger, or CI workflow.
- Bootstrap now receives an exact `canonical|rehearsal` argument. Canonical owner JSON remains byte-shape compatible; rehearsal owner JSON additionally requires `execution_kind=rehearsal` and `acceptance_evidence=false`.
- Rehearsal stage execution is restricted at both host and guest parsers to the first three ordered stages and requires an explicit `--as-of-date` at the host CLI.
- Successful rehearsal collection validates the exact checksum-bound three-stage prefix, writes `REHEARSAL-SUMMARY.json`, and writes only `REHEARSAL-OUTER-SHA256SUMS`. Rehearsal partial failures add `non_authoritative_rehearsal` and write only `REHEARSAL-PARTIAL-OUTER-SHA256SUMS`; both index names are rejected by the campaign-ledger schema.
- Added explicit rehearsal provision/run/collect/bootstrap-failure/partial-failure actions and exact handler-wiring tests. Canonical command and evidence tests remain unchanged and passing.
- Updated the runbook with the exact rehearsal commands, recovery split, authority exclusions, and stable-ID canonical-retirement procedure.
- GREEN gate: 510 affected tests passed in 1.58s.
- Static gates: Black formatted all changed Python, Ruff passed, Bash syntax passed, Python compile passed, and `git diff --check` passed.
- Protected artifacts unchanged: campaign ledger SHA-256 `45970d9a2240eb2090a7958d9add373fb5ec4ef6068b38d04ae4ac22ce4f4261`; workflow SHA-256 `61c26167e169bd327d1f4697197f0675d3f78a3d656e7544227f03fde2a0c336`.

## 2026-08-16 08:26 ICT — QCHECK and formal-review remediation

- Independent QCHECK found that a retry could overwrite an existing failure, rehearsal partial collection admitted later-stage evidence, and the guest CLI could default identity inputs. Formal g-check additionally found profile-state crossover, indistinct bootstrap evidence, missing owner/dependency binding, non-atomic collection, and insufficient provisioning wiring coverage.
- Added a second primary-owned RED contract for an immutable first failure, exact BASE/RTA/AC failure cut points, explicit execution kind/date, profile-bound stage state, canonical rejection of rehearsal state, distinct bootstrap output, owner/dependency-bound summaries, new-destination-only atomic extraction, and direct fixed-guest upload wiring. The expected RED was 7 focused failures after the first remediation pass; all were missing-boundary failures rather than setup failures.
- Remediation now makes every existing failure terminal before stage execution, restricts rehearsal evidence to the three-stage prefix, binds rehearsal state to guest/profile/dependency/Bangkok date, and keeps the canonical state schema unchanged. Extraction occurs in a private sibling temporary directory and renames only after validation; failures remove the temporary tree and never publish the destination.
- Re-review then found three remaining P1 issues: ledger-accepted inner checksum names, date continuity not persisted, and a collection-time owner TOCTOU. A third RED confirmed 7 expected failures. Frozen rehearsal success, partial, and bootstrap output now uses only `REHEARSAL-SHA256SUMS` plus rehearsal-specific outer indexes; the ledger rejects every such name. Collection requires the authorized date, compares it with the summary, and revalidates the exact owner immediately before atomic publication.
- Added a direct wrapper test proving rehearsal uploads invoke only `munbon-control-plan-rehearsal`. Added failure-boundary coverage for zero, one, and two preceding PASS stages and extraction-failure cleanup coverage.
- Current full harness result: 536 passed, including the embedded Node request-inventory suites. Black, Ruff, Bash syntax, Python compilation, and diff whitespace checks pass after formatting.
- Protected artifacts remain byte-identical at the SHA-256 values recorded above. No ledger row or CI-workflow byte changed.

## 2026-08-16 08:37 ICT — Formal g-check clean disposition

- Final g-check reviewed snapshot `2026-08-16/0835` after three remediation rounds. All earlier P0/P1/P2 findings are fixed and dispositioned; the reviewer reports no actionable P0, P1, or P2 findings.
- The final P2 date-spelling regression was confirmed RED for compact `20260816` and is fixed by canonical ISO-date validation before dispatch. The final P2 runbook ambiguity is fixed: provisioning automatically finalizes bootstrap-failure evidence, and standalone recovery is allowed only after automatic collection failure/interruption when the destination is absent. A behavioral test pins the rehearsal collection call.
- Final quality evidence: 538 full harness tests passed; before the final documentation/test-only refinement, the same production code passed 537 tests three consecutive times. Black, Ruff, Bash syntax, Python compilation, and diff whitespace checks pass.
- QCHECK function/test assessment: new helpers remain small and composable; canonical and rehearsal schemas are explicitly separated; tests exercise defect-sensitive state crossover, date mismatch, owner mutation, failure immutability, index non-promotion, atomic cleanup, fixed upload targeting, and every valid rehearsal failure boundary. No untested public action or parser branch remains in the source slice.

## 2026-08-16 12:02 ICT — Exact ARM64 Python closure refresh

- The exact dependency build for backend `f48f347a19b78e767027e2405d501a2fc5927621` and frontend `067b3e22401854f8c6d6db42dc0c5c1872fca6f8` first failed on npm registry `EIDLETIMEOUT`. The diagnostic guest's prior user npm config was absent. A bounded diagnostic-only config (`fetch-timeout=1800000`, `fetch-retries=5`, `maxsockets=1`) completed all five locked npm trees without changing package identities or source files.
- The builder then correctly failed closed on Python wheel-set drift. Exact Debian 12 ARM64 resolution preserved all four counts but changed the content-address digest for flow-monitoring, scheduler, and bff-water-planning; ros-gis-integration remained byte-identical.
- Independently computed closure tuples: flow-monitoring `1fcccdfef76712bde019df56c9f6e81e750f97e62e5a05a4d441b5c8ba0c41df 84`; scheduler `67a87a9a59b8a678f14414fc14c9d79cee75c0ab772f36cebe9cefe1f541d1d2 96`; ros-gis-integration `16bc077f84400bc346ccb6f5e755fdb53a8545eb792c64cd79bd2bf2113fc9da 67`; bff-water-planning `e778cd3b518b4f751e0ac35918575073b10c70ed853cf19fb87a9cb21d7e3fd8 81`.
- RED updated the existing exact lock assertion first and failed because the three stale digests remained in `python-closures.lock` (`1 failed`). GREEN changes only those three digest fields and their existing exact test expectations; requirements, counts, builder logic, stage logic, ledger, workflow, and runtime authority remain unchanged (`1 passed`).
- Independent QCHECK found that duplicating aggregate digests in the test was not independently auditable. A second RED failed on missing per-wheel receipts. Four sorted receipts are now committed under `ops/control-plan-read-local/python-closure-receipts/` with 84, 96, 67, and 81 exact wheel hashes. The test validates receipt syntax/order, derives each count and aggregate SHA-256 from receipt bytes, and compares those derived tuples with the runtime lock (`1 passed`).

## 2026-08-16 12:08 ICT — Closure-refresh QCHECK and formal g-check disposition

- Independent QCHECK initially reported one P2: matching aggregate literals in the lock and test were not independently auditable. The committed per-wheel receipts and builder-equivalent derivation test fully remediate it.
- Independent re-review recomputed all four receipt aggregates/counts, reran the focused assertion (`1 passed`), and reports no actionable P0, P1, or P2 findings.
- Primary formal g-check confirms the receipt byte stream matches the builder algorithm: both use GNU `sha256sum` lines for the same flat wheel directory in bytewise filename order, and both SHA-256 the complete newline-terminated stream. The test also pins the exact four-service order, receipt syntax, sorted filenames, counts, and lock equality. No runtime logic, requirements, ledger, workflow, guest, or authority changed.
- RepoPrompt's external review provider was attempted twice and returned its account usage-limit boundary before producing a review. This is recorded as unavailable review infrastructure, not a passing review. The independent Terra review plus primary full-gate review is the formal fallback disposition for this bounded data refresh.
- Final gates: 538 full harness tests passed; Black, Ruff, Python compileall, and diff whitespace checks passed. Formal disposition: no actionable P0, P1, or P2 remains.
