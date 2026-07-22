# Coding Log - PR 7.3a and 7.3b commissioning readiness

Started: 2026-07-21 15:30:35 +0700

## Governing evidence

- Source audit: `ops/archive-backend-main-plans-20260721` commit `fa2d9d29bcedcc3f32471845faf6a4a8a923d8c9`, file `coding-logs/2026-07-21-14-28-06 Coding Log (commissioning-readiness-software).md`, especially the system review and blocker/drift matrices at lines 211-346.
- Implementation baseline: clean local `main` and `origin/main` at `44703c3d5804bb79f390f68cf73b6e68314077d7`.
- Auggie semantic search is unavailable through a bounded two-second interface in this environment. Planning uses the required fallback: direct inspection of root and service guidance, Flow model release/snapshot/settings/readiness wiring, Scheduler Flow client/authority/readiness/metrics wiring, SCADA approved-field/config/startup/execution wiring, PM2 configuration, hardening workflow, current tests, and exact-string call-site searches.
- Safety invariant: tracked `CONTROL_EXECUTION_MODE=disabled` and `ALLOW_MACHINE_COMMANDS=false`; no real approval, field artifact, capability, service secret, authority grant, migration apply, PM2 mutation, PLC request, or machine write is part of either PR.

## Plan Draft A - one cross-service commissioning PR

### Overview

Implement the versioned commandability approval, Flow snapshot v4, Scheduler stored-proof verification, rich SCADA D6 runtime bundle, exact-release preflight, separate PM2 topology, Prometheus alerts, and safe evidence collector in one atomic change. This maximizes cross-component atomicity but creates a large mixed semantic/operations review surface.

### Files to change

- `contracts/control-commissioning/v1/**`: strict approval schema, manifest, non-approved fixture, and invalid drift fixtures.
- Flow `src/core/commandability_approval.py`, `model_snapshot.py`, `schemas/control.py`, settings/startup/readiness, and focused tests.
- Scheduler Flow-client mirror, authority-grant stored-proof validation, authority request evidence v2, shared test support, and focused tests.
- SCADA `domain/approved-field-bundle.ts`, registry/config/startup wiring, documentation, and colocated tests.
- PR 7.3b infra: PM2 topology/preflight, monitoring rules/tests, safe evidence collector/tests, CI paths, and operations docs.

### Implementation steps

1. Scaffold contract/loaders and write defect-sensitive tests.
2. Run focused tests RED for missing contracts, v4 behavior, stored approval checks, rich bundle runtime checks, exact-release preflight, topology, alert references, and redaction.
3. Implement the smallest cross-service changes to pass.
4. Refactor only opaque or duplicated validation.
5. Run formatter/lint/typecheck/focused and full service gates, three reliability passes, wiring checks, QCHECK, and formal `g-check`.

### Test coverage

- `test_unset_approval_preserves_snapshot_v3_dark` - unchanged dark snapshot contract.
- `test_v4_requires_exact_runtime_cross_binding` - no partial trust promotion.
- `test_scheduler_rejects_v3_true_booleans` - booleans alone grant nothing.
- `test_scheduler_rejects_tampered_approval_after_snapshot_hash` - semantic proof remains content-bound.
- `loadApprovedFieldBundle derives one coherent runtime bundle` - registry and anchor share one source.
- `machine mode rejects legacy split artifacts` - hand-authored bypass cannot arm.
- `preflight rejects release or migration drift` - stale deployment fails closed.
- `rules reference existing bounded metrics` - alert names cannot silently drift.
- `evidence output omits secret values` - collection is operator-safe.

### Decision completeness

- Goal: close the software-only trust and deployment-readiness gaps without enabling actuation.
- Non-goals: real approvals/artifacts, DB changes, runtime deployment, flags, grants, drills, PLC probes, or writes.
- Success: positive synthetic tests exercise every future path; default runtime remains v3/dark; configured drift fails closed; all quality gates pass.
- Public interfaces: approval contract v1; optional Flow approval path; Flow snapshot v4 union; Scheduler commandability evidence v2; optional SCADA rich artifact path; deployment preflight/evidence CLIs; monitoring rules.
- Failure policy: unset artifacts are dark; set-but-invalid artifacts and stale release/schema preflight fail closed; read-only collection reports unavailable rather than fabricating green.
- Rollout/backout: deploy code dark, stage external artifacts, validate, run shadow/drills, and authorize separately. Remove artifact paths before code rollback.
- Acceptance: focused/full service gates, three test passes, exact dark-config searches, rule validation, and read-only collector fixtures.

### Dependencies

- Future external D6, model/envelope approval, dedicated service auth, and SRE scrape/receiver configuration are explicitly outside implementation.

### Wiring verification

| Component | Entry point | Registration | Schema/table |
|---|---|---|---|
| approval loader | Flow lifespan | `src/main.py` | control-commissioning v1 |
| snapshot v4 | Flow model-snapshot POST | response union/builder | stored snapshot text; no DB change |
| stored proof verifier | Scheduler applicability/grant | `core/authority_grant.py` | existing plan/grant rows |
| rich D6 bundle | SCADA startup | `src/index.ts` | external artifact to in-memory snapshot/anchor |
| deployment preflight | operator CLI before PM2 replace | package scripts/runbook | scheduler migration registry read-only |
| alert rules | Prometheus rule loader | monitoring config | existing metric series |
| evidence collector | operator CLI | runbook | read-only process/HTTP/DB/file evidence |

### Trade-offs

- Pros: one merge contains every contract and operational consumer.
- Cons: excessive blast radius, difficult diagnosis, and coupled rollback.

## Plan Draft B - two sequential dark PRs

### Overview

PR 7.3a makes future commandability possible only through content-addressed external approval and one rich D6 runtime source. After it lands and passes exact-main verification, PR 7.3b adds exact-release/schema preflight, separate central/field PM2 topology, monitoring rules, and safe evidence collection.

### Files to change

- PR 7.3a: shared commissioning contract; Flow approval/snapshot/startup/readiness; Scheduler Flow mirror/authority proof; SCADA rich bundle/config/startup; focused docs/tests.
- PR 7.3b: `infra/pm2/**`, `infra/monitoring/**`, operational scripts/tests, hardening workflow path filters, and deployment/monitoring documentation.

### Implementation steps

#### PR 7.3a

1. Add contract and loader stubs; add schema/hash/cross-binding tests; capture RED.
2. Implement bounded strict Flow approval loading and runtime verification.
3. Add conditional snapshot v4 while preserving v3 byte/semantic output when unset or not approved.
4. Update Scheduler mirror and require v4 stored approval plus evidence-v2 hash/ref echo; bind approval capability/envelope/scope to current server-owned context.
5. Add SCADA rich-bundle loader deriving registry and lineage in memory; machine mode requires it and rejects split legacy paths.
6. Run Flow/Scheduler/SCADA gates, three reliability passes, wiring checks, QCHECK, formal review, commit, local merge, and exact-main verification.

#### PR 7.3b

1. Add preflight/topology/rule/collector tests and capture RED.
2. Implement exact manifest SHA and scheduler migration-0013 preflight without secret output.
3. Keep Scheduler/worker in the central PM2 profile and SCADA in a separate field-capable profile; both gates remain dark.
4. Add scrape targets and rules for readiness, scrape failure, heartbeat, rejection, in-doubt, readback mismatch, and non-operator writes.
5. Add bounded read-only evidence collection for release, migration ids, process state, readiness, metric families, artifact hashes, release/envelope identity, and zero/actual grant/drill counts.
6. Run infra/script/service gates, three reliability passes, wiring checks, QCHECK, formal review, commit, local merge, and exact-main verification.

### Test coverage

- PR 7.3a tests listed in Draft A plus v3 exact-output regression, non-approved staged artifact, D6 scope mismatch, quantizer inversion, readback ambiguity, and split-artifact rejection.
- `test_preflight_requires_exact_release_sha_and_0013` - no stale binary/schema pair.
- `test_pm2_topologies_keep_machine_boundaries_separate_and_dark` - correct process placement.
- `test_alert_rules_cover_all_incident families` - actionable rule inventory.
- `test_evidence_collector_bounds_and_redacts_output` - no credentials or unbounded payloads.

### Decision completeness

- Goal: 7.3a closes semantic trust gaps; 7.3b closes deployment/observability drift.
- Non-goals: identical to Draft A; neither PR performs deployment or operational enablement.
- Success: each PR is independently dark, reversible, locally landed, and exact-main verified before the next begins.
- Public interfaces: 7.3a owns contracts/env/snapshot/evidence versions; 7.3b owns operator CLIs/topology/rules.
- Failure policy: semantic artifacts and preflight fail closed; observation degrades to explicit unavailable.
- Rollout/backout: merge 7.3a first, then 7.3b; remove paths before code rollback; flags never change.
- Acceptance: service-scoped gates and post-merge tests at each exact local-main commit.

### Dependencies

- No external dependency is needed for software tests. Real host, secret, D6, approval, migration, alert receiver, and drill evidence remain owner gates.

### Wiring verification

| Component | Entry point | Registration | Schema/table |
|---|---|---|---|
| 7.3a approval | Flow snapshot creation | lifespan/service builder | commissioning v1 |
| 7.3a D6 bundle | SCADA startup | `main()` | external rich artifact |
| 7.3a authority proof | applicability/grant | authority service/core | existing stored snapshot/grant tables |
| 7.3b preflight | deploy operator | CLI/runbook | migrations through 0013 |
| 7.3b topology | PM2 start | central and field configs | no schema |
| 7.3b monitoring | Prometheus reload | scrape/rule files | existing metrics |
| 7.3b evidence | operator CLI | runbook | read-only runtime truth |

### Trade-offs

- Pros: narrow reviews, independent rollback, and clear fault isolation.
- Cons: a temporary state exists where trust semantics have landed but deployment tooling has not.

## Comparative analysis

Draft A is atomically complete but mixes safety semantics with host operations and creates a review surface too broad for the repository's one-change-at-a-time practice. Draft B preserves the required atomicity inside the Flow-Scheduler-SCADA trust contract while isolating deployment mechanics. Draft B is preferred because it yields a safe dark intermediate state and lets exact-main verification distinguish semantic defects from packaging/topology defects.

## Unified execution plan

Adopt Draft B. Land two local feature branches sequentially into local `main`; do not push, open remote PRs, deploy, or change external state. Preserve lifecycle logs during review, then archive logs/plans on separate `ops/archive-*` branches and leave the product `main` worktree clean.

### PR 7.3a functions

- `load_commandability_approval()` parses a capped strict document and verifies its canonical content hash.
- `verify_commandability_approval()` binds release, engine, model configs, envelope, capability pair, approved gate scope, and approval evidence.
- `build_model_snapshot()` returns unchanged v3 unless an externally approved, verified document exists; only then emits v4 with all commandability gates true.
- Scheduler stored-proof validation reproduces both snapshot and approval hashes, requires v4, and binds the current capability/scope/envelope before grantability.
- `loadApprovedFieldBundle()` reads one capped rich artifact, validates exact configured site scope plus quantizer/readback invariants, and derives the in-memory capability snapshot and lineage anchor.

### PR 7.3b functions

- Deployment preflight validates exact release manifest SHA, clean expected file set, tracked/applied migration equality including 0013, required built entry points, and dark flags.
- PM2 builders keep Scheduler/worker central and SCADA field-hosted, with host-supplied paths/secrets and dark defaults.
- Alert validation pins rules to known metric families and required incidents.
- Evidence collection emits only bounded allow-listed process/readiness/metric/hash/count fields and redacts any secret-shaped input.

### Final acceptance gates

- Flow: formatter plus focused/full pytest three times.
- Scheduler: focused/full pytest three times; integration only with the repository-approved disposable loopback DB if available.
- SCADA: format check, typecheck, lint, tests three times, build.
- Infra/scripts: typecheck/lint/tests three times, syntax/fixture checks, `promtool check rules` when installed.
- Formal `g-check` on staged intended files before each commit; address findings.
- Local `main` contains two sequential conventional merges/commits and passes exact-commit post-merge checks.
- Product worktree ends clean; archive refs retain coding logs/plans and point to their provenance.

### Decision-complete checklist

- No approval or field truth is inferred.
- Snapshot v3 remains immutable and dark; positive commandability requires v4.
- Rich D6 is one runtime source for capability plus lineage.
- Existing migration 0013 is required but no migration is added or applied.
- Public interfaces and failure modes are named.
- Every behavior has a defect-sensitive test and production caller.
- Both independent execution flags stay false/disabled in tracked configuration.
- No implementation decision remains open.

## Review (2026-07-21 16:02:02 +0700) - PR 7.3a working tree

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend`
- Branch: `feat/7-3a-dark-commandability-d6-validation`
- Scope: working tree against `44703c3d5804`; Flow v4 approval, Scheduler authority validation, SCADA rich D6 runtime bundle, shared contract, tests, and wiring.
- Commands Run: bounded `git status`/`git diff --stat` and targeted diffs; Flow scoped Black and full pytest; Scheduler scoped Black and full pytest; SCADA Prettier, ESLint, TypeScript, Vitest, and build; exact dark/config searches.

### Findings

CRITICAL

- No unresolved findings.

HIGH

- RESOLVED: `services/scheduler/src/core/authority_grant.py` originally required the live Flow `scada_graph` and `routing_topology` objects to contain only `config_sha256`. Real snapshots carry additional required metadata, so every real v4 approval would have failed as corruption. The validator now reads the required digest from the full producer object, and `test_full_flow_snapshot_metadata_does_not_invalidate_the_v4_approval` reproduces the real shape.
- RESOLVED: `services/scada-gate-control/src/domain/approved-field-bundle.ts` originally validated D6 quantizer geometry but did not bind the approved unit/register map or target levels to the actual Modbus runtime. A bundle could advertise capability the command planner could not write, or approve different registers than the process used. Startup now requires exact unit/command/readback addresses and every target level to be writable by the live planner; focused tests cover both mismatches.

MEDIUM

- RESOLVED: Scheduler accepted any nonblank approval timestamp ending in `Z`. It now parses and requires a UTC instant, with a self-consistently rehashed malformed-artifact test.
- RESOLVED: the committed SCADA example artifact could initially be loaded after configuration despite its loud non-field-approved marker. Runtime loading now rejects example/not-approved/do-not-deploy markers, with a defect-sensitive test.

LOW

- No unresolved findings.

### Open Questions / Assumptions

- The external hydraulic and D6 approvals remain operations-owned artifacts. No real approval, credential, endpoint, authority grant, or field register truth is committed by 7.3a.
- The configured SCADA process controls one canonical pilot gate, matching the current single-gate controller architecture.

### Recommended Tests / Validation

- Rerun full Flow after regenerating the prediction-engine descriptor; the first full run was 1351 passed, 14 skipped, with only the expected two descriptor-drift failures, and the regenerated descriptor's 17 focused tests pass.
- Rerun Scheduler authority/client focused tests after the real-snapshot compatibility fix.
- Rerun the full SCADA gate after the runtime register/target binding fix.
- Verify tracked command flags remain `CONTROL_EXECUTION_MODE=disabled` and `ALLOW_MACHINE_COMMANDS=false` before commit.

### Rollout Notes

- Unset approval/bundle paths retain v3/empty dark behavior. Set-but-invalid paths fail startup/readiness.
- Snapshot v4 and machine-armed boot require external evidence; this change does not supply it.
- Rotate the SCADA validation receipt store at any future rich-bundle/lineage trust cutover.

## PR 7.3a implementation evidence

- TDD RED: Flow approval loader 15 failures; shared contract 3 failures; Scheduler stored-v4/approval suite 27 failures; SCADA rich bundle missing module/config failures; Scheduler client rejected v4.
- Flow GREEN: scoped Black clean; full suite `1353 passed, 14 skipped`; generated prediction-engine descriptor rebuilt and `--check` passes.
- Scheduler GREEN: full suite `1023 passed, 59 skipped`; post-review authority/client/API/contract slice `194 passed`.
- SCADA GREEN: Prettier, ESLint, TypeScript, full Vitest `421 passed, 7 skipped`, and production build.
- QCHECK/formal review found and fixed real Flow-shape rejection, D6 runtime register/target drift, malformed UTC approval acceptance, and committed-example loading. No CRITICAL/HIGH findings remain.
- Dark gate evidence: tracked PM2 Scheduler and worker remain `CONTROL_EXECUTION_MODE=disabled`; SCADA defaults `ALLOW_MACHINE_COMMANDS=false`; no real approval/bundle/secret/grant is committed.

## Review (2026-07-21 16:27:23 +0700) - PR 7.3b working tree

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend`
- Branch: `feat/7-3b-dark-deployment-observability`
- Baseline: `9eeb63a6afb9a4c89d8a9e62024e873eee9560aa` (local-main merge of PR 7.3a)
- Scope: central/field PM2 topology, exact-release and migration preflight, Prometheus scrape/rule configuration, safe evidence CLI, CI routing, tests, and operations documentation.
- Commands Run: bounded status/stat and targeted source/test review; `git diff --check`; PM2 Prettier, TypeScript, ESLint, Jest, and build; Scheduler migration/model/readiness/heartbeat slice; SCADA TypeScript, ESLint, full Vitest, and build under Node 22; YAML parser fallback because `promtool` is not installed; built field-topology smoke.

### Findings

CRITICAL

- No unresolved findings.

HIGH

- RESOLVED: the initial HTTP collector called `response.text()` and checked size only after buffering, so a hostile or broken endpoint could defeat the advertised evidence bound. `readBoundedResponse()` now streams, cancels immediately beyond the byte cap, and has exact-boundary/overflow tests.
- RESOLVED: a successful `pm2 jlist` with a missing, stopped, duplicate, or old-release process initially produced an empty/partial process list without an explicit failure signal. `assessPm2Processes()` now checks every role-owned process for presence, uniqueness, online status, and exact current-release cwd; defects appear in `unavailable` and are covered by a whole-structure test.
- RESOLVED: caller-controlled collection timestamps, artifact basenames, and unavailable keys could bypass value projection and leak secret-shaped text. The safe builder now accepts only UTC collection timestamps and non-sensitive bounded identifiers, substitutes an ordinal artifact label when unsafe, and has an adversarial regression test.

MEDIUM

- RESOLVED: the field process `cwd` was correct when TypeScript ran from source but resolved to `infra/services/scada-gate-control` from compiled `dist`. Repo-root resolution is now source/dist aware in the common builder, the redundant override is gone, and both unit and built-JS smoke tests prove the service cwd.
- RESOLVED: non-2xx Scheduler readiness was initially discarded as merely unavailable, losing the safe migration/table failure details operators need. JSON readiness now retains its bounded allow-listed body and numeric HTTP status even on 503; metrics still reject non-success responses.
- RESOLVED: heartbeat and execution-family alerts could remain absent rather than firing on an old binary, and a down metrics target could suppress scrape-error series. Rules now cover absent worker/execution metrics and `up == 0` in addition to readiness, scrape error, rejection, mismatch, in-doubt, and shadow-write signals.
- RESOLVED: preflight checked source entry points but omitted the Flow/Scheduler virtualenv executables that PM2 actually invokes. Central preflight now requires both Python and Uvicorn binaries for both services before replacement.

LOW

- No unresolved findings. `promtool` is unavailable locally, so YAML parsing plus exact metric/rule contract tests are the local fallback; the runbook still requires site `promtool` validation before Prometheus reload.

### Function checklist

- Major functions use existing deployment vocabulary, bounded inputs, static failure text, and injected/pure records where testability matters. No new class was introduced.
- Complexity remains linear: migration parity, PM2 assessment, allow-list projection, and streamed HTTP collection each have one bounded responsibility.
- External dependencies are explicit (`git`, `psql`, `pm2`, HTTP); errors never surface captured stderr or process environments.

### Test checklist

- Tests fail for real release/schema/topology/redaction/alert defects and compare whole reports where practical.
- Current migration 0013 is locked to its independently computed full checksum without forbidding future migrations.
- Secret projection tests use adversarial PM2 env, readiness debug, metric, count, timestamp, filename, and unavailable-key inputs.
- Service/database-touching checks remain separate from pure infra unit tests.

### Open Questions / Assumptions

- The SRE/commissioning owner must choose and substitute the real central/field scrape targets; tracked examples use `.example.invalid` and cannot silently point at a field host.
- No live deployment, migration, secret provisioning, artifact loading, Prometheus reload, authority grant, PLC request, or external evidence capture is performed by this local PR.

### Rollout Notes

- Run role-specific preflight against the approved full SHA before `pm2 startOrReload`; any missing/extra/checksum-drifted Scheduler migration, stale checkout, missing binary, wrong topology, or armed command flag fails closed.
- Collect central and field evidence separately after deployment. An unavailable probe or process is named, never converted into green evidence.
- Both command gates remain dark. Trust artifacts/service auth are optional host inputs and require a separate approved cutover.

## PR 7.3b implementation evidence

- TDD RED: missing field topology/preflight/evidence modules; missing monitoring files; missing CI path/job; central trust pass-through not wired; bounded HTTP and PM2 runtime assessment modules absent; alert inventory missing target/absent-series coverage.
- PM2 GREEN: Prettier check, TypeScript, ESLint, Jest `39 passed`, and production build; final reliability pass repeated three times at `39 passed` each.
- Scheduler smoke: migration runner, migration/model parity, readiness, and worker-heartbeat slice `68 passed`.
- SCADA smoke: Node 22 TypeScript and ESLint green; full Vitest `421 passed, 7 skipped`; production build green. Node 26 produced an upstream V8 CJS-loader crash after an otherwise complete passing suite, so the supported Node 22 gate was used for the definitive run.
- Config syntax: Prometheus/rule/workflow YAML parsed successfully. `promtool` is not installed locally, so site `promtool` remains a deployment gate.
- Built topology smoke: compiled field builder resolves `scada-gate-control` to the real repository service cwd and reports `ALLOW_MACHINE_COMMANDS=false`.
- CLI fail-closed smoke: dirty-release preflight and wrong-commit evidence collection exited nonzero with static messages and did not echo injected secret values.
- Formal review fixes: streaming HTTP cap, exact PM2 presence/status/cwd evidence, caller-metadata redaction, compiled field cwd, 503 readiness preservation, absent/down alert coverage, and actual venv binary checks. No unresolved CRITICAL/HIGH findings.
- Dark evidence: central Scheduler/worker remain `CONTROL_EXECUTION_MODE=disabled`; field SCADA remains `ALLOW_MACHINE_COMMANDS=false`; examples use `.example.invalid`; no real target, secret, approval, artifact, migration, grant, drill, or machine call is included.

## Local landing and exact-main verification

- PR 7.3a product commit: `04c827d5` (`feat(control): add dark commissioning trust contracts`).
- PR 7.3a first local-main merge: `9eeb63a6`; exact-main Flow/Scheduler/SCADA focused verification passed before PR 7.3b began.
- PR 7.3b product commit: `36035ff6` (`feat(control): add dark deployment readiness tooling`).
- Final local-main merge: `2623b1cd`. Local `main` had incorporated current `origin/main` `e364d17f` before the final merge; `2623b1cd` contains both PR 7.3a and 7.3b histories plus that newer ops baseline.
- Exact-final-main infra: formatting, TypeScript, ESLint, Jest `39 passed`, and build.
- Exact-final-main Scheduler: migration/model/readiness/heartbeat/commissioning-contract slice `71 passed`.
- Exact-final-main SCADA under Node 22: TypeScript, ESLint, full Vitest `421 passed, 7 skipped`, and build.
- Exact-final-main central preflight approved `2623b1cd`, complete fixture parity through `0013_operator_approved_execution`, unique Scheduler/worker topology, and `CONTROL_EXECUTION_MODE=disabled`.
- Exact-final-main field preflight approved `2623b1cd`, dedicated `scada-gate-control` topology, and `ALLOW_MACHINE_COMMANDS=false`.
- The exact-main preflight used a temporary offline applied-migration fixture with independently computed current checksums; no live database, process, host, or external system was changed.

## Review (2026-07-22 09:10:34 +0700) - PR 7.3a submission commit

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-pr73a-submit-20260722`
- Branch: `feat/7-3a-dark-commissioning-trust`
- Scope: commit range `80f3060f3bce0de721d20c9e1408fe9305502d32...17d4b4a9`; rebased PR 7.3a product commit only.
- Commands Run: bounded diff name/stat and targeted patch inspection; exact wiring searches; Flow and Scheduler Black; Flow descriptor `--check`; Flow/Scheduler focused and full pytest; SCADA Prettier, TypeScript, ESLint, Vitest, and build; three reliability passes; whitespace and bounded secret scan.
- Auggie semantic retrieval was abandoned at the required two-second timeout; direct file inspection and exact-symbol searches were used as the documented fallback.

### Findings

CRITICAL

- No findings.

HIGH

- No findings. Flow validates and content-binds the approval at startup and snapshot construction; Scheduler independently revalidates the stored v4 artifact; SCADA binds the rich bundle to the live unit/register map and writable target levels.

MEDIUM

- No findings. Every new module has a production call site, strict invalid configuration fails closed, and unset approval/bundle configuration preserves the existing dark behavior.

LOW

- No findings.

### Open Questions / Assumptions

- Real approval, D6 field bundle, credentials, authority grant, and field register truth remain external commissioning inputs and are intentionally absent.
- Opt-in database suites remain skipped without disposable loopback test URLs: Flow 14, Scheduler 59, and SCADA 7. The bare service gates pass exactly as configured.
- Node 26 triggers the previously documented upstream V8 CJS-loader crash; supported Node 22.22.3 passes all three SCADA reliability runs.

### Recommended Tests / Validation

- Focused Flow approval/snapshot/readiness suite: `66 passed`.
- Focused Scheduler authority/client/contract suite: `194 passed, 12 skipped`.
- Full Flow suite: `1353 passed, 14 skipped` on each of three runs.
- Full Scheduler suite: `1025 passed, 59 skipped` on each of three runs.
- Full SCADA suite under Node 22: `421 passed, 7 skipped` on each of three runs; format, typecheck, lint, and build also passed.
- Prediction-engine descriptor, Black, whitespace, dark-gate, wiring, and bounded secret checks passed.

### Rollout Notes

- This submission changes no runtime, deployment, migration, authority, or machine-command state.
- `CONTROL_EXECUTION_MODE=disabled` and `ALLOW_MACHINE_COMMANDS=false` remain the tracked defaults.
- Any future rich-bundle trust cutover must use operations-owned evidence and rotate the validation receipt store as documented.

## Review (2026-07-22 09:19:22 +0700) - SCADA token authority-boundary test repair

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-pr73a-submit-20260722`
- Branch: `test/scada-token-authority-boundary`
- Scope: one-line test-only change in `command-intent-execute.spec.ts` after exact merged PR 7.3a produced intermittent `403` responses in two positive execution-route tests.
- Root cause: the module-level authority deadline was five minutes ahead with millisecond precision while JWT `exp` was generated five minutes ahead at whole-second precision. Token creation after a second boundary could therefore place `exp` up to one second beyond the authority deadline and correctly trigger the production fail-closed check.

### Findings

CRITICAL

- No findings.

HIGH

- RESOLVED: the positive-test token now expires after four minutes, strictly inside the five-minute authority window. Production route and verifier behavior are unchanged.

MEDIUM

- No findings.

LOW

- No findings.

### Test and quality evidence

- TDD RED came from the exact merged PR 7.3a tree: two existing positive execution tests intermittently returned `403` instead of `200` and `503`.
- The focused file passed 20 consecutive runs under Node 22.22.3: `5 passed` each run.
- The complete SCADA suite passed three times: `421 passed, 7 skipped` each run.
- Prettier check, TypeScript, ESLint, production build, and `git diff --check` passed.

### Rollout Notes

- This is test-only and does not alter service authentication, token validation, authority grants, runtime configuration, or machine-command state.

## Review (2026-07-22 09:24:51 +0700) - PR 7.3b submission commit

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-pr73a-submit-20260722`
- Branch: `feat/7-3b-dark-deployment-readiness`
- Scope: commit range `2e124d74...f0c2fac8`; PR 7.3b rebuilt from refreshed `origin/main` after PR 7.3a and the SCADA post-merge test repair.
- Patch identity: stable patch id `a7225a958c12d60e023750b625bf102a958810c7` exactly matches the previously implemented and reviewed product commit `36035ff6`.
- Review reused the full prior function/test/implementation QCHECK because the product patch is byte-equivalent; fresh base-sensitive gates were rerun against current `origin/main`.

### Findings

CRITICAL

- No unresolved findings.

HIGH

- No unresolved findings. Exact-release, migration, process-topology, streaming evidence bounds, and secret projection remain fail closed.

MEDIUM

- No unresolved findings. Central and field process roots, non-success readiness evidence, absent metrics, scrape failures, and required venv binaries remain covered.

LOW

- No unresolved findings. `promtool` remains unavailable locally; YAML parsing and exact monitoring-rule tests are the documented fallback, while site `promtool` remains a deployment gate.

### Test and quality evidence

- PM2 infrastructure verify passed three times: formatting, TypeScript, ESLint, and `39 passed`; production build passed.
- Scheduler migration/model/readiness/heartbeat/commissioning slice: `71 passed`.
- SCADA Node 22.22.3: TypeScript, ESLint, full Vitest `421 passed, 7 skipped`, and production build passed.
- Workflow and Prometheus YAML parsed; whitespace, dark-gate, bounded secret, and exact patch-identity checks passed.

### Rollout Notes

- This PR adds dark deployment readiness only. It does not apply migrations, provision secrets, load approval artifacts, reload Prometheus, mutate PM2, issue authority, or enable machine commands.
- Central remains `CONTROL_EXECUTION_MODE=disabled`; field remains `ALLOW_MACHINE_COMMANDS=false`.

## GitHub lifecycle completion (2026-07-22 09:27:20 +0700)

- PR 7.3a: `#115`, admin-squash-merged as `0df6d6181107d65e62dccc990e3fb20c5f636b65` after formal QCHECK/g-check and local three-pass service gates.
- Exact PR 7.3a post-merge validation exposed an intermittent existing SCADA test-fixture boundary race. Production fail-closed behavior was retained; the test-only repair was reviewed, opened as PR `#116`, and admin-squash-merged as `2e124d7414d52ecb7b8fb41cfc9d9e6455aceec2`.
- PR 7.3b: `#117`, rebuilt from refreshed `origin/main`, verified to have the same stable patch id as the reviewed product commit, then admin-squash-merged as `8095bfe37550200da00ecb554edc646febf8aff9`.
- Every GitHub check annotation on PRs `#115`, `#116`, and `#117` reported that the job was not started because the account is locked due to a billing issue. Each PR includes an admin-evidence comment with the successful local replacement gates.
- Exact final remote-main infra: Prettier, TypeScript, ESLint, Jest `39 passed`, and build.
- Exact final remote-main Scheduler: migration/model/readiness/heartbeat/commissioning slice `71 passed`.
- Exact final remote-main SCADA under Node 22.22.3: TypeScript, ESLint, Vitest `421 passed, 7 skipped`, and build.
- Final remote `main`: `8095bfe37550200da00ecb554edc646febf8aff9`.
- Software is landed but runtime remains dark: no deployment, migration apply, artifact/secret provisioning, authority grant, PM2/Prometheus mutation, PLC request, or machine write occurred.

## Primary local landing (2026-07-22 09:28:38 +0700)

- The clean primary checkout at `/Users/subhajlimanond/dev/munbon2-backend` is on `main` at `8095bfe37550200da00ecb554edc646febf8aff9`, exactly equal to `origin/main`.
- The prior divergent local-only `main` tip is preserved recoverably as `archive/local-main-pr73-pre-github-20260722` at `efbdf5cfdc06f6e82e9560af40af5a49d9f54915`.
- The durable lifecycle log and pointer are published on `origin/ops/archive-pr-7-3a-7-3b-commissioning-readiness-20260722`.
