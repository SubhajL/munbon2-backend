# Plan supersession index

Updated: 2026-11-02, Asia/Bangkok. [Development completion register](DEVELOPMENT_COMPLETION_REGISTER.md) is the **single current status authority for the named V2 scope**. This index is a provenance/disposition map, not permission to execute historical instructions. Repository policy remains [CLAUDE.md](../../CLAUDE.md).

V2 governs future execution, retaining completed control-plan source and historical evidence. Its defaults and bounded P01 were approved by the project owner on November 2. It does not retroactively rewrite prior verdicts or turn historical acceptance into current production approval.

## Plan supersession

| ID | Artifact | Storage | Disposition | Current authority |
| --- | --- | --- | --- | --- |
| V2 | `coding-logs/2026-11-01-10-38-45 Coding Log (reviewed-development-completion-plan-v2).md` | retained-local | Current prospective scope; sections 13–20 extend P01–P08; defaults approved November 2 | DEVELOPMENT_COMPLETION_REGISTER.md |
| OCT31 | `coding-logs/2026-10-31-11-12-30 Coding Log (reconciled-development-completion-plan).md` | retained-local | Superseded prospectively by V2; preserve unchanged | DEVELOPMENT_COMPLETION_REGISTER.md |
| AUG22 | `coding-logs/2026-08-22-05-55-30 Coding Log (current-session-handoff).md` | retained-local | Preserved handoff/current dirty-primary pointer target; not the new implementation log | DEVELOPMENT_COMPLETION_REGISTER.md |
| AUG01 | `coding-logs/2026-08-01-09-58-42 Coding Log (current-session-handoff-and-next-paths).md` | tracked | Historical pickup and completed-source evidence; later runtime/RC and V2 dispositions prevail | DEVELOPMENT_COMPLETION_REGISTER.md |
| JUL22 | `coding-logs/2026-07-22-10-10-17 Coding Log (revised-control-plan-runtime-write-roadmap).md` | tracked | Historical roadmap; delivered stages/RID-v2/roster supersede missing-source prescriptions | DEVELOPMENT_COMPLETION_REGISTER.md |
| JUL23 | `coding-logs/2026-07-23-07-59-02 Coding Log (local-first-roadmap-gates).md` | tracked | Historical local-first ordering; current source and exact accepted artifacts remain distinct | DEVELOPMENT_COMPLETION_REGISTER.md |
| FLOW-PROGRAM | `services/flow-monitoring/docs/remediation/PROGRAM_REVIEW_2026-07-09.md` | tracked | Preserve original program review and external actions; not a current completion checklist | DEVELOPMENT_COMPLETION_REGISTER.md |
| FLOW-WAVES | `services/flow-monitoring/docs/remediation/WAVE_2-4_PLAN_2026-07-12.md` | tracked | Historical wave ordering/specs; retain delivered work and V2 conditional/deferred boundaries | DEVELOPMENT_COMPLETION_REGISTER.md |
| FLOW-MASTER | `services/flow-monitoring/docs/remediation/REMEDIATION_MASTER.md` | tracked | Historical finding/specification inventory; each current F-row has a separate register disposition | DEVELOPMENT_COMPLETION_REGISTER.md |
| FLOW-REVIEW | `services/flow-monitoring/docs/remediation/PR_REVIEW_GUIDE.md` | tracked | Historical per-PR verdicts retained; old pending/source/security claims are dated, not current status | DEVELOPMENT_COMPLETION_REGISTER.md |
| FLOW-HANDOFF | `services/flow-monitoring/docs/remediation/HANDOFF.md` | tracked | Historical handoff and documented E2 execution; current scope verification remains open | DEVELOPMENT_COMPLETION_REGISTER.md |
| PHASES | `PR_PHASE_PLAN.md` | tracked | Historical branch-splitting proposal; do not remove active ROS-GIS or blindly replay it | DEVELOPMENT_COMPLETION_REGISTER.md |
| TASKS | `docs/TASK_STATUS_TRACKING.md` | tracked | Historical 2024 task totals; not a current completion percentage or authority | DEVELOPMENT_COMPLETION_REGISTER.md |
| LOCAL-ACCEPTANCE | `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md` | tracked | Exact-SHA local RC acceptance retained; no transfer to a new combined release | DEVELOPMENT_COMPLETION_REGISTER.md |
| CAMPAIGN | `docs/operations/control-plan-campaign-ledger.jsonl` | tracked | Frozen separate nine-stage campaign; LOCAL-RC-1 remains ledger-ineligible | DEVELOPMENT_COMPLETION_REGISTER.md |
| DARK-DEPLOYMENT | `docs/operations/CONTROL_PLANE_DARK_DEPLOYMENT.md` | tracked | Preserve control-plane deployment contract; not smartfarm's missing independent artifact or deployment authority | DEVELOPMENT_COMPLETION_REGISTER.md |

## Storage and pickup safety

`retained-local` artifacts are preserved at their named paths under the owner's backend primary checkout (`/Users/subhajlimanond/dev/munbon2-backend`). They were untracked at baseline and are **not included by a clean main-based worktree**. Their filenames above are evidence identities, not broken repository hyperlinks or a claim those plans were committed. Do not copy or rewrite them just to make a link resolve. The active P01 Coding Log records the approved bounded contract for this candidate.

The owner explicitly selected the new `coding-logs/2026-11-02-15-46-03 Coding Log (p01-development-completion-register).md` and authorized changing **only the implementation worktree's** `.codex/coding-log.current`. The dirty primary pointer continues to select AUG22. Any later merge/synchronization must reconcile that protected primary change explicitly; never reset it away.

## Conflicts resolved for future work

- Current active planning roster: `ros_gis.sections_current` and dataset-version provenance, 41 sections/six zones/45,204 rai; not old raw-GIS 47,385-rai prescriptions.
- Supersession replay returns the original planning-depth receipt under current source/tests; do not revive the older conflicting 409 rule.
- W4 is persist-only by default. ROS migration `0004` already owns dataset-version immutability; historical W4 migration numbering is not executable authority.
- Shadow dispatch is already PM2-registered; periodic expected `baselines={}` is deliberately gated. Immediate execution readback is separately delivered. Do not recreate a background loop.
- Engineering-prior modeling remains planning-only (`commandable:false` without separate approval); inferred coverage does not confer field validation.
- Notifier email is tracked source; Telegram output is ignored local artifact drift, not committed source delivery. A later build must preserve that artifact first.
- Existing frontend local CI-1/CI-2 are delivered and mandatory. P05 adds hosted adaptation; actual execution and main protection remain owner gates.
- July 11 history purge is documented-executed, not assumed absent. Verify current scope through O-HIST before considering separately approved remediation. Source cleanup alone does not prove credential rotation.
- Old sensor/chart PRs #1–#3 are content-triage/metadata work under P07, not a stack to merge. Preserve every unique hunk before authorized closure.

P01 changes no frozen evidence, campaign record, historical Coding Log, runtime approval or operational state. Subsequent source work follows the register's dependency-ready gates, with explicit contracts and one production writer at a time.
