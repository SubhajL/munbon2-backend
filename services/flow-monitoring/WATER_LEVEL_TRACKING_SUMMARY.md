# Water Level Tracking in Munbon Irrigation Network

## Overview
The hydraulic network model now tracks actual water levels throughout the system, accounting for:
- Head losses across gates
- Friction losses in canals
- Backwater effects
- Energy conservation principles

## Key Components

### 1. Node Water Levels
Each node in the network maintains:
- **Water Surface Elevation** (m MSL) - Actual water level
- **Canal Bottom Elevation** (m MSL) - Invert level
- **Water Depth** (m) - Water surface minus bottom
- **Flow Balance** - Inflow and outflow rates

### 2. Gate Hydraulics
Gate flow calculations consider:
- **Upstream Water Level** - Actual level before the gate
- **Downstream Water Level** - Actual level after the gate
- **Gate Opening** - Percentage or height
- **Flow Regime** - Free flow, submerged, or weir flow

### 3. Head Loss Components

#### Gate Losses
- Major head losses occur at flow control structures
- Typical losses: 0.1-3m depending on gate restriction
- Calculated using gate-specific hydraulic equations

#### Friction Losses
- Gradual decrease along canal reaches
- Calculated using Manning's equation
- Typical losses: 0.1-0.5m per km

### 4. Example Water Level Profile

From the simulation results:

| Location | Water Level (m MSL) | Water Depth (m) | Notes |
|----------|-------------------|----------------|--------|
| Source (Dam) | 221.00 | - | Reservoir level |
| M(0,0) Outlet | 218.89 | 0.89 | After main gate |
| M(0,1) RMC Start | 218.83 | 0.93 | 0.06m drop |
| M(0,2) LMC Start | 218.79 | 0.89 | 0.10m drop |
| M(0,3) | 218.58 | 0.78 | 0.21m drop |
| M(0,5) Zone 2 | 217.07 | 0.07 | 1.51m total drop |

### 5. Key Observations

1. **Major Head Losses at Gates**
   - Source to M(0,0): 2.11m drop (main control)
   - M(0,3) to M(0,4): 1.05m drop
   - Controlled by gate opening percentage

2. **Friction Losses in Canals**
   - LMC: ~0.1-0.2m per section
   - Depends on flow rate and canal geometry
   - Higher flows = higher losses

3. **Flow Distribution**
   - M(0,0) splits flow to RMC (0.72 m³/s) and LMC (1.08 m³/s)
   - Further distribution at branch points
   - Controlled by gate settings

### 6. Visualization Features

The HTML visualization shows:
1. **Longitudinal Profiles** - Water surface along main canals
2. **Gate Effects** - Head drops at each control structure
3. **Network-Wide Levels** - Comparative view of all nodes
4. **Energy Grade Lines** - Including velocity head

### 7. Practical Applications

This water level tracking enables:
- **Real-time Monitoring** - Compare actual vs expected levels
- **Loss Detection** - Identify abnormal head losses
- **Gate Optimization** - Adjust gates for desired water levels
- **Predictive Control** - Forecast downstream impacts

### 8. Integration with Sensor Data

The model can be updated with real sensor readings:
```python
# Update with actual sensor reading
model.update_node_levels('M(0,3)', sensor_reading_msl)

# Recalculate downstream impacts
model.propagate_levels_downstream('M(0,3)', current_flow)
```

### 9. Future Enhancements

1. **Dynamic Updates** - Real-time sensor integration
2. **Optimization** - Automatic gate adjustments
3. **Alerts** - Abnormal water level detection
4. **Forecasting** - Predict levels hours ahead

The hydraulic network model provides a comprehensive framework for tracking and managing water levels throughout the irrigation system.