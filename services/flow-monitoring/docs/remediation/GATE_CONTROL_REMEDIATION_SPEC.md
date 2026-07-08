# Munbon Gate-Control Remediation Spec (A–D)

Master spec covering every defect raised in the audit of the demand→gate-flow→SCADA
pipeline. Companion: `HYDRAULIC_REMEDIATION_SPEC.md` (full code for B5–B8); this
document is the superset and adds C (wiring/consistency/gate-law/demand) and D (timing).

Suggested repo path: `services/flow-monitoring/docs/GATE_CONTROL_REMEDIATION_SPEC.md`.

## Defect → fix index

| Defect | Summary | Fix section |
|---|---|---|
| A1 | hardcoded 3-zone paths → silent zeros | §2 topology, §5 aggregation |
| A2 | synthetic node IDs (`Zone2`) don't map to real gates | §1 data model |
| A3 | real graph exists but unused | §2 topology |
| A4 | aggregates per-zone, not per-section/FTO | §1 map, §5 aggregation |
| B5 | no conveyance loss | §5 aggregation |
| B6 | coincident-peak (all demand at once) | §6 timing, §7 rotation |
| B7 | no capacity check | §7 rotation |
| B8 | no branch-split coupling | §8 split solve |
| C9 | control code never runs (demo only) | §10 consolidation |
| C10 | three divergent "flow per gate" impls | §10 consolidation |
| C11 | inverted/unclamped gate law (F-01) | §3 gate law |
| C12 | no real demand producer (hardcoded 25.0) | §4 demand contract |
| D13 | static snapshot, no travel-time coupling | §6 timing |

## §0 Preconditions (blocking — land before anything else)

1. **F-11** single connected topology — adopt `munbon_network_updated.json` (59 edges,
   fully connected) or regenerate from the gate-ID hierarchy; delete the 5 stale variants.
2. **F-01** gate flow law corrected (§3).
3. **F-04** real per-section `design_discharge` wired (replace hardcoded `15.0`).

---

## §1 Data model — one source of truth (A2, A4, C10-data)

```jsonc
// network.json  (regenerated, canonical)
{
  "nodes": {
    "M(0,5)": { "canal":"LMC", "zone":2, "q_max":8.737, "area_rai":1240,
                "gate_type":"sluice", "levels":[0.0,0.5,0.8,1.0],   // discrete auto flows (frac)
                "calibration":{"K1":1.5675,"K2":-1.654,"source":"field","confidence":0.95} },
    ...
  },
  "edges": [ ["S","M(0,0)"], ["M(0,0)","M(0,1)"], ... ],   // connected tree
  "reaches": {                                             // keyed by "u->v"
    "M(0,2)->M(0,3)": { "length_m":5260,"manning_n":0.014,"bed_slope":0.00012,
                        "design_discharge":8.737,"lining":"concrete",
                        "cross_section":{...},"seepage_rate_m_s":3.0e-7,
                        "operational_loss_frac":0.05 }
  }
}
```

```jsonc
// section_node_map.json  — fixes A4: ROS section_id -> network node
{ "01-02-05-01":"M(0,5)", "01-06-03-01":"M(0,1; 1,1; 1,2; 1,0)", ... }
```

Rules: node IDs are the real `M(i,j,k)` keys (A2); demand attaches **per node** because
20 of 33 delivery nodes are interior, not leaves (A4); every coefficient/geometry lives
once, here — no parallel truth.

---

## §2 Topology (A1, A3, F-11)

```python
import networkx as nx, json
def load_network(path="network.json"):
    d = json.load(open(path))
    G = nx.DiGraph(); G.add_nodes_from(d["nodes"]); G.add_edges_from(d["edges"])
    assert nx.is_weakly_connected(G) and len(nx.descendants(G,"S"))>=len(d["nodes"]), \
        "topology not a single connected component reaching all nodes"   # hard guard
    return G, d["nodes"], d["reaches"]
```

Aggregation uses `nx.descendants` / `nx.topological_sort` on `G` — never a hardcoded
path table (kills A1/A3). The `assert` makes a fragmented graph fail fast, not silently.

---

## §3 Gate flow law — corrected (C11 / F-01)

The wired `hydraulic_service._calculate_required_opening` is **directionally inverted and
unclamped** (`Cs=k1·opening^k2` with opening as a fraction → flow falls as the gate
opens; 287 m³/s at 10% for an 11 m³/s gate). Replace with the physically-correct rating:

```python
G_MIN, G_MAX = 0.05, 1.0          # opening as gate-travel ratio Go/height
CS_LO, CS_HI = 0.30, 1.00

def discharge_coeff(K1, K2, Hs, Go):
    Cs = K1 * (Hs / Go) ** K2      # Go in the DENOMINATOR — correct direction
    return max(CS_LO, min(CS_HI, Cs))   # physical clamp (was missing)

def gate_flow(cal, L, Hs, dH, Go):       # Q = Cs·L·Hs·√(2gΔH)
    if dH <= 0 or Hs <= 0 or Go <= 0: return 0.0
    return discharge_coeff(cal.K1, cal.K2, Hs, Go) * L * Hs * math.sqrt(2*9.81*dH)

def required_opening(cal, L, Hs, dH, q_target):
    """Newton on the CORRECT law with REAL levels (not hardcoded 2.0/0.2)."""
    Go = 0.5*G_MAX
    for _ in range(40):
        q = gate_flow(cal, L, Hs, dH, Go)
        err = q - q_target
        if abs(err) < 1e-3: break
        dGo = 1e-4
        dq = (gate_flow(cal,L,Hs,dH,min(G_MAX,Go+dGo)) - q)/dGo or 1e-6
        Go = min(G_MAX, max(G_MIN, Go - err/dq))
    return Go
```

- Feed **real** upstream/downstream levels (sensor or solved), never fixed constants.
- Propagate `cal.confidence` (0.95 field / 0.80 size-default / 0.30 generic) onto every
  result; surface it — do **not** claim a validated 90% CI.
- **Regression test (must exist):** monotonicity — `gate_flow` strictly increasing in `Go`
  for K2<0; and `gate_flow(...,G_MAX) ≤ 1.2·q_max`. This test fails on today's code.

---

## §4 Demand producer & contract (C12)

Today the wired demand is a hardcoded `25.0`. Define the real producer→consumer contract.

**Producer:** the nightly ROS/`ros_gis` pipeline (the *operational* demand lineage).
**Transport:** `POST /api/v1/control/demands` on flow-monitoring.

```jsonc
// request body — TIME-PHASED per-section demand (also fixes D13 input)
{ "period": {"start":"2026-07-08T00:00Z","end":"2026-07-15T00:00Z"},
  "deliveries": [
    { "section_id":"01-02-05-01", "volume_m3":48000, "priority":0.82,
      "field_water_level_m":0.12, "earliest":"...", "latest":"..." }, ...
  ] }
```

- Server maps `section_id → node` (§1), attaches `volume_m3` as node demand.
- `volume_m3` is already field-water-level-adjusted upstream in ROS; carry
  `field_water_level_m` only for the closure loop (§7 step 7).
- Retire `_get_system_demand()`'s `25.0`. If no demand posted → no gate commands
  (fail closed), not a fabricated constant.

---

## §5 Aggregation with conveyance loss (A1, A4, B5)

Post-order descendants sum over the connected graph, adding per-reach loss (B5):

```python
def required_flow_per_reach(G, node_demand, reaches, passes=2):
    order = list(reversed(list(nx.topological_sort(G))))   # leaves -> root
    reach_flow, subtree = {}, {}
    for _ in range(passes):                                 # relax seepage(depth)
        for n in order:
            q = node_demand.get(n, 0.0)                     # THIS node's own area (A4)
            for c in G.successors(n):
                thru = subtree.get(c, 0.0)
                r = reaches[f"{n}->{c}"]
                loss = seepage(r) + r["operational_loss_frac"]*thru     # B5
                reach_flow[(n,c)] = thru + loss
                q += reach_flow[(n,c)]
            subtree[n] = q
    return reach_flow
```

`seepage(r) = r.seepage_rate_m_s · wetted_perimeter(r) · length`. Every node contributes
(A1); interior demands included (A4); head gate now carries **more** than Σ field demand (B5).

---

## §6 Time-phased demand & travel-time coupling (D13)

The instantaneous "sum all downstream demand now" is wrong: water released now arrives
later. Reconcile demand *windows* with routing delay so a gate carries only what is
**active after travel time**.

```python
def routed_delay(G, reaches, src, node, q):
    """Sum travel time along path; velocity from Manning at flow q (existing helper)."""
    t = 0.0
    for u,v in zip(path(G,src,node)[:-1], path(G,src,node)[1:]):
        r = reaches[f"{u}->{v}"]; V = manning_velocity(r, q)
        t += r["length_m"]/max(V,0.1)
    return t

def active_set_at(t_now, windows, G, reaches):
    """A delivery's water must LEAVE the head earlier by its routed delay."""
    active = []
    for w in windows:
        lead = routed_delay(G, reaches, "S", w.node, w.q)
        if (w.start - lead) <= t_now < (w.end - lead):   # release window, delay-shifted
            active.append(w)
    return active
```

- Gate-open command for delivery *w* is issued at `w.start − routed_delay`; close at
  `w.end − routed_delay`. Add a canal fill/drain buffer (`storage_volume/q`) at block edges.
- The reach target at `t_now` is the descendants sum over **`active_set_at(t_now)`**, not
  over all deliveries — this is the time-aware version of §5 and the object D13 said was missing.

---

## §7 Rotation scheduler — capacity + concurrency (B6, B7)

Greedy capacity-aware scheduler (full code in companion §3). Essence:

```python
def fits(d, load, Q_cap, uplift):
    return all(load[e] + d.q*(1+uplift(e,load[e])) <= Q_cap[e] for e in d.path_edges)
# start highest-priority delivery only if it fits EVERY reach on its path;
# free its capacity on finish; advance event-driven.
```

- `Q_cap[e] = reaches[e].design_discharge` (F-04).
- `d.q` = highest discrete gate level ≤ `q_max`, ≥ `q_min` (auto-gate levels, §9).
- Invariant `Σ_active q·(1+λ) ≤ Q_cap` on every reach ∀t → **B7**; only concurrent
  demand summed → **B6**. Infeasible sums defer to later slots (never over-command).
- Upgrade path: OR-Tools CP-SAT RCPSP (reaches = renewable resources), ~33 deliveries in s.
- **Closure loop:** integrate delivered volume per section; close when `V_i` met;
  re-run on the new active set (generalizes `dynamic_flow_reducer`).

---

## §8 Branch-split solve (B8)

Keep `hydraulic_solver.solve_network()` as the **forward** engine (it already resolves the
split via node continuity + level iteration, on the correct orifice law). Replace the crude
`optimize_gates_for_target` with a coordinated head→tail **inverse**, run per active set:

```python
def set_gates_for_targets(solver, reach_targets, Q_cap):
    for (u,v) in topo_order_head_to_tail(solver.G):
        q  = min(reach_targets.get((u,v),0.0), Q_cap[(u,v)])       # clamp (B7)
        Go = 0.0 if q<=0 else required_opening(cal(u,v), L(u,v), Hs(v), dH(u,v), q)  # §3
        solver.set_opening((u,v), quantize_to_level((u,v), Go, q, Q_cap))            # §9
    return solver.solve_network(solver.current_settings())         # verify split forward
```

Shared upstream gate is sized to the summed target; downstream gates split it; the forward
solve confirms consistency.

---

## §9 Discrete-level actuation bridge (the SCADA gap)

flow-monitoring emits continuous openings; `scada-gate-control` accepts only levels 1–4.
Nothing bridges them today. Add the quantizer + command hop:

```python
def quantize_to_level(edge, Go, q_target, Q_cap):
    cands = [(L, flow_at_level(edge, L)) for L in (2,3,4)]         # from node.levels
    ok = [L for L,f in cands if f >= q_target and f <= Q_cap[edge]]
    return min(ok) if ok else max(L for L,_ in cands)              # else 100% + flag deficit

# then: POST scada-gate-control /api/gates/{id}/command-level { targetValue: L, confirmed:true }
```

Treat level granularity as an upstream *constraint* (§7 picks `d.q` from the level set), so
the scheduler never asks for a flow no level can deliver.

---

## §10 Consolidation & wiring (C9, C10)

**C10 — collapse the three "flow per gate" implementations into one module**
`services/flow-monitoring/src/core/network_flow_controller.py`, the single source of truth:

```
NetworkFlowController
  ├─ load_network()                 §2   (connected graph + reaches + calibration)
  ├─ attach_demand(deliveries)      §4   (section_node_map)
  ├─ required_flow_per_reach()      §5   (aggregation + B5)
  ├─ schedule_rotation()            §7   (B6/B7)  ── uses active_set_at §6 (D13)
  ├─ set_gates_for_targets()        §8   (inverse) ── uses required_opening §3 (C11)
  └─ emit_scada_commands()          §9   (quantize + POST)
```

Delete/retire the demos: `integrated_gate_control.py`,
`dynamic_flow_reducer.py` (logic absorbed into `schedule_rotation`),
`water_gate_controller_{integrated,local,enhanced,v2}.py`,
`gate_opening_calculator.py`, `calibrated_gate_flow.py` (fake calibrations),
and the stub `_get_saint_venant_results`/`_get_manning_results` façades.

**C9 — wire it into the running service.** `main.py` already constructs
`DualModeGateController(db, network_file, geometry_file)`; have it hold a
`NetworkFlowController`, and expose:
- `POST /api/v1/control/demands` (§4) → `attach_demand`
- `POST /api/v1/control/plan` → `schedule_rotation` → returns the time-phased gate plan
- the plan executor issues `command-level` to SCADA at each window's delay-shifted time.
Remove `_solve_optimal_gate_settings`'s dummy `50%`.

---

## §11 Acceptance matrix (every defect → test)

| Defect | Test |
|---|---|
| A1 | every node with `area>0` appears in `required_flow_per_reach`; no empty paths |
| A2 | all emitted gate IDs ∈ network node keys |
| A3 | aggregation uses `nx.descendants`; no path dict in codebase (grep gate) |
| A4 | interior delivery node's own demand included in its parent reach |
| B5 | earth reach seepage > 0; head flow > Σ demand by Σ losses; tail FTO fully served |
| B6 | reach target = Σ **active** windows only (assert vs all-demand sum) |
| B7 | assert `Σ q·(1+λ) ≤ design_discharge` on every reach ∀ t; over-demand deferred |
| B8 | known bifurcation split matches analytical ± ε; inverse hits each branch target |
| C9 | integration test drives `/demands`→`/plan`→SCADA; no demo `__main__` in path |
| C10 | only `NetworkFlowController` computes flow-per-gate (others deleted) |
| C11 | monotonicity: `gate_flow` increasing in `Go`; `flow(G_MAX) ≤ 1.2·q_max` (fails today) |
| C12 | no demand posted → zero commands (fail closed); `25.0` constant removed |
| D13 | gate-open time = window.start − routed_delay; active set is delay-shifted |
| topology | loader `assert` rejects any fragmented graph |

---

## §12 Phased rollout

- **P0 (no hardware)** — F-11 topology, F-01 gate law (§3), F-04 capacity, delete demos (§10).
- **P1 (software)** — `NetworkFlowController`: §1 data model, §2, §4 contract, §5 aggregation+B5, §8 forward/inverse. Offline plan generation + verification.
- **P2 (scheduler)** — §6 timing + §7 rotation + §9 quantize; wire `/plan` and the SCADA bridge (§10). Shadow-mode (advise operators, don't actuate).
- **P3 (closed loop + sensors)** — zone-head stage sensors; §7 closure loop live; calibrate seepage (B5 Tier-3) and expand gate calibration beyond 10/59.
- **P4 (optional)** — diffusive-wave routing (companion modeling-ladder L4) once sensors support it.
