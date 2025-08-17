# ROS/GIS Integration Service - Implementation Status

## Overview
The ROS/GIS Integration Service (Instance 18) has been implemented to bridge agricultural water requirements with hydraulic delivery capabilities. This service runs on port 3022 and provides a GraphQL API for complex queries and mutations.

## Service Details
- **Port**: 3022
- **Framework**: FastAPI with Strawberry GraphQL
- **Purpose**: Integrate crop water needs (ROS) with spatial data (GIS) for optimal water delivery

## Implemented Features

### 1. GraphQL API

#### Queries
- `section(id)` - Get detailed section information
- `sectionsByZone(zone)` - Get all sections in a zone
- `sectionPerformance(sectionId, weeks)` - Historical performance data
- `deliveryPoints()` - All delivery gates with served sections
- `gateMappings()` - Gate utilization and mappings
- `spatialMapping(sectionId)` - Spatial routing information
- `weeklyPerformanceSummary(week)` - Aggregated performance metrics
- `demandConflicts(week)` - Check for scheduling conflicts

#### Mutations
- `submitDemands(input)` - Submit weekly water demands
- `updateDeliveryFeedback(week, sectionId, deliveredM3, efficiency)` - Update performance
- `recalculatePriorities(week)` - Recalculate demand priorities
- `updateSectionMapping(sectionId, newGateId)` - Change delivery gate

### 2. Section-to-Gate Mapping System

**Features:**
- Spatial mapping of agricultural sections to delivery gates
- Support for many-to-one relationships (multiple sections per gate)
- Distance and travel time calculations
- Elevation-based gravity flow validation
- Dynamic gate reassignment capabilities

**Key Components:**
- `SpatialMappingService` - Core spatial operations
- Mock data for 16 sections across 4 zones
- Haversine distance calculations
- Travel time estimates based on flow velocity

### 3. Demand Aggregation Engine

**Features:**
- Groups section demands by delivery gate
- Weather-based adjustments (rainfall, ET)
- Weighted priority calculations
- Volume aggregation with loss estimates
- Conflict detection for over-allocation

**Key Components:**
- `DemandAggregatorService` - Aggregation logic
- Weather adjustment factors
- Rainfall reduction calculations (1mm ≈ 10m³/ha)
- Integration with scheduler service

### 4. Priority Resolution Engine

**Multi-factor Priority Calculation:**
- **Crop Stage Factor** (40% weight)
  - Flowering: 1.0 (critical)
  - Grain filling: 0.95
  - Vegetative: 0.7
  - Maturity: 0.5

- **Moisture Deficit Factor** (30% weight)
  - >50%: 1.0 (critical)
  - 35-50%: 0.85
  - 20-35%: 0.7
  - <20%: 0.5

- **Economic Value Factor** (20% weight)
  - Sugarcane: 0.9
  - Vegetables: 0.85
  - Rice: 0.8
  - Maize: 0.7

- **Stress Indicator Factor** (10% weight)
  - Critical: 1.0
  - Severe: 0.9
  - Moderate: 0.7
  - Mild: 0.5

### 5. Feedback Loop Manager

**Features:**
- Tracks actual delivery performance
- Updates ROS with water received
- Calculates delivery efficiency
- Manages deficit carry-forward
- Generates performance reports

**Key Components:**
- `FeedbackService` - Performance tracking
- Section performance history
- Weekly summary generation
- Integration with water accounting

### 6. Integration Client

**External Service Connections:**
- Flow Monitoring Service (port 3011)
- Scheduler Service (port 3021)
- ROS Service (port 3041) - mocked
- GIS Service (port 3040) - mocked
- Weather API - mocked

## REST API Compatibility

For services that cannot use GraphQL:
- GET `/api/v1/sections/{section_id}` - Section details
- GET `/api/v1/zones/{zone}/sections` - Sections by zone
- GET `/api/v1/status` - Service configuration

## Database Schema

### PostgreSQL Tables (Planned)
```sql
-- Sections table with PostGIS geometry
CREATE TABLE sections (
    section_id VARCHAR(50) PRIMARY KEY,
    zone INTEGER NOT NULL,
    area_hectares DECIMAL(10,2),
    crop_type VARCHAR(50),
    soil_type VARCHAR(50),
    elevation_m DECIMAL(6,2),
    delivery_gate VARCHAR(50),
    geometry GEOMETRY(Polygon, 4326),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Demands table
CREATE TABLE demands (
    demand_id SERIAL PRIMARY KEY,
    section_id VARCHAR(50) REFERENCES sections(section_id),
    week VARCHAR(8),
    volume_m3 DECIMAL(12,2),
    priority DECIMAL(3,1),
    priority_class VARCHAR(20),
    crop_type VARCHAR(50),
    growth_stage VARCHAR(50),
    created_at TIMESTAMP
);

-- Performance tracking
CREATE TABLE section_performance (
    performance_id SERIAL PRIMARY KEY,
    section_id VARCHAR(50) REFERENCES sections(section_id),
    week VARCHAR(8),
    planned_m3 DECIMAL(12,2),
    delivered_m3 DECIMAL(12,2),
    efficiency DECIMAL(3,2),
    deficit_m3 DECIMAL(12,2),
    created_at TIMESTAMP
);
```

## Configuration

Environment variables:
```env
# Service Configuration
SERVICE_NAME=ros-gis-integration
PORT=3022
ENVIRONMENT=development
LOG_LEVEL=INFO

# Database Connections
POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/munbon
REDIS_URL=redis://localhost:6379/2

# External Services
FLOW_MONITORING_URL=http://localhost:3011
SCHEDULER_URL=http://localhost:3021
ROS_SERVICE_URL=http://localhost:3041
GIS_SERVICE_URL=http://localhost:3040

# Mock Mode
USE_MOCK_SERVER=true
MOCK_SERVER_URL=http://localhost:3099

# Priority Weights
CROP_STAGE_WEIGHT=0.4
MOISTURE_DEFICIT_WEIGHT=0.3
ECONOMIC_VALUE_WEIGHT=0.2
STRESS_INDICATOR_WEIGHT=0.1
```

## Running the Service

1. Install dependencies:
```bash
cd services/ros-gis-integration
pip install -r requirements.txt
```

2. Start the service:
```bash
python src/main.py
```

3. Access endpoints:
- GraphQL Playground: http://localhost:3022/graphql
- Health: http://localhost:3022/health
- API Docs: http://localhost:3022/docs

## Testing

Run the test script:
```bash
python test_integration.py
```

This tests:
- GraphQL queries and mutations
- REST endpoint compatibility
- Mock server integration
- Priority calculations
- Demand aggregation

## Integration Points

### From ROS Service (Mocked)
- Crop types and growth stages
- Water requirements (mm/day)
- Stress indicators
- Growth calendars

### From GIS Service (Mocked)
- Section boundaries
- Elevation data
- Delivery mappings
- Soil types

### To Flow Monitoring
- Aggregated demands by gate
- Delivery priorities
- Performance feedback
- Schedule verification

### To Scheduler
- Weekly demand submissions
- Priority-sorted requirements
- Delivery windows
- Conflict notifications

## Key Achievements

1. **Unified GraphQL API**: Single endpoint for complex agricultural-hydraulic queries
2. **Smart Aggregation**: Groups demands efficiently by delivery infrastructure
3. **Multi-factor Priorities**: Balances crop needs, economics, and system constraints
4. **Feedback Integration**: Closes the loop between planned and actual deliveries
5. **Spatial Intelligence**: Understands physical relationships and constraints

## Next Steps

1. **Database Migration**: Move from mock data to PostgreSQL/PostGIS
2. **Real Service Integration**: Connect to actual ROS and GIS services
3. **Advanced Routing**: Implement graph-based delivery path optimization
4. **Machine Learning**: Add predictive demand forecasting
5. **Performance Optimization**: Implement caching and query optimization
6. **Thai Language Support**: Add localization for field teams

The service successfully bridges the gap between what farmers need (ROS) and what the irrigation system can deliver (hydraulics), providing the critical integration layer for optimal water distribution.