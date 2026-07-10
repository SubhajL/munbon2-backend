# Program Review & Forward Roadmap — 2026-07-09

**Scope:** full review of remediation PRs #7–#24 (`origin/main = 4e45795`) against the devlog
discussions (`docs/mb2-devlogs.md`) and `PR_REVIEW_GUIDE.md`, plus the forward PR roadmap.
**Method:** four independent review agents (P0 PRs, P1 PRs, current-tree audit, spec-fidelity)
+ a Codex adversarial pass over the never-Codex-reviewed #20–#22 core + a Codex planning pass
on the roadmap. All claims verified against code/diffs; isolated suites re-run
(flow-monitoring remediation suites 135/135 green; bff-water-planning 17/17).

---

## Part 1 — Review findings

### 1.1 Verdict summary

Every merged PR maps to a discussed finding; none contradicts an agreed decision. The new
`core/` kernel (gate_flow, network_topology, demand_aggregation, conveyance_loss,
canal_capacity, network_flow_controller — 733 LOC, pure, fail-closed, 135 isolated tests) is
solid and is the right foundation for B8 and the scheduler. The program's systemic weaknesses:
(1) builds well, deletes poorly — the legacy broken stack still runs beside the new one;
(2) PR bodies repeatedly overclaimed; (3) doc layering — superseded decisions still presented
as current in the older docs.

| PR | Item | Verdict |
|----|------|---------|
| #7 | F-01 gate law | Sound-with-caveats (CS_MIN floor → small-target inverse defect, see 1.2#3) |
| #8 | F-11 topology | Sound-with-caveats (adopted file was still ~29/59 wrong; fixed by #20) |
| #9 | F-04 capacity | Sound |
| #10 | C10 dedupe | Sound-with-caveats (guard narrow; inverted law survives in `calibrated_flow_model_v2.py:131`) |
| #11 | F-08 JobScheduler | Sound (weak smoke tests; TZ comment false → fixed #18) |
| #12 | SEC creds | Sound-with-caveats (**gate self-blocked; merged with its own check red**) |
| #13 | F-07 crop_registry | **Defective as merged** (missing `"Zone"` col; non-idempotent) — repaired by #16 |
| #15 | SEC follow-up | Sound-with-caveats (residue mischaracterized — see 1.2#1) |
| #16 | F-07 fix | Sound |
| #17 | QCHECK nits | Sound (meta-tested guard regex — good practice) |
| #18 | F-08 TZ | Sound |
| #19 | A1–A3 aggregation | Sound (verified vs independent BFS; docstring "20/33 interior" stale → 32/33) |
| #20 | F-11b serial chains | Sound (grammar + lock independently re-derived; oracle covers 37/59 edges only, and is the same dataset as #21's geometry) |
| #21 | B5 conveyance loss | Sound-with-caveats (dry-reach seepage, see 1.2#4; `side_slope=0.06` contradicts geometry in 37/37 sections) |
| #22 | Seepage calibration | Sound-with-caveats (plausibility test genuinely two-sided; headline metric mislabeled — true LMC ≈48 L/s/km, network ≈39, not 68) |
| #23 | C9 wiring | Sound-with-caveats (verified live; legacy controller left on fragmented topology; cwd-relative paths; `/plan` static vs spec's time-phased) |
| #24 | Codex hardening | Sound (all 7 fixes verified) |

### 1.2 New defects found by this review

1. **HIGH — leaked password in runtime code.** `__ROTATED_DB_PASSWORD__` in 27 tracked `.js`/`.ts`
   (8 runtime service sources: sensor-data, awd-control, external-api, scada-integration,
   sensor-location-mapping, bff-water-control) as `process.env.X || '__ROTATED_DB_PASSWORD__'` fallbacks —
   services silently run on the leaked credential when env is unset. Also in flow-monitoring's
   live `.env`; prod IP `43.208.201.191` in 179 tracked files. **Rotation still outstanding.**
2. **HIGH (Codex) — `edges_from_names` accepts wrong roots.** Any single-tuple id with
   position 0 (e.g. `M(1,0)`) attaches to root S; `["M(0,0)","M(1,0)"]` yields two source
   edges and still passes `is_spanning_tree` (`network_topology.py:157`). Committed config
   unaffected; future regeneration could silently produce a wrong-but-accepted topology.
3. **MED — flow-law inverse lies about small targets** (found by two agents independently).
   Opening enters only through Cs (clamped ≥0.3) → flow discontinuous at Go→0
   (q(1 mm) ≈ 3.1 m³/s). `required_opening_m(q_target=1.0)` → opening≈0,
   `feasible: True, achievable: 3.1`; no caller checks `achievable`. **Must fix before B8**
   (overdelivery hazard).
4. **MED — B5 charges seepage on dry reaches.** Fixed-depth seepage accrues on all 37
   surveyed reaches regardless of flow: `/plan` with losses + zero demand → **2.46 m³/s at
   the head**; partial/rotational plans grossly overstated. Semantics decision needed before
   the scheduler consumes `/plan`.
5. **MED — `/api/v1/hydraulics/*` dead-on-arrival.** `hydraulic_service.py:58` hardcoded
   absolute path → FileNotFoundError → all requests 500 outside a specific container layout;
   per-request solver+DB-manager rebuild; saint-venant/manning/rating façades still return
   constants (5.2/5.0/4.8) behind it; `_get_gate_capacity` flat 10.0 fallback.
6. **MED — demand-key spacing trap.** 44/59 gate ids contain spaces (`'M (0,1; 1,0)'`);
   `/plan` rejects the normalized compact form as unknown node (B5 normalizes internally —
   inconsistent). Will bite the C12 producer.
7. **MED — legacy dual stack still live.** `main.py:44-46` builds `DualModeGateController`
   on fragmented `munbon_network_final.json` (2/57 reachable) + template geometry, serving
   `/api/v1/gates/*`; `deploy-flow-monitoring.yml:56` still ships that file to EC2.
8. **Lows:** bare `NaN` in `network.json` (not strict JSON); `canal_geometry.json` summary
   says 46 vs 37 actual; `gate_configuration.json` has 7/59 gates; secret-scan bypasses
   (multi-commit pushes scan only HEAD~1; renames escape; workflow self-excluded); default
   `pytest` can never pass (`--cov-fail-under=80` vs ~16k dead LOC); documented
   `uvicorn src.main:app` cannot boot (`python src/main.py` from service root works);
   ~65% of `src/` LOC dead/demo; 9 stale topology JSONs beside the canonical one; 5 legacy
   test suites broken (23F/34E); 503s echo internal exception strings; F-01 level fallback
   logs at `debug`; no guard against a future `k2>0` calibration breaking bisection.

### 1.3 Adherence gaps (discussions/specs → shipped work)

- **C10 partially closed:** 4 flow-law implementations still live-imported; inverted law
  survives in `calibrated_flow_model_v2.py:131` (class still instantiated); guard scans one
  file + 5 filenames only.
- **F-11 "delete stale variants" never executed** (MASTER §1.2 ordered it).
- **SV-façade removal was P1 scope — not done** (and the router is broken besides).
- **C9 narrower than spec:** GATE §10 specified `/control/demands` + time-phased plan;
  shipped is stateless static `/plan` (disclosed).
- **Docs layering:** MASTER §1.2 still teaches the star parent rule + "verify vs
  updated.json"; GATE §0.1 / HYDR preamble / HANDOFF "Decisions locked" still endorse
  `updated.json`; GATE §3 teaches the rejected Newton inverse; old seepage values
  unannotated; service CLAUDE.md's F-11 gotcha still endorses `updated.json`;
  **HANDOFF's "CURRENT STATUS" is 10 PRs stale while claiming currency**; README indexes
  5/9 docs; confidence label 0.30 (docs) vs 0.60 (code); Tier-2 of the seepage ladder and
  the L1–L5 modeling-ladder definition are missing from the doc set.
- **Process:** P0 self-merged without QCHECK; Codex adversary skipped #19–#23; #12 merged
  with its own CI check failing. Every retroactive adversarial run found a HIGH (three
  times now, including this review).

---

## Part 2 — Forward roadmap (unified plan, Claude + Codex synthesis)

### 2.0 Maintainer decisions — **ALL DECIDED 2026-07-09**

1. **Dry-reach seepage semantics — DECIDED (recommendation accepted):** charge seepage only
   on reaches with positive planned flow; optional `always_wet` reach set for trunks kept
   charged; current all-reaches behavior behind an explicit flag for steady whole-network runs.
2. **Legacy `/api/v1/gates/*` + fake `/hydraulics/model` — DECIDED (recommendation
   accepted):** repoint gates to canonical config + feature-flag it off by default
   (fail-closed 503 with clear reason); delete/501 the model façades; hard-retire after the
   F-02 SCADA bridge replaces the workflow.
3. **Demand truth + storage — DECIDED:** (a) ROS/Excel engine is the single demand source of
   truth, **updated every crop season**; RID-Plan/AquaCrop numbers are retained as an
   explicit, **switchable option** (runtime-selectable `demand_source = ros | aquacrop`,
   provenance-logged — never a silent priority). (b) Stored demands live in flow-monitoring's
   Postgres with provenance columns (source engine, formula version, computed_at, crop season).
4. **SCADA V1.0 Excel — DECIDED (commit it):** source file provided at
   `munbon2-backend-integration/SCADA Section Detailed Information 2025-08-23 V1.0 SL.xlsx`
   (198 KB); to be committed to the repo as the config generator's input (E3 resolved).

### 2.1 External actions (not PRs — schedule now)

- **E1: rotate `__ROTATED_DB_PASSWORD__`** (all DBs using it) — overdue; nothing else neutralizes it.
- **E2: `git filter-repo` history purge + team re-clone** — after E1 and after PR 0.6 lands.
- **E3:** provide the SCADA V1.0 Excel (decision 4). **E4:** GIS shapefile export for
  crop_registry. **E5:** RID's authoritative auto-gate list (needed for F-02 quantizer scope).

### 2.2 PR waves

Sizes: S ≈ ≤½ day, M ≈ 1–2 days, L ≈ 3–5 days. Lifecycle per PR: plan → TDD → QCHECK +
Codex adversary (non-skippable) → open PR → **user admin-merges**.

**Wave 0 — stabilize: security + core correctness (parallel lanes)**

| PR | Title | Scope | Size | Deps |
|----|-------|-------|------|------|
| 0.1 | Flow-monitoring CI gate | New `.github/workflows/flow-monitoring-tests.yml` running the isolated suites + one-flow-law guard + topology-connected check; branch protection | M | — |
| 0.2 | Fix small-target gate-flow inverse | `core/gate_flow.py`: expose `min_deliverable_flow`; `required_opening_m` fails closed below it; callers consume `achievable`; reject `k2>0` calibrations; fallback logging `debug→warning` | M | — (blocks B8) |
| 0.3 | Reject invalid topology roots | `edges_from_names`: only `M(0,0)` attaches to S; other single-tuple ids → `NetworkTopologyError` | S | — |
| 0.4 | Dry-reach seepage semantics | `conveyance_loss.py`/`demand_aggregation.py`: loss only where flow>0 (+ optional `always_wet` set + legacy flag); tests: zero-demand plan ⇒ zero head flow | M | Decision 1 |
| 0.5 | Config/data/doc strictness | Regenerate `network.json` strict JSON (no `NaN`); fix `canal_geometry.json` summary (46→37) + side-slope reconciliation note; SEEPAGE_CALIBRATION metric correction (~48 LMC / ~39 network); stale docstrings | M | 0.3 |
| 0.6 | Remove runtime credential fallbacks | Strip `\|\| '__ROTATED_DB_PASSWORD__'` from the 27 tracked `.js`/`.ts` (fail closed on missing env); move hardcoded prod IP to env in runtime files | M/L | — (pairs with E1) |
| 0.7 | Harden secret-scan | Scan full push range (`event.before..after`), include renames + workflow files (inline allowlist, not self-exclusion), add IP/conn-string patterns | S/M | 0.6 |

**Wave 1 — one truth at runtime (kill the dual stack)**

| PR | Title | Scope | Size | Deps |
|----|-------|-------|------|------|
| 1.1 | Strict config loaders | New `core/config_loader.py`: schema + metadata validation, strict JSON, fail-closed on drift; used by all runtime loads | M | 0.5 |
| 1.2 | Node-id normalization at boundaries | New `core/node_id.py` (canonical compact form); `/plan` + geometry/calibration joins accept both, respond canonical | M | 0.3 |
| 1.3 | Hydraulic service app-scoped + canonical | Fix absolute geometry path (anchor to `__file__`), singleton lifespan construction, same canonical config as `/control` | M | 1.1 |
| 1.4 | Delete fake model façades | Remove/501 saint-venant/manning/rating constants, dummy gauges, hardcoded 30.0 system capacity; `_get_gate_capacity` 10.0 → calibration/q_max-based with warning | M | 1.3, Decision 2 |
| 1.5 | Retire/quarantine legacy gates stack | Repoint `DualModeGateController` to canonical config; feature-flag `/api/v1/gates/*` off by default; fix `deploy-flow-monitoring.yml` to ship canonical configs + deployment smoke | M/L | 1.1, 1.2, Decision 2 |
| 1.6 | Single flow law repo-wide | Extract loader from `CalibratedFlowModelV2`, delete `calibrated_flow_model{,_v2}.py` inverted laws; guard scans all of `src/` | M | 0.2 |
| 1.7 | Hypothesis property tests | Physics invariants: flow monotonicity/continuity, inverse round-trip, spanning-tree, loss conservation; add `hypothesis` dep | S/M | 0.2–0.4 |
| 1.8 | Dead-code purge | Delete 9 stale topology JSONs, ~30 dead root scripts, `api/v1/gate_control.py`, dead core modules (import-graph-verified); keepers → `scripts/` | L | 1.5, 1.6 |
| 1.9 | Test-suite hygiene | Quarantine/fix 5 legacy suites, remove 3 script-style `test_*.py` from `src/`, drop `--cov-fail-under` (or scope to `core/`), bare `pytest` green | M | 1.8 |
| 1.10 | Docs layering pass | Supersession banners (MASTER §1.2, GATE §0/§1/§3, HYDR §0.1); HANDOFF → pointer to PR_REVIEW_GUIDE; README 9/9 index; CLAUDE.md F-11 gotcha + boot command; 0.30→0.60 alignment; commit this review | M | — (anytime) |
| 1.11 | Full-tree secret baseline | After E1+E2: CI scans the whole tree, not just diffs | S | 0.7 + E1/E2 |

**Wave 2 — finish P1 (offline control plane)**

| PR | Title | Scope | Size | Deps |
|----|-------|-------|------|------|
| 2.1 | SCADA workbook config generator | One provenance pipeline: Excel → `network.json` + `canal_geometry.json` + `gate_calibrations.json` (+ full `gate_configuration.json`), versioned metadata, lock tests | L | 1.1, 0.3, E3 |
| 2.2 | 22 missing reach geometries | Generate from V1.0 `Characteristics` sheet via 2.1 | M/L | 2.1 |
| 2.3 | Similar-gate calibration (F-05 short-term) | Estimates for the 49 default gates from type/dimensions; honest lower confidence | M | 2.1 (or standalone from current JSON) |
| 2.4 | Stored demand contract + anti-corruption layer (C12a) | `POST /api/v1/control/demands`: normalized ids, units, time phases, provenance; fail-closed; storage per Decision 3 | M/L | 1.2, Decision 3 |
| 2.5 | A4 `section_node_map` contract | Schema + fail-closed loader; placeholder data flagged until ros-gis spatial layer exists | M | 1.2 |
| 2.6 | Demand-source reconciliation (F-06/F-09) + producer (C12b) | ROS engine as SoT; ros-gis producer posts to `/demands` via section_node_map; retire/flag `aquacrop_priority`; every demand logs source | L | 2.4, 2.5 |
| 2.7 | B8 branch-split inverse | New `core/branch_split.py`: reach targets → head→tail per-gate openings via corrected law, capacity-clamped, quantization seam; wired to `/control` | L | 0.2, 0.3, 0.4, 1.2, 1.6 |
| 2.8 | `/plan` observability & uncertainty | Per-reach confidence, capacity headroom (B7 check), geometry coverage, loss basis, feasible/achievable | M | 2.7 (fields from 2.2/2.3 as available) |
| 2.9 | OpenAPI contract tests | Schema-locked tests for `/control/plan`, `/control/demands`, gates surface | S/M | 2.4 |

**Wave 3 — P2 (scheduling + SCADA shadow)**

| PR | Title | Scope | Size | Deps |
|----|-------|-------|------|------|
| 3.1 | Greedy capacity-aware rotation scheduler (B6/B7) | New `core/rotation_scheduler.py`; invariant: Σ active flows + losses ≤ reach capacity, ∀ reach, ∀ t | L | 2.7, 2.8 |
| 3.2 | D13 travel-time offsets | New `core/travel_time.py`; commands issued early by routed delay + fill/drain buffers | M/L | 3.1, 2.2 |
| 3.3 | SCADA discrete-level quantizer (F-02a) | New `core/scada_quantizer.py`; lowest safe level ≥ target; quantization deficit fed back | M | 2.3, 2.7, E5 |
| 3.4 | SCADA bridge in shadow mode (F-02b) | Advisory-only publisher + kill switch/feature flag; compare vs operator actions; no actuation until readback proven | M/L | 3.1–3.3 |
| 3.5 | CP-SAT scheduler (optional) | OR-Tools upgrade — only if greedy shows real bottlenecks | L | 3.1 + evidence |

**Wave 4 — P3/P4 (hardware-gated; plan only)**
Zone-head stage sensor ingestion → Tier-3 seepage calibration → confidence from rating-fit
residuals → F-05 field program → optional Muskingum–Cunge. Do not start before shadow-mode
telemetry and sensors exist.

### 2.3 Parallelism & priority

- **Wave 0:** 0.1–0.7 are ~all independent — up to 5 lanes. 0.2/0.3/0.4 are the physics
  blockers; 0.6/0.7 the security lane; 1.10 (docs) can also start immediately.
- **Wave 1:** 1.3/1.4 ∥ 1.5 ∥ 1.6 after 1.1/1.2; 1.8→1.9 serial after them.
- **Wave 2:** three lanes — config/data (2.1→2.2, 2.3), demand (2.4→2.5→2.6), control
  (2.7→2.8); 2.9 rides along.
- **Wave 3:** mostly serial (3.1 → 3.2/3.3 → 3.4).
- **Priority logic:** field-safety + security first (a wrong opening command and a leaked
  credential are the two ways this system hurts someone); then single-truth consolidation so
  regressions can't hide; then finish P1; actuation last, shadow-first.

### 2.4 Cut / defer

Full Saint-Venant: cut (remove the façade instead). CP-SAT: defer until greedy shows
bottlenecks. Muskingum–Cunge: defer until sensors + Tier-3. Manual expansion of
`gate_configuration.json`: don't — generate from provenance (2.1). Claiming SEC "done":
not until E1+E2 complete.
