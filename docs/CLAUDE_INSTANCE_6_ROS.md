# Claude Instance 6: ROS Service

## Scope of Work
This instance handles Royal Irrigation Office Service (ROS) calculations for water demand, crop coefficients, evapotranspiration, and irrigation scheduling.

## Assigned Components

### 1. **ROS Service** (Primary)
- **Path**: `/services/ros`
- **Port**: 3047
- **Responsibilities**:
  - Reference evapotranspiration (ETo) calculation
  - Crop coefficient (Kc) management
  - Water demand calculations
  - Irrigation scheduling algorithms
  - Crop calendar management
  - Water balance calculations

### 2. **Crop Management Module**
- **Path**: `/services/ros/src/modules/crop-management`
- **Responsibilities**:
  - Crop database with growth stages
  - Kc values by growth stage
  - Root depth progression
  - Critical depletion factors
  - Yield response factors

### 3. **Weather Integration**
- **Path**: `/services/ros/src/integrations/weather`
- **Responsibilities**:
  - Fetch weather data for ETo
  - Calculate solar radiation
  - Compute vapor pressure deficit
  - Wind speed adjustments

## Environment Setup

```bash
# ROS Service
cat > services/ros/.env.local << EOF
SERVICE_NAME=ros-service
PORT=3047
NODE_ENV=development

# Database
DB_HOST=localhost
DB_PORT=5434
DB_NAME=munbon_ros
DB_USER=postgres
DB_PASSWORD=postgres123

# Calculation Parameters
DEFAULT_ALTITUDE=200  # meters above sea level
DEFAULT_LATITUDE=14.88  # degrees
DEFAULT_LONGITUDE=102.02  # degrees
PSYCHROMETRIC_CONSTANT=0.665  # kPa/°C

# Irrigation Efficiency
SURFACE_IRRIGATION_EFFICIENCY=0.65
SPRINKLER_EFFICIENCY=0.85
DRIP_EFFICIENCY=0.95
DEFAULT_EFFICIENCY=0.65

# Soil Parameters
DEFAULT_SOIL_TYPE=clay_loam
FIELD_CAPACITY=0.35  # volumetric
WILTING_POINT=0.15   # volumetric
TOTAL_AVAILABLE_WATER=200  # mm/m

# Management Allowed Depletion (MAD)
MAD_VEGETABLES=0.50
MAD_GRAIN_CROPS=0.55
MAD_RICE=0.20
MAD_DEFAULT=0.50

# External Services
WEATHER_SERVICE_URL=http://localhost:3006
GIS_SERVICE_URL=http://localhost:3007
MOISTURE_SERVICE_URL=http://localhost:3005

# Redis Cache
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=4
CACHE_TTL_ETO=3600  # 1 hour
CACHE_TTL_KC=86400  # 24 hours
EOF
```

## Database Schema

```sql
-- Crop types and characteristics
CREATE TABLE crop_types (
    id SERIAL PRIMARY KEY,
    crop_code VARCHAR(20) UNIQUE NOT NULL,
    crop_name_en VARCHAR(100),
    crop_name_th VARCHAR(100),
    crop_group VARCHAR(50),  -- 'cereal', 'vegetable', 'fruit', 'other'
    total_growing_days INTEGER,
    mad_fraction DECIMAL(3,2),  -- Management Allowed Depletion
    yield_response_factor DECIMAL(3,2),  -- Ky
    max_root_depth_m DECIMAL(3,2)
);

-- Crop growth stages
CREATE TABLE crop_stages (
    id SERIAL PRIMARY KEY,
    crop_code VARCHAR(20) REFERENCES crop_types(crop_code),
    stage_name VARCHAR(50),  -- 'initial', 'development', 'mid', 'late'
    stage_order INTEGER,
    duration_days INTEGER,
    kc_value DECIMAL(3,2),
    root_depth_fraction DECIMAL(3,2),
    critical_depletion DECIMAL(3,2)
);

-- ETo calculations log
CREATE TABLE eto_calculations (
    id SERIAL PRIMARY KEY,
    calculation_date DATE,
    location GEOGRAPHY(POINT, 4326),
    altitude_m REAL,
    tmin REAL,
    tmax REAL,
    tmean REAL,
    rhmin REAL,
    rhmax REAL,
    wind_speed_2m REAL,
    solar_radiation REAL,
    eto_value REAL,
    method VARCHAR(50),  -- 'penman-monteith', 'hargreaves'
    created_at TIMESTAMP DEFAULT NOW()
);

-- Water demand calculations
CREATE TABLE water_demand_calculations (
    id SERIAL PRIMARY KEY,
    parcel_id VARCHAR(50),
    field_id VARCHAR(50),
    calculation_date DATE,
    crop_code VARCHAR(20),
    growth_stage VARCHAR(50),
    area_rai DECIMAL(10,2),
    eto REAL,
    kc REAL,
    etc REAL,  -- ETc = ETo × Kc
    effective_rainfall REAL,
    soil_moisture_depletion REAL,
    net_irrigation_requirement REAL,
    gross_irrigation_requirement REAL,
    irrigation_efficiency DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Irrigation schedules
CREATE TABLE irrigation_schedules (
    id SERIAL PRIMARY KEY,
    zone_id VARCHAR(20),
    schedule_date DATE,
    total_water_required_m3 DECIMAL(15,2),
    available_water_m3 DECIMAL(15,2),
    priority_algorithm VARCHAR(50),
    status VARCHAR(20),  -- 'draft', 'approved', 'executing', 'completed'
    created_at TIMESTAMP DEFAULT NOW()
);

-- Crop calendar
CREATE TABLE crop_calendar (
    id SERIAL PRIMARY KEY,
    zone_id VARCHAR(20),
    parcel_id VARCHAR(50),
    crop_code VARCHAR(20),
    planting_date DATE,
    expected_harvest_date DATE,
    actual_harvest_date DATE,
    season VARCHAR(20),  -- 'wet', 'dry'
    year INTEGER
);

-- Sample crop data
INSERT INTO crop_types (crop_code, crop_name_en, crop_name_th, crop_group, total_growing_days, mad_fraction, yield_response_factor, max_root_depth_m) VALUES
('RICE_WET', 'Rice (Wet Season)', 'ข้าวนาปี', 'cereal', 120, 0.20, 1.00, 0.60),
('RICE_DRY', 'Rice (Dry Season)', 'ข้าวนาปรัง', 'cereal', 110, 0.20, 1.00, 0.60),
('CORN', 'Corn', 'ข้าวโพด', 'cereal', 125, 0.55, 1.25, 1.00),
('SUGARCANE', 'Sugarcane', 'อ้อย', 'other', 365, 0.65, 1.20, 1.20);

-- Rice growth stages
INSERT INTO crop_stages (crop_code, stage_name, stage_order, duration_days, kc_value, root_depth_fraction, critical_depletion) VALUES
('RICE_WET', 'initial', 1, 30, 1.05, 0.10, 0.50),
('RICE_WET', 'development', 2, 30, 1.20, 0.50, 0.30),
('RICE_WET', 'mid', 3, 40, 1.20, 1.00, 0.20),
('RICE_WET', 'late', 4, 20, 0.90, 1.00, 0.20);
```

## Core Algorithms

### 1. FAO Penman-Monteith ETo
```javascript
function calculateETo(weatherData, location) {
  const {
    tmin, tmax, rhmin, rhmax,
    wind2m, solarRad, altitude, latitude
  } = weatherData;
  
  // Temperature
  const tmean = (tmin + tmax) / 2;
  
  // Saturation vapor pressure
  const es = (svp(tmin) + svp(tmax)) / 2;
  
  // Actual vapor pressure
  const ea = (svp(tmin) * rhmax/100 + svp(tmax) * rhmin/100) / 2;
  
  // Slope of saturation vapor pressure curve
  const delta = 4098 * svp(tmean) / Math.pow(tmean + 237.3, 2);
  
  // Psychrometric constant
  const P = 101.3 * Math.pow((293 - 0.0065 * altitude) / 293, 5.26);
  const gamma = 0.665e-3 * P;
  
  // Net radiation
  const Rn = solarRad * 0.77;  // Assuming albedo = 0.23
  
  // Soil heat flux (daily = 0)
  const G = 0;
  
  // ETo calculation
  const numerator = 0.408 * delta * (Rn - G) + 
                   gamma * (900 / (tmean + 273)) * wind2m * (es - ea);
  const denominator = delta + gamma * (1 + 0.34 * wind2m);
  
  return numerator / denominator;
}

// Saturation vapor pressure
function svp(temp) {
  return 0.6108 * Math.exp(17.27 * temp / (temp + 237.3));
}
```

### 2. Water Demand Calculation
```javascript
async function calculateWaterDemand(parcelId, date) {
  // Get parcel info
  const parcel = await gisService.getParcel(parcelId);
  
  // Get crop and growth stage
  const cropInfo = await getCropInfo(parcelId, date);
  const growthStage = calculateGrowthStage(cropInfo.plantingDate, date);
  
  // Get weather data and calculate ETo
  const weather = await weatherService.getDaily(date, parcel.location);
  const eto = calculateETo(weather, parcel.location);
  
  // Get Kc for current growth stage
  const kc = await getKc(cropInfo.cropCode, growthStage);
  
  // Calculate ETc
  const etc = eto * kc;
  
  // Get effective rainfall
  const rainfall = await getEffectiveRainfall(date, parcel.location);
  
  // Get soil moisture
  const moisture = await moistureService.getFieldMoisture(parcel.fieldId);
  const depletion = calculateDepletion(moisture, cropInfo.soilType);
  
  // Net irrigation requirement
  const netIrrigation = Math.max(0, etc - rainfall + depletion);
  
  // Gross irrigation requirement
  const efficiency = getIrrigationEfficiency(parcel.irrigationType);
  const grossIrrigation = netIrrigation / efficiency;
  
  return {
    eto,
    kc,
    etc,
    effectiveRainfall: rainfall,
    soilMoistureDepletion: depletion,
    netIrrigation,
    grossIrrigation,
    efficiency,
    waterVolume: grossIrrigation * parcel.area * 1600 / 1000  // m³
  };
}
```

### 3. Irrigation Scheduling
```javascript
async function generateIrrigationSchedule(zoneId, date, availableWater) {
  // Get all parcels in zone
  const parcels = await gisService.getParcelsInZone(zoneId);
  
  // Calculate water demand for each parcel
  const demands = await Promise.all(
    parcels.map(p => calculateWaterDemand(p.id, date))
  );
  
  // Sort by priority (stress level, crop value, etc.)
  const prioritized = prioritizeParcels(parcels, demands);
  
  // Allocate water
  const schedule = allocateWater(prioritized, availableWater);
  
  return {
    zoneId,
    date,
    totalDemand: demands.reduce((sum, d) => sum + d.waterVolume, 0),
    availableWater,
    allocations: schedule,
    deficitParcels: schedule.filter(s => s.allocated < s.required)
  };
}

// Priority algorithms
function prioritizeParcels(parcels, demands) {
  return parcels.map((p, i) => ({
    ...p,
    demand: demands[i],
    priority: calculatePriority(p, demands[i])
  })).sort((a, b) => b.priority - a.priority);
}

function calculatePriority(parcel, demand) {
  const stressFactor = demand.soilMoistureDepletion / 0.5;  // MAD
  const cropValue = getCropValue(parcel.cropType);
  const growthStage = getGrowthStageSensitivity(parcel.cropStage);
  
  return stressFactor * 0.5 + cropValue * 0.3 + growthStage * 0.2;
}
```

## Current Status
- ✅ Database schema designed
- ✅ Basic service structure
- ⚠️ ETo calculation: Algorithm ready, not implemented
- ❌ Kc management: Not implemented
- ❌ Water demand calculation: Not implemented
- ❌ Irrigation scheduling: Not implemented
- ❌ API endpoints: Not created

## Priority Tasks
1. Implement Penman-Monteith ETo calculation
2. Create crop coefficient management system
3. Build water demand calculation engine
4. Implement irrigation scheduling algorithms
5. Create API endpoints for all calculations
6. Add crop calendar management
7. Build water balance tracking
8. Implement priority-based allocation

## API Endpoints

### ETo Calculation
```
POST /api/v1/ros/eto/calculate
GET /api/v1/ros/eto/daily?date={}&lat={}&lng={}
GET /api/v1/ros/eto/history?start={}&end={}&location={}

### Crop Management
GET /api/v1/ros/crops
GET /api/v1/ros/crops/{cropCode}
GET /api/v1/ros/crops/{cropCode}/stages
GET /api/v1/ros/crops/{cropCode}/kc?stage={}

### Water Demand
POST /api/v1/ros/demand/calculate
GET /api/v1/ros/demand/parcel/{parcelId}?date={}
GET /api/v1/ros/demand/zone/{zoneId}?date={}
GET /api/v1/ros/demand/forecast?days=7

### Irrigation Scheduling
POST /api/v1/ros/schedule/generate
GET /api/v1/ros/schedule/zone/{zoneId}/current
PUT /api/v1/ros/schedule/{scheduleId}/approve
GET /api/v1/ros/schedule/{scheduleId}/execution

### Crop Calendar
GET /api/v1/ros/calendar/zone/{zoneId}
POST /api/v1/ros/calendar/planting
PUT /api/v1/ros/calendar/{id}/harvest
```

## Testing Commands

```bash
# Calculate ETo
curl -X POST http://localhost:3047/api/v1/ros/eto/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2024-07-08",
    "location": {"lat": 14.88, "lng": 102.02},
    "weather": {
      "tmin": 22, "tmax": 35,
      "rhmin": 60, "rhmax": 85,
      "wind2m": 2.5,
      "solarRad": 22.5
    }
  }'

# Get water demand for parcel
curl http://localhost:3047/api/v1/ros/demand/parcel/P12345?date=2024-07-08

# Generate irrigation schedule
curl -X POST http://localhost:3047/api/v1/ros/schedule/generate \
  -H "Content-Type: application/json" \
  -d '{
    "zoneId": "Z1",
    "date": "2024-07-08",
    "availableWater": 500000
  }'

# Get crop Kc values
curl http://localhost:3047/api/v1/ros/crops/RICE_WET/kc?stage=mid
```

## Integration Requirements

### From Weather Service (Instance 1)
```javascript
interface WeatherDataForETo {
  tmin: number;          // °C
  tmax: number;          // °C
  rhmin: number;         // %
  rhmax: number;         // %
  wind2m: number;        // m/s at 2m height
  solarRadiation: number; // MJ/m²/day
  rainfall: number;      // mm
}
```

### From Moisture Service (Instance 3)
```javascript
interface SoilMoistureForROS {
  fieldId: string;
  rootZoneMoisture: number;  // %
  fieldCapacity: number;     // %
  wiltingPoint: number;      // %
  currentDepletion: number;  // mm
}
```

### From GIS Service (Instance 4)
```javascript
interface ParcelDataForROS {
  parcelId: string;
  area: number;         // rai
  cropType: string;
  plantingDate: Date;
  soilType: string;
  irrigationType: string;
  location: {
    lat: number;
    lng: number;
    altitude: number;
  };
}
```

## Notes for Development
- Use FAO-56 document as reference
- Cache ETo calculations (weather-dependent)
- Support multiple calculation methods
- Handle missing weather data gracefully
- Implement seasonal Kc adjustments
- Consider local calibration factors
- Add water stress coefficients
- Support deficit irrigation strategies