# Gravity Flow Optimizer - End-to-End Data Flow

## Overview
The Gravity Flow Optimizer ensures water delivery using only gravity (no pumps), optimizing gate operations to maximize reach while minimizing losses. This document details the complete data flow from input requests to optimized delivery plans.

## 1. Input Data Sources

### 1.1 Real-Time Data Inputs
```json
{
  "current_water_levels": {
    "Source": 221.5,      // m MSL
    "M(0,0)": 219.2,
    "M(0,2)": 218.9
  },
  "current_gate_states": {
    "Source->M(0,0)": {
      "opening_m": 1.5,
      "flow_m3s": 4.2,
      "type": "automated"
    }
  },
  "canal_conditions": {
    "M(0,0)->M(0,2)": {
      "sediment_level": "moderate",
      "last_maintenance": "2024-12-01"
    }
  }
}
```

### 1.2 Delivery Requirements
```json
{
  "target_deliveries": [
    {
      "section_id": "Zone_2_Section_A",
      "zone": 2,
      "required_flow_m3s": 2.5,
      "required_volume_m3": 50000,
      "target_elevation_m": 217.5,
      "priority": "high",
      "crop_type": "rice",
      "growth_stage": "flowering"
    }
  ]
}
```

### 1.3 Network Topology
- Canal geometry (PostGIS)
- Node elevations
- Gate characteristics
- Cross-connections

## 2. Core Processing Pipeline

### 2.1 Feasibility Analysis

#### Step 1: Elevation Feasibility Check
```python
# Calculate available head
available_head = source_elevation - target_elevation
# available_head = 221.0 - 217.5 = 3.5m

# Calculate required head
friction_losses = Σ(L × S_f)  # Manning's equation
minor_losses = 0.1 × friction_losses
gate_losses = n_gates × 0.1m
required_head = friction_losses + minor_losses + gate_losses + min_depth

# Decision
feasible = available_head >= required_head
```

**Computation Example:**
- Canal length: 2000m
- Friction slope (S_f): 0.0002
- Friction loss: 2000 × 0.0002 = 0.4m
- Minor losses: 0.1 × 0.4 = 0.04m
- Gate losses (3 gates): 3 × 0.1 = 0.3m
- Minimum depth: 0.3m
- Total required: 1.04m < 3.5m ✓ FEASIBLE

#### Step 2: Minimum Depth Verification
```python
# For each canal segment
Q = A × V  # Continuity equation
A = y(b + my)  # Trapezoidal area
y = solve_for_depth(Q, b, m)  # Iterative solution

# Check constraint
depth_ok = y >= min_depth_m (0.3m)
```

### 2.2 Hydraulic Calculations

#### Manning's Equation Implementation
```python
# Normal depth calculation (iterative)
def calculate_normal_depth(Q, b, m, S, n):
    # Q = (1/n) × A × R^(2/3) × S^(1/2)
    # Solve iteratively using Newton-Raphson
    
    y = 1.0  # Initial guess
    for iteration in range(100):
        A = y * (b + m * y)
        P = b + 2 * y * sqrt(1 + m²)
        R = A / P
        
        Q_calc = (1/n) * A * R^(2/3) * S^0.5
        error = Q_calc - Q
        
        if abs(error) < 0.001:
            break
            
        # Newton-Raphson update
        y = y - error / derivative
    
    return y
```

#### Energy Calculations
```python
# Total energy at any point
E = z + y + V²/(2g)
# Where:
# z = bed elevation
# y = water depth
# V²/2g = velocity head

# Hydraulic Grade Line (HGL)
HGL = z + y  # Pressure head line

# Energy Grade Line (EGL)
EGL = HGL + V²/(2g)
```

### 2.3 Optimization Engine

#### Multi-Objective Optimization Problem
```python
# Objective function
minimize: f(x) = w1×ΣHL + w2×ΣΔQ + w3×ΣΔG

# Where:
# HL = head losses
# ΔQ = flow deviations from targets
# ΔG = gate movement from current position
# w1, w2, w3 = weights

# Subject to constraints:
# 1. Flow conservation: Σ(Q_in) = Σ(Q_out) at each node
# 2. Capacity: Q ≤ Q_max for each canal
# 3. Depth: y ≥ y_min for all sections
# 4. Velocity: v_min ≤ v ≤ v_max
# 5. Gate limits: 0 ≤ opening ≤ max_opening
```

#### Optimization Algorithm
```python
# Using scipy.optimize.minimize with SLSQP method
result = minimize(
    objective_function,
    x0=current_gate_openings,
    method='SLSQP',
    bounds=gate_bounds,
    constraints=[
        flow_conservation_constraint,
        depth_constraint,
        velocity_constraint
    ]
)

optimal_gate_settings = result.x
```

### 2.4 Flow Splitting Optimization

#### Gate Flow Calculation
```python
# Free flow condition (downstream level < gate opening)
Q = Cd × w × a × sqrt(2×g×h)

# Submerged flow condition
Q = Cd × w × a × sqrt(2×g×h) × sqrt(1 - submergence_ratio)

# Where:
# Cd = discharge coefficient (0.61)
# w = gate width
# a = gate opening
# h = upstream head
```

#### Split Ratio Optimization
```python
# For junction M(0,0) splitting to zones
total_inflow = Q_source
demands = [Q_zone1, Q_zone2, ..., Q_zone6]

# Optimize split ratios
ratios = optimize_splits(total_inflow, demands, priorities)

# Result: Gate openings that achieve desired splits
gate_openings = {
    "M(0,0)->M(0,2)": 1.8m,  # 40% of flow
    "M(0,0)->M(0,5)": 1.5m   # 35% of flow
}
```

### 2.5 Travel Time Prediction

#### Velocity Calculation
```python
# From continuity equation
V = Q / A

# Where A depends on water depth
A = y × (b + m × y)  # Trapezoidal section

# Apply condition factors
V_actual = V × condition_factor
# condition_factor: 1.0 (clean), 0.85 (moderate sediment), 0.7 (heavy)
```

#### Travel Time Computation
```python
# For each canal segment
t_segment = L / V

# Total travel time
t_total = Σ(t_segment) + t_filling

# Dry channel startup adds filling time
t_filling = Volume_to_fill / Q_initial × 1.3  # 30% for absorption
```

**Example Calculation:**
- Path: Source → M(0,0) → M(0,2) → Zone_2
- Distances: 500m + 1200m + 800m = 2500m
- Velocities: 1.5, 1.2, 1.0 m/s
- Travel times: 333s + 1000s + 800s = 2133s ≈ 0.59 hours

### 2.6 Sequencing Optimization

#### Multi-Criteria Scoring
```python
def calculate_delivery_score(zone, request):
    # Priority score (0-1)
    priority_score = request.priority / 10
    
    # Elevation advantage (higher zones first)
    elevation_score = zone_elevation / max_elevation
    
    # Urgency (deadline proximity)
    time_to_deadline = (deadline - now).hours
    urgency_score = 1 / (1 + time_to_deadline/24)
    
    # Volume efficiency
    volume_score = min(volume / 100000, 1.0)
    
    # Weighted combination
    total_score = (0.4 × priority_score +
                  0.3 × elevation_score +
                  0.2 × urgency_score +
                  0.1 × volume_score)
    
    return total_score
```

#### Sequence Optimization Algorithm
1. **Initial Sorting**: Multi-criteria scores
2. **Greedy Construction**: Minimize switching costs
3. **Local Search**: 2-opt improvements
4. **Evaluation**: Residence time and efficiency

### 2.7 Energy Recovery Analysis

#### Micro-Hydro Potential
```python
# Theoretical power
P_theoretical = ρ × g × Q × H
# P = 1000 × 9.81 × 3.5 × 2.0 = 68.7 kW

# Actual recoverable power
P_actual = P_theoretical × η_turbine × η_generator
# P_actual = 68.7 × 0.85 × 0.95 = 55.5 kW

# Annual energy production
E_annual = P_actual × hours × availability
# E_annual = 55.5 × 8760 × 0.9 = 437.8 MWh

# Economic analysis
payback_years = capital_cost / (annual_revenue - O&M_cost)
```

### 2.8 Contingency Routing

#### Graph-Based Path Finding
```python
# Build network graph with blockages
G = create_network_graph()
apply_blockages(G, blockage_list)

# Find alternative paths
alternatives = nx.all_simple_paths(
    G, source, destination, cutoff=10
)

# Evaluate each path
for path in alternatives:
    capacity = min(edge_capacities_on_path)
    length = sum(edge_lengths_on_path)
    feasibility = evaluate_gravity_feasibility(path)
    
    if feasibility > threshold:
        valid_alternatives.append(path)
```

## 3. Output Generation

### 3.1 Optimal Gate Settings
```json
{
  "optimal_gate_settings": {
    "Source->M(0,0)": {
      "optimal_opening_m": 2.1,
      "flow_m3s": 5.2,
      "head_loss_m": 0.15,
      "upstream_level_m": 221.5,
      "downstream_level_m": 221.35,
      "velocity_ms": 1.3,
      "froude_number": 0.45
    }
  }
}
```

### 3.2 Energy Profiles
```json
{
  "energy_profiles": {
    "Zone_2_Path": [
      {
        "location": "Source",
        "elevation_m": 221.0,
        "water_depth_m": 0.5,
        "total_energy_m": 221.58,
        "specific_energy_m": 0.58
      }
    ]
  }
}
```

### 3.3 Delivery Schedule
```json
{
  "delivery_sequence": ["Zone_1", "Zone_2", "Zone_5"],
  "gate_operations": [
    {
      "time": "06:00",
      "gate_id": "M(0,0)->M(0,1)",
      "action": "open",
      "target_opening_m": 1.8
    }
  ],
  "expected_completion": "18:00"
}
```

## 4. Integration Points

### 4.1 Data Inputs From Other Services
- **Sensor Data Service**: Real-time water levels, flows
- **GIS Service**: Canal geometry, elevations
- **Weather Service**: Precipitation affecting flows
- **Scheduler Service**: Delivery requirements

### 4.2 Data Outputs To Other Services
- **Core Monitoring**: Optimal gate settings
- **Scheduler**: Feasible delivery windows
- **Water Accounting**: Expected deliveries
- **Alert Service**: Low depth warnings

## 5. Performance Metrics

### 5.1 Optimization Metrics
- Convergence time: < 500ms for 20 gates
- Iteration count: typically 50-200
- Solution quality: within 1% of optimal

### 5.2 Hydraulic Accuracy
- Flow prediction: ±5% of actual
- Travel time: ±10% accuracy
- Energy loss: ±0.1m precision

### 5.3 System Efficiency
- Water delivery efficiency: 85-95%
- Energy utilization: Maximum gravity use
- Micro-hydro potential: 200-500 kW total

## 6. Critical Computations

### 6.1 Real-Time Calculations
1. **Gate Flow**: Every gate change
2. **Water Levels**: Continuous monitoring
3. **Feasibility**: Before each delivery

### 6.2 Optimization Cycles
1. **Full Network**: Every 4 hours
2. **Local Adjustments**: Every 30 minutes
3. **Emergency Rerouting**: On-demand

### 6.3 Predictive Analytics
1. **Travel Times**: For scheduling
2. **Energy Recovery**: Daily assessment
3. **Maintenance Needs**: Weekly analysis

## Conclusion
The Gravity Flow Optimizer orchestrates complex hydraulic calculations, multi-objective optimization, and predictive analytics to ensure efficient water delivery using only gravity. The system continuously balances competing objectives while maintaining hydraulic constraints and maximizing energy efficiency.