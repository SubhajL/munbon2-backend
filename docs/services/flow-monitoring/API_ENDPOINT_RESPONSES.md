# Flow Monitoring Service - API Response Examples

## 1. POST /api/v1/irrigation/schedule
Create irrigation schedule with gate operations

### Request:
```json
{
  "requests": [
    {
      "zone": "Zone 2",
      "volume_m3": 10000,
      "flow_rate_m3s": 2.0,
      "priority": 1
    },
    {
      "zone": "Zone 5", 
      "volume_m3": 7500,
      "flow_rate_m3s": 1.5,
      "priority": 2
    },
    {
      "zone": "Zone 6",
      "volume_m3": 5000,
      "flow_rate_m3s": 1.0,
      "priority": 3
    }
  ],
  "start_time": "2024-01-15T08:00:00Z"
}
```

### Response (201 Created):
```json
{
  "schedule_id": "SCH-2024-0115-001",
  "status": "scheduled",
  "created_at": "2024-01-15T03:45:00Z",
  "summary": {
    "total_volume_m3": 22500,
    "total_duration_hours": 3.5,
    "zones_count": 3,
    "gates_involved": 14
  },
  "gate_operations": [
    {
      "operation_id": "OP-001",
      "gate_id": "Source->M(0,0)",
      "action": "open",
      "time": "2024-01-15T04:54:00Z",
      "opening_percent": 90.0,
      "flow_rate_m3s": 4.5,
      "reason": "Combined flow for Zones 2, 5, 6"
    },
    {
      "operation_id": "OP-002",
      "gate_id": "M(0,0)->M(0,2)",
      "action": "open",
      "time": "2024-01-15T04:56:00Z",
      "opening_percent": 90.0,
      "flow_rate_m3s": 4.5,
      "reason": "Shared path for all zones"
    },
    {
      "operation_id": "OP-003",
      "gate_id": "M(0,2)->M(0,3)",
      "action": "open",
      "time": "2024-01-15T04:58:00Z",
      "opening_percent": 90.0,
      "flow_rate_m3s": 4.5,
      "reason": "Shared path for all zones"
    },
    {
      "operation_id": "OP-004",
      "gate_id": "M(0,3)->M(0,5)",
      "action": "open",
      "time": "2024-01-15T05:00:00Z",
      "opening_percent": 90.0,
      "flow_rate_m3s": 4.5,
      "reason": "Shared path for all zones"
    },
    {
      "operation_id": "OP-005",
      "gate_id": "M(0,5)->Zone2",
      "action": "open",
      "time": "2024-01-15T05:02:00Z",
      "opening_percent": 40.0,
      "flow_rate_m3s": 2.0,
      "reason": "Zone 2 delivery"
    },
    {
      "operation_id": "OP-006",
      "gate_id": "M(0,5)->M(0,12)",
      "action": "open",
      "time": "2024-01-15T05:04:00Z",
      "opening_percent": 50.0,
      "flow_rate_m3s": 2.5,
      "reason": "Path to Zones 5 and 6"
    },
    {
      "operation_id": "OP-020",
      "gate_id": "Source->M(0,0)",
      "action": "reduce",
      "time": "2024-01-15T09:00:00Z",
      "opening_percent": 50.0,
      "flow_rate_m3s": 2.5,
      "reason": "Zone 5 complete - reduce flow"
    },
    {
      "operation_id": "OP-030",
      "gate_id": "M(0,5)->Zone2",
      "action": "close",
      "time": "2024-01-15T09:23:00Z",
      "opening_percent": 0.0,
      "flow_rate_m3s": 0.0,
      "reason": "Zone 2 complete - 10,000 m³ delivered"
    }
  ],
  "timeline": {
    "Zone 2": {
      "path": ["Source", "M(0,0)", "M(0,2)", "M(0,3)", "M(0,5)", "Zone2"],
      "travel_time_minutes": 186,
      "water_arrival": "2024-01-15T08:00:00Z",
      "irrigation_start": "2024-01-15T08:00:00Z",
      "irrigation_end": "2024-01-15T09:23:00Z",
      "duration_hours": 1.38,
      "volume_delivered_m3": 10000
    },
    "Zone 5": {
      "path": ["Source", "M(0,0)", "M(0,2)", "M(0,3)", "M(0,5)", "M(0,12)", "Zone5"],
      "travel_time_minutes": 210,
      "water_arrival": "2024-01-15T08:00:00Z",
      "irrigation_start": "2024-01-15T08:00:00Z",
      "irrigation_end": "2024-01-15T09:00:00Z",
      "duration_hours": 1.0,
      "volume_delivered_m3": 7500
    },
    "Zone 6": {
      "path": ["Source", "M(0,0)", "M(0,2)", "M(0,3)", "M(0,5)", "M(0,12)", "M(0,14)", "Zone6"],
      "travel_time_minutes": 225,
      "water_arrival": "2024-01-15T08:00:00Z",
      "irrigation_start": "2024-01-15T08:00:00Z",
      "irrigation_end": "2024-01-15T09:30:00Z",
      "duration_hours": 1.5,
      "volume_delivered_m3": 5000
    }
  },
  "shared_paths": {
    "Source->M(0,0)": {
      "zones_using": ["Zone 2", "Zone 5", "Zone 6"],
      "combined_flow_m3s": 4.5,
      "capacity_utilization_percent": 86.5
    },
    "M(0,0)->M(0,2)": {
      "zones_using": ["Zone 2", "Zone 5", "Zone 6"],
      "combined_flow_m3s": 4.5,
      "capacity_utilization_percent": 86.5
    }
  },
  "warnings": [],
  "estimated_completion": "2024-01-15T11:30:00Z"
}
```

## 2. GET /api/v1/network/status
Get current water levels, flows, and gate positions

### Response (200 OK):
```json
{
  "timestamp": "2024-01-15T08:15:00Z",
  "system_state": "irrigating",
  "active_zones": ["Zone 2", "Zone 5", "Zone 6"],
  "water_levels": {
    "Source": {
      "level_m": 221.0,
      "elevation_msl": 221.0,
      "depth_m": null,
      "status": "stable"
    },
    "M(0,0)": {
      "level_m": 219.2,
      "elevation_msl": 219.2,
      "depth_m": 1.2,
      "status": "stable"
    },
    "M(0,2)": {
      "level_m": 218.9,
      "elevation_msl": 218.9,
      "depth_m": 1.0,
      "status": "stable"
    },
    "M(0,3)": {
      "level_m": 218.7,
      "elevation_msl": 218.7,
      "depth_m": 0.9,
      "status": "falling",
      "rate_m_per_hour": -0.02
    },
    "M(0,5)": {
      "level_m": 218.0,
      "elevation_msl": 218.0,
      "depth_m": 1.0,
      "status": "stable"
    },
    "M(0,12)": {
      "level_m": 216.5,
      "elevation_msl": 216.5,
      "depth_m": 1.5,
      "status": "rising",
      "rate_m_per_hour": 0.01
    }
  },
  "flows": {
    "Source->M(0,0)": {
      "flow_m3s": 4.5,
      "velocity_ms": 1.2,
      "status": "normal",
      "direction": "forward"
    },
    "M(0,0)->M(0,2)": {
      "flow_m3s": 4.5,
      "velocity_ms": 1.3,
      "status": "normal",
      "direction": "forward"
    },
    "M(0,2)->M(0,3)": {
      "flow_m3s": 4.5,
      "velocity_ms": 1.4,
      "status": "normal",
      "direction": "forward"
    },
    "M(0,3)->M(0,5)": {
      "flow_m3s": 4.5,
      "velocity_ms": 1.5,
      "status": "normal",
      "direction": "forward"
    },
    "M(0,5)->Zone2": {
      "flow_m3s": 2.0,
      "velocity_ms": 1.0,
      "status": "normal",
      "direction": "forward"
    },
    "M(0,5)->M(0,12)": {
      "flow_m3s": 2.5,
      "velocity_ms": 1.1,
      "status": "normal",
      "direction": "forward"
    }
  },
  "gate_positions": {
    "Source->M(0,0)": {
      "position_percent": 90.0,
      "opening_m": 2.5,
      "status": "open",
      "mode": "automatic",
      "last_changed": "2024-01-15T04:54:00Z"
    },
    "M(0,0)->M(0,2)": {
      "position_percent": 90.0,
      "opening_m": 2.5,
      "status": "open",
      "mode": "automatic",
      "last_changed": "2024-01-15T04:56:00Z"
    },
    "M(0,5)->Zone2": {
      "position_percent": 40.0,
      "opening_m": 1.0,
      "status": "open",
      "mode": "automatic",
      "last_changed": "2024-01-15T05:02:00Z"
    }
  },
  "active_schedules": [
    {
      "schedule_id": "SCH-2024-0115-001",
      "progress_percent": 45,
      "volumes_delivered": {
        "Zone 2": 4500,
        "Zone 5": 3375,
        "Zone 6": 2250
      }
    }
  ],
  "alarms": [],
  "system_efficiency": {
    "hydraulic_efficiency_percent": 92.5,
    "delivery_accuracy_percent": 98.2,
    "water_loss_percent": 2.3
  }
}
```

## 3. POST /api/v1/hydraulics/solve
Run hydraulic solver for given gate settings

### Request:
```json
{
  "gate_settings": [
    {
      "upstream": "Source",
      "downstream": "M(0,0)",
      "opening": 2.5
    },
    {
      "upstream": "M(0,0)",
      "downstream": "M(0,2)",
      "opening": 2.5
    },
    {
      "upstream": "M(0,2)",
      "downstream": "M(0,3)",
      "opening": 2.5
    }
  ],
  "boundary_conditions": {
    "Source": {
      "type": "fixed_level",
      "value": 221.0
    }
  },
  "solver_options": {
    "max_iterations": 100,
    "tolerance": 0.001,
    "relaxation_factor": 0.7
  }
}
```

### Response (200 OK):
```json
{
  "solution_id": "SOL-2024-0115-042",
  "status": "converged",
  "iterations": 23,
  "computation_time_ms": 145,
  "convergence": {
    "max_residual": 0.0008,
    "avg_residual": 0.0003,
    "converged": true,
    "convergence_history": [
      {"iteration": 1, "residual": 0.25},
      {"iteration": 5, "residual": 0.08},
      {"iteration": 10, "residual": 0.02},
      {"iteration": 20, "residual": 0.001},
      {"iteration": 23, "residual": 0.0008}
    ]
  },
  "results": {
    "water_levels": {
      "Source": 221.0,
      "M(0,0)": 219.2,
      "M(0,2)": 218.9,
      "M(0,3)": 218.7,
      "M(0,5)": 218.0,
      "M(0,12)": 216.5,
      "Zone2": 217.8,
      "Zone5": 216.3,
      "Zone6": 216.0
    },
    "flows": {
      "Source->M(0,0)": 4.5,
      "M(0,0)->M(0,2)": 4.5,
      "M(0,2)->M(0,3)": 4.5,
      "M(0,3)->M(0,5)": 4.5,
      "M(0,5)->Zone2": 2.0,
      "M(0,5)->M(0,12)": 2.5,
      "M(0,12)->Zone5": 1.5,
      "M(0,12)->M(0,14)": 1.0,
      "M(0,14)->Zone6": 1.0
    },
    "velocities": {
      "Source->M(0,0)": 1.2,
      "M(0,0)->M(0,2)": 1.3,
      "M(0,2)->M(0,3)": 1.4,
      "M(0,3)->M(0,5)": 1.5
    },
    "head_losses": {
      "Source->M(0,0)": 0.05,
      "M(0,0)->M(0,2)": 0.02,
      "M(0,2)->M(0,3)": 0.03,
      "M(0,3)->M(0,5)": 0.08
    }
  },
  "mass_balance": {
    "total_inflow_m3s": 4.5,
    "total_outflow_m3s": 4.5,
    "imbalance_m3s": 0.0,
    "balance_error_percent": 0.0
  },
  "warnings": [],
  "recommendations": [
    {
      "type": "efficiency",
      "message": "Gate M(0,3)->M(0,5) is operating at 90% capacity. Consider opening parallel path if available."
    }
  ]
}
```

## 4. GET /api/v1/telemetry/flow/history
Get historical flow data

### Request:
```
GET /api/v1/telemetry/flow/history?gate_id=Source->M(0,0)&start_time=2024-01-15T00:00:00Z&end_time=2024-01-15T12:00:00Z&interval=5m
```

### Response (200 OK):
```json
{
  "gate_id": "Source->M(0,0)",
  "start_time": "2024-01-15T00:00:00Z",
  "end_time": "2024-01-15T12:00:00Z",
  "interval": "5m",
  "unit": "m3/s",
  "statistics": {
    "min": 0.0,
    "max": 4.5,
    "avg": 2.1,
    "std_dev": 1.8,
    "total_volume_m3": 90720
  },
  "data": [
    {
      "timestamp": "2024-01-15T00:00:00Z",
      "flow_m3s": 0.0,
      "quality": "good"
    },
    {
      "timestamp": "2024-01-15T00:05:00Z",
      "flow_m3s": 0.0,
      "quality": "good"
    },
    {
      "timestamp": "2024-01-15T04:54:00Z",
      "flow_m3s": 0.5,
      "quality": "good"
    },
    {
      "timestamp": "2024-01-15T04:55:00Z",
      "flow_m3s": 2.2,
      "quality": "good"
    },
    {
      "timestamp": "2024-01-15T05:00:00Z",
      "flow_m3s": 4.5,
      "quality": "good"
    },
    {
      "timestamp": "2024-01-15T08:00:00Z",
      "flow_m3s": 4.5,
      "quality": "good"
    },
    {
      "timestamp": "2024-01-15T09:00:00Z",
      "flow_m3s": 2.5,
      "quality": "good"
    },
    {
      "timestamp": "2024-01-15T09:23:00Z",
      "flow_m3s": 1.0,
      "quality": "good"
    },
    {
      "timestamp": "2024-01-15T09:30:00Z",
      "flow_m3s": 0.0,
      "quality": "good"
    }
  ],
  "events": [
    {
      "timestamp": "2024-01-15T04:54:00Z",
      "type": "gate_opened",
      "description": "Gate opened for irrigation schedule SCH-2024-0115-001"
    },
    {
      "timestamp": "2024-01-15T09:00:00Z",
      "type": "flow_reduced",
      "description": "Flow reduced - Zone 5 complete"
    },
    {
      "timestamp": "2024-01-15T09:23:00Z",
      "type": "flow_reduced",
      "description": "Flow reduced - Zone 2 complete"
    },
    {
      "timestamp": "2024-01-15T09:30:00Z",
      "type": "gate_closed",
      "description": "Gate closed - All deliveries complete"
    }
  ],
  "metadata": {
    "sensor_id": "FLW-001",
    "sensor_type": "ultrasonic",
    "accuracy_m3s": 0.05,
    "last_calibration": "2024-01-01T00:00:00Z"
  }
}
```

## 5. WebSocket Real-time Updates
Continuous stream of system updates

### Connection:
```javascript
ws://localhost:3011/ws
```

### Message Examples:

#### Water Level Update:
```json
{
  "type": "water_level",
  "timestamp": "2024-01-15T08:15:30Z",
  "node": "M(0,3)",
  "level": 218.65,
  "change_rate": -0.02,
  "status": "falling"
}
```

#### Flow Rate Update:
```json
{
  "type": "flow_rate",
  "timestamp": "2024-01-15T08:15:30Z",
  "gate_id": "M(0,5)->Zone2",
  "flow": 2.0,
  "velocity": 1.0,
  "direction": "forward"
}
```

#### Gate Position Update:
```json
{
  "type": "gate_position",
  "timestamp": "2024-01-15T09:00:00Z",
  "gate_id": "Source->M(0,0)",
  "position": 50.0,
  "previous_position": 90.0,
  "action": "reduced",
  "reason": "Zone 5 complete"
}
```

#### Schedule Progress Update:
```json
{
  "type": "schedule_progress",
  "timestamp": "2024-01-15T08:30:00Z",
  "schedule_id": "SCH-2024-0115-001",
  "zone_progress": {
    "Zone 2": {
      "volume_delivered": 5400,
      "volume_target": 10000,
      "percent_complete": 54,
      "estimated_completion": "2024-01-15T09:23:00Z"
    },
    "Zone 5": {
      "volume_delivered": 4050,
      "volume_target": 7500,
      "percent_complete": 54,
      "estimated_completion": "2024-01-15T09:00:00Z"
    },
    "Zone 6": {
      "volume_delivered": 2700,
      "volume_target": 5000,
      "percent_complete": 54,
      "estimated_completion": "2024-01-15T09:30:00Z"
    }
  },
  "overall_progress": 54
}
```

#### System Alert:
```json
{
  "type": "alert",
  "timestamp": "2024-01-15T08:45:00Z",
  "severity": "warning",
  "code": "HIGH_VELOCITY",
  "message": "High velocity detected in canal section M(0,2)->M(0,3)",
  "details": {
    "velocity_ms": 2.1,
    "threshold_ms": 2.0,
    "gate_id": "M(0,2)->M(0,3)",
    "recommended_action": "Consider reducing flow rate"
  }
}
```

#### Delivery Complete:
```json
{
  "type": "delivery_complete",
  "timestamp": "2024-01-15T09:00:00Z",
  "zone": "Zone 5",
  "volume_delivered": 7500,
  "accuracy_percent": 100.0,
  "duration_hours": 1.0,
  "next_action": "Reducing upstream flows"
}
```

## Error Response Format

### Example Error (400 Bad Request):
```json
{
  "error": {
    "code": "INVALID_FLOW_RATE",
    "message": "Requested flow rate exceeds gate capacity",
    "details": {
      "requested_flow": 6.0,
      "gate_capacity": 5.0,
      "gate_id": "M(0,0)->M(0,2)",
      "suggested_flow": 4.5
    }
  },
  "timestamp": "2024-01-15T08:00:00Z",
  "request_id": "req-123-456"
}
```

### Example Error (503 Service Unavailable):
```json
{
  "error": {
    "code": "HYDRAULIC_SOLVER_UNAVAILABLE",
    "message": "Hydraulic solver service is currently processing maximum requests",
    "details": {
      "current_queue": 10,
      "max_queue": 10,
      "estimated_wait_seconds": 30,
      "retry_after": "2024-01-15T08:00:30Z"
    }
  },
  "timestamp": "2024-01-15T08:00:00Z",
  "request_id": "req-123-457"
}
```