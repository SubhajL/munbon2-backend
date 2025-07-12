# Claude Instance 8: Water Planning BFF Service

## Scope of Work
This instance handles the Backend-for-Frontend service for water planning, irrigation scheduling, and water allocation planning.

## Assigned Components

### 1. **Water Planning BFF Service** (Primary)
- **Path**: `/services/bff-water-planning`
- **Port**: 4002
- **Responsibilities**:
  - Irrigation schedule planning
  - Water demand forecasting
  - Crop water requirement calculations
  - Water allocation optimization
  - Seasonal planning
  - What-if scenario analysis

### 2. **Planning Algorithms**
- **AquaCrop Integration**: Crop yield predictions
- **ET-based Planning**: Evapotranspiration calculations
- **Optimization Engine**: Water allocation algorithms
- **Scenario Manager**: Multiple planning scenarios

## Environment Setup

```bash
# Water Planning BFF Service
cat > services/bff-water-planning/.env.local << EOF
SERVICE_NAME=bff-water-planning
PORT=4002
NODE_ENV=development

# GraphQL Configuration
GRAPHQL_PATH=/graphql
GRAPHQL_PLAYGROUND=true
SUBSCRIPTION_ENDPOINT=/graphql/subscriptions

# Internal Services
ROS_SERVICE_URL=http://localhost:3047
GIS_SERVICE_URL=http://localhost:3007
WEATHER_SERVICE_URL=http://localhost:3006
MOISTURE_SERVICE_URL=http://localhost:3005
CROP_SERVICE_URL=http://localhost:3028
ANALYTICS_SERVICE_URL=http://localhost:3030

# Planning Configuration
PLANNING_HORIZON_DAYS=90
DEFAULT_IRRIGATION_EFFICIENCY=0.85
WATER_STRESS_THRESHOLD=0.30
PLANNING_TIME_STEP_HOURS=24

# AquaCrop Integration
AQUACROP_API_URL=http://localhost:5000
AQUACROP_MODEL_VERSION=7.0

# Optimization Parameters
MAX_OPTIMIZATION_TIME_SECONDS=300
OPTIMIZATION_ALGORITHM=GENETIC
GA_POPULATION_SIZE=100
GA_GENERATIONS=50

# Redis Cache
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=10
CACHE_TTL_PLANNING=3600  # 1 hour
CACHE_TTL_FORECAST=1800  # 30 minutes

# Database
DB_HOST=localhost
DB_PORT=5434
DB_NAME=munbon_planning
DB_USER=postgres
DB_PASSWORD=postgres123
EOF
```

## GraphQL Schema

```graphql
type Query {
  # Current Plans
  getActiveIrrigationPlan(zoneId: ID!): IrrigationPlan!
  getWaterAllocationPlan(date: Date!): WaterAllocationPlan!
  getCropWaterRequirements(zoneId: ID!, dateRange: DateRangeInput!): [CropWaterRequirement!]!
  
  # Forecasting
  predictWaterDemand(input: WaterDemandForecastInput!): WaterDemandForecast!
  predictCropYield(input: CropYieldPredictionInput!): CropYieldPrediction!
  getWeatherForecast(location: LocationInput!, days: Int!): WeatherForecast!
  
  # Analysis
  analyzeWaterBalance(zoneId: ID!, period: PeriodInput!): WaterBalanceAnalysis!
  compareScenarios(scenarioIds: [ID!]!): ScenarioComparison!
  getOptimalSchedule(constraints: ScheduleConstraintsInput!): OptimalSchedule!
}

type Mutation {
  # Planning Operations
  createIrrigationPlan(input: IrrigationPlanInput!): IrrigationPlan!
  updateIrrigationPlan(id: ID!, updates: IrrigationPlanUpdateInput!): IrrigationPlan!
  approveIrrigationPlan(id: ID!, approverNotes: String): IrrigationPlan!
  
  # Scenario Management
  createScenario(input: ScenarioInput!): Scenario!
  runScenarioSimulation(scenarioId: ID!): SimulationResult!
  compareScenarios(baseId: ID!, compareIds: [ID!]!): ComparisonResult!
  
  # Optimization
  optimizeWaterAllocation(input: OptimizationInput!): OptimizationResult!
  optimizeIrrigationSchedule(input: ScheduleOptimizationInput!): ScheduleOptimizationResult!
  
  # Crop Planning
  planCropRotation(input: CropRotationInput!): CropRotationPlan!
  adjustCropCalendar(input: CropCalendarAdjustmentInput!): CropCalendar!
}

type Subscription {
  planningProgress(planId: ID!): PlanningProgress!
  optimizationStatus(taskId: ID!): OptimizationStatus!
  waterDemandUpdates(zoneId: ID!): WaterDemandUpdate!
}

# Complex Types
type IrrigationPlan {
  id: ID!
  zoneId: ID!
  status: PlanStatus!
  startDate: Date!
  endDate: Date!
  schedules: [IrrigationSchedule!]!
  totalWaterRequired: Float!
  totalAreaCovered: Float!
  expectedYield: YieldPrediction!
  approvals: [Approval!]!
}

type WaterDemandForecast {
  period: Period!
  totalDemand: Float!
  demandByZone: [ZoneDemand!]!
  demandByCrop: [CropDemand!]!
  confidenceInterval: ConfidenceInterval!
  assumptions: [Assumption!]!
}

type OptimizationResult {
  id: ID!
  status: OptimizationStatus!
  objective: Float!
  allocation: [WaterAllocation!]!
  constraints: [ConstraintStatus!]!
  iterations: Int!
  computeTime: Float!
}
```

## Planning Workflows

### 1. Seasonal Planning Flow
```javascript
async function createSeasonalPlan(season, year) {
  // Step 1: Get crop calendar
  const cropCalendar = await cropService.getSeasonalCalendar(season, year);
  
  // Step 2: Calculate water requirements
  const waterRequirements = await calculateSeasonalWaterDemand(
    cropCalendar,
    await weatherService.getHistoricalData(season)
  );
  
  // Step 3: Check water availability
  const waterAvailability = await getWaterAvailabilityForecast(season);
  
  // Step 4: Optimize allocation
  const optimization = await optimizeWaterAllocation({
    demand: waterRequirements,
    supply: waterAvailability,
    priorities: await getPriorityMatrix()
  });
  
  // Step 5: Generate schedules
  const schedules = await generateIrrigationSchedules(optimization);
  
  return {
    season,
    year,
    cropCalendar,
    waterRequirements,
    allocation: optimization,
    schedules
  };
}
```

### 2. Daily Planning Update
```javascript
async function updateDailyPlan(date) {
  // Get current conditions
  const [weather, moisture, waterLevels] = await Promise.all([
    weatherService.getCurrentWeather(),
    moistureService.getFieldMoisture(),
    waterLevelService.getCurrentLevels()
  ]);
  
  // Recalculate requirements
  const adjustedDemand = await recalculateWaterDemand({
    weather,
    moisture,
    date
  });
  
  // Adjust schedules
  const updatedSchedules = await adjustSchedules(
    adjustedDemand,
    waterLevels
  );
  
  // Notify affected farmers
  await notifyScheduleChanges(updatedSchedules);
  
  return updatedSchedules;
}
```

## Planning Algorithms

### ET-Based Planning
```javascript
function calculateETBasedDemand(crop, stage, weather) {
  const eto = calculatePenmanMonteith(weather);
  const kc = getCropCoefficient(crop, stage);
  const etc = eto * kc;
  
  // Adjust for rainfall
  const effectiveRainfall = weather.rainfall * 0.8;
  const netIrrigation = Math.max(0, etc - effectiveRainfall);
  
  // Account for efficiency
  const grossIrrigation = netIrrigation / IRRIGATION_EFFICIENCY;
  
  return {
    eto,
    kc,
    etc,
    netIrrigation,
    grossIrrigation
  };
}
```

### Water Allocation Optimization
```javascript
async function optimizeAllocation(demand, supply, constraints) {
  const model = {
    objective: 'maximize_coverage',
    variables: createDecisionVariables(demand),
    constraints: [
      waterAvailabilityConstraint(supply),
      minimumAllocationConstraint(),
      priorityConstraint(),
      ...constraints
    ]
  };
  
  // Run genetic algorithm
  const result = await runGeneticAlgorithm(model, {
    populationSize: 100,
    generations: 50,
    crossoverRate: 0.8,
    mutationRate: 0.1
  });
  
  return result;
}
```

## API Endpoints

### Planning Endpoints
```
POST /graphql - Main GraphQL endpoint
GET /api/v1/planning/templates/{type} - Planning templates
GET /api/v1/planning/export/{planId} - Export plan as PDF/Excel
POST /api/v1/planning/import - Import planning data
GET /api/v1/planning/reports/{type} - Planning reports
```

## Current Status
- ❌ Service structure: Not created
- ❌ Planning algorithms: Not implemented
- ❌ AquaCrop integration: Not connected
- ❌ Optimization engine: Not built
- ❌ Scenario manager: Not implemented

## Priority Tasks
1. Set up GraphQL service with Apollo
2. Implement ET-based planning algorithms
3. Build water demand forecasting
4. Create optimization engine
5. Integrate AquaCrop model
6. Build scenario comparison tools
7. Implement planning templates
8. Create planning dashboard components

## Testing Commands

```bash
# Create irrigation plan
curl -X POST http://localhost:4002/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { createIrrigationPlan(input: { zoneId: \"Z1\", startDate: \"2024-07-15\", endDate: \"2024-10-15\", cropType: \"RICE\" }) { id totalWaterRequired schedules { date volume } } }"
  }'

# Get water demand forecast
curl -X POST http://localhost:4002/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query { predictWaterDemand(input: { zoneId: \"Z1\", days: 30 }) { totalDemand demandByZone { zoneId demand } } }"
  }'

# Run optimization
curl -X POST http://localhost:4002/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { optimizeWaterAllocation(input: { availableWater: 1000000, zones: [\"Z1\", \"Z2\"], method: \"GENETIC\" }) { allocation { zoneId volume } } }"
  }'
```

## Integration Points

### With ROS Service
```javascript
// Get ETo calculations
const eto = await rosService.calculateETo(location, date);
const cropWaterReq = await rosService.getCropWaterRequirement(crop, stage);
```

### With Weather Service
```javascript
// Get weather forecast for planning
const forecast = await weatherService.getForecast(location, days);
const historicalPattern = await weatherService.getHistoricalPattern(month);
```

### With Analytics Service
```javascript
// Get historical efficiency data
const efficiency = await analyticsService.getIrrigationEfficiency(zoneId);
const yieldData = await analyticsService.getHistoricalYield(crop, zone);
```

## Notes for Development
- Cache planning results aggressively
- Implement async optimization jobs
- Support multiple planning scenarios
- Provide planning templates
- Add uncertainty quantification
- Support collaborative planning
- Implement approval workflows
- Generate planning reports automatically