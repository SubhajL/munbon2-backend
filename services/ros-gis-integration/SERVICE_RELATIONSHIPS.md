# Service Relationships and Data Flow

## Overview
This document explains how the ROS/GIS Integration Service relates to other services in the Munbon system, particularly addressing the relationship with the Scheduler Service.

## Key Service Relationships

### 1. Daily Demand Calculation Flow

```
[Daily Process - 6:00 AM]
    ↓
Data Ingestion Service
    ├── Processes geopackage files
    └── Stores AquaCrop results → ros_gis.aquacrop_results
    ↓
ROS/GIS Integration Service (this service)
    ├── Fetches ROS calculations (ROS Service)
    ├── Fetches AquaCrop results (Database)
    ├── Combines demands (configurable strategy)
    └── Stores daily demands → ros_gis.daily_demands
```

### 2. Control Interval Accumulation

```
[Weekly/Biweekly/Monthly]
    ↓
ROS/GIS Integration Service
    ├── Accumulates daily demands by section
    ├── Aggregates by irrigation channel
    ├── Calculates peak flows and totals
    └── Prepares scheduling request
    ↓
Scheduler Service (separate service)
```

### 3. Service Responsibilities

#### ROS/GIS Integration Service (This Service)
**Primary Role: Demand Calculation and Spatial Aggregation**

- **Daily Tasks:**
  - Calculate water demands (ROS + AquaCrop)
  - Store plot-level daily demands
  - Track growth stages and stress levels

- **Control Interval Tasks:**
  - Accumulate demands to operational periods
  - Aggregate by sections and channels
  - Apply priority scoring
  - Optimize delivery paths
  - **PREPARE** scheduling requests

- **What it DOES NOT do:**
  - Does NOT create actual field operation schedules
  - Does NOT determine gate operation sequences
  - Does NOT assign time slots to farmers

#### Scheduler Service (Separate Service)
**Primary Role: Temporal Scheduling and Coordination**

- **Receives from ROS/GIS Integration:**
  ```json
  {
    "interval": "weekly",
    "channel_demands": {
      "channel_zone_2": {
        "total_demand_m3": 50000,
        "sections": ["Zone_2_A", "Zone_2_B"],
        "peak_flow_required_m3s": 2.5,
        "delivery_gates": ["M(0,2)->Zone_2"]
      }
    },
    "section_priorities": [...],
    "constraints": {...}
  }
  ```

- **Creates:**
  - Detailed time-based schedules
  - Gate operation sequences with timestamps
  - Farmer notification schedules
  - Maintenance windows
  - Conflict resolution

- **Returns to ROS/GIS Integration:**
  ```json
  {
    "schedule_id": "SCH-2024-W03-Z2",
    "operations": [
      {
        "time": "2024-01-15T06:00:00Z",
        "gate": "M(0,2)->Zone_2",
        "action": "open",
        "flow_rate_m3s": 2.5,
        "sections": ["Zone_2_A"],
        "duration_hours": 4
      }
    ]
  }
  ```

### 4. Why Two Separate Services?

**Separation of Concerns:**
1. **ROS/GIS Integration** = WHAT water is needed WHERE
2. **Scheduler Service** = WHEN and HOW to deliver it

**Benefits:**
- Clear boundaries of responsibility
- Independent scaling (scheduling is computationally intensive)
- Different update frequencies (demands daily, schedules weekly)
- Allows multiple scheduling strategies without affecting demand calculation

### 5. Data Flow Example

```
Monday (Day 1):
  - ROS/GIS: Calculate daily demands for all plots
  - Store: 1,000 plot demands → daily_demands table

Tuesday-Saturday (Days 2-6):
  - ROS/GIS: Continue daily calculations
  - Accumulate: 6,000 total plot-day records

Sunday (Day 7):
  - ROS/GIS: Accumulate week's demands
    - By section: 200 sections × 50,000 m³ average
    - By channel: 20 channels × 500,000 m³ average
    - Calculate priorities and optimal paths
  
  - ROS/GIS → Scheduler: Send aggregated demand request
  
  - Scheduler: Create detailed schedule
    - Monday 6:00-10:00: Channel 1 → Sections A,B,C
    - Monday 10:00-14:00: Channel 2 → Sections D,E,F
    - etc.
  
  - Scheduler → Flow Monitoring: Execute schedule
  
  - Flow Monitoring → SCADA: Operate gates
```

### 6. Integration Points

**ROS/GIS Integration provides to Scheduler:**
- Aggregated demands by channel/section
- Priority scores for each section
- Optimal delivery paths
- Hydraulic constraints
- Loss estimates

**Scheduler provides to ROS/GIS Integration:**
- Schedule IDs for tracking
- Confirmed delivery windows
- Actual vs planned reconciliation

**Both services share:**
- Common section/gate identifiers
- Consistent time zones (UTC + local)
- Performance feedback loop

### 7. API Interactions

```python
# ROS/GIS Integration Service
async def submit_to_scheduler(self, accumulated_demands):
    """Submit demands for scheduling"""
    
    # Prepare scheduling request
    request = {
        "interval_type": "weekly",
        "start_date": "2024-01-15",
        "end_date": "2024-01-21",
        "demands": accumulated_demands,
        "constraints": {
            "max_concurrent_gates": 5,
            "maintenance_windows": [...],
            "priority_overrides": [...]
        }
    }
    
    # Call Scheduler Service API
    response = await scheduler_client.create_schedule(request)
    
    # Store schedule reference
    await self.store_schedule_reference(response.schedule_id)
    
    return response

# Scheduler Service (different service)
async def create_schedule(self, demand_request):
    """Create operational schedule from demands"""
    
    # Complex scheduling algorithm
    # - Time slot optimization
    # - Conflict resolution
    # - Resource allocation
    # - Notification scheduling
    
    return detailed_schedule
```

## Summary

The **ROS/GIS Integration Service** is responsible for:
1. Calculating water demands (WHAT and WHERE)
2. Spatial aggregation and optimization
3. Priority determination
4. Preparing data for scheduling

The **Scheduler Service** is responsible for:
1. Creating time-based schedules (WHEN)
2. Sequencing operations
3. Managing conflicts
4. Coordinating field operations

Together, they form a complete water management pipeline from demand calculation to field delivery.