# Development completion register

Status snapshot: 2026-11-02, Asia/Bangkok. This is the **single current status authority for the named V2 development scope**, not a certification of every historical service or a live operations dashboard. [Plan supersession index](PLAN_SUPERSESSION_INDEX.md) preserves the older plans and their original verdicts. [Repository rules](../../CLAUDE.md) remain the development-policy authority.

## Scope and decisions

The project owner (user) approved the V2 defaults and bounded local P01 on 2026-11-02:

1. Tracked TypeScript **email** is notifier source of truth; preserve ignored local Telegram output before any later clean build. No hidden channel fallback or stash manipulation.
2. Durable **outbox is the sole automatic sensor-processing path**. LISTEN only wakes that same consumer; unsupported direct/dual consumers must fail startup.
3. `SMARTFARM_ALLOW_VALVE_COMMANDS=false` is the independent default-deny boundary. Dark runtime must not initialize/contact MSSQL. This is an approved future implementation contract, not a claim current smartfarm already enforces it.
4. Support the existing worker aliases through shared factories, not duplicated services.
5. Hold uncertain/post-send outcomes for reconciliation; never automatically replay a possibly executed physical command.

The user is accountable for O-SEC, O-HIST and O-PROT-1 in **both backend and frontend**. Assignment is not evidence of rotation, history verification or effective protection, and grants no operational mutation. Other service/domain/data-owner assignments remain explicit prerequisites, not invented names.

P01 is source documentation/static validation only. S01 is the first subsequent production remediation. Ready work is selected by prerequisites, one production writer at a time; no stacking on unmerged changes. P07/P08-draft can progress when their own prerequisites are satisfied. P05 hosts existing frontend gates; it does not rebuild them.

## Identity and evidence rules

- Source inspection baseline: backend `2a53090c608331b282e331502ae1ec5851ae9c15`; frontend `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`. Both advertised main refs were reconfirmed November 2.
- Historical accepted local runtime: backend `a26c0fd000b0b6da443135ffeadb992eded8fb5b`, same frontend `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`; ten local stages plus wrapper, **11 passed**, 0 failed/unreached. `LOCAL-RC-1` has `campaign_ledger_eligible=false`.
- Frozen separate campaign: `2026-08-20-nine-stage-orbstack-7f032c4c-attempt-1`, **9 passed**, `successful_closed`. Do not append RC results or reinterpret its stage family.
- **No runtime acceptance transfers** to a new combined candidate SHA, including the current backend documentation/static-test descendant. Source equality or a running guest inventory cannot certify current health, deployment or activation.
- Current hosted capacity, effective protection, production health and live command gates were **not freshly queried** for P01. November 1/older billing/protection observations below remain dated evidence, not newly established facts.
- No unqualified development-complete while source-security, owner rotation/history disposition, required real DB, actual hosted checks or effective main protection remain open. No source merge grants operational authority.
- A `source-complete` row describes only its named source boundary. `pending` requires the row's fresh affected/release gate; it does not erase delivered source. Source inspection, senior-reported counts without attached exact commands/SHA/logs, and host-side frontend tests are not proof of a service's full gate or pinned-container gate. `historical-pass` means retained prior evidence for the stated limited scope, not tests rerun by P01. `historical-accepted` applies only to the exact local-RC artifact. `unaccepted` makes no claim about what may currently be running.
- Evidence locations are typed: `repo:` exists in this repository; `frontend:` identifies separate frontend source; `local:` is retained local planning authority; `external:` identifies retained private evidence. Local/external references are identity summaries, not portable repository links or automatically revalidated evidence.

Aliases: F-07-security includes the historical SEC finding; O-CI includes external action E6. The tables join by ID; every row's evidence supplies source refs, date, origin and candidate. Every row has a separate next gate, authorization prerequisite and done criterion. Static tests reject duplicate/missing records and candidate/family transfer. P01's detailed local gate/review outcomes are recorded in its [active Coding Log](<../../coding-logs/2026-11-02-15-46-03 Coding Log (p01-development-completion-register).md>); no push or merge is authorized by that record.

## Completion register

| ID | Owner | Source | Local | Runtime | Production | Family | Evidence | Disposition |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P01 | Primary coding session | source-complete | local-gates-passed | not-applicable | not-applicable | documentation | EV-P01 | Local candidate only; verified recovery receipt and static results in active log; review/delivery are separate gates |
| S01 | Backend maintainer (assignment pending) | planned | pending | not-reverified | unaccepted | plan | EV-V2 | Required next source-secret remediation; no security closure yet |
| P02 | Backend maintainer (assignment pending) | source-partial | pending | not-reverified | unaccepted | source | EV-SF | Existing mechanisms; five reproduced defects and six sequential S2.1–S2.6 slices remain |
| P02-D | Backend maintainer (assignment pending) | planned | pending | not-reverified | unaccepted | plan | EV-V2 | Separate dark smartfarm artifact required; canal topology is not its deployment artifact |
| P03 | Notifier maintainer (assignment pending) | source-partial | pending | not-reverified | unaccepted | source | EV-NOTIFIER | Email source delivered; clean reproducibility/channel artifact gap remains |
| P04 | Notifier maintainer (assignment pending) | source-partial | pending | not-reverified | unaccepted | source | EV-NOTIFIER | Line tail is not proven last-24-hour coverage |
| P05 | Frontend maintainer (assignment pending) | planned | pending | not-reverified | unaccepted | plan | EV-V2 | Hosted adapter only; existing exact-SHA local gates retained |
| P06-L | Lab owner (assignment pending) | planned | pending | not-reverified | unaccepted | plan | EV-V2 | Disposable-target identity guard/runner required; no lab provisioned here |
| P06-S | Sensor maintainer (assignment pending) | source-partial | pending | not-reverified | unaccepted | source | EV-SENSOR | Active service needs safe suite selection and acknowledgement repair |
| P06-H | Backend maintainer (assignment pending) | planned | pending | not-reverified | unaccepted | plan | EV-V2 | Host qualified service commands only after their source/lab prerequisites |
| P07 | Project owner (user) | planned | pending | not-reverified | unaccepted | plan | EV-V2 | Old PR hunk dispositions and exact legacy-template retirement; no blind merge/closure |
| P08-draft | Primary coding session | planned | pending | not-applicable | not-applicable | plan | EV-V2 | Draft manifest can proceed after P01; draft is not release acceptance |
| P08-final | Project owner (user) | planned | pending | not-reverified | unaccepted | plan | EV-V2 | Blocked until all applicable release/security/governance evidence exists |
| F-01 | Flow maintainer (assignment pending) | source-complete | pending | not-reverified | unaccepted | source | EV-FLOW | Corrected gate-flow core delivered; field validity not inferred |
| F-04 | Flow maintainer (assignment pending) | source-complete | pending | not-reverified | unaccepted | source | EV-FLOW | Real per-reach capacity source delivered; old 15.0-stub claim is historical |
| F-02 | RID/field owner (assignment pending) | source-complete | historical-pass | not-reverified | unaccepted | source | EV-CP | Dark/shadow and approved-execution/readback source delivered; periodic baselines remain empty |
| F-05 | Domain/field owner (assignment pending) | source-complete | pending | not-reverified | unaccepted | source | EV-MODEL | Planning-only inference/provenance delivered; 10 measured/48 inferred artifact records are not site attestation |
| F-06 | Product/domain owner (assignment pending) | source-partial | historical-pass | not-reverified | unaccepted | source | EV-ROS | Canonical ROS/Excel path delivered; legacy AquaCrop/sync source-policy debt remains |
| F-09 | Product/domain owner (assignment pending) | source-partial | historical-pass | not-reverified | unaccepted | source | EV-ROS | Canonical immutable lineage delivered; legacy formulas/callers not universally unified |
| F-07-data | GIS owner (assignment pending) | source-complete | historical-pass | not-reverified | unaccepted | source | EV-CROP | Tracked loader/tests/migration delivered; approved export and target-load acceptance external |
| F-07-security | Project owner (user) | source-partial | pending | not-reverified | unaccepted | security | EV-SEC | Security-open; source scan cannot prove rotation |
| F-08-boot | RID-MS maintainer (assignment pending) | source-complete | pending | not-reverified | unaccepted | source | EV-RID | Missing JobScheduler import/boot defect fixed with Bangkok cron |
| F-08-ingest | RID-MS owner (assignment pending) | source-partial | pending | not-reverified | unaccepted | source | EV-RID | Daily source-check is a logging scaffold; explicitly deferred from named dark release, not field-hardware work |
| E1 | Project owner (user) | not-applicable | pending | not-applicable | unaccepted | security | EV-SEC | Rotation OPEN/UNVERIFIED until sanitized owner proof |
| E2 | Project owner (user) | not-applicable | pending | not-applicable | unaccepted | history | EV-HIST | July 11 documented-executed purge; current refs/artifact/clone scope verification outstanding |
| O-SEC | Project owner (user) | not-applicable | pending | not-applicable | unaccepted | security | EV-SEC | Accountable owner assigned; cutover/revocation evidence still required |
| O-HIST | Project owner (user) | not-applicable | pending | not-applicable | unaccepted | history | EV-HIST | Reconcile documented E2 proof; no automatic repeat rewrite |
| O-PROT-1 | Project owner (user) | not-applicable | pending | not-applicable | unaccepted | governance | EV-GOV | Both repos need effective basic protections; historical unprotected/capability observations not freshly queried |
| O-PROT-2 | Project owner (user) | not-applicable | pending | not-applicable | unaccepted | governance | EV-GOV | Actual trusted required-check contexts and enforcement evidence still required |
| O-CI | Account-capacity contact (assignment pending) | not-applicable | pending | not-applicable | unaccepted | governance | EV-GOV | Historical zero-step billing refusal is not passing CI; fresh execution/capability unknown |
| SEN-GATE | Sensor maintainer (assignment pending) | source-partial | pending | not-reverified | unaccepted | source | EV-SENSOR | Active sensor-data cannot be omitted or qualified against operator defaults |
| SEN-ACK | Sensor maintainer (assignment pending) | source-partial | pending | not-reverified | unaccepted | source | EV-SENSOR | DeleteMessage on required-processing failure is a demonstrated source gap |
| LEGACY-SF | Project owner (user) | planned | pending | not-reverified | unaccepted | source | EV-LEGACY | One tracked template; no found executable consumer; exact retirement pending, ignored files protected |
| CP-SOURCE | Backend maintainer (assignment pending) | source-complete | historical-pass | not-reverified | unaccepted | source | EV-CP | BFF/auth/roster/RID-v2/control/readback/local harness source delivered; do not rebuild |
| FE-SOURCE | Frontend maintainer (assignment pending) | source-complete | historical-pass | not-reverified | unaccepted | source | EV-FE | Control-plan/read/write/proxy source delivered dark; not production activation |
| LOCAL-FE-CI-1 | Frontend maintainer (assignment pending) | source-complete | pending | not-reverified | unaccepted | source | EV-FE | Existing mandatory pinned-container local source gate delivered |
| LOCAL-FE-CI-2 | Frontend maintainer (assignment pending) | source-complete | pending | not-reverified | unaccepted | source | EV-FE | Existing mandatory pinned-browser combined gate delivered; fixtures are not live-service acceptance |
| LOCAL-RC-1 | Project owner (user) | source-complete | historical-pass | historical-accepted | unaccepted | local-rc | EV-RC | Exact August local acceptance retained; not acceptance of current backend SHA |
| HIST-CAMPAIGN | Project owner (user) | not-applicable | historical-pass | not-applicable | unaccepted | frozen-campaign | EV-CAMPAIGN | Frozen nine-stage successful_closed history; separate from RC |
| C-FIELD | RID/field owner (assignment pending) | deferred-by-design | pending | not-reverified | unaccepted | plan | EV-V2 | Separate approved baseline/commissioning contract required |
| C-PROD | Project owner (user) | deferred-by-design | pending | not-reverified | unaccepted | plan | EV-V2 | Separate inventory/deployment/acceptance/activation authority required |
| C-W4 | Product/domain owner (assignment pending) | deferred-by-design | not-applicable | not-applicable | unaccepted | plan | EV-V2 | Excluded from the named dark release |
| C-OPT | Product/domain owner (assignment pending) | deferred-by-design | not-applicable | not-applicable | unaccepted | plan | EV-V2 | Excluded from the named dark release |

## Remaining gates

| ID | Next gate | Authorization | Done criterion |
| --- | --- | --- | --- |
| P01 | Required final three static runs and native review recorded in active log, then separately authorize Git delivery | Local P01 and isolated recovery approved; Git delivery separate | Truthful register/docs and receipt-backed exact ignore exceptions; no runtime claim |
| S01 | Reconcile reviewed inventories and scan tracked candidate/full tree locally | Lock exact findings/files; no credential operation | Zero unapproved literals, redacted gate GREEN, owner rotation still separately proved |
| P02 | S01 then S2.1–S2.6; safe unit selectors, lifecycle, outcomes, durable claims, aliases, real labs | New bounded production slices and approved lab identity | Five original regressions plus full source/required real DB gates pass three times |
| P02-D | P02 and S01; independent smartfarm PM2/preflight/dark process tests | New exact artifact contract; no PM2 start/reload | Tracked exact-SHA artifact, loopback API, single consumer owner and zero dark MSSQL contact |
| P03 | S01; preserve local Telegram artifact; clean email build and inert import tests | Approved email default; builds only in isolated worktree | All declared commands use same reproducible source-owned email graph |
| P04 | P03; bounded aware 24h parser and real local browser/HTTP/SSH/SMTP lab | Explicit loopback lab/fixtures; no recipients | Truthful complete/truncated/unavailable coverage and failure cleanup proved |
| P05 | S01 and existing FE gates; main-based hosted adapter, then O-CI | New FE contract; no policy/billing mutation | Exact candidate/base pinned local gates plus actual nonzero-step hosted evidence |
| P06-L | Owner-approved lab profile and disposable-target identity tests | Named targets/versions/platform/fixtures; no shared or remote DB | Safe runner can land; absent required lab remains BLOCKED, not skipped-pass |
| P06-S | S01 and P06-L; unit isolation, failure acknowledgement and partial-write idempotency | Explicit queue/redrive and real lab contract | Required persistence gates acknowledgement; full safe source/required DB evidence |
| P06-H | P02/P02-D, P03/P04, P06-L/P06-S, S01; then O-CI | New workflow contract only | Same qualified commands hosted with actual steps and stable terminal summaries |
| P07 | Retained old PR path/hunk evidence and canonical/legacy reachability | Closure separately authorized; exact template deletion Luna-only | Each differing hunk dispositioned; unique work retained; no blind merge or recursive ignored-file deletion |
| P08-draft | P01; draft service-specific manifest and authority boundaries | Documentation only | Exact artifact/evidence/held-outcome fields explicit; missing gates remain blocked |
| P08-final | S01, O-SEC, O-HIST, O-CI, O-PROT-1, O-PROT-2 plus applicable source/real-DB/hosted/legacy/artifact gates | Release certification only when evidence complete; operations separate | No required skips/open security/governance uncertainty; all exact-candidate evidence bound |
| F-01 | Preserve gate-flow regressions; field physics acceptance remains distinct | New RED/domain review for any new physics change | Current guide reflects corrected core; no inferred field validation |
| F-04 | Preserve per-reach capacity regressions | New contract for any changed capacity semantics | No stale hardcoded-stub claim; current capacity source referenced |
| F-02 | Approved D6/pilot/capability/expected-baseline source, expiry/restart/held semantics | Separate C-FIELD contract and operational grant | Periodic baseline integration and field acceptance proved independently of delivered immediate readback |
| F-05 | Reconcile 58-record artifact versus older 59-gate universe; approved measurements/model proof | Domain/field owner and independent commandability approval | Coverage and field validity attested; inferred values never presented as measured |
| F-06 | Product confirms ROS/Excel authority and inventories supported live legacy callers | New bounded legacy retirement/adapter contract if selected | Each remaining legacy fallback has a decision; no second canonical producer |
| F-09 | Inventory live ROS/RID-MS formulas/callers and choose thin adapter/retirement | New bounded contract if supported paths need change | Canonical immutable lineage preserved; no universal unification claim without proof |
| F-07-data | Approved GIS export and separately authorized target load | GIS owner names data/target | Actual imported lineage/counts and real target acceptance recorded |
| F-07-security | S01 plus O-SEC and O-HIST dispositions | Source cleanup does not authorize secrets/history operations | Source inventory and owner receipts both close their independent boundaries |
| F-08-boot | Preserve missing-import/Bangkok cron regression | No new runtime start authorized here | Original boot defect remains fixed |
| F-08-ingest | RID-MS owner supplies ingest-source contract and chooses implement versus retire | Separate main-based behavior contract if supported at launch | All three jobs' real effects, unavailable status and idempotent start/stop proved; never boot-only proof |
| E1 | Owner response/cutover/revocation/verification receipts | Named security operation separately approved | Affected identities rotated/revoked or documented noncredential determination |
| E2 | Read-only reconcile July 11 proof/current applicable refs and carriers | Further rewrite needs fresh exact-ref grant and evidence mapping | Owner outcome covers refs, PR/cache/clone/artifact handling and preserved SHA consequences |
| O-SEC | Sanitized identity/scope/owner/time/cutover/revocation/evidence receipt | Separate credential grant, no old-literal login experiment | Compromise response verified without exposing values or reusable credential hashes |
| O-HIST | Obtain retained E2 proof and approved redacted current-ref/artifact process | Read-only first; no filter-repo/force-push by default | Documented work reconciled; further remediation independently authorized if needed |
| O-PROT-1 | Export/inspect then apply supported basic controls for both repositories | Owner/account action separately approved | Effective PR/review/direct-push/bypass/deletion/force-push restrictions evidenced, capability blocker explicit |
| O-PROT-2 | Real trusted check contexts after O-CI and O-PROT-1 | Owner policy grant and account capability | Fresh effective required-check snapshot/app identity and reviewer receipt for both repos |
| O-CI | Assign account-capacity contact; restore/verify actual execution | Spending/runner/billing action separate | Fresh named-candidate jobs execute nonempty steps; local/YAML success not substituted |
| SEN-GATE | P06-L/P06-S/P06-H safe selectors and owned Timescale/PostGIS target | No operator .env or shared/default DB | Full unit/build/lint/type and required real DB tests run without prerequisite skips |
| SEN-ACK | P06-S required persistence/partial-write idempotency and explicit redrive policy | No AWS/DLQ mutation implied | Failure/unknown input not deleted as success; successful required persistence permits one acknowledgement |
| LEGACY-SF | P07 exact tracked-template preservation/reachability check | Exact deletion through Luna; no ignored-secret inspection | Useful nonsecret contract retained, canonical path intact, obsolete tracked references retired |
| CP-SOURCE | Preserve current routes/contracts and mandatory full source gates; fresh DB gate at release | No rebuilding or old-guest rerun | Source delivery stays distinct from exact combined-release acceptance |
| FE-SOURCE | Preserve read/write/proxy contracts and default-dark flags | New FE changes require exact clean candidate gates | Existing source remains delivered; no implicit write activation |
| LOCAL-FE-CI-1 | Run for every future exact clean FE candidate with explicit ancestor base | Isolated worktree, pinned Linux ARM64 images | Install/format/types/lint/three-timezone tests/both dark builds and checksummed evidence pass |
| LOCAL-FE-CI-2 | Combined runner CI-1 then CI-2 at same candidate/base | Pinned browser/container, hermetic fixtures only | Both modes' real browser proxy smoke and cleanup pass; no hosted/live-service claim |
| LOCAL-RC-1 | Preserve exact evidence; new combined artifact needs separately authorized fresh acceptance | No reuse of old guest or evidence relabeling | Current source status never inherits predecessor runtime approval |
| HIST-CAMPAIGN | Preserve ledger and historical validator contract | No append/reinterpretation under P01 | Nine-stage history unchanged and RC remains ledger-ineligible |
| C-FIELD | Versioned approved expected baseline with pilot/freshness/supersession/restart semantics | New bounded source and field commissioning grants | Real integration/commissioning evidence before commandability claims |
| C-PROD | Scoped read-only inventory, proposal, exact dark deployment, independent acceptance, separate activation | Fresh named account/region/target grant at each phase | Each phase's authority/evidence explicit; no implemented aws-inventory CLI assumed |
| C-W4 | Retain persist-only; new equation/units/temporal allocation/correction/lineage contract only if selected | Separate product/schema approval; ROS 0004 already occupied | No recomputation smuggled into MVP or immutable history |
| C-OPT | Demonstrated scheduling bottleneck and chosen success criterion before CP-SAT | Separate measured-need contract | No speculative optimizer counted as missing default-launch work |

## Evidence catalogue

| ID | Source refs | Date | Origin | Candidate | Family |
| --- | --- | --- | --- | --- | --- |
| EV-P01 | `repo:docs/development/DEVELOPMENT_COMPLETION_REGISTER.md`; `repo:docs/development/PLAN_SUPERSESSION_INDEX.md`; `repo:tests/planning/test_completion_register.py` | 2026-11-02 | local-candidate | Uncommitted P01 worktree from backend 2a53090c608331b282e331502ae1ec5851ae9c15; not delivered | documentation |
| EV-V2 | `local:2026-11-01-10-38-45 Coding Log (reviewed-development-completion-plan-v2).md` sections 6 and 13–20 | 2026-11-01 | retained-V2-audit | backend=2a53090c608331b282e331502ae1ec5851ae9c15; frontend=067b3e22401854f8c6d6db42dc0c5c1872fca6f8 | plan |
| EV-SF | `repo:services/smartfarm-water-control/src/index.js`; `repo:services/smartfarm-water-control/src/services/outboxPoller.js`; `repo:services/smartfarm-water-control/src/services/valveCommandService.js`; `external:munbon-plan-audit-20261031-111230/smartfarm-oracles.log` | 2026-10-31 | retained-V2-audit | backend=2a53090c608331b282e331502ae1ec5851ae9c15 | source |
| EV-NOTIFIER | `repo:services/daily-chart-notifier/src/runner.ts`; `repo:services/daily-chart-notifier/src/email.ts`; `repo:services/daily-chart-notifier/src/log-fetcher.ts`; `repo:services/daily-chart-notifier/package.json` | 2026-11-01 | retained-V2-audit | backend=2a53090c608331b282e331502ae1ec5851ae9c15 | source |
| EV-SENSOR | `repo:services/sensor-data/src/cmd/consumer/main.ts`; `repo:services/sensor-data/test/integration/water-level-smoothing.spec.ts`; `local:V2 section 17 P06-S` | 2026-11-01 | retained-V2-audit | backend=2a53090c608331b282e331502ae1ec5851ae9c15 | source |
| EV-FLOW | `repo:services/flow-monitoring/src/core/gate_flow.py`; `repo:services/flow-monitoring/src/core/canal_capacity.py`; `repo:services/flow-monitoring/tests/unit/test_gate_flow.py`; `repo:services/flow-monitoring/tests/unit/test_canal_capacity.py` | 2026-11-01 | retained-V2-audit | backend=2a53090c608331b282e331502ae1ec5851ae9c15 | source |
| EV-CP | `repo:services/bff-water-planning/src/main.py`; `repo:services/scheduler/src/api/v1/endpoints/auth.py`; `repo:services/scheduler/src/jobs/shadow_dispatch_once.py`; `repo:infra/pm2/build-irrigation-config.ts`; `repo:ops/control-plan-read-local/run-stage-suite.py`; `external:munbon-plan-audit-20261031-111230/` focused source-test logs | 2026-10-31 | retained-V2-audit | backend=2a53090c608331b282e331502ae1ec5851ae9c15 | source |
| EV-MODEL | `repo:services/flow-monitoring/scripts/build_scada_config.py`; `repo:services/flow-monitoring/src/config/gate_calibrations.json`; `repo:services/flow-monitoring/data/model-releases/engineering-prior-v5-v1.json` | 2026-11-01 | retained-V2-audit | backend=2a53090c608331b282e331502ae1ec5851ae9c15 | source |
| EV-ROS | `repo:services/ros-gis-integration/src/services/daily_requirement_producer.py`; `repo:services/ros-gis-integration/src/services/requirement_source_loader.py`; `repo:services/ros-gis-integration/src/services/ros_sync_service.py`; `repo:services/ros/src/services/water-demand.service.js`; `repo:services/rid-ms/src/services/water-demand-calculator.service.js` | 2026-11-01 | retained-V2-audit | backend=2a53090c608331b282e331502ae1ec5851ae9c15 | source |
| EV-CROP | `repo:services/bff-water-planning/scripts/load_crop_registry.py`; `repo:services/bff-water-planning/scripts/test_load_crop_registry.py`; `repo:services/bff-water-planning/migrations/009_crop_registry.sql`; `local:V2 section 13.4` 17 pure loader tests retained | 2026-11-01 | retained-V2-audit | backend=2a53090c608331b282e331502ae1ec5851ae9c15 | source |
| EV-RID | `repo:services/rid-ms/src/index.js`; `repo:services/rid-ms/src/jobs/job-scheduler.js`; `repo:services/rid-ms/src/jobs/job-scheduler.test.js` | 2026-11-01 | retained-V2-audit | backend=2a53090c608331b282e331502ae1ec5851ae9c15 | source |
| EV-SEC | `repo:services/flow-monitoring/docs/remediation/HANDOFF.md`; `local:V2 sections 13.3 and 15`; `external:munbon-plan-review-20261101-103845/` redacted inventory identities only | 2026-11-01 | retained-V2-audit | backend=2a53090c608331b282e331502ae1ec5851ae9c15; no credential liveness tested | security |
| EV-HIST | `repo:services/flow-monitoring/docs/remediation/HANDOFF.md`; `local:V2 section 15 O-HIST` | 2026-11-01 | retained-V2-audit | Documented July 11 archive 10f6d9d1; current applicable-ref/carrier scope unverified | history |
| EV-GOV | `local:V2 sections 13.2 and 15`; `external:munbon-plan-review-20261101-103845/` dated branch/capability evidence | 2026-11-01 | retained-V2-audit | Backend historical run 32507669619 zero steps; both main protections historical observations only | governance |
| EV-LEGACY | `repo:services/smart-farm-water-control/.env.example`; `local:V2 sections 13.2 and 14` reachability inventory | 2026-11-01 | retained-V2-audit | backend=2a53090c608331b282e331502ae1ec5851ae9c15; template values not exposed | source |
| EV-FE | `frontend:AGENTS.md`; `frontend:package.json`; `frontend:scripts/local-fe-ci-all.mjs`; `external:munbon-plan-audit-20261031-111230/frontend-focused.log`; `external:munbon-plan-audit-20261031-111230/frontend-runtime-source.log` | 2026-10-31 | retained-V2-audit | frontend=067b3e22401854f8c6d6db42dc0c5c1872fca6f8; source tests on host Node 26, not a new pinned-container gate | source |
| EV-RC | `repo:docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md`; `repo:ops/control-plan-read-local/tests/test_local_artifacts.py`; `external:2026-08-21-local-rc1-a26c0fd000b0-067b3e224018-20260821T162700Z-5d7a9c31/success-attempt-1` | 2026-08-21 | retained-acceptance | backend=a26c0fd000b0b6da443135ffeadb992eded8fb5b; frontend=067b3e22401854f8c6d6db42dc0c5c1872fca6f8 | local-rc |
| EV-CAMPAIGN | `repo:docs/operations/control-plan-campaign-ledger.jsonl`; `repo:docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md` | 2026-08-20 | retained-campaign | backend=7f032c4c20e7f9cdd443d64f7adbeb37342ff190; campaign=2026-08-20-nine-stage-orbstack-7f032c4c-attempt-1 | frozen-campaign |

## Execution and release boundary

P01 does not rerun application/real-DB/guest/browser acceptance. Its test scope is offline documentation, source wiring and Git-ignore semantics. Required source/full service and disposable real integration gates remain in their own P02/P03/P04/P06 contracts; missing labs are BLOCKED, never a passing skip. Senior-reported suite counts are not promoted into independently rerun release results.

Retain V2's explicit **three affected-scope runs at the same candidate**, including its later P02/P02-D/P08 requirements. Native `g2-check` supplies formal findings review; `g2-qcheck` owns gate orchestration and required independent review, as explicitly approved by the user. Configuration implementation, including these narrow ignore exceptions, remains Luna-Max-only; primary authors prose/tests and independently verifies receipt/GREEN/wiring. No blanket admin merge, production notification, credential operation, history rewrite, AWS action, guest replacement, deployment, field command, W4 recomputation or optimizer authority is conveyed.
