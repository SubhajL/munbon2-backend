# Gate Configuration Guide for Munbon Irrigation System

## Overview

The Munbon irrigation system has **59 gates** distributed across 6 zones:
- **20 Automated gates** - Controlled via SCADA system
- **39 Manual gates** - Operated by field teams on Tuesday/Thursday

This guide explains how to access and use gate configuration data across all instances.

## Gate Configuration Structure

Each gate has the following properties:

```json
{
  "gate_id": "M(0,2)->Zone_2",
  "type": "automated",              // "automated" or "manual"
  "name": "Zone 2 Inlet",
  "location": {
    "lat": 14.8234,
    "lon": 103.1567
  },
  "zone": 2,
  "width_m": 2.0,
  "max_opening_m": 2.0,
  "max_flow_m3s": 5.0,
  "calibration": {
    "k1": 0.60,                   // Calibration coefficients
    "k2": -0.11
  },
  "scada_id": "SCADA_002",        // For automated gates only
  "physical_markers": "Green post with 6 notches",
  "fallback_manual": true,        // Can be operated manually if SCADA fails
  "manual_operation": {           // For manual gates only
    "turns_to_open": 20,
    "time_to_operate_minutes": 12,
    "tool_required": "standard_wheel"
  }
}
```

## API Endpoints

### 1. Get All Gate Configurations
```http
GET http://localhost:3011/api/v1/gates/config/all

Response: Complete gate configuration dictionary
```

### 2. Get Specific Gate Configuration
```http
GET http://localhost:3011/api/v1/gates/config/M(0,2)->Zone_2

Response: {
  "gate_id": "M(0,2)->Zone_2",
  "name": "Zone 2 Inlet",
  "type": "automated",
  ...
}
```

### 3. Get Gates by Type
```http
GET http://localhost:3011/api/v1/gates/config/type/automated
GET http://localhost:3011/api/v1/gates/config/type/manual

Response: ["Source->M(0,0)", "M(0,2)->Zone_2", ...]
```

### 4. Get Gates by Zone
```http
GET http://localhost:3011/api/v1/gates/config/zone/2

Response: [
  {
    "gate_id": "M(0,2)->Zone_2",
    "name": "Zone 2 Inlet",
    "type": "automated",
    "location": {...}
  },
  ...
]
```

### 5. Get Gates Near Location
```http
GET http://localhost:3011/api/v1/gates/config/near-location?lat=14.82&lon=103.15&radius_km=5

Response: Gates within radius, sorted by distance
```

### 6. Get Physical Markers (for Field Teams)
```http
GET http://localhost:3011/api/v1/gates/config/physical-markers

Response: {
  "M(0,0)->M(0,2)": "Blue post with 8 notches",
  "M(0,2)->Zone_2": "Green post with 6 notches",
  ...
}
```

### 7. Get Operational Summary
```http
GET http://localhost:3011/api/v1/gates/config/summary

Response: {
  "total_gates": 59,
  "automated_gates": 20,
  "manual_gates": 39,
  "gates_with_fallback": 15,
  "zones": [0, 1, 2, 3, 4, 5, 6],
  "automation_percentage": 33.9
}
```

## Using Gate Configuration in Each Instance

### Instance 16 (Flow Monitoring)
```python
from services.gate_registry import get_gate_registry

registry = get_gate_registry()

# Check if gate is automated
if registry.is_automated("M(0,2)->Zone_2"):
    # Send SCADA command
    pass
else:
    # Generate manual instruction
    pass

# Get calibration for flow calculation
calibration = registry.get_gate_calibration("M(0,2)->Zone_2")
k1, k2 = calibration["k1"], calibration["k2"]
```

### Instance 17 (Scheduler)
```python
# Get manual gates for field team assignment
manual_gates = await client.get("/api/v1/gates/config/type/manual")

# Group gates by zone for efficient routing
for zone in range(1, 7):
    zone_gates = await client.get(f"/api/v1/gates/config/zone/{zone}")
    # Assign to appropriate team based on location
```

### Instance 18 (ROS/GIS Integration)
```python
# Find delivery gates near agricultural sections
section_location = {"lat": 14.825, "lon": 103.155}
nearby_gates = await client.get(
    f"/api/v1/gates/config/near-location",
    params={
        "lat": section_location["lat"],
        "lon": section_location["lon"],
        "radius_km": 3
    }
)

# Choose appropriate gate based on type and capacity
for gate in nearby_gates:
    if gate["type"] == "automated" or gate["fallback_manual"]:
        # Prefer automated or fallback-capable gates
        selected_gate = gate
        break
```

## Gate Naming Convention

Gates follow a hierarchical naming pattern:
- **Source gates**: `Source->M(x,y)`
- **Distribution gates**: `M(x,y)->M(a,b)`
- **Zone inlet gates**: `M(x,y)->Zone_N`
- **Field gates**: `Zone_N->Field_A`

Where:
- `M(x,y)` represents a main node at coordinates (x,y)
- Numbers indicate the hierarchical level and position

## Zone Distribution

| Zone | Purpose | Automated | Manual | Total |
|------|---------|-----------|---------|-------|
| 0 | Main distribution | 3 | 5 | 8 |
| 1 | Not active | 2 | 4 | 6 |
| 2 | Rice - high priority | 5 | 7 | 12 |
| 3 | Rice - medium priority | 4 | 6 | 10 |
| 4 | Not active | 1 | 5 | 6 |
| 5 | Sugarcane | 3 | 8 | 11 |
| 6 | Mixed crops | 2 | 4 | 6 |

## Physical Markers for Manual Gates

Each manual gate has physical markers to help field teams:
- **Color-coded posts**: Different colors for different zones
- **Notch system**: Number of notches indicates maximum opening
- **Example**: "Blue post with 8 notches" means:
  - Blue = Distribution level gate
  - 8 notches = Can be opened in 8 increments

## Tools Required for Manual Operation

Three types of tools are used:
1. **standard_wheel** - Most common, for gates up to 2.5m wide
2. **large_wheel** - For gates wider than 2.5m
3. **lever_type** - For older gates or emergency operation

## Integration with Field Mobile App

The mobile app (Instance 17) uses this configuration to:
1. Show gate locations on map
2. Display physical markers for identification
3. Indicate required tools
4. Calculate operation time for scheduling
5. Provide fallback instructions for automated gates

## Updating Gate Configuration

To update gate configuration:
1. Edit `/services/flow-monitoring/src/config/gate_configuration.json`
2. Restart the Flow Monitoring service
3. Changes are immediately available to all instances via API

## Example: Complete Gate Query Flow

```python
# Instance 18: Find delivery gate for section
section = "Zone_2_Section_A"
zone = 2

# 1. Get all gates in zone
zone_gates = requests.get(
    f"http://localhost:3011/api/v1/gates/config/zone/{zone}"
).json()

# 2. Filter by type preference
automated_gates = [g for g in zone_gates if g["type"] == "automated"]
manual_gates = [g for g in zone_gates if g["type"] == "manual"]

# 3. Check capacity
selected_gate = None
required_flow = 3.5  # m³/s

for gate in automated_gates + manual_gates:
    gate_config = requests.get(
        f"http://localhost:3011/api/v1/gates/config/{gate['gate_id']}"
    ).json()
    
    if gate_config["max_flow_m3s"] >= required_flow:
        selected_gate = gate_config
        break

print(f"Selected gate: {selected_gate['gate_id']} ({selected_gate['type']})")
```

## Best Practices

1. **Always check gate type** before sending control commands
2. **Prefer automated gates** when available for better control
3. **Use fallback_manual** gates as backup for critical operations
4. **Cache gate configurations** locally to reduce API calls
5. **Monitor gate_registry logs** for configuration issues

This configuration system ensures all instances have consistent, up-to-date information about gate capabilities and constraints.