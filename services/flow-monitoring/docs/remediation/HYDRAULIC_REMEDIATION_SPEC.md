# Flow-Monitoring Hydraulic Remediation Spec

Target service: `services/flow-monitoring`. Suggested repo path for this file:
`services/flow-monitoring/docs/HYDRAULIC_REMEDIATION_SPEC.md`.

Scope: fixes for the demand→gate-flow pipeline defects **B5** (conveyance loss),
**B6/B7** (concurrency + capacity via rotation), and **B8** (branch-split coupling),
plus the schema and wiring they depend on. Prerequisite: a single **connected**
network graph (adopt `munbon_network_updated.json`; see topology finding F-11) and a
corrected gate-flow equation (`Cs = K1·(Hs/Go)^K2` with the 0.3–1.0 clamp; F-01).

---

## 0. Schema additions

### 0.1 Canal section — add capacity + seepage (extends `canal_geometry_template.json`)

```jsonc
{
  "section_id": "LMC_03",
  "from_node": "M(0,2)",
  "to_node":   "M(0,3)",
  "geometry": {
    "length_m": 5260,
    "cross_section": { "type":"trapezoidal","bottom_width_m":12.0,"depth_m":3.0,
                       "side_slope":1.5,"lining":"concrete" },
    "hydraulic_params": {
      "manning_n": 0.014,
      "bed_slope": 0.00012,
      "design_discharge": 8.737,      // ALREADY PRESENT — wire it into capacity checks
      "freeboard_m": 0.5,
      "seepage_rate_m_s": 3.0e-7,     // NEW — default by lining; calibrate later
      "operational_loss_frac": 0.05   // NEW — spill/check leakage, default 5%
    }
  }
}
```

Default `seepage_rate_m_s` by lining (literature, replace by calibration):
`concrete → 3.0e-7`, `earth → 1.5e-6`, unknown → `1.0e-6`.

### 0.2 Section→node map (fixes A4 / demand attachment)

ROS keys demand by `ros_gis.section_id` (e.g. `01-02-05-01`); the graph keys by
`M(i,j,k)`. Provide the join explicitly:

```jsonc
// section_node_map.json
{ "01-02-05-01": "M(0,5)", "01-06-03-01": "M(0,1; 1,1; 1,2; 1,0)", ... }
```

Each network node MAY carry its own command-area demand (33 of 59 nodes have
`area>0`; 20 are interior, not leaves) — so demand attaches per node, not per leaf.

---

## 1. B5 — conveyance-loss model

Per reach `r`, seepage as wetted-perimeter flux at operating depth `y ≈ 0.7·depth`:

```python
def wetted_perimeter(cs, y):
    b, m = cs["bottom_width_m"], cs.get("side_slope", 1.0)
    return b + 2*y*math.sqrt(1 + m*m)

def reach_seepage_m3s(section):
    g  = section["geometry"]; cs = g["cross_section"]; hp = g["hydraulic_params"]
    y  = 0.7 * cs["depth_m"]
    P  = wetted_perimeter(cs, y)
    return hp["seepage_rate_m_s"] * P * g["length_m"]     # m^3/s lost along the reach

def reach_loss_uplift(section, throughflow_m3s):
    """Total loss = seepage + operational. Returns absolute m^3/s to ADD upstream."""
    seep = reach_seepage_m3s(section)
    op   = section["geometry"]["hydraulic_params"].get("operational_loss_frac", 0.05)
    return seep + op * throughflow_m3s
```

Evaporation is omitted (short residence). Seepage grows mildly with depth/flow, so
the up-tree aggregation (§2.1) does 1–2 relaxation passes.

Calibration (Tier-3, once per lining class): run a reach at steady `Q_in`, measure
`Q_out`; `seepage_rate ≈ (Q_in − Q_out) / (P·L)`. Overwrite the default.

---

## 2. Corrected demand aggregation (A1–A4 + B5)

### 2.1 Post-order descendants sum with loss uplift

```python
import networkx as nx

def required_flow_per_reach(G, node_demand, sections_by_edge, passes=2):
    """
    G: connected DiGraph (from munbon_network_updated.json), root 'S'.
    node_demand[n]: this node's own command-area demand (m^3/s), 0 if none.
    Returns required flow ENTERING each edge (== the gate on that edge).
    """
    order = list(reversed(list(nx.topological_sort(G))))   # leaves -> root
    reach_flow = {}
    for _ in range(passes):                                 # relax seepage(depth)
        subtree = {}
        for n in order:
            q = node_demand.get(n, 0.0)
            for c in G.successors(n):
                edge = (n, c)
                thru = subtree.get(c, 0.0)
                sec  = sections_by_edge.get(edge)
                loss = reach_loss_uplift(sec, thru) if sec else 0.0
                reach_flow[edge] = thru + loss              # flow entering edge n->c
                q += reach_flow[edge]                       # parent must supply it
            subtree[n] = q
    return reach_flow      # keyed by (upstream, downstream) == gate_id components
```

Invariant: `reach_flow[(u,v)] = Σ(demand of v's subtree) + Σ(losses of reaches below u→v)`.
Because `G` is the *connected* graph, every node contributes — no silent zeros (A1),
IDs are real (A2), interior demands are included (A4).

### 2.2 Feasibility flag (B7 at aggregation)

```python
def capacity_violations(reach_flow, sections_by_edge):
    out = []
    for edge, q in reach_flow.items():
        cap = sections_by_edge[edge]["geometry"]["hydraulic_params"]["design_discharge"]
        if q > cap:
            out.append((edge, q, cap))          # -> defer demand into rotation (Section 3)
    return out
```

---

## 3. B6/B7 — capacity-aware rotation scheduler

Turns "everyone at once, uncapped" into "concurrently-active set that fits every reach."

### 3.1 Inputs

```python
@dataclass
class Delivery:
    section_id: str
    node: str                 # network node (via section_node_map)
    volume_m3: float          # V_i over the period (ROS, already field-WL-adjusted)
    q_min: float; q_max: float
    level_flows: list[float]  # discrete achievable flows {q(L2),q(L3),q(L4)} for auto gates
    priority: float           # crop stress / equity; higher = earlier
    path_edges: list[tuple]   # reaches head->node (nx.shortest_path on G)
```

`Q_cap[edge] = design_discharge`. `uplift(edge, q)` from §1.

### 3.2 Greedy list scheduler (reference implementation)

```python
def schedule_rotation(deliveries, Q_cap, uplift, period_s, min_run_s=1800):
    # 1. choose operating flow per delivery = highest discrete level <= q_max, >= q_min
    for d in deliveries:
        feasible = [q for q in d.level_flows if d.q_min <= q <= d.q_max] or [d.q_max]
        d.q = max(feasible)
        d.dur = d.volume_m3 / d.q

    # 2. feasibility of the whole period
    head_cap = Q_cap[('S', 'M(0,0)')]
    if sum(d.volume_m3 for d in deliveries) > head_cap * period_s:
        log_deficit(...)                         # curtail by priority or extend period

    waiting = sorted(deliveries, key=lambda d: -d.priority)
    active, t, windows = [], 0.0, []
    load = defaultdict(float)                     # current flow committed per reach

    def fits(d):
        return all(load[e] + d.q*(1+uplift(e, load[e])) <= Q_cap[e] for e in d.path_edges)

    while waiting or active:
        # start everything that fits, in priority order
        for d in list(waiting):
            if fits(d):
                for e in d.path_edges: load[e] += d.q*(1+uplift(e, load[e]))
                d.start = t; d.end = t + max(d.dur, min_run_s)
                active.append(d); waiting.remove(d)
        if not active: break                      # nothing can start -> deadlock/deficit
        # advance to next finish
        t = min(d.end for d in active)
        for d in [d for d in active if d.end <= t]:
            for e in d.path_edges: load[e] -= d.q*(1+uplift(e, load[e]))
            windows.append(d); active.remove(d)
    return windows                                # each: (section, node, q, start, end)
```

By construction `Σ active q ≤ Q_cap` on every reach at every instant → **B7 satisfied**;
only concurrently-active demand is ever summed → **B6 satisfied**.

> Rigorous alternative: model as RCPSP with reaches as renewable resources and solve
> with OR-Tools CP-SAT (minimize makespan s.t. capacity + on/off + min-run). ~33
> deliveries solve in seconds. The greedy above is the MVP; CP-SAT is the upgrade.

### 3.3 Travel-time offset (delay-aware commands)

```python
for w in windows:
    tt = routed_travel_time(G, 'S', w.node, w.q)     # existing propagate_flow_with_delay
    w.gate_open_at  = w.start - tt                    # water must be released earlier
    w.gate_close_at = w.end   - tt
    # add canal fill/drain buffer at rotation-block boundaries (storage volume / q)
```

### 3.4 Time-varying reach targets (the object B6 said was missing)

```python
def reach_targets_at(t, windows, uplift):
    load = defaultdict(float)
    for w in windows:
        if w.start <= t < w.end:
            for e in w.path_edges: load[e] += w.q*(1+uplift(e, load[e]))
    return load        # Q_target[edge] at time t; guaranteed <= Q_cap[edge]
```

---

## 4. B8 — forward split + coordinated inverse

`hydraulic_solver.solve_network()` already resolves the **forward** branch split
(node continuity + level iteration) and uses the directionally-correct orifice law.
Keep it as the physics engine. Replace the crude `optimize_gates_for_target()`:

```python
def set_gates_for_targets(solver, reach_targets, Q_cap):
    """Coordinated head->tail inverse for ONE concurrently-active set."""
    for edge in topo_order_head_to_tail(solver.G):
        q = min(reach_targets.get(edge, 0.0), Q_cap[edge])       # clamp (B7)
        if q <= 0:
            solver.set_opening(edge, 0.0); continue
        Go = solver.required_opening(edge, q)                    # CORRECTED Cs=K1(Hs/Go)^K2
        solver.set_opening(edge, quantize_to_level(edge, Go, q, Q_cap))
    result = solver.solve_network(solver.current_settings())     # verify split forward
    return result                                                # actual per-branch flows
```

Run this **per rotation time-block** (single active set) rather than globally, so the
shared upstream gate is sized to the summed target while downstream gates split it.

### 4.1 Discrete-level quantization (auto gates)

```python
def quantize_to_level(edge, Go_continuous, q_target, Q_cap):
    # pick the lowest discrete level whose delivered flow >= q_target, capped by Q_cap
    levels = [(L, flow_at_level(edge, L)) for L in (2,3,4)]
    ok = [L for L,f in levels if f >= q_target and f <= Q_cap[edge]]
    return min(ok) if ok else max(L for L,_ in levels)   # else fully open + flag deficit
```

---

## 5. Wiring & sequence

```
ROS section demand ──section_node_map──▶ node_demand[n]
        │
        ▼
required_flow_per_reach (§2, connected graph + B5 uplift)
        │  capacity_violations? ──▶ defer to rotation
        ▼
schedule_rotation (§3, capacity + concurrency + travel-time)
        │  per time-block:
        ▼
reach_targets_at(t) ──▶ set_gates_for_targets (§4, corrected inverse)
        │                        │ solve_network verifies split
        ▼                        ▼
quantize_to_level ──▶ SCADA command-level {1..4}   (bridge that today is missing)
```

Replace `_get_canal_capacity()`'s hardcoded `15.0` with `design_discharge` lookup.

---

## 6. Acceptance tests

- **B5**: earth reach at design flow returns non-zero seepage; head-gate flow >
  Σ(field demand) by the summed reach losses; tail FTO receives its full demand.
- **A1/A4**: every delivery node with `area>0` contributes; interior-node demand
  is included; no node returns an empty path.
- **B7**: for demand set exceeding LMC `design_discharge`, aggregation flags it and
  the scheduler never co-activates beyond capacity on any reach (assert per-instant
  `Σq ≤ Q_cap`).
- **B6**: reach target at time t equals Σ of *only* the windows active at t.
- **B8**: `solve_network` on a known bifurcation reproduces the analytical split
  within tolerance; `set_gates_for_targets` drives each branch to its target ± ε.
- **Discrete**: quantizer never selects a level exceeding `Q_cap`; deficits are flagged.
- **Topology precondition**: solver refuses to run unless the loaded graph is a single
  connected component reaching all 59 nodes from `S`.
