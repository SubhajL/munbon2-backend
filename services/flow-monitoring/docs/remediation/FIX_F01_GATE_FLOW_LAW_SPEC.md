# Fix Spec — F-01: Gate flow law blows up to ~287 m³/s

Focused remediation for the inverted gate-flow / required-opening computation.
Repo target: `services/flow-monitoring/src/services/hydraulic_service.py`
(`_calculate_required_opening`) and the flow model it calls. Consolidates the flow
law into one correct implementation and retires the divergent copies.

---

## 1. The defect — three stacked bugs, not one

Reproduced for gate **M(0,0)** (K1=1.0693, K2=−1.229): computed flow **rises as the gate
closes** and hits **287 m³/s at 10 % open** for a gate rated ~11 m³/s.

Wired code (`hydraulic_service._calculate_required_opening`):
```python
Cs = calibration.k1 * (opening ** calibration.k2)     # BUG 1 + BUG 3
calculated_flow = Cs * base_coeff
base_coeff = gate_width * upstream_depth * sqrt(2*9.81*head_diff)  # BUG 2: 2.0, 0.2 hardcoded
# no Cs clamp                                          # BUG 4
```

| # | Bug | Effect |
|---|---|---|
| **B1** | `opening` is a 0–1 **fraction** in `opening^K2`; the correct law has **`(Hs/Go)`** with the opening in the **denominator** (Go in metres) | direction inverts — flow ↓ as gate opens |
| **B2** | `upstream_depth=2.0`, `head_diff=0.2` **hardcoded** for every gate | ignores real hydraulics |
| **B3** | `Hs` taken as an **absolute level** in the sibling `calibrated_gate_flow` (e.g. 219 m MSL) | dimensional blow-up (219 “m” of head) |
| **B4** | **no `Cs` clamp** (physical range ≈ 0.3–1.0) | `Cs=18.1` → 287 m³/s |

The correct RID rating (already used in structure — but with fake K1/K2 — by
`calibrated_gate_flow.py`) is:

```
Q  = Cs · L · Hs · √(2g·ΔH)
Cs = K1 · (Hs / Go)^K2          (clamped to [Cs_min, Cs_max])
```

Fixing F-01 = combine the **correct structure** (from `calibrated_gate_flow`) with the
**real K1/K2** (from `gate_calibration_loader`) + **head-over-sill semantics** + **real
levels** + a **capacity ceiling**.

---

## 2. Corrected model — definitions & units (all lengths in metres)

| Symbol | Meaning | Source |
|---|---|---|
| `sill` | gate sill elevation (m MSL) | node/gate config |
| `Hu` | upstream head over sill = `upstream_level − sill` (≥0) | real level (sensor/solved) |
| `Hd` | downstream head over sill = `downstream_level − sill` (≥0) | real level |
| `ΔH` | driving head = `Hu − Hd` (>0 required) | derived |
| `Hs` | rating head over sill — **`Hd` for submerged, `Hu` for free** (a depth, NOT an MSL elevation) | derived |
| `Go` | gate opening in **metres** ∈ `[min_opening, max_opening]` (NOT a fraction) | control var |
| `L` | gate width (m) | calibration |
| `K1,K2` | rating coefficients; `confidence` | `gate_calibrations.json` |
| `q_max` | physical gate capacity (m³/s) | network node |

Regime: submergence `σ = Hd / Hu`. `σ ≥ 0.8` → submerged (use `Hs=Hd`, `ΔH=Hu−Hd`);
`σ < 0.8` → free flow (`Hs=Hu`, `ΔH=Hu`). The K1/K2 rating is applied in both; a free-flow
gate with the classic orifice form may be used as a cross-check.

Sanity with real numbers (M(0,0), Hs=1.5 m, ΔH=0.2 m, L=4 m, clamp [0.3,1]):
`Go=0.2 → Q≈3.6`, `Go=1.0 → Q≈7.7`, `Go=2.0 → Q≈11.9` — monotonic ↑, capped near q_max. ✓

---

## 3. Reference implementation (single source of truth)

New module `core/gate_flow.py` — the **only** gate-flow law in the service.

```python
import math
G = 9.81
CS_MIN, CS_MAX = 0.30, 1.00
SUBMERGED_THRESHOLD = 0.80

class GateFlowError(ValueError): ...

def _heads(upstream_level, downstream_level, sill):
    Hu = upstream_level - sill
    Hd = downstream_level - sill
    return Hu, Hd

def discharge_coeff(K1, K2, Hs, Go):
    """Cs = K1·(Hs/Go)^K2, Go in metres, clamped to physical range."""
    if Go <= 0 or Hs <= 0:
        return CS_MIN
    Cs = K1 * (Hs / Go) ** K2
    return max(CS_MIN, min(CS_MAX, Cs))          # BUG 4 fix

def gate_flow_m3s(cal, upstream_level, downstream_level, Go):
    """Forward: flow through a gate at opening Go (metres). Correct + guarded."""
    Hu, Hd = _heads(upstream_level, downstream_level, cal.sill)
    if Hu <= 0:                    # no water above sill
        return 0.0
    dH = Hu - Hd
    if dH <= 1e-4:                 # no driving head → no (forward) flow
        return 0.0
    Go = min(max(Go, 0.0), cal.max_opening)
    if Go <= 0:
        return 0.0
    submerged = (Hd / Hu) >= SUBMERGED_THRESHOLD if Hu > 0 else False
    Hs = Hd if submerged else Hu   # BUG 3 fix: head OVER SILL, never absolute MSL
    if Hs <= 0:
        Hs = Hu
    Cs = discharge_coeff(cal.K1, cal.K2, Hs, Go)      # BUG 1 fix: Hs/Go, Go in metres
    q  = Cs * cal.width * Hs * math.sqrt(2 * G * dH)
    return min(q, cal.q_max)       # capacity ceiling — final blow-up guard
```

### 3.1 Inverse — required opening (safeguarded Newton + bisection fallback)

```python
def required_opening_m(cal, upstream_level, downstream_level, q_target, tol=1e-3):
    """Opening (metres) to pass q_target, on REAL levels. Monotone ⇒ bracket+bisect safe."""
    Hu, _ = _heads(upstream_level, downstream_level, cal.sill)
    if Hu <= 0 or q_target <= 0:
        return 0.0
    lo, hi = cal.min_opening, cal.max_opening
    q_hi = gate_flow_m3s(cal, upstream_level, downstream_level, hi)
    if q_target >= q_hi:                       # target exceeds capacity at this head
        return hi, {"feasible": False, "achievable": q_hi,
                    "reason": "exceeds gate capacity at current head"}
    # monotone increasing in Go ⇒ bisection is unconditionally convergent
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        q = gate_flow_m3s(cal, upstream_level, downstream_level, mid)
        if abs(q - q_target) < tol:
            break
        lo, hi = (mid, hi) if q < q_target else (lo, mid)
    return mid, {"feasible": True, "achievable": q,
                 "confidence": cal.confidence,          # 0.95 field / 0.80 default / 0.60 generic
                 "within_calibration": cal.range_min <= (max(Hu,1e-9)/max(mid,1e-9)) <= cal.range_max}
```

Notes:
- **Bisection, not raw Newton** — the forward law is monotone in `Go`, so bisection can’t
  diverge or oscillate (the old ±30 %/Newton loop could). Keep Newton only as an inner
  accelerator with a bisection guard if speed matters.
- **Real levels** are arguments — the hardcoded `2.0/0.2` are gone (BUG 2 fix).
- **Feasibility** returned explicitly instead of silently clipping.

---

## 4. Invariants (must hold — enforced by tests §6)

1. **Monotonicity:** `gate_flow_m3s` is strictly increasing in `Go` on `(0, max_opening]` when `ΔH>0`. *(Fails on today's code.)*
2. **Capacity ceiling:** `gate_flow_m3s(...) ≤ q_max` for all inputs. *(Kills the 287 case.)*
3. **Cs bound:** `CS_MIN ≤ Cs ≤ CS_MAX` always.
4. **Dimensional:** `Hs, ΔH` are heads-over-sill in `[0, ~5] m`, never MSL elevations.
5. **Round-trip:** `gate_flow_m3s(cal, U, D, required_opening_m(cal,U,D,q)) ≈ q` (within tol) for feasible `q`.
6. **Dry / no-head:** `Hu≤0` or `ΔH≤0` ⇒ flow 0, no exception, no NaN.

---

## 5. Consolidation (ties to C10)

`core/gate_flow.py` becomes the sole flow law. **Delete / redirect:**
- `hydraulic_service._calculate_required_opening` → call `required_opening_m`.
- `calibrated_gate_flow.py` (fake K1/K2 + MSL `Hs`) → remove; callers use `core/gate_flow`.
- `gate_opening_calculator.py` (Cd=0.61 analytic) → remove.
- `_get_saint_venant_results` / `_get_manning_results` hardcoded façades → remove or back
  with real results.
- `gate_hydraulics.calculate_*_flow` (classic `Cd·b·a·√2gh`) → keep only if used by
  `hydraulic_solver.solve_network` as the forward engine; otherwise migrate it to call
  `core/gate_flow` so there is exactly one law. Calibration loads from
  `gate_calibrations.json` (real K1/K2; 10/59 field, rest size-default with lower confidence).

---

## 6. Test matrix (`core/gate_flow.spec` — property + regression)

| Test | Assertion |
|---|---|
| **Regression: the 287 case** | `gate_flow_m3s(M00, U, D, Go=0.10·max)` ≤ `q_max` (was 287) |
| **Direction** | `q(Go=0.2) < q(Go=1.0) < q(Go=2.0)` (strictly increasing) |
| **Property (fast-check)** | ∀ Go∈(0,max], ΔH>0: `q(Go+δ) ≥ q(Go)` |
| **Cs clamp** | ∀ inputs: `0.3 ≤ Cs ≤ 1.0` |
| **Round-trip** | `q(required_opening_m(q★)) ≈ q★` for feasible `q★` |
| **Capacity** | target > capacity ⇒ `feasible=False`, opening=max, achievable=q_hi |
| **Dimensional** | levels given as MSL (e.g. 219/218.8, sill 218) ⇒ Hs≈0.8 m, finite Q, no blow-up |
| **Dry** | `upstream_level < sill` ⇒ 0.0 |
| **No head** | `ΔH ≤ 0` ⇒ 0.0 |
| **Confidence surfaced** | field gate ⇒ 0.95; size-default ⇒ 0.80; generic ⇒ 0.60 (never asserted as validated CI) |

The first two tests **fail on the current code** and pass after the fix — they are the
guard against regression.

---

## 7. Rollout

- **P0:** land `core/gate_flow.py` + tests; repoint `hydraulic_service` and the
  controller to it; delete the fake/stub variants. Pure code, no hardware.
- **P1:** feed **real** upstream/downstream levels from sensor state or
  `hydraulic_solver` output (not constants); add the calibration-range warning to logs.
- **P2:** expand field calibration beyond 10/59 gates; recompute confidence from fit
  residuals rather than the fixed 0.95/0.80 labels.

**Dependency:** every downstream fix (aggregation → rotation → inverse → SCADA command)
consumes this law. F-01 is the first thing to land — a correct pipeline on an inverted
gate equation still emits wrong commands.
