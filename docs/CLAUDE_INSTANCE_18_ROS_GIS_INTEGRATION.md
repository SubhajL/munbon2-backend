# Claude Instance 18: ROS/GIS Integration with Flow Monitoring

## Context
You are implementing Task 66 for the Munbon Irrigation Backend project. This integration layer connects crop water requirements (ROS) and spatial data (GIS) with the Flow Monitoring Service's dual-mode capabilities. This task depends on Tasks 50, 59, and 60 being complete.

## Your Task
Create the unified integration layer that bridges section-level agricultural demands with hydraulic delivery capabilities.

## Key Integration Points

### From ROS Service
- Crop types and growth stages by section
- Water requirements (mm/day or m³/section)
- Stress indicators and priorities
- Growth stage calendars

### From GIS/SHAPE Service
- Section boundaries and areas
- Elevation data
- Delivery point mapping
- Soil type distribution

### To Flow Monitoring
- Section-level water demands
- Delivery priorities and windows
- Spatial routing requirements
- Performance feedback

## Core Features to Implement

1. **Section-Level Demand Aggregator**
   ```python
   {
     "section_id": "Zone_2_Section_A",
     "area_hectares": 150,
     "crop": "rice",
     "growth_stage": "flowering",
     "water_demand_m3": 15000,
     "priority": "critical",
     "delivery_window": {
       "start": "2024-01-16T06:00:00Z",
       "end": "2024-01-18T18:00:00Z"
     }
   }
   ```

2. **Spatial-Hydraulic Mapper**
   - Link GIS sections to hydraulic delivery points
   - Handle many-to-one relationships (multiple sections per gate)
   - Calculate weighted demands for shared delivery points

3. **Priority Resolution Engine**
   - Crop growth stage priorities
   - Soil moisture deficits
   - Economic value weighting
   - Drought stress indicators

4. **Feedback Loop Manager**
   - Actual delivery volumes to ROS
   - Update crop models with water received
   - Track delivery efficiency by section
   - Generate deficit carry-forward

5. **Weather Integration**
   - Rainfall adjustments to demands
   - ET-based requirement updates
   - Forecast-based planning

## Technical Specifications
- Python/FastAPI service on port 3022
- GraphQL API for complex queries
- PostGIS for spatial operations
- Redis for caching

## API Examples

### Demand Submission
```graphql
mutation SubmitWeeklyDemands {
  submitDemands(
    week: "2024-W03"
    demands: [
      {
        sectionId: "Zone_2_Section_A"
        volumeM3: 15000
        priority: CRITICAL
      }
    ]
  ) {
    scheduleId
    status
    conflicts
  }
}
```

### Performance Query
```graphql
query SectionPerformance {
  section(id: "Zone_2_Section_A") {
    deliveries(weeks: 4) {
      planned
      actual
      efficiency
      deficits
    }
  }
}
```

## Implementation Priorities
1. Section mapping service
2. Demand aggregation engine
3. Priority resolution
4. Feedback loop
5. Weather adjustments

## Critical Success Factors
- Accurate section-to-gate mapping
- Timely demand submission (24hr advance)
- Clear priority rules
- Reliable feedback to ROS

Remember: This is the bridge between agricultural needs and hydraulic reality. Both sides must trust the data.