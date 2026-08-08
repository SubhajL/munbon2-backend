# Coding Log: PR 6/7 remediation and PR 8/9 sequencing review

Date: 2026-08-06
Mode: analysis and planning only
Repository: `/Users/subhajlimanond/dev/munbon2-backend`
Backend baseline: `4029b86bcdd9da3bbe6a7c98128f6b9ee9afa622`
Frontend baseline: `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`

## Request

Decide whether to accept a proposed four-PR remediation program for PR 6 and
PR 7, including a BFF authorization split and local JWT verification, and
whether remediation should precede or follow PR 8, PR 9, and the write gate
flip.

## Skill and exploration record

- `g-planning`: used because the request asks for a detailed multi-PR execution
  decision with dependencies, file scope, tests, and wiring verification.
- `g-review`: used because the proposed local JWT verifier changes a security
  boundary and needs system-level review.
- Auggie semantic exploration was attempted with the required 1.8-second
  timeout and timed out. The review continued with bounded direct source,
  migration, test, runbook, and Coding Log inspection.
- No product source, tests, branches, commits, remotes, PRs, or runtime state
  were changed.
- A separate remediation worktree already exists at
  `.claude/worktrees/pr6-pr7-remediation`; it was treated as another team's
  workspace and inspected read-only.

## Decision summary

1. Agree with real OrbStack acceptance. Source-only tests cannot establish
   browser, outage, database, sequencing, logout, and restored-dark behavior.
2. Do not agree that PR 6/7 remediation requires changing product authorization
   or adding local JWT verification to the BFF.
3. Remediate PR 6/7 now, before PR 8 and PR 9. PR 8 depends on the persist-only
   proof; PR 9 depends on all prior gates and exact final SHAs.
4. Do not flip any external/production-equivalent gate as part of remediation.
   Temporary local false/true/false drills are allowed only inside the named
   acceptance stages, with fail-safe restoration to false.
5. If the product truly requires field-team planning-depth reads during a
   Scheduler outage, treat it as a separate security architecture program,
   preferably after the existing dark acceptance train is repaired and closed.

## Settled facts

### What the PR 6/7 review actually requires

The formal review found that the outage stage fabricated
`reads_preserved=true`; its requested fix was to attempt a real read and report
the actual result. It did not require planning-depth reads to succeed during a
Scheduler outage.

The formal review also requires:

- real browser form interaction instead of direct `fetch` standing in for UI;
- mutation observation on every page/context;
- exact replay of the captured canonical request;
- deterministic outage injection and inspection of the real Submit control;
- real logout response, reload behavior, and refresh-token revocation;
- schema-correct, fail-closed persistence snapshots;
- target-bound row/hash diffs and same-database sequential execution.

The remediation team's first adversarial synthesis independently reached the
same truthful framing:

- field-team planning-depth roster/active reads return 403 under the current
  product contract; prove Submit is absent and forbidden mutations do not occur;
- during Scheduler outage, planning-depth reads fail; prove Submit is
  hidden/disabled, no successful POST occurs, and do not claim those reads were
  preserved.

Those are acceptance-harness corrections, not product behavior changes.

### Current authorization boundary

All planning-depth reads and writes call `load_operator_principal`, which:

1. forwards the bearer token to Scheduler;
2. maps Scheduler authentication/availability/contract failures;
3. requires `operator` in `effective_roles`.

Consequently:

- field-team planning-depth reads are 403 by design;
- Scheduler outage makes planning-depth principal resolution unavailable;
- writes remain operator-only;
- the BFF currently treats Scheduler as the JWT authority.

### Why the proposed JWT plan is unsafe as written

The proposed implementation says to mirror
`ops/control-plan-read-runtime/verify_bearer.py`. That file's
`decode_jwt_claims` only base64-decodes the payload. It does not verify the JWT
signature. Its claim checks are safe in their original harness context only
because the token was already exercised against authoritative server endpoints.
It is not an authentication implementation to copy into the BFF.

The Scheduler's real authentication path additionally provides:

- pinned-algorithm signature verification;
- required expiry and configured clock skew;
- mode-aware token claim-policy validation;
- token type, subject, JTI, issuer, audience, and role semantics;
- fail-closed Redis revocation checks;
- dual-read compatibility for hashed and legacy revocation keys;
- role hierarchy and active-user policy.

A BFF verifier limited to HS256 plus secret/issuer/audience/expiry can accept a
token Scheduler would reject, especially a revoked token. Conversely, a stricter
but non-parity implementation can reject legitimate tokens. This is a new
security authority, not a moderate extension of the harness.

### PR 8/9 dependency

The accepted roadmap defines:

`LOCAL-WRITE-UI-1 -> LOCAL-PERSIST-ONLY-1 -> LOCAL-WRITE-ACT-1 -> LOCAL-RC-1`

PR 8 rehearses false/true/false activation, failures, reconciliation, stability,
rollback, and immutable history. PR 9 recreates disposable state and executes
every local stage without skipped drills or manual repair at exact final SHAs.
Therefore PR 8/9 cannot truthfully consume the current PR 6/7 result.

### Earlier PR 3/4 gap that also blocks PR 8/9

The read-only PR 1-5 audit found no remaining CRITICAL/HIGH defect from PR 1/2
on current frontend `main`, but it found one unresolved HIGH backend defect from
PR 3/4: roster provenance is read in one database connection, discarded down to
section values, and those values are persisted in a later connection/transaction.
The immutable submission stores request and expanded hashes but not
`dataset_version_id` or `source_hash`.

An authority activation between the two connections can therefore commit a
submission expanded from a roster that is no longer current, and the ledger
cannot prove which roster revision produced its 41 values. The advisory lock
serializes submissions for a planning week; it does not serialize or bind the
ROS/GIS authority activation. This is directly relevant to PR 8 activation and
PR 9 release-candidate evidence and needs a focused disposition before either
gate proceeds.

## Draft A: narrow acceptance remediation before PR 8/9 (recommended)

### Goal

Make PR 6 and PR 7 acceptance-ready without changing production authorization,
then prove them against the real OrbStack frontend, BFF, Scheduler, Auth,
Postgres, and Redis environment.

### PR A0: bind roster provenance atomically

Repository: `munbon2-backend`

Scope:

- add an additive migration after 011 that stores the roster
  `dataset_version_id` and `source_hash` used by each planning-depth submission;
- retain provenance in the typed roster value passed to persistence rather than
  discarding it to a plain section list;
- load/validate the authoritative roster within the same write transaction that
  obtains the planning-week advisory lock and inserts the immutable submission,
  or establish an equally strong database-enforced binding to the active
  version;
- include provenance in durable ledger reads and snapshot hashes without
  weakening legacy-row compatibility;
- add migration-built Postgres tests that activate a replacement authority
  version between request setup and commit and prove the stored provenance and
  expanded values remain one coherent snapshot.

Exit gate:

- legacy migration and read compatibility is proven;
- create, correct, replay, conflict, and concurrent-successor tests remain green;
- a real-Postgres authority-activation race test is green;
- independent review has no unresolved CRITICAL/HIGH finding.

### PR A1: persist-only and shared harness foundation

Repository: `munbon2-backend`

Scope:

- replace nonexistent snapshot tables/columns with migration-backed schema;
- abort the stage on any snapshot/query/normalization failure;
- canonicalize and hash all relevant row fields, including mutable status and
  publication fields where present;
- bind W2 diffs to the create/correct receipt IDs, lineage, expected row counts,
  canonical values, and request hashes;
- reject missing, substituted, negative, zero, and unrelated W2 deltas;
- isolate persist-only to a deterministic, prechecked scope distinct from the UI
  stage and give `_persist_only_rid_week` its own RID-calendar contract;
- remove the frozen frontend SHA constant from `run_local_base`; validate the
  guest checkout against `context.frontend_sha`, while orchestration validates
  that reviewed SHA against frontend `origin/main`;
- make frontend dark environment construction delete inherited write-path
  variables instead of allowing host-env leakage;
- use the actual `MUNBON_OPERATOR_*` bootstrap names;
- pass `--as-of-date` through orchestration;
- explicitly account for permitted Redis DB 2 rate-limit mutations and
  `auth.refresh_tokens` session/logout mutations;
- guarantee cleanup in outer `finally` paths and prove a post-disarm 503 dark
  probe.

Verified schema targets include:

- `water_planning.planning_depth_submissions`;
- `water_planning.planning_depth_values`;
- `ros_gis.water_requirement_runs`;
- `ros_gis.daily_water_requirements`;
- `scheduler.control_plan_runs`;
- `scheduler.control_plan_campaign_versions`;
- `auth.refresh_tokens` (the Auth DataSource sets schema `auth`).

Exit gate:

- focused unit/contract tests green;
- migration-built disposable-Postgres integration proves every snapshot query;
- same-database UI-then-persist sequencing test green;
- QCHECK and independent formal review have no unresolved CRITICAL/HIGH finding;
- source PR lands, but is not yet called runtime accepted.

### PR A2: write-UI browser and behavioral evidence

Repository: `munbon2-backend`
Dependency: PR A0 and PR A1 landed
Frontend dependency: current reviewed PR 5 SHA unless runtime inspection finds a
real frontend defect

Scope:

- drive week selection, depth editing, Save, and Submit through the real DOM;
- capture the outgoing POST bytes and correlate them with the reduced camelCase
  proxy receipt;
- resend the captured bytes unchanged and require 200, `replayed=true`, and the
  original submission ID;
- separately mutate the same client ID body and require 409;
- install method/path mutation classifiers for every browser context and page;
- induce deterministic Scheduler/principal failure using the established
  coordination pattern;
- assert planning-depth reads become unavailable, Submit is absent/disabled,
  and no write succeeds; never label these reads preserved;
- use field-team credentials to assert planning-depth 403, Submit absent, and no
  forbidden mutation; a named non-planning read may be reported only if a real
  DOM selector and response prove it;
- invoke the actual logout behavior, require the response contract, verify the
  refresh token is revoked, reload to `/login`, and prove protected retry fails;
- keep source-string checks only as supplemental tests, not as runtime proof.

Exit gate:

- focused Python and Node tests green, including negative sensitivity cases;
- independent formal review closes all PR 6 browser findings;
- source PR lands, but acceptance status waits for the combined runtime run.

### Combined OrbStack acceptance

After A1 and A2 land:

1. Provision exact backend and frontend SHAs.
2. Build a clean disposable state from migrations.
3. Run all nine currently defined stages sequentially against one live database.
4. Do not repair the database manually or skip a drill.
5. Produce sanitized evidence with exact SHAs and verified hashes.
6. Require frontend and BFF write flags false at the end, including after
   induced failure.
7. Only then mark PR 6/7 remediated and unblock PR 8.

### Files expected to change

- `services/bff-water-planning/migrations/012_<roster-provenance>.sql`
  - additive immutable roster version/hash columns, constraints, and legacy-row
    compatibility.
- `services/bff-water-planning/src/db/planning_depth_repository.py`
  - retain provenance and bind roster loading to the write transaction.
- `services/bff-water-planning/src/api/routes/planning_depths.py`
  and `planning_depths_v2.py`
  - stop loading a lossy roster snapshot in a separate connection.
- `services/bff-water-planning/src/schemas/planning_depth_submission.py`
  and/or `planning_depth_v2.py`
  - expose provenance only where the versioned immutable contract requires it;
    avoid unrelated capability fields.
- `services/bff-water-planning/tests/integration/test_planning_depth_postgres.py`
  - migration compatibility, provenance, and authority-activation race proof.
- `ops/control-plan-read-local/run-stage-suite.py`
  - snapshot schema, canonical row hashing, RID scope, shared source/env checks,
    cleanup, stage validators.
- `ops/control-plan-read-local/run-write-browser.js`
  - DOM workflow, captured request/replay, all-context mutation classifier,
    outage, field-team, and logout proofs.
- `ops/control-plan-read-local/orchestrate.py`
  - `--as-of-date` propagation and exact-SHA plumbing if not already complete.
- `ops/control-plan-read-local/tests/test_stage_suite.py`
  - snapshot/diff/RID/restoration and validator sensitivity tests.
- `ops/control-plan-read-local/tests/test_orchestrate.py`
  - date and SHA propagation tests.
- `ops/control-plan-read-local/tests/test_local_artifacts.py`
  - browser wiring and env-name contract tests.
- a colocated Node test for the extracted request classifier, or the existing
  browser-test location if one is already canonical.
- `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md`
  - exact invocation, truthful outage semantics, and artifact status.
- sanitized evidence files only after the real run.

No BFF authorization route, JWT verifier, API schema, or frontend capability
policy file is part of Draft A.

PR A0 necessarily changes the planning-depth persistence schema and repository;
that product correctness fix is distinguished from the rejected JWT/authz scope
because it closes an already-shipped immutable-ledger provenance defect and is
required for trustworthy activation evidence.

### Function outlines

#### `_take_persist_snapshot(context) -> PersistSnapshot`

- execute every named query;
- fail on SQL, schema, decoding, or canonicalization error;
- sort rows by stable primary identity;
- include canonical full-row representation and digest;
- record Postgres plus explicitly permitted Redis/Auth side effects separately.

#### `_validate_persist_diff(before, after, receipts, scope) -> Evidence`

- require exactly the receipt-bound create and correction submissions;
- require correction predecessor equals create ID;
- require 41 canonical values per submission, 82 total;
- verify request/row hashes and expected active identity;
- reject every unrelated W2 mutation and every downstream ROS/Scheduler mutation.

#### `_persist_only_rid_week(as_of_date) -> RidWeekKey`

- produce a deterministic RID-v2 week distinct from UI stage scope;
- validate supported calendar boundaries and clean/precondition state;
- cover R01, R52/R53, November 1, and ending-year transitions.

#### Browser request classifier

- accept method, normalized URL/path, page/context identity, and armed state;
- allow only the exact authenticated read/write/logout set for the active drill;
- append all unexpected non-GET or off-contract requests to evidence;
- be pure enough for `node --test` boundary cases.

### Required tests

- each snapshot query executes against migrations, not a mock dictionary;
- any nonexistent table/column or query error fails closed;
- empty-to-empty, zero, negative, substituted, unrelated, wrong-lineage, wrong
  count, changed hash, and missing-value evidence fail;
- UI stage followed by persist-only stage on one database succeeds without
  cleanup or manual repair;
- every RID-calendar boundary matches an independently precomputed oracle;
- dark env removes inherited write-path variables;
- every JavaScript-required credential exists in its Python launcher env;
- outgoing request bytes equal replay bytes;
- same client ID with changed bytes returns 409;
- unexpected mutations from a second page/context fail;
- healthy, Scheduler-outage, field-team, and logged-out states are distinguished;
- outage never claims planning-depth reads were preserved;
- logout status, refresh revocation, redirect, and protected retry are all
  independently asserted;
- failure injection at each stage still restores both flags false.

## Draft B: product authorization and local JWT program

### Goal

Make planning-depth reads available to any authenticated principal and keep them
available while Scheduler is down.

### Benefit

- literal field-team planning-depth read success;
- reduced read-path dependency on Scheduler availability;
- explicit read/write capability separation.

### Costs and risks

- creates a second JWT authority inside the BFF;
- must preserve signature, algorithm, claim-policy, revocation, role, active-user,
  clock-skew, key-rotation, and error-taxonomy parity;
- couples BFF availability to a fail-closed revocation store unless the security
  model deliberately changes revocation semantics;
- creates a principal-dependent `can_submit` signal inside otherwise domain read
  responses, with cache/contract/versioning implications;
- requires frontend and backend rollout coordination and rollback compatibility;
- expands PR 6/7 acceptance remediation into a security/product program not
  required by the original findings.

### Minimum architecture work before implementation

- product decision: which read resources field-team may access and why;
- threat model and abuse cases;
- authoritative token/claim/revocation contract shared from one source;
- parity corpus run against Scheduler and BFF verifiers;
- fail-closed Redis outage policy and capacity/SLO analysis;
- key rotation, dual-key period, secret distribution, and rollback plan;
- inactive-user and role-change propagation semantics;
- capability contract choice, preferably a dedicated principal/capability
  projection rather than mutating immutable roster/active domain payloads;
- observability for verifier disagreement and staged shadow comparison;
- independent security review and real outage/canary proof.

### Recommended sequencing if separately authorized

Do not put Draft B on the PR 6/7 remediation critical path. First repair and
close Draft A, then complete PR 8 and PR 9 under the current contract. Start
Draft B afterwards as a separately named product/security initiative with its
own compatibility rollout. If the product owner instead declares outage-tolerant
field-team reads a prerequisite for activation, pause PR 8/9 and rebaseline the
roadmap explicitly; do not silently smuggle it into harness remediation.

## Comparative synthesis

| Criterion | Draft A | Draft B |
|---|---|---|
| Closes actual PR 6/7 findings | Yes | Indirectly, with extra scope |
| Requires production behavior change | No | Yes |
| Changes JWT trust boundary | No | Yes |
| Can precede PR 8 safely | Yes | Only after security architecture work |
| Runtime OrbStack proof | Required | Required plus verifier parity/security proof |
| Frontend source change | Not expected | Required |
| Risk | Harness/acceptance correctness | Authentication and authorization correctness |

Draft A is the minimal complete correction. Draft B may be a valid future
product direction, but it is not a valid shortcut for proving the current
contract and is underspecified as an authentication design.

## Unified execution plan

1. Freeze PR 8, PR 9, and any non-local gate flip.
2. Keep the remediation worktree isolated; preserve the primary checkout's
   unrelated dirty files.
3. Implement PR A0 test-first, including the migration-built authority-activation
   race proof; review and land it.
4. Implement PR A1 test-first and validate against migration-built Postgres.
5. Run QCHECK and independent formal review; remediate all CRITICAL/HIGH items;
   land A1 and update exact backend SHA.
6. Implement PR A2 test-first, including Node classifier tests and negative
   Python evidence validation.
7. Run QCHECK and independent formal review; land A2.
8. Provision OrbStack at exact landed backend/frontend SHAs and run all nine
   stages sequentially on one clean database.
9. Verify sanitized evidence hashes and both write flags restored false.
10. Proceed to PR 8 / `LOCAL-WRITE-ACT-1`; repeat its full activation/rollback
   gate at the new exact SHAs.
11. Proceed to PR 9 / `LOCAL-RC-1`; recreate clean state and rerun every stage.
12. Keep all external gates dark. Any production/AWS gate flip remains a later,
    separately authorized operation after `LOCAL-RC-1 PASS`.
13. Open a separate product/security decision only if outage-tolerant field-team
    planning-depth reads remain desired.

## Wiring verification table

| Requirement | Implementation | Unit/contract proof | Integration/runtime proof |
|---|---|---|---|
| Roster provenance is atomic | migration + transactional repository | typed provenance and legacy compatibility | authority-activation race in Postgres |
| Snapshot is fail-closed | snapshot query executor | injected SQL/schema failure aborts | migration-built Postgres query set |
| Only target W2 rows change | canonical keyed diff | substitution/unrelated/zero/negative cases fail | same live DB before/after |
| Create/correct lineage | receipt-bound validator | wrong predecessor/count/hash fails | two real submissions, 82 values |
| Distinct stage scopes | RID week functions | boundary oracle and inequality | UI then persist-only sequential run |
| Exact frontend source | context SHA preflight | stale/mismatch cases fail | guest checkout equals reviewed SHA |
| Dark env is truly dark | env constructor | inherited vars deleted | post-disarm 503 probe |
| Real UI write | Playwright DOM actions | selector/wiring checks supplemental | edit, Save, Submit, rendered receipt |
| Exact replay | captured byte buffer | mutation of one byte detected | 200 replay and original ID |
| Conflict behavior | same ID, changed body | validator requires 409 | live BFF 409 |
| All-context mutation policy | pure classifier | page/context/method/path matrix | unexpected page-2 mutation fails |
| Scheduler outage truth | coordinated outage state | unavailable is not preserved | reads fail, Submit blocked, no POST |
| Field-team truth | current auth contract | 403/forbidden policy | Submit absent and no POST |
| Logout cleanup | response/session validator | weak redirects/status fail | refresh revoked, reload `/login` |
| Final safety | outer cleanup | every injected failure restores | both flags false after suite |

## Cross-language and schema verification

- Python stage queries must match SQL migrations exactly, including schema and
  primary key names.
- Python validators must match the Next.js proxy's reduced camelCase receipt;
  fields absent from that receipt must come from the captured outgoing request
  or authoritative database row, not be fabricated.
- JavaScript request bytes and Python evidence schema need one canonical
  encoding contract and explicit version.
- Auth side-effect queries must use schema `auth`; TypeORM's DataSource sets it
  even though `@Entity('refresh_tokens')` is unqualified.
- Redis rate-limit inspection must use the BFF's configured DB 2 namespace and
  must not assume the Auth revocation namespace shares the same logical DB.

## Decision completeness

### Assumptions

- The goal remains acceptance of the current shipped planning-depth contract,
  not a newly approved field-team/offline-read product requirement.
- Current exact SHAs were reverified locally; remote state can drift and must be
  rechecked immediately before implementation and runtime acceptance.
- The existing frontend PR 5 behavior is sufficient until a real browser run
  proves otherwise.

### Failure policy

- Any snapshot/query/evidence ambiguity fails the stage.
- Any unresolved CRITICAL/HIGH review item blocks landing or dependent stages.
- Any source/harness SHA change invalidates prior exact-SHA runtime evidence.
- Any cleanup failure leaves acceptance failed even if functional assertions
  passed.
- No absent or billing-blocked hosted job is reported as passing.

### Idempotency and concurrency

- Replay proof uses byte-identical captured request bytes and stable client ID.
- Persist-only uses a prechecked distinct scope; unexpected existing active rows
  fail with actionable diagnostics rather than being deleted.
- Browser mutation evidence records page/context identity to avoid hidden
  concurrent writes.
- Sequential stage acceptance uses one database to expose cross-stage residue.

### Observability and evidence

- Evidence names exact backend, frontend, harness, migration, and test SHAs.
- Runtime outcomes remain distinct from source tests and hosted CI state.
- Evidence is sanitized before export and hash-listed after final write.
- Outage fields describe observed statuses and selectors; no synthetic success
  booleans are allowed.

## System review

### End-to-end pipeline

```text
reviewed backend/frontend SHAs
  -> OrbStack guest provisioning
  -> clean migrations and service readiness
  -> operator/field-team authentication
  -> frontend DOM interaction
  -> Next.js proxy
  -> BFF principal projection through Scheduler
  -> Postgres W2 persistence + Redis rate limit
  -> browser/API/DB evidence correlation
  -> logout/Auth refresh-token mutation
  -> flags restored false
  -> sanitized exact-SHA evidence index
```

### Contract-drift matrix

| Producer | Consumer | Drift already observed | Required guard |
|---|---|---|---|
| SQL migrations | Python snapshot queries | nonexistent tables/columns | migration-backed execution |
| Next.js proxy | Python validator | snake_case/full receipt assumed | captured request + reduced camelCase schema |
| frontend UI | browser script | direct fetch bypassed form | real DOM actions and POST capture |
| UI stage | persist-only stage | same week caused stale active conflict | distinct deterministic scopes |
| host env | frontend guest env | dark inherited write variables | explicit deletion when dark |
| Scheduler auth | proposed BFF verifier | incomplete signature/claims/revocation parity | do not duplicate; separate security design |

### Strengths to preserve

- dark-by-default write flags and restoration checks;
- immutable append-only W2 submission model;
- exact-SHA evidence boundary;
- explicit named local gates before external activation;
- reduced proxy response and no-store authenticated reads;
- independent review requirement after prior self-review gaps.

### Severity-ordered risks

CRITICAL

- A local BFF JWT implementation copied from the harness decoder would not
  verify signatures and would bypass Scheduler's revocation/claim policy.
- Continuing PR 8/9 with current PR 6/7 evidence would certify a release train
  whose prerequisite database and browser proofs are known false.

HIGH

- Product authz expansion obscures whether the harness can truthfully test the
  current contract.
- Principal-dependent `can_submit` inside roster/active responses can create
  caching, schema, and compatibility errors.
- Source-only success can again be mislabeled as runtime acceptance.

MEDIUM

- Exact frontend/backend remotes can advance between planning and execution.
- Auth and Redis side-effect namespaces can be queried incorrectly if inferred
  rather than read from runtime configuration.
- A real browser run may expose an actual frontend selector or behavior defect;
  that should trigger a focused frontend fix, not preemptive policy redesign.

### Tactical roadmap

1. Land A0 roster-provenance correction.
2. Land A1 persist-only/shared harness correction.
3. Land A2 browser correction.
4. Run exact-SHA combined OrbStack acceptance.
5. Resume PR 8.
6. Run PR 9 clean RC.

### Strategic roadmap

If outage-tolerant field-team planning-depth reads become a real product
requirement, define an authorization architecture separately. Prefer one token
verification authority or a generated/shared verifier contract with explicit
revocation and rotation semantics. Roll out behind shadow parity metrics before
moving read traffic, and keep write authorization independently fail-closed.

## Final recommendation

Proceed now, but on Draft A rather than the proposed four-PR authorization
program. Keep PR 8, PR 9, and all gate flips blocked until the repaired PR 6/7
stages pass a real same-database OrbStack run at exact landed SHAs. Record the
field-team/offline-read idea as a separate product/security decision, not as a
silent expansion of acceptance remediation.
