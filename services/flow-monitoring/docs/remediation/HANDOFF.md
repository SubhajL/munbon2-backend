# Munbon remediation — handoff pointer

> **Historical handoff, not current status authority.** The single current owner is
> the [Development completion register](../../../../docs/development/DEVELOPMENT_COMPLETION_REGISTER.md)
> with [plan supersession index](../../../../docs/development/PLAN_SUPERSESSION_INDEX.md)
> (2026-11-02). Source, local/runtime acceptance, field authority, security and
> governance are separate states. No historical merge/operational grant is renewed here.
>
> Historical references remain:
> - [PR_REVIEW_GUIDE.md](PR_REVIEW_GUIDE.md): original per-PR review verdicts.
> - [PROGRAM_REVIEW_2026-07-09.md](PROGRAM_REVIEW_2026-07-09.md): original review,
>   roadmap and external-action record.
> - [WAVE_2-4_PLAN_2026-07-12.md](WAVE_2-4_PLAN_2026-07-12.md): historical wave
>   ordering/amendments; current dispositions and conditional scope are in the register.

## Historical standing-fact record (not a new grant)

- **Lifecycle per PR**: plan (Claude + Codex) → TDD → QCHECK + Codex adversary
  (non-skippable) → PR → admin-merge (delegated) → land local main.
- **Quality gate**: `pytest` from the service root (bare; core coverage floor
  enforced in CI). No quarantine list, no isolated-suite manifest — retired in
  Wave 1.9.
- **Canonical configs**: `src/config/{network,canal_geometry,gate_calibrations,
  gate_configuration}.json`, strict-loaded and drift-guarded (`core/config_loader`);
  `network.json` is regenerated from the gate-id naming grammar and locked by test.
- **External actions still open**: E1 rotate the leaked DB credential (its old value
  is redacted repo-wide as `__ROTATED_DB_PASSWORD__`) on all DBs, E4 GIS shapefile
  export for crop_registry, E5 RID's authoritative auto-gate list, E6 GitHub
  Actions billing lock (no CI runs until fixed). E2 (history purge) was **executed
  2026-07-11** (all refs rewritten + force-pushed, 0 carriers in 14,594 blobs;
  team re-clone comms still pending). E3 (SCADA V1.0 Excel) is in-repo.

## Historical audit context

The original audit findings (F-01 gate-flow blow-up, F-11 fragmented topology,
F-04 hardcoded capacity, C10 duplicate laws, F-07/F-08 demand plumbing, SEC
credentials) and the fix specs are in this folder: REMEDIATION_MASTER.md,
FIX_F01_GATE_FLOW_LAW_SPEC.md, GATE_CONTROL_REMEDIATION_SPEC.md,
HYDRAULIC_REMEDIATION_SPEC.md — now carrying supersession banners where later
work (F-11b serial-chain topology, bisection inverse, aged-concrete seepage)
replaced their original prescriptions. TOPOLOGY_RECONCILIATION.md documents the
star-vs-serial-chain discovery; SEEPAGE_CALIBRATION.md the B5 calibration.
Earlier versions of this HANDOFF (with the full P0 narrative) are in git history.
