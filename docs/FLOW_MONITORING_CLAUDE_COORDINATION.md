# Flow Monitoring Service - Claude Instance Coordination

## Instance Overview

### Critical Path Instances (Sequential)
1. **Instance 16**: Core Monitoring + Dual-Mode Control
   - Tasks: 50, 59, 65
   - Status: HIGHEST PRIORITY
   - Blocking: Instances 17, 18

2. **Instance 17**: Scheduler + Field Operations  
   - Tasks: 60, 61
   - Dependencies: Instance 16 APIs
   - Blocking: Field deployment

3. **Instance 18**: ROS/GIS Integration
   - Task: 66
   - Dependencies: Instances 16, 17
   - Final integration layer

### Independent Instances (Parallel)
4. **Instance 13**: Sensor Management
   - Task: 62
   - Can start immediately
   
5. **Instance 14**: Water Accounting
   - Task: 63
   - Can start immediately
   
6. **Instance 15**: Gravity Optimizer
   - Task: 64
   - Can start immediately

## Communication Protocols

### API Contracts Between Instances

#### Instance 16 → Instance 17
```python
# Gate control state
GET /api/v1/gates/state
{
  "gates": {
    "Source->M(0,0)": {
      "type": "automated",
      "state": "open",
      "opening_m": 1.8,
      "flow_m3s": 4.5,
      "mode": "auto"
    }
  }
}

# Schedule feasibility check
POST /api/v1/hydraulics/verify-schedule
{
  "proposed_operations": [...],
  "constraints": {...}
}
```

#### Instance 17 → Instance 16
```python
# Update manual gate state
PUT /api/v1/gates/manual/{gate_id}/state
{
  "opening_m": 1.5,
  "timestamp": "2024-01-16T06:30:00Z",
  "recorded_by": "Team_A_User_1"
}
```

#### Instance 18 → Instance 17
```python
# Submit weekly demands
POST /api/v1/scheduler/demands
{
  "week": "2024-W03",
  "sections": [
    {
      "id": "Zone_2_Section_A",
      "demand_m3": 15000,
      "priority": 9
    }
  ]
}
```

## Shared Data Models

### Gate Definition
```python
class Gate:
    gate_id: str
    gate_type: Enum["automated", "manual", "hybrid"]
    width_m: float
    max_opening_m: float
    calibration_k1: float
    calibration_k2: float
    location: GeoPoint
    upstream_node: str
    downstream_node: str
```

### Section Definition
```python
class Section:
    section_id: str
    zone: int
    area_hectares: float
    delivery_point: str  # gate_id
    elevation_range: Tuple[float, float]
    crop_type: str
    soil_type: str
```

## Integration Testing Strategy

### Phase 1: Unit Testing
Each instance develops comprehensive unit tests

### Phase 2: Integration Points
1. Instance 16 + 17: Gate control handoff
2. Instance 17 + 18: Demand scheduling
3. Instance 16 + 13: Sensor data flow

### Phase 3: End-to-End Scenarios
1. Weekly batch planning with mixed gates
2. Real-time adaptation during delivery
3. Emergency mode transitions
4. Sensor failure handling

## BFF Integration Notes

### Water Distribution (WD) BFF
- Consumes: Task 60 schedules, Task 63 accounting
- Provides: User-facing delivery status

### Water Control (WC) BFF  
- Consumes: Task 59 gate states, Task 65 mode status
- Provides: Control interface for operators

### Setup BFF
- Consumes: Task 50 configuration, Task 62 sensor setup
- Provides: System configuration UI

## Timeline Coordination

### Week 1-2: Foundation
- Instance 16 builds core monitoring
- Instances 13, 14, 15 start independent work

### Week 3-4: Integration
- Instance 17 integrates with Instance 16
- Continue independent instances

### Week 5: Final Integration
- Instance 18 connects all services
- End-to-end testing

## Risk Mitigation

1. **API Version Management**: All APIs must be versioned
2. **Mock Services**: Each instance provides mock endpoints
3. **Contract Testing**: Use Pact or similar for API contracts
4. **Daily Sync**: Brief coordination meeting
5. **Shared Documentation**: Update this file with changes

## Success Criteria

1. 20 automated gates respond to commands < 1 second
2. Weekly schedules generated in < 5 minutes
3. Field app works offline for 72 hours
4. 95% delivery accuracy at section level
5. Mode transitions complete < 30 seconds