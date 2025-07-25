# Gravity Flow Optimization - Detailed Example

## Scenario: Multi-Zone Water Delivery Request

### Initial Conditions
```yaml
Time: 06:00 AM
Date: 2024-01-15
Season: Dry season
Weather: Clear, no rain expected

Water Levels:
  Source: 221.45 m MSL (reservoir nearly full)
  M(0,0): 219.10 m (main junction)
  All zones: Currently not receiving water

Gate Status:
  All gates: Closed
  Type: 20 automated gates available
```

### Delivery Request
```json
{
  "request_id": "REQ-2024-0115-001",
  "timestamp": "2024-01-15T06:00:00Z",
  "deliveries": [
    {
      "zone": "Zone_2",
      "section": "Zone_2_Section_A",
      "volume_m3": 75000,
      "crop": "rice",
      "stage": "flowering",
      "priority": 9,
      "deadline": "2024-01-15T18:00:00Z"
    },
    {
      "zone": "Zone_5", 
      "section": "Zone_5_Section_B",
      "volume_m3": 50000,
      "crop": "sugarcane",
      "stage": "tillering",
      "priority": 7,
      "deadline": "2024-01-16T06:00:00Z"
    },
    {
      "zone": "Zone_3",
      "section": "Zone_3_Section_C",
      "volume_m3": 30000,
      "crop": "vegetables",
      "stage": "vegetative",
      "priority": 6,
      "deadline": "2024-01-15T12:00:00Z"
    }
  ]
}
```

## Step-by-Step Optimization Process

### Step 1: Feasibility Analysis

#### 1.1 Elevation Check
```
Zone_2 (217.5m):
  Available head = 221.0 - 217.5 = 3.5m
  Path: Source → M(0,0) → M(0,2) → Zone_2
  Total length: 500 + 1200 + 800 = 2500m
  
  Friction losses:
    - Source→M(0,0): 500m × 0.0002 = 0.10m
    - M(0,0)→M(0,2): 1200m × 0.0001 = 0.12m
    - M(0,2)→Zone_2: 800m × 0.00015 = 0.12m
    Total friction: 0.34m
  
  Minor losses (10%): 0.034m
  Gate losses (3 gates): 0.30m
  Minimum depth required: 0.30m
  
  Total required head: 0.974m < 3.5m ✓ FEASIBLE

Zone_5 (215.5m):
  Available head = 221.0 - 215.5 = 5.5m
  Required head: 1.2m < 5.5m ✓ FEASIBLE

Zone_3 (217.0m):
  Available head = 221.0 - 217.0 = 4.0m
  Required head: 1.1m < 4.0m ✓ FEASIBLE
```

#### 1.2 Flow Requirements
```
Zone_2: Q = 75000 m³ / 12 hours = 1.74 m³/s
Zone_5: Q = 50000 m³ / 24 hours = 0.58 m³/s  
Zone_3: Q = 30000 m³ / 6 hours = 1.39 m³/s

Total peak flow needed: 3.71 m³/s (if all simultaneous)
Source capacity: 10 m³/s ✓ ADEQUATE
```

### Step 2: Sequencing Optimization

#### 2.1 Multi-Criteria Scoring
```
Zone_3 (urgent vegetables):
  Priority score: 6/10 = 0.60
  Elevation score: 217.0/221.0 = 0.98
  Urgency score: 1/(1 + 6/24) = 0.80
  Volume score: 30000/100000 = 0.30
  Total: 0.4×0.60 + 0.3×0.98 + 0.2×0.80 + 0.1×0.30 = 0.724

Zone_2 (critical rice):
  Priority score: 9/10 = 0.90
  Elevation score: 217.5/221.0 = 0.98
  Urgency score: 1/(1 + 12/24) = 0.67
  Volume score: 75000/100000 = 0.75
  Total: 0.4×0.90 + 0.3×0.98 + 0.2×0.67 + 0.1×0.75 = 0.863

Zone_5 (sugarcane):
  Priority score: 7/10 = 0.70
  Elevation score: 215.5/221.0 = 0.98
  Urgency score: 1/(1 + 24/24) = 0.50
  Volume score: 50000/100000 = 0.50
  Total: 0.4×0.70 + 0.3×0.98 + 0.2×0.50 + 0.1×0.50 = 0.724
```

#### 2.2 Optimized Sequence
```
1. Zone_3 (06:00-08:10) - Most urgent
2. Zone_2 (08:30-20:30) - Highest priority  
3. Zone_5 (next day) - Flexible deadline
```

### Step 3: Hydraulic Calculations

#### 3.1 Zone_3 Delivery (First)
```python
# Required flow: 1.39 m³/s
# Canal: M(0,0)→M(0,3), b=3.5m, m=1.5, n=0.025, S=0.00015

# Calculate normal depth (iterative)
Initial guess: y = 1.0m
Iteration 1:
  A = 1.0 × (3.5 + 1.5×1.0) = 5.0 m²
  P = 3.5 + 2×1.0×√(1+1.5²) = 7.11 m
  R = 5.0/7.11 = 0.703 m
  Q_calc = (1/0.025) × 5.0 × 0.703^(2/3) × 0.00015^0.5 = 1.52 m³/s
  Error = 1.52 - 1.39 = 0.13

Converged after 8 iterations: y = 0.94m

# Gate opening calculation
Upstream head: h = 219.1 - 218.0 = 1.1m
Q = 0.61 × 3.5 × a × √(2×9.81×1.1)
1.39 = 0.61 × 3.5 × a × 4.65
a = 0.14m (gate opening)
```

#### 3.2 Zone_2 Delivery (Second)
```python
# Required flow: 1.74 m³/s
# Normal depth: y = 1.08m
# Gate opening: a = 0.17m
# Velocity: V = 1.74/5.8 = 0.30 m/s
# Froude number: Fr = 0.30/√(9.81×1.08) = 0.092 (subcritical)
```

### Step 4: Travel Time Prediction

#### 4.1 Water Front Progression
```
Zone_3 Path (dry startup):
  Segment 1: Source→M(0,0)
    Length: 500m
    Fill volume: 500 × 5.0 × 0.5 = 1250 m³
    Fill time: 1250/1.39 = 899s = 15 min
    Travel time: 500/1.2 = 417s = 7 min
    Total: 22 min

  Segment 2: M(0,0)→M(0,3)
    Length: 1500m
    Fill + travel: 45 min

  Segment 3: M(0,3)→Zone_3
    Length: 1000m
    Fill + travel: 30 min

  Total arrival time: 97 min ≈ 1.6 hours
  Water arrives at Zone_3: 07:36 AM
```

### Step 5: Energy Profile Calculation

#### 5.1 Hydraulic Grade Line (Zone_2 Path)
```
Location         Elevation  Depth   HGL      Velocity  EGL
Source           221.00     0.50    221.50   0.00      221.50
After gate 1     220.90     1.20    222.10   1.50      222.21
M(0,0)           220.90     1.10    222.00   1.40      222.10
After gate 2     220.70     1.05    221.75   1.35      221.84
M(0,2)           220.70     1.00    221.70   1.30      221.79
After gate 3     220.50     0.95    221.45   1.25      221.53
Zone_2           220.50     0.90    221.40   1.20      221.47

Total head loss: 221.50 - 221.47 = 0.03m (very efficient)
```

### Step 6: Optimization Results

#### 6.1 Optimal Gate Settings
```json
{
  "06:00": {
    "Source->M(0,0)": {"opening": 0.15, "flow": 1.39},
    "M(0,0)->M(0,3)": {"opening": 0.14, "flow": 1.39},
    "M(0,3)->Zone_3": {"opening": 0.13, "flow": 1.39}
  },
  "08:30": {
    "Source->M(0,0)": {"opening": 0.18, "flow": 1.74},
    "M(0,0)->M(0,2)": {"opening": 0.17, "flow": 1.74},
    "M(0,2)->Zone_2": {"opening": 0.16, "flow": 1.74},
    "M(0,0)->M(0,3)": {"opening": 0.00, "flow": 0.00}
  }
}
```

#### 6.2 Energy Recovery Potential
```
Gate: M(0,0)->M(0,2)
  Head difference: 0.25m
  Average flow: 1.74 m³/s
  Operating hours: 12 hours/day × 300 days = 3600 hours
  
  Power potential: 1000 × 9.81 × 1.74 × 0.25 = 4.27 kW
  Actual power: 4.27 × 0.85 × 0.95 = 3.45 kW
  Annual energy: 3.45 × 3600 = 12.4 MWh
  CO₂ reduction: 12.4 × 0.5 = 6.2 tons/year
  
  Economics:
    Revenue: 12,400 kWh × 4.5 THB = 55,800 THB/year
    Investment: 3.45 kW × 80,000 THB/kW = 276,000 THB
    Simple payback: 5.2 years
```

### Step 7: Contingency Planning

#### 7.1 Blockage Scenario
```
Event: Gate M(0,0)->M(0,2) fails at 10:00 AM
Impact: Zone_2 delivery interrupted

Alternative Route Analysis:
  Option 1: Via Zone_3 cross-connection
    Path: M(0,0) → M(0,3) → Zone_3 → Zone_2
    Extra distance: 800m
    Capacity: 1.5 m³/s (limited by cross-connection)
    Feasibility: 0.75 (viable)

  Option 2: Via Zone_1
    Path: M(0,0) → M(0,1) → Zone_1 → Zone_2  
    Extra distance: 1200m
    Capacity: 2.0 m³/s
    Feasibility: 0.82 (better option)

Emergency Protocol:
  1. Open cross-connection gate Zone_1→Zone_2
  2. Adjust M(0,0)→M(0,1) to 0.20m opening
  3. Notify Zone_2 farmers of 30-min delay
  4. Dispatch repair team to failed gate
```

### Step 8: Performance Metrics

#### 8.1 Delivery Efficiency
```
Zone_3:
  Requested: 30,000 m³
  Delivered: 30,000 m³
  Transit losses: 420 m³ (1.4%)
  Efficiency: 98.6%

Zone_2:
  Requested: 75,000 m³
  Delivered: 75,000 m³
  Transit losses: 1,050 m³ (1.4%)
  Efficiency: 98.6%

Overall Network Efficiency: 98.6%
Water saved vs pumping: 100% (gravity only)
Energy saved: 45 MWh (equivalent pumping energy)
```

#### 8.2 Optimization Performance
```
Computation time: 287 ms
Iterations: 156
Convergence error: 0.0008
Gates optimized: 6
Constraints satisfied: All
Solution quality: Optimal (within 0.1%)
```

## Summary

This example demonstrates how the Gravity Flow Optimizer:

1. **Validates feasibility** using elevation and hydraulic constraints
2. **Sequences deliveries** based on multi-criteria optimization
3. **Calculates precise gate settings** using hydraulic equations
4. **Predicts travel times** accounting for dry channel startup
5. **Identifies energy recovery** opportunities
6. **Plans contingencies** for system failures
7. **Maximizes efficiency** using only gravity

The system achieved 98.6% delivery efficiency while saving 45 MWh of pumping energy and identifying 12.4 MWh/year of micro-hydro potential.