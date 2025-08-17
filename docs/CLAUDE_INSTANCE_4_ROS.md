# Claude Instance 4: ROS Service

## Scope of Work
This instance handles Royal Irrigation Office Service (ROS) calculations for water demand, crop coefficients, and irrigation scheduling.

## Assigned Services

### 1. **ROS Service** (Primary)
- **Path**: `/services/ros`
- **Port**: 3047
- **Responsibilities**:
  - Water demand calculations
  - Crop coefficient (Kc) management
  - Reference evapotranspiration (ETo)
  - Irrigation scheduling algorithms
  - Integration with weather data

### 2. **Crop Management Integration**
- **Path**: `/services/ros/src/models/crops`
- **Responsibilities**:
  - Crop database management
  - Growth stage tracking
  - Water requirements by crop type
  - Seasonal adjustments

### 3. **Weather Data Integration**
- **Path**: `/services/ros/src/integrations/weather`
- **Responsibilities**:
  - Fetch weather data for ETo
  - Process meteorological parameters
  - Historical weather analysis

## Environment Setup

```bash
# Copy this to start your instance
cd /Users/subhajlimanond/dev/munbon2-backend

# Create ROS service directory if not exists
mkdir -p services/ros

# Set up environment file
cat > services/ros/.env.local << EOF
# ROS Service Configuration
SERVICE_NAME=ros-service
PORT=3047
NODE_ENV=development

# Database
DB_HOST=localhost
DB_PORT=5434
DB_NAME=munbon_ros
DB_USER=postgres
DB_PASSWORD=postgres123

# Weather Service
WEATHER_SERVICE_URL=http://localhost:3006
TMD_API_KEY=your-tmd-key

# GIS Service
GIS_SERVICE_URL=http://localhost:3007

# Calculation Parameters
DEFAULT_EFFICIENCY=0.85
SOIL_MOISTURE_THRESHOLD=0.3
MAX_IRRIGATION_HOURS=8

# Redis Cache
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=4
EOF
```

## Key Algorithms

### 1. ETo Calculation (Penman-Monteith)
```javascript
// FAO Penman-Monteith equation
ETo = (0.408 * Δ * (Rn - G) + γ * (900/(T + 273)) * u2 * (es - ea)) / 
      (Δ + γ * (1 + 0.34 * u2))

Where:
- Δ = Slope of saturation vapor pressure curve
- Rn = Net radiation
- G = Soil heat flux
- γ = Psychrometric constant
- T = Temperature
- u2 = Wind speed at 2m
- es = Saturation vapor pressure
- ea = Actual vapor pressure
```

### 2. Water Demand
```javascript
WaterDemand = (ETo * Kc * Area) / Efficiency

Where:
- ETo = Reference evapotranspiration
- Kc = Crop coefficient
- Area = Cultivation area
- Efficiency = Irrigation system efficiency
```

## Crop Coefficients Database
```sql
CREATE TABLE crop_coefficients (
    id SERIAL PRIMARY KEY,
    crop_type VARCHAR(100),
    growth_stage VARCHAR(50),
    kc_value DECIMAL(3,2),
    days_in_stage INTEGER,
    total_growing_days INTEGER
);

-- Example data
INSERT INTO crop_coefficients VALUES 
('Rice', 'Initial', 1.05, 30, 120),
('Rice', 'Development', 1.20, 30, 120),
('Rice', 'Mid-season', 1.20, 40, 120),
('Rice', 'Late season', 0.90, 20, 120);
```

## Current Status
- ✅ Basic service structure
- ✅ Database schema defined
- ⚠️ ETo calculation: Partial implementation
- ❌ Crop coefficient management: Not started
- ❌ API endpoints: Not implemented
- ❌ Weather integration: Not connected
- ❌ Scheduling algorithm: Not implemented

## Priority Tasks
1. Implement Penman-Monteith ETo calculation
2. Create crop coefficient management system
3. Build water demand calculation endpoint
4. Integrate with weather service
5. Implement irrigation scheduling algorithm
6. Add bulk calculation for zones
7. Create reporting endpoints

## API Endpoints to Implement
```
# ETo Calculation
POST /api/v1/eto/calculate
GET /api/v1/eto/daily?date={date}&location={lat,lng}

# Crop Management
GET /api/v1/crops
GET /api/v1/crops/{cropId}/kc?stage={stage}
POST /api/v1/crops/{cropId}/schedule

# Water Demand
POST /api/v1/demand/calculate
GET /api/v1/demand/parcel/{parcelId}
GET /api/v1/demand/zone/{zoneId}

# Irrigation Schedule
POST /api/v1/schedule/generate
GET /api/v1/schedule/zone/{zoneId}/today
PUT /api/v1/schedule/{scheduleId}/execute
```

## Testing Commands
```bash
# Calculate ETo
curl -X POST http://localhost:3047/api/v1/eto/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "temperature": 28,
    "humidity": 75,
    "windSpeed": 2.5,
    "radiation": 20,
    "latitude": 14.88,
    "date": "2024-07-08"
  }'

# Get water demand for parcel
curl http://localhost:3047/api/v1/demand/parcel/P12345

# Generate irrigation schedule
curl -X POST http://localhost:3047/api/v1/schedule/generate \
  -H "Content-Type: application/json" \
  -d '{
    "zoneId": "Z1",
    "date": "2024-07-08",
    "availableWater": 1000000
  }'
```

## Key Files to Create
```
services/ros/
├── src/
│   ├── routes/
│   │   ├── eto.routes.ts
│   │   ├── crop.routes.ts
│   │   ├── demand.routes.ts
│   │   └── schedule.routes.ts
│   ├── services/
│   │   ├── eto.service.ts
│   │   ├── crop.service.ts
│   │   ├── demand.service.ts
│   │   └── schedule.service.ts
│   ├── models/
│   │   ├── crop.model.ts
│   │   ├── eto.model.ts
│   │   └── schedule.model.ts
│   └── utils/
│       ├── calculations.ts
│       └── constants.ts
```

## Integration Points
```javascript
// Weather data from weather service
const weatherData = await weatherService.getDaily(date, location);

// Parcel data from GIS service
const parcelInfo = await gisService.getParcel(parcelId);

// Send schedule to water control
await waterControlService.executeSchedule(schedule);
```

## Notes for Development
- Use scientific formulas from FAO-56 document
- Cache ETo calculations (changes slowly)
- Validate all input parameters
- Handle missing weather data gracefully
- Support multiple crop types per parcel
- Consider soil moisture in calculations
- Add safety margins to water demand
- Implement priority-based scheduling