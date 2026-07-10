# Munbon control-plane remediation — spec set

Source-level audit of the demand → scheduling → gate-hydraulics → SCADA pipeline, and
the fix specs it produced. Read in this order:

1. **REMEDIATION_MASTER.md** — the complete finding→fix index (F-01…F-11 + A–D +
   data/security), prioritized P0–P4, with an acceptance matrix. Start here.
2. **FIX_F01_GATE_FLOW_LAW_SPEC.md** — P0. The gate-flow law that blows up to ~287 m³/s
   (three stacked bugs). The first thing to land — everything downstream consumes it.
3. **GATE_CONTROL_REMEDIATION_SPEC.md** — the A–D control-pipeline master (topology,
   data model, aggregation, timing, wiring, consolidation).
4. **HYDRAULIC_REMEDIATION_SPEC.md** — B5–B8 code (conveyance loss, rotation scheduler,
   branch-split solve).
5. **AUDIT_FINDINGS_REPORT.html** — the visual findings report (open in a browser).
6. **TOPOLOGY_RECONCILIATION.md** — why the F-11 star wiring was wrong on laterals and
   how the serial-chain topology is derived from the gate-id naming grammar (F-11b).
7. **SEEPAGE_CALIBRATION.md** — the B5 seepage recalibration to aged-concrete field
   values (provisional pending Tier-3 inflow/outflow measurement).
8. **PR_REVIEW_GUIDE.md** — how remediation PRs are reviewed; per-PR verdicts.
9. **PROGRAM_REVIEW_2026-07-09.md** — full program review of PRs #7–#24 + the forward
   roadmap (Waves 0–4, decisions D1–D4, externals E1–E6). **Current-status anchor.**
10. **HANDOFF.md** — pointer to the two status documents above (kept deliberately thin).

## P0 (do first — no hardware)
F-01 gate law · F-11 single connected topology · F-04 real per-section capacity ·
C10 delete duplicate implementations · F-07/F-08 demand plumbing + exposed credential.

Dependency spine: **F-01 + F-11 + F-04 → aggregation → inverse/split → scheduling →
SCADA bridge → closed loop.**

## Provisional inputs (flagged, not yet available)
- `section_node_map` — the ROS-section ↔ network-node correspondence (unwired ros-gis
  spatial layer).
- `seepage_rate_m_s` — literature defaults; require a Tier-3 inflow–outflow calibration.
- calibration `confidence` — should be derived from fit residuals, not the fixed labels.

_Specs authored from the 2026-07-08 audit; re-confirm file/line references before
acting. Several sections carry **supersession banners** where later evidence replaced
the original prescription (topology F-11b, bisection inverse, aged-concrete seepage) —
the banner text wins over the body it annotates._
