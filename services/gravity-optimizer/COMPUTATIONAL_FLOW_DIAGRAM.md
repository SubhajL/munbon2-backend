# Gravity Optimizer - Computational Flow Diagram

## Process Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INPUT LAYER                                  │
├─────────────────────┬─────────────────────┬────────────────────────┤
│   Sensor Data       │   User Requests     │   System State         │
│  - Water levels     │  - Delivery needs   │  - Gate positions      │
│  - Flow rates       │  - Priorities       │  - Canal conditions    │
│  - Gate sensors     │  - Volumes          │  - Maintenance status  │
└──────────┬──────────┴──────────┬──────────┴──────────┬─────────────┘
           │                     │                      │
           ▼                     ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DATA VALIDATION & PREPROCESSING                   │
│  • Sensor data filtering      • Request validation                  │
│  • Outlier detection          • Priority assignment                 │
│  • Missing data interpolation • Constraint checking                 │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FEASIBILITY ANALYSIS ENGINE                     │
├─────────────────────────────────┴───────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐    ┌──────────────────┐    ┌───────────────┐ │
│  │ Elevation Check  │    │  Depth Analysis  │    │ Path Finding  │ │
│  │                  │    │                  │    │               │ │
│  │ Δh = z₁ - z₂    │    │  y = f(Q,b,m,S) │    │ Dijkstra/A*  │ │
│  │ hf = L×Sf       │    │  y ≥ yₘᵢₙ       │    │ Graph search │ │
│  │ Feasible if:    │    │  Manning iter.   │    │ Blockage     │ │
│  │ Δh > Σ losses   │    │  Check all segs  │    │ avoidance    │ │
│  └──────────────────┘    └──────────────────┘    └───────────────┘ │
│           │                       │                       │          │
│           └───────────────────────┴───────────────────────┘          │
│                                   │                                  │
│                                   ▼                                  │
│                          ┌─────────────────┐                        │
│                          │ Feasibility     │                        │
│                          │ Decision Matrix │                        │
│                          └─────────────────┘                        │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
         ┌──────────────────┐         ┌──────────────────┐
         │    FEASIBLE      │         │   INFEASIBLE     │
         │  Continue to     │         │  Generate        │
         │  Optimization    │         │  Alternatives    │
         └────────┬─────────┘         └────────┬─────────┘
                  │                            │
                  ▼                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    HYDRAULIC COMPUTATION CORE                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  Manning's Equation Solver                   │   │
│  │                                                              │   │
│  │  Normal Depth:  Q = (1/n)×A×R^(2/3)×S^(1/2)                │   │
│  │                                                              │   │
│  │  Newton-Raphson Iteration:                                   │   │
│  │  yₙ₊₁ = yₙ - f(yₙ)/f'(yₙ)                                  │   │
│  │                                                              │   │
│  │  Where: f(y) = Q - (1/n)×A(y)×R(y)^(2/3)×S^(1/2)          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Gate Flow Calculator                      │   │
│  │                                                              │   │
│  │  Free Flow:    Q = Cd×w×a×√(2gh)                           │   │
│  │  Submerged:    Q = Cd×w×a×√(2gh)×√(1-σ)                    │   │
│  │                                                              │   │
│  │  Where: σ = (h₂-a)/(h₁-a) = submergence ratio             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Energy & HGL Calculator                         │   │
│  │                                                              │   │
│  │  Total Energy:  E = z + y + V²/2g                           │   │
│  │  HGL:           H = z + y                                   │   │
│  │  Specific Energy: Es = y + V²/2g                            │   │
│  │  Froude Number: Fr = V/√(gy)                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      OPTIMIZATION ENGINE                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Multi-Objective Function Formulation             │   │
│  │                                                              │   │
│  │  minimize: f(x) = w₁×Σ(head_loss) +                         │   │
│  │                   w₂×Σ|Qᵢ - Q_target| +                     │   │
│  │                   w₃×Σ|xᵢ - x_current|                      │   │
│  │                                                              │   │
│  │  subject to:                                                 │   │
│  │    - Flow conservation: Σ(Qᵢₙ) = Σ(Qₒᵤₜ)                   │   │
│  │    - Capacity: 0 ≤ Q ≤ Qₘₐₓ                                │   │
│  │    - Depth: y ≥ yₘᵢₙ                                        │   │
│  │    - Velocity: vₘᵢₙ ≤ v ≤ vₘₐₓ                             │   │
│  │    - Gate limits: 0 ≤ a ≤ aₘₐₓ                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    SLSQP Solver                              │   │
│  │                                                              │   │
│  │  Sequential Least Squares Programming:                      │   │
│  │  - Quadratic approximation of objective                     │   │
│  │  - Linear approximation of constraints                      │   │
│  │  - Trust region updates                                      │   │
│  │  - Convergence: |f(xₖ₊₁) - f(xₖ)| < ε                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ADVANCED ANALYTICS LAYER                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐    ┌──────────────────┐    ┌───────────────┐ │
│  │ Travel Time      │    │ Sequencing       │    │ Energy        │ │
│  │ Predictor        │    │ Optimizer        │    │ Recovery      │ │
│  │                  │    │                  │    │               │ │
│  │ t = Σ(L/V)      │    │ Multi-criteria   │    │ P = ρgQH      │ │
│  │ V = Q/A         │    │ scoring          │    │ η = 0.85      │ │
│  │ Condition       │    │ 2-opt search     │    │ ROI analysis  │ │
│  │ factors         │    │ Residence time   │    │ Site ranking  │ │
│  └──────────────────┘    └──────────────────┘    └───────────────┘ │
│           │                       │                       │          │
│  ┌────────┴───────────────────────┴───────────────────────┴──────┐  │
│  │                    Integrated Decision Matrix                  │  │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      CONTINGENCY PLANNING                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Network Graph Construction                      │   │
│  │                                                              │   │
│  │  G = (V, E) where:                                          │   │
│  │  V = {nodes: junctions, zones}                              │   │
│  │  E = {edges: canals with (capacity, length)}                │   │
│  │                                                              │   │
│  │  Apply blockages: Remove/reduce edge capacities             │   │
│  │  Add emergency connections when needed                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │           Alternative Path Finding (Modified Dijkstra)       │   │
│  │                                                              │   │
│  │  For each path p:                                            │   │
│  │    capacity(p) = min(edge_capacities)                       │   │
│  │    feasibility(p) = f(capacity, elevation, efficiency)      │   │
│  │    rank paths by feasibility score                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         OUTPUT GENERATION                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  • Optimal gate settings (openings, flows)                          │
│  • Energy profiles (HGL, EGL for all paths)                         │
│  • Delivery schedule (sequence, timing)                             │
│  • Travel time predictions                                          │
│  • Micro-hydro opportunities                                        │
│  • Contingency routes                                               │
│  • Performance metrics                                              │
│                                                                      │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      INTEGRATION & DISPATCH                          │
├─────────────────────┬─────────────────────┬────────────────────────┤
│   To Core Monitor   │   To Scheduler      │   To Field Teams       │
│  - Gate commands    │  - Feasible windows │  - Manual gate ops     │
│  - Flow targets     │  - Travel times     │  - Route changes       │
│  - Alert triggers   │  - Sequences        │  - Emergency actions   │
└─────────────────────┴─────────────────────┴────────────────────────┘
```

## Computational Complexity Analysis

### 1. Feasibility Check: O(n)
- n = number of canal segments
- Linear scan through path

### 2. Manning's Iteration: O(k)
- k = iterations (typically 10-50)
- Converges quadratically

### 3. Optimization: O(m² × n)
- m = number of gates
- n = number of constraints
- SLSQP complexity

### 4. Path Finding: O(V log V + E)
- V = nodes, E = edges
- Dijkstra's algorithm

### 5. Sequencing: O(z! / (z-k)!)
- z = zones, k = selections
- Reduced by heuristics

## Real-Time Performance Targets

| Operation | Target Time | Actual (Typical) |
|-----------|------------|------------------|
| Feasibility Check | < 50ms | 20-30ms |
| Full Optimization | < 500ms | 200-400ms |
| Travel Time Calc | < 100ms | 50-80ms |
| Contingency Route | < 200ms | 100-150ms |
| Energy Analysis | < 150ms | 80-120ms |

## Data Volume Estimates

| Data Type | Volume/Day | Storage |
|-----------|------------|---------|
| Sensor Readings | 1.7M records | 200 MB |
| Gate Operations | 10K records | 5 MB |
| Optimization Runs | 288 runs | 50 MB |
| Travel Predictions | 5K calculations | 10 MB |
| Energy Analyses | 100 assessments | 2 MB |