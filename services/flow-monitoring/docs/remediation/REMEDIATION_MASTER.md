# Munbon Backend — Master Remediation & Improvement Spec

Consolidates every finding from the end-to-end audit (demand → scheduling → gate
hydraulics → SCADA) into one prioritized, testable improvement plan. Companion specs
hold full code for their areas:
- `FIX_F01_GATE_FLOW_LAW_SPEC.md` — the gate-flow law (F-01/C11).
- `HYDRAULIC_REMEDIATION_SPEC.md` — conveyance loss + rotation + split (B5–B8).
- `GATE_CONTROL_REMEDIATION_SPEC.md` — the A–D control-pipeline master.

Legend — **Sev**: Crit / High / Med / Low. **P**: rollout phase (P0 = no hardware,
software only; …; P4 = optional/advanced). ✔ = fix fully specced elsewhere (pointer given).

---

## 0. Finding → fix index (complete)

| ID | Sev | Finding | Fix § | P |
|----|-----|---------|-------|---|
| F-01 / C11 | Crit | Gate flow law inverted, unclamped, hardcoded levels, MSL-`Hs` → 287 m³/s | §1.1 ✔ | P0 |
| F-11 | Crit | Wired network topology ~76% wrong; 6 conflicting files | §1.2 | P0 |
| F-02 | Crit | Hydraulic control ↔ SCADA actuator disconnected | §5.1 | P2 |
| F-03 / C9 | High | Auto control stubbed (demand 25.0, openings 50%) | §6.1 | P1 |
| F-04 / B7 | High | Canal `design_discharge` not enforced (hardcoded 15) | §3.3 ✔ | P0 |
| F-05 | High | Only 10/59 gates field-calibrated | §1.3 | P1/P3 |
| C10 / F-10 | High | Divergent flow-per-gate + hydraulic impls | §6.2 | P0/P1 |
| A1/A2/A3 | High | Hardcoded paths / synthetic IDs / graph unused | §3.1 ✔ | P1 |
| A4 | High | Aggregates per-zone, not per-section/FTO | §3.1 ✔ | P1 |
| B5 | High | No conveyance loss | §3.2 ✔ | P1 |
| B6/B7 | High | Coincident-peak; no capacity | §4 ✔ | P2 |
| B8 | High | No branch-split coupling | §5.2 ✔ | P1 |
| D13 | High | No travel-time coupling (static snapshot) | §4.2 ✔ | P2 |
| C12 | High | No real demand producer (hardcoded 25.0) | §2.1 | P1 |
| F-06 | Med | AquaCrop demand preferred but never populated | §2.2 | P1 |
| F-09 | Med | Three divergent demand formulas | §2.3 | P1 |
| F-07 | Med | `gis.crop_registry` no loader + hardcoded prod creds | §2.4 + §7.3 | P0 |
| F-08 | Med | RID-MS in-service cron module missing | §2.5 | P0 |
| SV-façade | Med | `saint-venant`/`manning` API returns hardcoded literals | §5.3 | P1 |
| CONF | Med | "Confidence" is a self-assigned label, not a CI | §1.4 | P3 |
| SEC | Med | Hardcoded prod DB creds in scripts | §7.3 | P0 |

---

## 1. Control-plane data integrity (foundation — P0)

### 1.1 Gate flow law (F-01/C11) — ✔ `FIX_F01_GATE_FLOW_LAW_SPEC.md`
Three stacked bugs (inverted `opening^K2`; MSL `Hs`; missing Cs clamp) + hardcoded
levels. Fix: single `core/gate_flow.py` with `Cs=K1·(Hs/Go)^K2` (Go metres, Hs = head
over sill), clamp `[0.3,1.0]`, `q≤q_max` ceiling, bisection inverse on real levels.
Regression test: `q(10% open) ≤ q_max`; monotone in `Go`.

### 1.2 Network topology (F-11)
The gate IDs encode the tree; regenerate the canonical 59-edge connected graph and make
it the only one.
> **SUPERSEDED (Wave 1.10 banner).** The parent rule sketched below — and its
> "verify vs updated.json" oracle — encode the F-11 STAR wiring that F-11b later
> proved wrong for lateral canals (29/59 edges corrected, PR #20). The canonical
> derivation is `core.network_topology.edges_from_names` (serial-chain grammar:
> `p>0` → serial predecessor `(a,p-1)`; `p==0` → drop the last tuple; only
> `M(0,0)` roots at S), and `src/config/network.json` is locked to it by test.
> The stale variants named below were deleted (Waves 1.6–1.8). Kept for history.

```python
def build_canonical_network(gate_ids):
    """Parent = ID with last ';a,b' segment dropped; M(0,k)→M(0,k-1); M(0,0)→S."""
    edges=set()
    for g in gate_ids:
        p=parent_from_id(g)          # deterministic from the hierarchical name
        if p: edges.add((p,g))
    edges.add(('S','M(0,0)'))
    return edges                     # 59 edges, connected — verify vs updated.json
```
- Emit one `network.json`; **delete** `final`, `structure`, `simple`, `complete`,
  `structure_updated`, `updated` variants (keep one, archived).
- Loader guard: `assert is_weakly_connected(G) and descendants('S')==all_nodes` — fail
  fast, never run on a fragmented graph.

### 1.3 Calibration coverage (F-05)
10/59 gates field-measured; 49 on size defaults (−27 %…+110 % error).
- **Short term:** `scripts/build_scada_config.py` now replaces generic defaults with
  **similar-gate estimation**, weighted by measured fit confidence and keyed by physical
  shape, dimensions, and canal class. Outputs remain `planning_only`; every inference
  records its measured donors, lower confidence, and algorithm/workbook source version.
- **Program:** rank uncalibrated gates by (a) command-area served, (b) position on
  critical delivery paths; field-rate the top-N first (tail FTOs and shared trunk gates
  matter most). Store `flow_range_tested` with each calibration.
- Surface each gate's calibration source + confidence on every command (§1.4).

### 1.4 Confidence — from residuals, not labels (CONF)
Today `confidence` is a hardcoded `0.95 / 0.80 / 0.60` (the shipped ladder; an earlier draft said 0.30).
- On calibration, compute `confidence = f(R², n_points, flow-range coverage)` from the
  rating fit residuals; store CI half-width, not a scalar label.
- Propagate to command output as a real uncertainty band; **never** assert "90 % correct".

---

## 2. Demand plane

### 2.1 Real demand producer & contract (C12) — P1
Retire the hardcoded `25.0`. Define `POST /api/v1/control/demands` with **time-phased,
per-section** volumes fed by the ROS/`ros_gis` pipeline (contract in
`GATE_CONTROL_REMEDIATION_SPEC.md §4`). No demand posted ⇒ **fail closed** (zero commands).

### 2.2 Reconcile ROS vs AquaCrop (F-06) — P1
`ros_gis.aquacrop_results` is read but written only by the mock; the real RID demand
(`seasonIrrM3PerRai`) sits unread in `agricultural_plots.properties`.
- **Decide the source of truth explicitly.** Either (a) route RID `seasonIrrM3PerRai`
  into `ros_gis.aquacrop_results` via a real ingest step, or (b) drop the `aquacrop`
  branch and make ROS/Excel the sole demand — and change the default
  `demand_combination_strategy` off `aquacrop_priority` so it stops silently falling back.
- Whatever is chosen, **log which source produced each demand** and the fallback reason.

### 2.3 One demand formula (F-09) — P1
Three implementations compute "water demand" differently (ROS: +percolation +rain +WL;
RID-MS calc: efficiency-based, no percolation; BFF script: no percolation).
- Promote the **ROS/Excel engine** to the single demand library; the RID-MS calculator
  and the BFF `populate_weekly_demands` script become either thin callers or are deleted.
- Add a contract test: same parcel + inputs ⇒ same demand across every caller.

### 2.4 `crop_registry` provenance (F-07-data) — P0
Table read by one untracked script, written by nothing in-repo.
- Replace the out-of-band shapefile import with a **tracked loader** (a migration or an
  ingest service) that populates `gis.crop_registry` from the source shapefiles, or
  repoint the reader at `gis.agricultural_plots` (the maintained table) and retire
  `crop_registry`.

### 2.5 RID-MS cron module (F-08) — P0
`rid-ms/src/index.js` imports `./jobs/job-scheduler`, which is absent/untracked ⇒ the
service fails to start as committed.
- Restore the module (daily shapefile check `0 6 * * *` + weekly cleanup + the water-demand
  refresh) **or** remove the dead import and the `updateAllWaterDemands` wiring. Add a
  smoke test that the service boots.

---

## 3. Aggregation & routing (A/B5) — ✔ `GATE_CONTROL_REMEDIATION_SPEC.md`

### 3.1 Graph-descendants aggregation (A1–A4) — P1 ✔ §2,§5
`nx.descendants` post-order sum over the connected graph; per-node demand via
`section_node_map`; interior delivery nodes included. Resolves A1/A2/A3; A4 needs the map.

### 3.2 Conveyance loss (B5) — P1 ✔ §5 + `HYDRAULIC_REMEDIATION_SPEC §1`
Tier-1 seepage flux `Q_seep = s·P·L` (soil-aware `s`, provisional pending Tier-3
calibration) + operational %, routed up-tree.

### 3.3 Capacity enforcement (F-04/B7) — P0 ✔
Replace `_get_canal_capacity()`'s hardcoded `15.0` with per-reach `design_discharge`;
flag any reach over capacity at aggregation → defer to rotation (§4).

---

## 4. Scheduling & feasibility (B6/B7/D13) — ✔ `HYDRAULIC_REMEDIATION_SPEC §3`, `GATE_CONTROL §6–7`

### 4.1 Capacity-aware rotation (B6/B7) — P2
Greedy scheduler: start a delivery only if it fits every reach on its path; free capacity
on finish. Invariant `Σ_active q·(1+λ) ≤ Q_cap ∀ reach,t`. Upgrade → OR-Tools CP-SAT RCPSP.

### 4.2 Travel-time coupling (D13) — P2
Reach target at `t` = descendants sum over the **delay-shifted active set**
(`active_set_at`); gate-open/close issued earlier by routed travel time + fill/drain buffer.

---

## 5. Hydraulic solve & actuation

### 5.1 SCADA bridge (F-02) — P2
Continuous opening (flow-monitoring) ↔ discrete levels 1–4 (`scada-gate-control`), with
no link today. Add:
```python
def command_gate(edge, q_target, Q_cap):
    Go = required_opening_m(cal(edge), Hu(edge), Hd(edge), q_target)   # core/gate_flow
    L  = quantize_to_level(edge, Go, q_target, Q_cap)                  # lowest level ≥ target ≤ cap
    post(f"{SCADA}/api/gates/{gate_id(edge)}/command-level",
         {"targetValue": L, "confirmed": True})
    return L
```
- Feed the **quantization back**: the scheduler picks `d.q` from the gate's discrete level
  flows so it never asks for a flow no level delivers.
- **Feedback loop:** read back the achieved level + measured/estimated flow; reconcile
  against target; re-plan on drift.

### 5.2 Branch-split solve (B8) — P1 ✔
Keep `hydraulic_solver.solve_network` as the forward split engine; replace
`optimize_gates_for_target` with the head→tail coordinated, capacity-clamped inverse on
`core/gate_flow` (`GATE_CONTROL §8`).

### 5.3 Saint-Venant / Manning façades (SV) — P1
`_get_saint_venant_results` / `_get_manning_results` / `_get_rating_curve_results` return
hardcoded literals behind an API that advertises real models.
- **Remove the façades** and the `saint-venant` enum, or back `manning` with the real
  `enhanced_hydraulic_solver` output. Do **not** ship an endpoint that fabricates results.
- Full unsteady Saint-Venant is **not** recommended given the data (no flow meters); the
  realistic upgrade is diffusive-wave (Muskingum–Cunge) — see the modeling ladder / MVP.
  Track as P4, gated on sensor rollout.

---

## 6. Consolidation & wiring

### 6.1 Wire the controller (F-03/C9) — P1
Promote the demo logic into one wired `core/network_flow_controller.py` behind
`/api/v1/control/{demands,plan}`; remove `_get_system_demand`'s `25.0` and
`_solve_optimal_gate_settings`'s `50 %` dummy.

### 6.2 Delete the divergent implementations (C10/F-10) — P0/P1
Single flow law (`core/gate_flow`) + single controller. **Retire:**
`integrated_gate_control.py`, `dynamic_flow_reducer.py` (absorbed into the scheduler),
`water_gate_controller_{integrated,local,enhanced,v2,fixed}.py` (keep one as the solver's
network adapter), `gate_opening_calculator.py`, `calibrated_gate_flow.py`, and the SV/Manning
façades. Grep-gate in CI: exactly one definition of the flow law and of flow-per-gate.

---

## 7. Cross-cutting

### 7.1 Testing
Property + regression tests per finding (matrix §9). CI gate: topology-connected,
flow-law monotone, capacity never exceeded, one-source-of-truth greps.

### 7.2 Observability
Every command carries: source demand id, calibration source+confidence, active-set at
issue time, capacity headroom, and quantization deficit (if any). Log fallback reasons
(demand source, default calibration, deferred delivery).

### 7.3 Security (SEC / F-07) — P0
Hardcoded production DB host + password in `bff-water-planning/scripts/populate_weekly_demands_with_events.py` (and the broad "credentials cleaned" history).
- Move all DB creds to env/secret manager; rotate the exposed `postgres` password;
  add a secret-scanning CI gate; purge from history if feasible.

---

## 8. Prioritized roadmap (dependency-ordered)

- **P0 — foundation, no hardware:** F-01 gate law · F-11 topology · F-04 capacity ·
  C10 delete duplicates · F-07/F-08 demand plumbing + SEC creds. *Nothing correct is
  possible until these land.*
- **P1 — software control plane:** `network_flow_controller` (C9) · A1–A4 aggregation ·
  B5 loss · B8 inverse · C12 demand contract · F-06/F-09 demand reconciliation ·
  SV façade removal · F-05 similar-gate calibration. Offline plan generation + verify.
- **P2 — scheduling + actuation:** B6/B7 rotation · D13 timing · F-02 SCADA bridge
  (shadow mode: advise, don't actuate).
- **P3 — closed loop + sensors:** zone-head stage sensors · closure loop · B5 Tier-3
  seepage calibration · CONF confidence-from-residuals · expand field calibration.
- **P4 — advanced (optional):** diffusive-wave routing once sensors support boundaries.

Dependency spine: **F-01 + F-11 + F-04 → aggregation → inverse/split → scheduling →
SCADA bridge → closed loop.** Everything consumes the corrected gate law and connected graph.

---

## 9. Acceptance matrix (every finding → test)

| Finding | Test |
|---|---|
| F-01 | `q(10%·max) ≤ q_max`; monotone in `Go`; round-trip flow↔opening |
| F-11 | loader rejects fragmented graph; canonical == 59-edge connected tree |
| F-04 | `Σ q ≤ design_discharge` per reach; over-demand deferred |
| A1–A4 | every `area>0` node contributes; IDs ∈ node keys; interior demand included |
| B5 | head flow > Σ demand by Σ losses; tail FTO fully served |
| B6/B7 | reach target = active set only; capacity never exceeded ∀t |
| B8 | bifurcation split matches analytical ± ε; inverse hits each branch target |
| D13 | gate-open time = window.start − routed_delay |
| C9 | integration: `/demands`→`/plan`→SCADA; no demo `__main__` in path |
| C10/F-10 | exactly one flow law + one flow-per-gate definition (CI grep) |
| C12 | no demand posted ⇒ zero commands; `25.0` removed |
| F-02 | continuous opening → level within capacity; command posted + read back |
| F-05 | uncalibrated gate uses similar-gate estimate with reduced confidence |
| F-06 | demand source logged; no silent aquacrop→ROS fallback |
| F-09 | same parcel ⇒ same demand across all callers |
| F-07/F-08 | crop_registry has a tracked loader; rid-ms boots (cron present) |
| SV | `saint-venant` enum removed or backed by real solver; no literal returns |
| CONF | confidence derived from fit; CI surfaced, not a fixed label |
| SEC | no secrets in source; scanning gate passes; password rotated |
```
