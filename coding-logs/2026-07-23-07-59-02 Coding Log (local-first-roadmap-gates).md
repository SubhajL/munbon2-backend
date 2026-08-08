# Local-first roadmap gates

Date: 2026-07-23

Status: decision-complete sequencing plan; no runtime or AWS mutation performed

## Overview

The corrected execution model has two distinct gates: local integration
acceptance proves the software and operating procedure before deployment, while
production RTA-1 proves the actual AWS host and deployed runtime. A local pass
unlocks continued source implementation and dark artifact preparation; it does
not unlock production data acceptance or user-visible/write activation.

This plan supersedes the execution ordering in the two newer planning logs. It
does not edit the historical roadmap or claim that its old AWS snapshot is
current.

## Verified current status

- Backend `main == origin/main == 8095bfe37550200da00ecb554edc646febf8aff9`.
- Frontend local `main`, local `origin/main`, and live remote `main` all equal
  `3a16498a60927996ac38e741b276150968d0cadc`.
- FE-4 is already landed: both App Router pages and both list/detail components
  are present with `NEXT_PUBLIC_CONTROL_PLAN_READS` tests.
- W1 is not present: there is no Scheduler `/api/v1/auth/principal` endpoint or
  effective-principal projection.
- W2 is not present: BFF migrations end at `009_crop_registry.sql`, with no
  planning-depth submission implementation.
- The last confirmed AWS snapshot showed an older control-plan runtime at
  `3885ee63`, so the user's recollection that the host may run an earlier backend
  is consistent with evidence. Current AWS state remains unverified and may have
  changed.
- The roadmap itself says source and runtime work may run in parallel. RTA-1
  directly blocks only AC-1, READ-ACT-1, and WRITE-ACT-1.

## Exploration note

Auggie semantic search timed out at the required two-second ceiling. This plan
therefore uses direct inspection and exact-string searches of:

- `AGENTS.md`
- `CONTEXT.md`
- `coding-logs/2026-07-22-10-10-17 Coding Log (revised-control-plan-runtime-write-roadmap).md`
- `coding-logs/2026-07-23-07-39-09 Coding Log (local-linux-rta1-acceptance-harness).md`
- `ops/control-plan-read-runtime/`
- `services/scheduler/src` and `services/scheduler/tests`
- `services/bff-water-planning/src`, `tests`, and `migrations`
- the live local/remote `smart-cms-app` main branch and FE-4 files

## Locked terminology

- **LTA-1**: local Linux integration acceptance. It runs the landed runtime and
  RTA procedure on a disposable native-arm64 OrbStack guest. A pass is evidence
  that the software can be deployed; it is not production acceptance.
- **RTA-1**: the existing roadmap's capacity-qualified production runtime
  acceptance on AWS. Its twelve requirements and thresholds are unchanged.
- **AWS-INV-1**: read-only inventory of the current AWS process/runtime/resource
  state. It authorizes no stop, deletion, replacement, or spend.
- **AWS-CLEAN-1**: a later explicitly authorized, target-by-target cleanup or
  cutover window. It is not authorized by this plan.

## Goal

Fully exercise the current backend/frontend runtime locally before any new real
deployment, continue safe source work without conflating it with activation,
then recover the existing AWS host if possible and run the unchanged production
RTA-1 before AC-1 or any read/write activation.

## Non-goals

- Do not treat local evidence as proof of AWS capacity, installed packages,
  credentials, data quality, networking, or saved PM2 state.
- Do not delete or stop any AWS software in this planning turn.
- Do not lower memory/swap thresholds or alter the twelve RTA-1 requirements.
- Do not modify the old roadmap or the previous local-harness plan.
- Do not activate Scheduler execution, ROS recurring/startup production,
  commandability, control-plan visibility, or planning-depth writes.
- Do not use production data or credentials inside the local guest.

# Plan Draft A — production gate before all further work

## Overview

Implement and pass LTA-1, immediately repair the AWS host, pass production
RTA-1, and only then resume any roadmap source work. This keeps one highly
visible gate but serializes work more aggressively than the roadmap requires.

## Files to change

- Add the local harness files under `ops/control-plan-read-local/` described in
  the prior local plan, corrected to native `arm64`.
- Add `docs/operations/CONTROL_PLAN_LOCAL_LINUX_ACCEPTANCE.md`.
- Do not change production runtime scripts unless a failing harness test proves
  a defect.

## Implementation steps and TDD sequence

1. Add/stub local orchestration tests.
2. Run them and confirm failures for missing arm64/isolation/order behavior.
3. Implement the smallest local harness changes.
4. Refactor only duplicated opaque command construction.
5. Run formatter, lint/type checks, focused tests, runtime tests, and full LTA-1.
6. Run AWS-INV-1 read-only.
7. Present a target-by-target cleanup/cutover proposal and wait for explicit
   authorization.
8. If authorized, perform AWS-CLEAN-1 and rerun the unchanged capacity gate.
9. Pass production RTA-1 before starting W1 or other source work.

Functions:

- `build_machine_command(spec)` emits a native-arm64 isolated guest command.
- `run_rta_steps()` enforces the existing twelve-step ordering locally.
- `capture_aws_inventory()` uses only bounded safe projections and makes no
  changes.
- `classify_runtime_processes(inventory)` labels exact current runtime,
  candidate-retired software, and unknown ownership without deciding deletion.

## Test coverage

- `test_build_machine_command_uses_native_arm64` — avoids x86 emulation locally.
- `test_run_rta_steps_never_saves_before_bearer` — preserves final save ordering.
- `test_inventory_contains_no_process_environment` — prevents AWS secret leakage.
- `test_unknown_process_is_never_cleanup_candidate` — cleanup fails ownership closed.

## Decision completeness

- Public surface: local CLI only; no API/schema/migration changes.
- Failure behavior: every failed local/AWS gate stops the sequence.
- Rollout: none until RTA-1 passes.
- Backout: preserve the pre-change PM2 dump; do not roll back durable migrations.
- Success: LTA-1 and production RTA-1 both pass before source work resumes.

## Dependencies and validation

- Native-arm64 OrbStack, local dependencies, exact accepted SHA, then AWS access
  and separately authorized cleanup targets.
- Validate with local 12-step evidence, AWS-INV-1 evidence, and production RTA-1
  evidence.

## Wiring verification

| Component | Entry point | Registration | Schema/table |
| --- | --- | --- | --- |
| Local harness | `orchestrate.py run` | local operator CLI | local disposable schemas |
| Existing RTA scripts | local then AWS runner | tracked PM2 ecosystem | Scheduler/ROS/BFF registries |
| AWS inventory | `orchestrate.py aws-inventory` | operator CLI, read-only | none |

## Draft A trade-offs

Strength: simplest governance story and earliest production-host truth.

Gap: it unnecessarily blocks W1 and other dark source work even though the
roadmap explicitly permits parallel work. If AWS access or cleanup approval is
slow, development stalls without improving production safety.

# Plan Draft B — local qualification plus parallel dark delivery

## Overview

Pass LTA-1 first, then allow source implementation and full local integration
testing to continue while AWS inventory/recovery proceeds as a separate
operations lane. Production RTA-1 remains a hard prerequisite for AC-1 and all
activation nodes.

## Files to change

- Add the same native-arm64 local harness and operations documentation as Draft A.
- W1 later changes the Scheduler files already named in the historical roadmap.
- W2 later adds BFF migration 010, manifest/runner, service/router/repository,
  and tests already named in the historical roadmap.
- FE-5/FE-6 later change the frontend files named in that roadmap.
- The historical roadmap remains unchanged; this Coding Log owns the revised
  execution status and gate meanings.

## Implementation steps and TDD sequence

1. Implement and pass LTA-1 against exact backend `8095bfe3...` and frontend
   `3a16498a...` using the native-arm64 isolated guest.
2. Test FE-4 both dark and locally visible: false flag returns no page/navigation;
   true flag exercises authenticated list/detail against the local backend.
3. After LTA-1 passes, start W1 tests first, confirm the correct failures,
   implement the minimum endpoint, land through its normal PR, update the local
   guest to the accepted backend SHA, and rerun the affected LTA matrix.
4. Repeat the tests-first/PR/local-regression cycle for W2, FE-5, and FE-6. W2
   writes may be enabled only inside the disposable guest; deployed artifacts
   remain dark.
5. In parallel, run AWS-INV-1. Identify whether the host still runs the older
   backend, which unrelated processes consume resources, current saved PM2
   state, restart counts, listeners, memory, and swap.
6. Produce an explicit AWS-CLEAN-1 proposal listing each candidate process,
   owner/purpose, stop/delete command, dependency impact, rollback, and expected
   memory recovery. Wait for user authorization before executing it.
7. After authorized cleanup/cutover, rerun the unchanged capacity gate. If it
   passes, deploy the exact accepted dark artifacts and run production RTA-1.
8. Only after production RTA-1 passes may AC-1 run with real approved sources.
   READ-ACT-1 and WRITE-ACT-1 retain all original dependencies.

Functions:

- Local harness functions are identical to Draft A.
- W1 uses `get_effective_principal(current_user)` and the strict
  `EffectivePrincipalProjection` from the historical roadmap.
- W2 uses `canonicalize_planning_depth_request`,
  `validate_planning_depth_roster`, `expand_planning_depth_values`,
  `load_effective_principal`, `consume_planning_depth_write_limit`,
  `create_planning_depth_submission`, and
  `get_active_planning_depth_submission` as already specified.
- `build_cleanup_proposal(inventory)` returns documentation only; no function in
  the inventory path can issue a stop/delete command.

## Test coverage

- Local harness tests from Draft A.
- `test_fe4_dark_routes_remain_unavailable` — confirms production-default UI off.
- `test_fe4_visible_reads_real_local_backend` — proves local end-to-end read path.
- W1 endpoint/auth/revocation/cache tests from the historical roadmap.
- W2 pure/client/route/PostgreSQL tests from the historical roadmap.
- `test_source_sha_change_requires_lta_regression` — prevents stale local proof.
- `test_cleanup_proposal_cannot_execute_commands` — separates audit from mutation.

## Decision completeness

- Public surface: LTA local CLI/evidence label; future W1/W2 APIs remain exactly
  as specified in the roadmap.
- Local representative data is allowed only for software testing and is labeled
  non-AC-1. AC-1 still requires real approved sources and cannot use fixtures.
- Failure behavior: local test failure blocks the related PR/deployment artifact;
  AWS inventory uncertainty blocks cleanup; AWS capacity failure keeps RTA-1
  failed; all activation flags remain false.
- Rollout: merge source slices one at a time, test each accepted SHA locally,
  deploy nothing new to AWS until the combined local suite passes.
- Backout: revert an unactivated code artifact normally; never down-migrate W2
  after durable rows; preserve prior AWS PM2 state for cutover rollback.
- Success: all current/future dark code passes local integration before AWS
  deployment, then the actual AWS host independently passes RTA-1.

## Dependencies and validation

- LTA-1 needs no production credentials/data.
- W2 local integration needs a representative local 41-section/47,385-rai
  canonical roster derived from the repository's approved invariant tests; it
  remains explicitly non-production evidence.
- Production RTA-1 needs the real host, exact SHAs, current local dependencies,
  monitoring, central auth, and capacity.
- AC-1 needs real approved GIS/planting/agronomic sources and a real operator
  login after RTA-1.

## Wiring verification

| Component | Entry point | Registration | Schema/table |
| --- | --- | --- | --- |
| LTA-1 | local orchestrator | native-arm64 OrbStack guest | disposable service schemas |
| FE-4 local visible path | Next routes/hooks | flag-gated navigation/pages | Scheduler/BFF read projections |
| W1 | Scheduler `/api/v1/auth/principal` | Scheduler v1 router | none |
| W2 | BFF POST/active GET | BFF `main.py` router | `water_planning.*`, registry 010 |
| AWS-INV-1 | safe inventory CLI | operator invocation only | none |
| AWS-CLEAN-1 | separately approved runbook | exact target list | none |
| Production RTA-1 | existing `activate.sh`/verifier | tracked PM2 ecosystem | real Scheduler/ROS/BFF registries |
| AC-1 | real ROS manual run | ROS route and Scheduler reads | real requirement/control-plan rows |

## Draft B trade-offs

Strength: maximizes predeployment test depth without weakening production
acceptance or idling safe source work.

Gap: requires disciplined evidence labels and SHA invalidation so nobody mistakes
LTA-1 for production truth.

# Comparative synthesis

Draft A is operationally simple but stricter than the roadmap. It converts an
activation dependency into an unnecessary development dependency.

Draft B matches the roadmap's explicit parallelism and the user's desired
local-first workflow. Its risk—confusing local and production evidence—is solved
with separate names, evidence manifests, and an unlock matrix.

Draft B is selected, with Draft A's fail-closed AWS inventory/cleanup boundary.

# Unified execution plan

## Unlock matrix

| Work | After LTA-1 pass? | Requires production RTA-1? |
| --- | --- | --- |
| FE-4 local flag-on/off integration | Yes | No |
| W1 implementation/PR/local integration | Yes | No |
| W2 implementation/PR/local integration | Yes | No |
| FE-5/FE-6 implementation/PR/local integration | Yes | No |
| ME-1/FE-8 implementation and dark tests | Yes | No |
| Deploy new combined artifact to AWS | Only after full local pass | Deployment begins RTA path |
| AC-1 real-data acceptance | No | Yes |
| READ-ACT-1 user-visible reads | No | Yes, plus AC-1 |
| WRITE-ACT-1 production writes | No | Yes, plus W1/W2/FE-5/FE-6 |

## Phase 1 — native-arm64 full local baseline

1. Implement the local harness from the prior plan but use `--arch arm64`.
2. Provision a separate isolated Debian 12 guest; do not touch the existing
   OrbStack Ubuntu guest.
3. Run the exact RTA twelve-step procedure against backend `8095bfe3...`.
4. Run FE-4 against the local backend with its flag false and true.
5. Produce one evidence manifest labeled `LOCAL_INTEGRATION_ACCEPTANCE`,
   containing exact backend/frontend SHAs and no secrets.
6. A failed LTA-1 blocks new deployment and the related source slice, but does
   not rewrite the production RTA result.

## Phase 2 — continue source work locally

1. FE-4 is already complete; do not reopen it unless local integration exposes
   a defect.
2. W1 is the next backend source slice. Follow its existing TDD, QCHECK,
   g-check, PR/admin-merge/local-main lifecycle.
3. Update the guest to each newly accepted SHA and rerun focused service tests,
   migration/preflight tests, readiness/stability, and bearer tests.
4. Proceed to W2 only after W1 lands. Test W2 migrations on an explicitly
   disposable database and test writes only with local flags/data.
5. Proceed to FE-5/FE-6 after W1/W2 contracts stabilize. Keep both frontend
   public flags false in deployable builds.
6. Source merges remain one at a time per repository. No local pass for an old
   SHA transfers to a newer SHA automatically.

## Phase 3 — AWS read-only truth before cleanup

Run AWS-INV-1 only after local baseline passes:

1. Capture timestamp/host identity, exact PM2 names/status/cwd/SHA/restarts,
   saved PM2 dump hash, systemd/Docker process projections, memory/swap, disk,
   and listeners without environments or secrets.
2. Classify every process as current required dependency, older Munbon runtime,
   unrelated candidate, or unknown. Unknown is never a cleanup target.
3. Confirm whether the older `3885ee63` runtime still serves the first backend
   version; do not assume it is disposable.
4. Record which exact processes account for capacity pressure. Do not infer from
   names alone.
5. Produce the AWS-CLEAN-1 proposal and stop for explicit authorization.

## Phase 4 — separately authorized AWS cleanup/cutover

Only after the user approves an exact target list:

1. Back up the current PM2 saved set and configuration references without
   copying secrets into evidence.
2. Stop one approved nonessential target at a time, observe dependency health,
   and remeasure memory/swap. Delete only after its rollback path is proven.
3. Prefer removing unrelated/retired software before touching the older backend.
4. If the old backend itself must stop to free capacity, require an explicit
   cutover window, preserve its PM2 state, stop it without deleting, and rerun
   the capacity gate before installing/starting the new exact runtime.
5. If swap remains over 1 GiB, do not clear it merely to manufacture a pass.
   Wait for natural recovery or request separate authorization for a controlled
   reboot/host operation.
6. If the original thresholds pass, proceed to exact dark deployment and RTA-1.
   If they still fail, CAP-1 remains active.

## Phase 5 — production acceptance and roadmap continuation

1. Run all twelve original RTA-1 steps on AWS with exact accepted SHAs.
2. On pass, mark production RTA-1 accepted; on failure, preserve the first failed
   reason and rollback only named processes.
3. Run AC-1 using real approved data—never the local representative dataset.
4. Run READ-ACT-1 only after FE-4 dark deployment, RTA-1, and AC-1 all pass.
5. Run WRITE-ACT-1 only after RTA-1 and all W1/W2/FE-5/FE-6 requirements pass.

## Public interfaces and contracts

- Local CLI: `orchestrate.py plan|provision|run|collect|teardown`, fixed
  `--arch arm64`, exact full SHA, isolated guest only.
- Evidence status values: `LOCAL_INTEGRATION_ACCEPTANCE` and
  `PRODUCTION_RUNTIME_ACCEPTANCE`; they are never interchangeable.
- No current production API/schema/env changes are introduced by this sequencing
  plan. Future W1/W2 interfaces remain owned by their existing detailed plans.
- AWS inventory has no mutation subcommand. Cleanup is a separate runbook/action.

## Failure modes

| Failure | Result |
| --- | --- |
| LTA capacity/install/migration/readiness/bearer failure | Stop locally; no AWS deployment. |
| FE-4 flag-on integration failure | Reopen only the demonstrated defect. |
| New source SHA without regression evidence | Artifact is not deployment-qualified. |
| AWS state differs from old evidence | Replace assumptions with AWS-INV-1 output. |
| Unknown process ownership | Exclude from cleanup. |
| Capacity passes only after stopping old backend | Require approved cutover window. |
| Swap remains above limit | Stop; no artificial gate weakening. |
| Production RTA fails | AC-1 and activation remain blocked. |
| Local representative data passes | Does not satisfy AC-1. |

## Monitoring and backout

- Local: watch four `/ready` endpoints, restart-count equality, resource readings,
  auth lifecycle, migration parity, and promtool/preflight results.
- AWS cleanup: observe dependencies and capacity after each approved stop; keep a
  process-scoped rollback command and prior PM2 dump.
- Production RTA: retain the original monitoring/preflight and five-minute
  stability requirements.
- Activation: preserve existing false flags and original READ/WRITE backout
  procedures.

## Acceptance commands and outcomes

- Local harness tests: all focused unit/integration tests pass.
- Local runtime: existing `activate.sh` reports capacity/stability pass and saves
  PM2 only after 300 seconds.
- Local bearer: existing verifier prints every fixed PASS verdict.
- FE-4: false flag hides routes/navigation; true flag reads authenticated local
  list/detail without rendering mutations.
- AWS inventory: produces sanitized evidence only and changes no process state.
- Production: original RTA-1 produces exact SHA/migration/listener/readiness/
  stability/bearer/monitoring/dark-flag evidence.

## Files to change during implementation

- `ops/control-plan-read-local/orchestrate.py`
- `ops/control-plan-read-local/bootstrap-linux.sh`
- `ops/control-plan-read-local/seed-local-operator.js`
- `ops/control-plan-read-local/run-linux-acceptance.py`
- `ops/control-plan-read-local/systemd/munbon-local-auth.service`
- `ops/control-plan-read-local/tests/test_orchestrate.py`
- `ops/control-plan-read-local/tests/test_run_linux_acceptance.py`
- `ops/control-plan-read-local/tests/test_seed_local_operator.py`
- `docs/operations/CONTROL_PLAN_LOCAL_LINUX_ACCEPTANCE.md`

Future W1/W2/FE files remain exactly those listed in the historical roadmap and
must be handled in separate sequential PRs. The existing production RTA scripts
remain unchanged unless tests prove a defect.

## Final wiring verification

| Producer/component | Boundary | Consumer | Runtime proof |
| --- | --- | --- | --- |
| Accepted backend/frontend SHAs | LTA manifest | local guest | clean exact checkouts |
| Native-arm64 harness | existing runtime scripts | four PM2 apps | listeners/readiness/stability |
| Local auth operator | bearer verifier | Scheduler/BFF | full login/read/logout/reuse chain |
| Local representative roster | actual ROS/Scheduler paths | FE-4/W2 local tests | 41-section invariant, non-AC-1 label |
| Each landed source slice | new exact SHA | LTA regression | focused plus full local evidence |
| AWS-INV-1 | sanitized inventory | cleanup proposal | zero state mutations |
| Approved cleanup targets | process-scoped stop/delete | capacity gate | before/after evidence and rollback |
| Production exact release | tracked ecosystem | RTA-1 | original twelve-step evidence |
| RTA-1 pass | production gate | AC-1 | real ROS/operator acceptance |
| AC-1 pass | real plan evidence | READ-ACT-1 | authenticated UI smoke |
| W1/W2/FE chain plus RTA | dark artifacts | WRITE-ACT-1 | staging then production activation |

## Success criteria

- Full current software stack passes LTA-1 on native arm64 before AWS deployment.
- FE-4 is recognized as complete, not reopened as pending.
- W1 and later source work can proceed after LTA-1 without claiming activation.
- Every accepted new SHA reruns the relevant local full-stack qualification.
- AWS is inventoried from current truth before any cleanup proposal.
- No AWS target is stopped/deleted without explicit authorization.
- If cleanup restores capacity, the existing host can satisfy unchanged RTA-1;
  resize/move is not required merely because the earlier crowded state failed.
- AC-1, READ-ACT-1, and WRITE-ACT-1 remain blocked until actual production RTA-1
  passes.

## Decision-complete checklist

- [x] Local testing and production acceptance use distinct names/evidence.
- [x] FE-4 current landed status is verified.
- [x] Next backend source slice is W1; W2 remains dependent on W1.
- [x] Local architecture is native arm64, not emulated amd64.
- [x] Local data cannot be mistaken for AC-1 real-data evidence.
- [x] AWS inventory is read-only and cleanup requires new authority.
- [x] Old backend runtime is protected until current ownership/purpose is known.
- [x] Capacity thresholds and dark flags are unchanged.
- [x] Rollout/backout and SHA invalidation are explicit.
- [x] Wiring covers local, source, AWS operations, and activation boundaries.

