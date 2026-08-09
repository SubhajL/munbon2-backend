# Coding Log — nine-stage OrbStack local acceptance (frozen run)

Date: 2026-08-09 (+07). Host-driven OrbStack acceptance of the frozen candidate.

## Freeze (enforced by orchestrate.py: origin/main == local main == SHA, both repos)
- Backend `32d89099a0e83eb58b9190841156e44a6f8ceeb1` (contains #155/#157, #161, #160).
- Frontend `067b3e22401854f8c6d6db42dc0c5c1872fca6f8` (reverified immediately pre-run).

## Execution
- `orchestrate.py plan` → SHAs accepted, isolation + `aws_actions:false` confirmed.
- Started the isolated guest; `provision` archived prior evidence, recreated
  `munbon_local` from tracked migrations, rebuilt both frontends (PASS bootstrap).
- `run-all`: single provision, nine stages sequential against one live DB, no
  re-provision between stages, no manual repairs, no candidate-changing commits.

## Result: FAILED at LOCAL-WRITE-UI-1 (7/9 PASS)
BASE-0, RTA-1, AC-1, READ-ACT-1, EVIDENCE-1, GO-READ-1, WRITE-FOUNDATION-1 PASS;
LOCAL-WRITE-UI-1 FAIL (`browser_verify_submit_affordance_failed`), reproducible
across the sequential run and an isolated stage re-run; PERSIST-ONLY not reached.

## Root cause (investigated; evidence dir 2026-08-09-nine-stage-orbstack-32d89099)
Captured detail `page.waitForFunction: Timeout 35000ms` — the app issues no
planning-depth roster/active reads on `/smart-water/dashboard` and renders no
submit control under the WRITE-UI flag config. The #160 read-recorder was proven
functional in real Chromium (injection installs, fetch wrapped, sentinel set),
so this is a frontend↔harness integration gap at the frozen frontend `067b3e22`,
NOT a defect in #155/#160/#161. Filed as #165.

## Write flags
`control_plan_reads`, `control_plan_evidence_reads`, `water_planning_submit`
verified false in every stage that ran; no armed frontend persists. The final
PERSIST-ONLY completion gate was not reached (run halted at WRITE-UI).

## Discipline honored
No manual repairs of the run, no skipped stages, no DB recreation between stages,
no candidate-changing commits. The failure is reported truthfully rather than
worked around. Diagnostics were read-only guest investigations that did not alter
the candidate, the acceptance DB content, or the collected evidence.
