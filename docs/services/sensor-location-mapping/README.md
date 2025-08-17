# Sensor Location Mapping Service

This service maps sensor locations to Munbon irrigation zones/sections and validates water levels against crop requirements.

## Features

- Map sensor GPS coordinates to irrigation zones and sections
- Retrieve sensor data by zone/section
- Validate water levels against crop water requirements
- Dashboard API for monitoring water status across zones
- Support for both water level and moisture sensors

## Setup

```bash
cd services/sensor-location-mapping
npm install
npm run dev
```

## Environment Variables

### Local Development
```env
# Both databases on EC2 (consolidated to port 5432)
TIMESCALE_HOST=43.209.22.250
TIMESCALE_PORT=5432
TIMESCALE_DB=sensor_data
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=postgres123

POSTGIS_HOST=43.209.22.250
POSTGIS_PORT=5432
POSTGIS_DB=gis_db
POSTGIS_USER=postgres
POSTGIS_PASSWORD=postgres123

PORT=3018
```

### Production (EC2)
```env
# Both databases on localhost (from EC2's perspective)
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5432
TIMESCALE_DB=sensor_data
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=postgres123

POSTGIS_HOST=localhost
POSTGIS_PORT=5432
POSTGIS_DB=gis_db
POSTGIS_USER=postgres
POSTGIS_PASSWORD=postgres123

PORT=3018
```

## Deployment to EC2

```bash
# Deploy to EC2
./deploy-to-ec2.sh

# Check service status on EC2
ssh -i ~/dev/th-lab01.pem ubuntu@43.209.22.250 "pm2 status sensor-location-mapping"

# View logs
ssh -i ~/dev/th-lab01.pem ubuntu@43.209.22.250 "pm2 logs sensor-location-mapping"

# Restart service
ssh -i ~/dev/th-lab01.pem ubuntu@43.209.22.250 "pm2 restart sensor-location-mapping"
```

## API Endpoints

### Sensor Mapping

- `POST /api/v1/sensors/map-location` - Map sensor to zone/section
- `GET /api/v1/zones/:zoneCode/sensors` - Get all sensors in a zone
- `GET /api/v1/sections/:sectionCode/sensors` - Get sensors by section
- `PUT /api/v1/sensors/:sensorId/location` - Update sensor location
- `GET /api/v1/sensors/:sensorId/readings` - Get recent sensor readings

### Water Validation

- `POST /api/v1/zones/:zoneCode/validate-water` - Validate water levels
- `GET /api/v1/zones/requiring-attention` - Get zones needing attention
- `POST /api/v1/zones/validate-multiple` - Validate multiple zones

### Dashboard

- `GET /api/v1/dashboard/overview` - System overview
- `GET /api/v1/dashboard/zone-summary` - Zone sensor coverage
- `GET /api/v1/dashboard/water-status` - Real-time water status
- `GET /api/v1/dashboard/sensor-map` - Sensor location data

## Example Usage

### Local Development
```bash
# Map Sensor to Zone
curl -X POST http://localhost:3018/api/v1/sensors/map-location \
  -H "Content-Type: application/json" \
  -d '{
    "sensorId": "AWD-B7E6",
    "lat": 14.123456,
    "lng": 102.654321
  }'

# Validate Water Level
curl -X POST http://localhost:3018/api/v1/zones/Z1/validate-water \
  -H "Content-Type: application/json" \
  -d '{
    "cropType": "rice",
    "cropWeek": 3
  }'

# Get Dashboard Overview
curl http://localhost:3018/api/v1/dashboard/overview
```

### Production (EC2)
```bash
# Map Sensor to Zone
curl -X POST http://43.209.22.250:3018/api/v1/sensors/map-location \
  -H "Content-Type: application/json" \
  -d '{
    "sensorId": "AWD-B7E6",
    "lat": 14.123456,
    "lng": 102.654321
  }'

# Validate Water Level
curl -X POST http://43.209.22.250:3018/api/v1/zones/Z1/validate-water \
  -H "Content-Type: application/json" \
  -d '{
    "cropType": "rice",
    "cropWeek": 3
  }'

# Get Dashboard Overview
curl http://43.209.22.250:3018/api/v1/dashboard/overview
```

## Integration Points

- **TimescaleDB**: Reads sensor data and locations
- **PostGIS**: Maps coordinates to zones/sections using spatial queries
- **ROS Service**: Would integrate for actual crop water requirements

## Notes

- Currently uses simplified crop water requirements
- In production, would integrate with ROS water demand service
- Sensor locations are fetched from TimescaleDB sensor_registry table
- Zone boundaries are stored in PostGIS irrigation_zones table