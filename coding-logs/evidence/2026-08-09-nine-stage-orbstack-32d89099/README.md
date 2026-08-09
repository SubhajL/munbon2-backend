# Nine-stage OrbStack local acceptance — frozen run 2026-08-09

## Frozen candidate (exact SHAs)
- **Backend** `32d89099a0e83eb58b9190841156e44a6f8ceeb1` (origin/main; contains
  #155 via #157, the Codex R2 evidence #161, and the LOCAL-WRITE-UI-1
  evidence-truthfulness fix #160). Bundle enforced `origin/main == local main ==
  release_sha`.
- **Frontend** `067b3e22401854f8c6d6db42dc0c5c1872fca6f8` (smart-cms-app;
  reverified `HEAD == origin/main == local main` immediately before the run).

## Isolation
OrbStack guest `munbon-control-plan-local` — Debian 12 arm64, isolated +
network-isolated, 8 GiB / 4 CPU / 40 GiB. `aws_actions: false`. Provisioning
archived the prior evidence directory and recreated `munbon_local` from the
tracked migrations (destroy-and-rebuild; see `evidence-archive/` on the guest).

## Outcome — the acceptance did NOT fully pass
Run sequentially against the one live database (single provision, no
re-provision between stages, no manual repairs, no candidate-changing commits):

| Stage | Result |
|---|---|
| LOCAL-BASE-0 | PASS |
| LOCAL-RTA-1 | PASS |
| LOCAL-AC-1 | PASS |
| LOCAL-READ-ACT-1 | PASS |
| LOCAL-EVIDENCE-1 | PASS |
| LOCAL-GO-READ-1 | PASS |
| LOCAL-WRITE-FOUNDATION-1 | PASS |
| **LOCAL-WRITE-UI-1** | **FAIL** — `browser_verify_submit_affordance_failed` |
| LOCAL-PERSIST-ONLY-1 | not reached (sequential run halted at the failure) |

**Root cause (fully investigated, see `ROOT-CAUSE-INVESTIGATION.md`):** the
frozen frontend does not issue the planning-depth roster/active reads or render
the submit control on `/smart-water/dashboard` under the WRITE-UI flag config.
This is a frontend↔harness integration gap at the frozen candidate, NOT a defect
in the #155/#160/#161 work (the #160 read-recorder is proven functional).
Reproducible across two orchestrator runs.

## Write flags
The two control-plane write flags were verified **false** in every stage that
ran (`control_plan_reads=false`, `control_plan_evidence_reads=false`,
`water_planning_submit=false`; see `guest-evidence/LOCAL-BASE-0.json`,
`LOCAL-GO-READ-1.json`). No armed/write-enabled frontend persists. The final
PERSIST-ONLY completion gate was not reached because the run halted at WRITE-UI.

## Contents
- `guest-evidence/` — verbatim sanitized stage manifests (7 PASS JSONs + the
  WRITE-UI failure manifest), `stage-state.json`, GO-READ screenshots, the
  harness's own per-file `SHA256SUMS`, and the armed-frontend log.
- `ROOT-CAUSE-INVESTIGATION.md` — the WRITE-UI failure investigation.
- `SHA256SUMS` — hash list over this evidence directory.

## Follow-up
WRITE-UI frontend gap tracked as issue #165.
