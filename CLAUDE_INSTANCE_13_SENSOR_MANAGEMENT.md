# Claude Instance 13: Hybrid Sensor Network Management System

## Context
You are implementing Task 62 for the Munbon Irrigation Backend project. The system has only 6 water level sensors and 1 moisture sensor that must be strategically deployed across a large irrigation network with both automated and manual gates.

## Your Task
Implement the Hybrid Sensor Network Management System that optimizes the placement and utilization of limited mobile sensors.

## Key Requirements

### Sensor Constraints
- Total sensors: 6 water level + 1 moisture (all mobile)
- Must serve both real-time monitoring (automated gates) and validation (manual operations)
- Sensors can be relocated weekly by field teams
- GPS coordinates available for mapping

### Core Features to Implement

1. **Sensor Allocation Optimizer**
   - Balance between continuous monitoring and spot validation
   - Consider upcoming irrigation schedules
   - Account for historical problem areas

2. **Mobility Scheduler**
   - Weekly placement recommendations
   - Minimize field team travel
   - Coordinate with batch operation schedules

3. **Data Interpolation Engine**
   - Estimate conditions at ungauged locations
   - Use hydraulic models for interpolation
   - Provide confidence scores

4. **Calibration System**
   - Use mobile readings to calibrate fixed estimates
   - Track accuracy over time
   - Improve predictions iteratively

### Technical Specifications
- Python/FastAPI service
- Port: 3018
- Integrate with PostGIS for spatial operations
- Connect to InfluxDB for sensor data
- Use TimescaleDB for historical analysis

### Deliverables
1. Sensor allocation algorithm
2. REST APIs for placement recommendations
3. Interpolation service with confidence scoring
4. Calibration data management
5. Visualization dashboard

### Integration Points
- Receives: Irrigation schedules, gate operations, historical sensor data
- Provides: Sensor placement plans, interpolated values, confidence scores

## Implementation Notes
- Design for offline operation (field teams may have no connectivity)
- Consider battery life in placement decisions
- Account for sensor installation/removal time in scheduling
- Handle sensor failures gracefully

Start by creating the service skeleton and defining the optimization algorithms.