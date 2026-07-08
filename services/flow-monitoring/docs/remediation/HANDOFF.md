# Munbon — Session Handoff (2026-07-08)

Read this first in a new session. It captures repo/merge state, the audit findings,
decisions locked, deliverables, and exactly where to start. **Nothing has been committed
or pushed. No merge has been executed.** All work is docs/specs + one artifact.

---

## 1. Repos & merge plan

Three local folders are **three working copies of ONE GitHub repo**
(`github.com/SubhajL/munbon2-backend`), each on a different branch. They share history
(each has an `other` remote pointing at a sibling folder).

| Folder | Branch | Last commit | Unique content | Note |
|---|---|---|---|---|
| `munbon2-backend` (canonical, has `origin`) | `feat/daily-chart-notifier` | 2025-11-26 | `services/daily-chart-notifier` | 50 service dirs (inflated by `*.backup`) |
| `munbon2-backend-scada` | `feat/scada-gate-control` | **2026-06-10 (newest)** | `services/scada-gate-control` (Modbus) + `scada-gate-control-web` (Next.js 16) | **most advanced**, +7 commits over main |
| `munbon2-backend-smartfarm` | `feature/smartfarm-debug` | 2025-11-17 | none (== `main`) | disposable — can reset to main |

**Merge verified CLEAN (not executed):** `feat/daily-chart-notifier` + `feat/scada-gate-control`
share base `2ed11c0` (= `main`), touch **disjoint files** (each adds its own `services/`
dir), and `git merge-tree` reports **0 conflicts**. Neither branch currently has both features.

**Recommended merge plan (do in `munbon2-backend`, the copy with `origin`):**
1. `git stash -u` (a feature branch is checked out with dirty state)
2. `git fetch other feat/scada-gate-control` ; `git branch scada-gate-control other/feat/scada-gate-control`
3. `git switch -c integration/scada+daily-chart main`
4. `git merge --no-ff feat/daily-chart-notifier` ; `git merge --no-ff scada-gate-control` (both clean)
5. Verify: all 3 service dirs present; smoke-build `scada-gate-control{,-web}` + `daily-chart-notifier`; **reconcile PM2 ecosystem config** (register all three, check port collisions); note the scada branch commits `dist/`/`.next/` build artifacts — consider gitignoring before final push.
6. `git switch main && git merge --ff-only integration/…` → **STOP for approval before `git push origin main`** (push is the only outward step).
7. Reconcile the other copies: `git fetch origin && git switch main && git reset --hard origin/main`. Long-term keep ONE working copy + branches; delete the smartfarm copy.

---

## 2. What the audit found (flow-monitoring control plane)

Full detail in the spec set (§4). Headline: a thoughtfully-scoped hydraulic design on a
**mostly-scaffolded, partly-incorrect** implementation. The single operational lineage is
**ROS/Excel demand → `ros_gis` nightly cron**; everything on the gate-control side is stubbed,
disconnected, or wrong.

Critical/High findings (IDs used across the specs):
- **F-01** gate flow law returns **287 m³/s at 10 % open** for an 11 m³/s gate — three stacked bugs (inverted `opening^K2`; `Hs` as absolute MSL; no `Cs` clamp) + hardcoded levels. Reproduced numerically.
- **F-11** the wired network topology (`munbon_network_final.json`) is **~76 % wrong** (42 edges, 14 correct, 2/59 nodes reachable). `munbon_network_updated.json` (59 edges) is correct; canonical tree is regenerable from the `M(i,j,k)` gate IDs.
- **F-02** hydraulic control (continuous opening) ↔ `scada-gate-control` (discrete levels 1–4) are **not connected** — no quantizer, no command bridge.
- **F-03/C9** automatic control is **stubbed** (`_get_system_demand`→25.0, `_solve_optimal_gate_settings`→50 %).
- **F-04/B7** canal capacity is a **hardcoded 15 m³/s** (`_get_canal_capacity`); real per-section `design_discharge` exists but is unused.
- **F-05** only **10/59 gates** are field-calibrated (K1/K2); rest use size defaults (−27 %…+110 % error).
- **A1–A4** demand→gate aggregation uses a hardcoded 3-zone path table, synthetic node IDs, per-zone (not per-section) granularity; a real graph exists but is unused.
- **B5** no conveyance (seepage) loss uplift. **B6/B7** coincident-peak, no capacity. **B8** no branch-split coupling. **D13** no travel-time coupling.
- **C10/F-10** 3+ divergent flow-per-gate impls and 4 gate-flow implementations coexist; the calibrated one is unwired.
- Demand plane: **F-06** AquaCrop preferred (`aquacrop_priority`) but `ros_gis.aquacrop_results` is written only by the mock → silent ROS fallback; **F-09** three divergent demand formulas; **F-07** `gis.crop_registry` has no in-repo loader + **hardcoded prod DB creds** in an untracked script; **F-08** `rid-ms` imports a missing `jobs/job-scheduler` (won't boot).
- **Saint-Venant is NOT implemented** — the `saint-venant`/`manning` API options return hardcoded literals. The real solver is steady Manning + storage relaxation.

---

## 3. Decisions locked this session

- **Merge is clean**; use an integration branch; don't push without approval.
- **Adopt `munbon_network_updated.json`** as the canonical topology (or regenerate from gate IDs); delete the 5 stale variants.
- **ROS/Excel is the single demand source of truth**; retire the RID-MS calculator + BFF-script formulas; **fail-closed** on missing demand (kill the 25.0 fallback).
- **F-01 fix uses the correct RID rating** `Cs=K1·(Hs/Go)^K2` (Go metres, Hs = head over sill), clamp [0.3,1.0], `q≤q_max` ceiling, **bisection** (not Newton) for the inverse.
- **B5 Tier-1 seepage** (`Q_seep = s·P·L`) is the correct starting method — but make `s` **soil-aware** (not just concrete/earth) and treat it as **provisional pending a Tier-3 inflow–outflow calibration**.
- **Do NOT build full Saint-Venant** — the data (no flow meters, mobile-only stage sensors) can't drive or validate it. Target the **diffusive-wave (Muskingum–Cunge)** rung instead, gated on a sensor rollout.
- **F-01 + F-11 + F-04 are P0** — everything downstream consumes the corrected gate law and connected graph.

---

## 4. Deliverables (already on disk, untracked)

In `services/flow-monitoring/docs/remediation/`:
- `README.md` — index + reading order.
- `REMEDIATION_MASTER.md` — complete finding→fix catalog, P0–P4, acceptance matrix. **Start here.**
- `FIX_F01_GATE_FLOW_LAW_SPEC.md` — the gate-law fix (P0).
- `GATE_CONTROL_REMEDIATION_SPEC.md` — A–D control-pipeline master.
- `HYDRAULIC_REMEDIATION_SPEC.md` — B5–B8 code.
- `AUDIT_FINDINGS_REPORT.html` — visual report (also the live artifact below).
- `HANDOFF.md` — this file.

Live artifact (private): **https://claude.ai/code/artifact/9de1249b-5bca-4c7d-9a7c-d83a2a025155**
`git add services/flow-monitoring/docs/remediation/` to commit the doc set.

---

## 5. Where to start (next session, ordered)

1. **Decide: execute the merge?** If yes, run §1 steps 1–5 in `munbon2-backend`, stop before push, report build/PM2 status.
2. **Commit the remediation docs** (§4) and optionally **mirror to `munbon2-backend-scada`**.
3. **P0 engineering** (any order, all no-hardware):
   - Regenerate canonical `network.json` from the gate-ID hierarchy; add the loader connectivity guard (F-11).
   - Implement `core/gate_flow.py` per `FIX_F01_…` + the monotonicity/287 regression tests (F-01).
   - Wire real `design_discharge` into `_get_canal_capacity` (F-04).
   - Delete duplicate flow/hydraulic impls (C10); restore/remove `rid-ms` cron (F-08); move DB creds to secrets + rotate (F-07/SEC).
4. Then P1 (controller wiring, aggregation, B5, B8, demand contract) per the roadmap.

---

## 6. Open / offered-but-not-done

- **Merge NOT executed**; nothing committed or pushed.
- Doc set **not mirrored** to the scada copy.
- Canonical `network.json` **not yet generated** (offered).
- Spec `seepage_rate` defaults **not yet made soil-aware** (offered).

## 7. Caveats (carry forward)

- **Provisional inputs, not ready:** `section_node_map` (unwired ros-gis spatial layer),
  calibrated `seepage_rate` (needs Tier-3 campaign), residual-based `confidence` (needs calibration data).
- **Re-verify all file/line references** before acting — they were current at the 2026-07-08 audit;
  the wired network file, calibration counts, and stubs may have moved.
- The flow-monitoring code is **identical across all three copies** (shared `main` baseline),
  so the remediation applies regardless of which branch is consolidated.
