# Munbon remediation — handoff pointer

> **This file no longer tracks current status** (it went stale twice while claiming
> currency — review finding, PROGRAM_REVIEW §1.3). Status now lives in exactly two
> places:
>
> 1. **[PR_REVIEW_GUIDE.md](PR_REVIEW_GUIDE.md)** — how the remediation PRs are
>    reviewed and what each one shipped (per-PR verdicts).
> 2. **[PROGRAM_REVIEW_2026-07-09.md](PROGRAM_REVIEW_2026-07-09.md)** — the full
>    program review of PRs #7–#24 plus the forward roadmap (Waves 0–4, maintainer
>    decisions D1–D4, external actions E1–E6). The wave PRs themselves (#25 onward)
>    carry their own detailed bodies on GitHub.
>
> **Where things stand** is always derivable from: `git log origin/main` +
> the roadmap tables in PROGRAM_REVIEW §2.2.

## Standing facts that do not go stale

- **Lifecycle per PR**: plan (Claude + Codex) → TDD → QCHECK + Codex adversary
  (non-skippable) → PR → admin-merge (delegated) → land local main.
- **Quality gate**: `pytest` from the service root (bare; core coverage floor
  enforced in CI). No quarantine list, no isolated-suite manifest — retired in
  Wave 1.9.
- **Canonical configs**: `src/config/{network,canal_geometry,gate_calibrations,
  gate_configuration}.json`, strict-loaded and drift-guarded (`core/config_loader`);
  `network.json` is regenerated from the gate-id naming grammar and locked by test.
- **External actions still open**: E1 rotate the leaked DB credential (its old value is redacted repo-wide as `__ROTATED_DB_PASSWORD__`) on all DBs, E2
  `git filter-repo` history purge + team re-clone (after E1), E4 GIS shapefile
  export for crop_registry, E5 RID's authoritative auto-gate list, E6 GitHub
  Actions billing lock (no CI runs until fixed). E3 (SCADA V1.0 Excel) is in-repo.

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
