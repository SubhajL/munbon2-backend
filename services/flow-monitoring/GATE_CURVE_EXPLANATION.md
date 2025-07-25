# Detailed Explanation of Gate Performance Curves

## The Physics Behind the Curves

The gate performance curves show how flow rate changes with gate opening percentage. These curves are **NOT linear** because of the fundamental hydraulic equation for flow through gates.

## 1. Basic Sluice Gate Equation

For a sluice gate (vertical lift gate), the flow is calculated using:

```
Q = Cd × b × a × √(2g × h)
```

Where:
- **Q** = Flow rate (m³/s)
- **Cd** = Discharge coefficient (0.61 for sluice gates)
- **b** = Gate width (m)
- **a** = Gate opening height (m)
- **g** = Gravity (9.81 m/s²)
- **h** = Effective head (m)

## 2. Why the Curve Shape?

The key insight is that **Q is proportional to 'a' (gate opening)** but also depends on **√h**.

### For Free Flow:
- Flow increases linearly with gate opening
- The curve would be nearly straight

### For Submerged Flow (Most Common):
In your screenshot, all gates show "submerged flow", which means the downstream water level affects the flow. This introduces a **reduction factor**:

```
Reduction Factor = √(1 - (h₂/h₁)²)
```

Where:
- h₁ = upstream water depth
- h₂ = downstream water depth

## 3. Step-by-Step Calculation Example

Let's trace through the Main Outlet calculation:

### Given:
- Gate width (b) = 2.5 m
- Gate height = 1.5 m
- Max opening = 1.2 m (80% of height)
- Upstream level = 221 m
- Downstream level = 219 m
- Sill elevation = 0 m (assumed)

### At 25% Opening:
```
a = 0.25 × 1.2 = 0.3 m
h₁ = 221 - 0 = 221 m
h₂ = 219 - 0 = 219 m
Submergence ratio = 219/221 = 0.991

Reduction factor = √(1 - 0.991²) = √(1 - 0.982) = √0.018 = 0.134

Q = 0.61 × 2.5 × 0.3 × √(2 × 9.81 × 221) × 0.134
Q = 0.61 × 2.5 × 0.3 × 65.88 × 0.134
Q = 0.61 × 2.5 × 0.3 × 8.83
Q = 4.04 m³/s
```

### At 50% Opening:
```
a = 0.50 × 1.2 = 0.6 m
Q = 0.61 × 2.5 × 0.6 × 65.88 × 0.134
Q = 8.08 m³/s (doubles because 'a' doubles)
```

## 4. Why Nearly Linear in Your Case?

In your screenshot, the curves appear nearly linear because:

1. **High Submergence**: With upstream at 221m and downstream at 219m, the submergence ratio is very high (0.991)
2. **Constant Reduction**: The reduction factor stays nearly constant across all openings
3. **Same Water Levels**: All calculations use the same upstream/downstream levels

This makes Q primarily dependent on 'a' (gate opening), creating nearly linear curves.

## 5. When Curves Become Non-Linear

The curves would show more curvature if:

### A. Variable Head Conditions
If water levels changed with flow:
- Higher flows → Lower upstream level (drawdown)
- Higher flows → Higher downstream level (backwater)

### B. Flow Regime Changes
Transitioning between:
- Free flow (low downstream level)
- Submerged flow (high downstream level)
- Weir flow (gate fully open)

### C. Gate Geometry Effects
For butterfly valves, the area change is non-linear:
```python
# From the code:
if theta < 0.1:  # Nearly closed
    area_factor = 0.05 * (theta / 0.1)
elif theta < np.pi / 4:  # 0-45 degrees
    area_factor = np.sin(2 * theta) * 0.7
else:  # 45-90 degrees
    area_factor = 0.7 + 0.3 * (theta - np.pi/4) / (np.pi/4)
```

## 6. Real-World Validation

These curves match real gate behavior:
- **Linear portion**: Common in submerged flow with constant levels
- **Flattening at high openings**: Would occur if velocity limits are reached
- **Consistent velocities**: The 3.29 m/s shown is realistic for 2m head difference

## 7. Code Implementation

From `visualize_gate_hydraulics.py`:
```python
# Test different openings
openings = [25, 50, 75, 100]

for opening_pct in openings:
    result = controller.open_gate_realistic(
        gate_id, opening_pct,
        upstream_level=levels['upstream'],
        downstream_level=levels['downstream']
    )
```

Each point on the curve is calculated using:
1. Convert percentage to actual opening (m)
2. Apply discharge coefficient and contraction
3. Calculate flow based on hydraulic conditions
4. Apply reduction for submerged flow

## Summary

The nearly linear curves in your screenshot are correct for:
- Constant water levels (221m upstream, 219m downstream)
- High submergence conditions (98% submerged)
- Sluice gates with linear opening-to-area relationship

In reality, these curves would show more curvature if water levels varied with flow or if gates transitioned between flow regimes. The implementation correctly captures the hydraulic physics, but the specific conditions in this test create nearly linear relationships.