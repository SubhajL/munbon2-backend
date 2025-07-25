# Water Accounting Service - End-to-End Data Flow

## Overview

The Water Accounting Service tracks water from gate release to crop consumption at the section level (50-200 hectares), calculating losses, efficiencies, and deficits along the way.

## 1. Water Delivery Initiation

### Data Sources
```
Scheduler Service (Port 3017) → Delivery Schedule
├── Delivery ID: DEL-20240713-SEC101-001
├── Section ID: SEC-Z1-001 (Zone 1, Section 1)
├── Scheduled Volume: 400,000 m³
├── Time Window: 2024-07-13 06:00 to 2024-07-14 06:00
└── Gate Assignment: RG-1-1 (Regulator Gate 1-1)
```

### Pre-Delivery Setup
1. **Section Characteristics Retrieved**:
   - Area: 150 hectares
   - Canal length: 8.5 km
   - Canal type: Earthen (unlined)
   - Crop: Rice (reproductive stage)
   - Seepage coefficient: 0.025 (2.5% per km)

2. **Environmental Conditions**:
   - Temperature: 32°C
   - Humidity: 65%
   - Wind speed: 2.5 m/s
   - Solar radiation: 280 W/m²

## 2. Flow Monitoring During Delivery

### Real-Time Data Collection
```
Flow Monitoring Service (Port 3016) → Flow Readings
Every 15 minutes:
{
    "timestamp": "2024-07-13T06:00:00",
    "gate_id": "RG-1-1",
    "flow_rate_m3s": 5.2,
    "water_level_m": 1.85,
    "gate_opening": 0.75
}
```

### Flow Pattern Example (24-hour delivery)
```
Hour 0-4:   Ramp up    (3.0 → 5.2 m³/s)
Hour 4-20:  Steady     (5.2 m³/s average)
Hour 20-24: Ramp down  (5.2 → 2.0 m³/s)
```

## 3. Volume Integration Process

### Computation Method: Trapezoidal Integration

```python
# For each time interval
Volume_i = (Flow_i + Flow_i+1) / 2 × Δt

# Total volume
Total_Volume = Σ Volume_i

# Example calculation:
Interval 1: (3.0 + 3.5) / 2 × 900s = 2,925 m³
Interval 2: (3.5 + 4.2) / 2 × 900s = 3,465 m³
...
Total: 410,400 m³ (gate outflow)
```

### Integration Results
```json
{
    "total_volume_m3": 410400,
    "integration_details": {
        "method": "trapezoidal",
        "num_readings": 96,
        "duration_hours": 24,
        "avg_flow_rate_m3s": 4.75,
        "peak_flow_rate_m3s": 5.2,
        "time_resolution_seconds": 900
    }
}
```

## 4. Transit Loss Calculations

### A. Seepage Loss
```
Formula: Seepage = Volume × Seepage_Rate × Canal_Length × Time_Factor

Calculation:
- Base seepage rate: 2.5% per km (earthen canal)
- Canal length: 8.5 km
- Transit time factor: 0.8 (for 24-hour delivery)
- Seepage = 410,400 × 0.025 × 8.5 × (1 + 0.8)
- Seepage = 157,278 m³
```

### B. Evaporation Loss
```
Formula: Evaporation = Surface_Area × Evap_Rate × Time

Parameters:
- Canal surface area: 8,500m × 5m = 42,500 m²
- Base evap rate: 0.0001 m/hour
- Environmental factors:
  - Temp factor: 1.24 (32°C)
  - Humidity factor: 0.35 (65% RH)
  - Wind factor: 1.25 (2.5 m/s)
  - Solar factor: 1.12 (280 W/m²)

Calculation:
- Adjusted rate: 0.0001 × 1.24 × 0.35 × 1.25 × 1.12 = 0.000061 m/hr
- Evaporation = 42,500 × 0.000061 × 24 = 62.2 m³
```

### C. Operational Loss
```
Formula: Operational = Volume × Base_Loss × Flow_Factor

Calculation:
- Base loss: 1% (standard)
- Flow factor: 1.0 (normal flow rate)
- Operational = 410,400 × 0.01 × 1.0 = 4,104 m³
```

### Total Transit Loss
```
Total Loss = Seepage + Evaporation + Operational
Total Loss = 157,278 + 62.2 + 4,104 = 161,444 m³
Loss Percentage = 161,444 / 410,400 × 100 = 39.3%
```

## 5. Section Inflow Calculation

```
Section Inflow = Gate Outflow - Transit Losses
Section Inflow = 410,400 - 161,444 = 248,956 m³
```

## 6. Efficiency Calculations

### A. Delivery (Conveyance) Efficiency
```
Delivery Efficiency = Section Inflow / Gate Outflow
Delivery Efficiency = 248,956 / 410,400 = 0.607 (60.7%)

Classification: "Fair" (between 55-65%)
```

### B. Application Efficiency
```
Assumed Values:
- Water Applied: 248,956 m³ (all section inflow)
- Water Consumed by Crop: 211,612 m³ (85% of applied)
- Return Flow: 24,896 m³ (10% of applied)
- Deep Percolation: 12,448 m³ (5% of applied)

Application Efficiency = Consumed / Applied
Application Efficiency = 211,612 / 248,956 = 0.85 (85%)

Classification: "Excellent" (above 85%)
```

### C. Overall System Efficiency
```
Overall Efficiency = Delivery × Application
Overall Efficiency = 0.607 × 0.85 = 0.516 (51.6%)

Classification: "Poor" (below 55%)
Limiting Factor: "Delivery" (conveyance losses)
```

## 7. Water Balance Accounting

### Section Water Balance
```
Inflows:
├── Canal delivery: 248,956 m³
└── Total inflow: 248,956 m³

Outflows:
├── Crop ET: 211,612 m³
├── Return flow: 24,896 m³
├── Deep percolation: 12,448 m³
└── Total outflow: 248,956 m³

Balance: 0 m³ (balanced)
```

### Demand vs Supply Analysis
```
Water Demand (150 ha × 2,000 m³/ha): 300,000 m³
Water Delivered to Section: 248,956 m³
Deficit: 51,044 m³ (17.0%)
```

## 8. Deficit Tracking

### Weekly Deficit Record
```json
{
    "section_id": "SEC-Z1-001",
    "week_number": 28,
    "year": 2024,
    "water_demand_m3": 300000,
    "water_delivered_m3": 248956,
    "water_consumed_m3": 211612,
    "delivery_deficit_m3": 51044,
    "deficit_percentage": 17.0,
    "stress_level": "moderate",
    "estimated_yield_impact": 8.5
}
```

### Stress Level Determination
```
Deficit % → Stress Level:
0-10%    → "mild"
10-20%   → "moderate" ✓ (17.0%)
20-30%   → "severe"
>30%     → "critical"
```

### Yield Impact Estimation
```
Base Impact = Deficit% × 0.5 = 17.0 × 0.5 = 8.5%
Stress Multiplier = 1.2 (moderate)
Timing Multiplier = 1.3 (critical growth stage)
Final Impact = 8.5 × 1.2 × 1.3 = 13.26%
Capped at: 8.5% (reasonable limit for single week)
```

## 9. Carry-Forward Management

### Current Status
```json
{
    "section_id": "SEC-Z1-001",
    "active": true,
    "total_deficit_m3": 142589,
    "deficit_breakdown": {
        "2024-W25": 35420,
        "2024-W26": 28900,
        "2024-W27": 27225,
        "2024-W28": 51044
    },
    "weeks_in_deficit": 4,
    "priority_score": 78.5,
    "cumulative_stress_index": 0.95
}
```

### Priority Score Calculation
```
Components:
- Base score (deficit amount): 40 points
- Age factor (4 weeks): 30 points
- Stress factor (moderate): 20 points
- Location factor: -11.5 points (upstream advantage)

Total Priority Score: 78.5/100
```

## 10. Recovery Planning

### Recovery Plan Generation
```json
{
    "section_id": "SEC-Z1-001",
    "total_deficit_m3": 142589,
    "recovery_plan": {
        "weekly_compensation_m3": 35647,
        "recovery_weeks": 4,
        "schedule": [
            {"week": 29, "compensation_m3": 35647, "cumulative": 35647},
            {"week": 30, "compensation_m3": 35647, "cumulative": 71294},
            {"week": 31, "compensation_m3": 35647, "cumulative": 106941},
            {"week": 32, "compensation_m3": 35648, "cumulative": 142589}
        ]
    }
}
```

## 11. Performance Metrics & Reporting

### Section Performance Summary
```json
{
    "section_id": "SEC-Z1-001",
    "reporting_period": "2024-W28",
    "performance_score": 0.68,
    "metrics": {
        "delivery_efficiency": 0.607,
        "application_efficiency": 0.85,
        "overall_efficiency": 0.516,
        "uniformity_coefficient": 0.92
    },
    "classification": "fair",
    "recommendations": [
        "Canal lining to reduce seepage by 60%",
        "Night irrigation to reduce evaporation",
        "Gate automation for consistent flow"
    ]
}
```

## 12. Data Storage

### PostgreSQL (Relational Data)
```sql
-- Water delivery record
INSERT INTO water_deliveries (
    delivery_id, section_id, gate_outflow_m3, 
    section_inflow_m3, transit_loss_m3, status
) VALUES (
    'DEL-20240713-SEC101-001', 'SEC-Z1-001', 410400,
    248956, 161444, 'completed'
);

-- Efficiency record
INSERT INTO efficiency_records (
    section_id, delivery_id, conveyance_efficiency,
    application_efficiency, overall_efficiency
) VALUES (
    'SEC-Z1-001', 'DEL-20240713-SEC101-001', 0.607,
    0.85, 0.516
);
```

### TimescaleDB (Time-Series Data)
```sql
-- Flow measurements (every 15 minutes)
INSERT INTO flow_measurements (
    time, gate_id, section_id, flow_rate_m3s, cumulative_volume_m3
) VALUES (
    '2024-07-13 06:00:00', 'RG-1-1', 'SEC-Z1-001', 3.0, 0
),
... -- 96 records total
```

## 13. Integration with Other Services

### Outbound Communications

1. **To Scheduler Service (Port 3017)**:
   ```json
   {
       "event": "delivery_complete",
       "delivery_id": "DEL-20240713-SEC101-001",
       "actual_volume_m3": 248956,
       "efficiency": 0.607,
       "deficit_m3": 51044
   }
   ```

2. **To GIS Service (Port 3018)**:
   ```json
   {
       "event": "deficit_update",
       "section_id": "SEC-Z1-001",
       "location": {"lat": 16.123, "lon": 103.456},
       "deficit_m3": 51044,
       "stress_level": "moderate",
       "priority_score": 78.5
   }
   ```

## 14. Key Performance Indicators

### System-Wide Metrics
- Average delivery efficiency: 65%
- Average application efficiency: 82%
- Sections meeting targets: 68%
- Water saved through monitoring: 15%
- Deficit recovery rate: 85%

### Optimization Opportunities
1. **Canal lining priority sections**: Save 150,000 m³/season
2. **Night irrigation adoption**: Reduce evaporation by 40%
3. **Flow control automation**: Improve efficiency by 10-15%
4. **Deficit early warning**: Reduce severe stress by 60%

## Conclusion

The Water Accounting Service provides comprehensive tracking from gate to field, enabling:
- Accurate loss quantification
- Performance benchmarking
- Deficit management
- Data-driven improvements
- Farmer trust through transparency

This forms the foundation for optimizing water use across the entire Munbon irrigation system.