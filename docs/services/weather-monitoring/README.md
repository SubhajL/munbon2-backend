# Weather Monitoring Service

This microservice provides comprehensive weather data exposure and analysis for the Munbon Irrigation Control System. It reads weather data from multiple sources (TMD, AOS, OpenWeather) and provides real-time updates, forecasts, analytics, and irrigation recommendations.

## Features

- **Multi-source Weather Data**: Integrates data from Thai Meteorological Department (TMD), Aeronautical Observation Stations (AOS), and other sources
- **Real-time Updates**: WebSocket and MQTT support for live weather data streaming
- **Weather Analytics**: Trend analysis, anomaly detection, and comparative analytics
- **Irrigation Recommendations**: Smart irrigation suggestions based on weather conditions and crop requirements
- **Evapotranspiration Calculations**: Uses Penman-Monteith equation for accurate ET calculations
- **Alert System**: Automated alerts for extreme weather conditions
- **Dual Database Support**: Reads from both TimescaleDB (AOS data) and PostgreSQL (other sources)

## API Endpoints

### Weather Data
- `GET /api/v1/weather/current` - Get current weather readings
- `GET /api/v1/weather/historical` - Get historical weather data
- `GET /api/v1/weather/aggregated` - Get aggregated weather statistics
- `GET /api/v1/weather/stations` - List weather stations
- `GET /api/v1/weather/forecast` - Get weather forecasts

### Analytics
- `GET /api/v1/weather/analytics` - Get weather analytics for a location
- `GET /api/v1/weather/analytics/trends` - Get weather trends
- `GET /api/v1/weather/analytics/anomalies` - Detect weather anomalies
- `POST /api/v1/weather/analytics/comparison` - Compare weather between locations
- `GET /api/v1/weather/evapotranspiration` - Calculate ET for irrigation

### Irrigation
- `GET /api/v1/weather/irrigation/recommendation` - Get irrigation recommendations
- `GET /api/v1/weather/irrigation/schedule` - Generate irrigation schedule
- `GET /api/v1/weather/irrigation/water-balance` - Analyze water balance

### Alerts
- `GET /api/v1/weather/alerts` - Get active weather alerts
- `PUT /api/v1/weather/alerts/:id/acknowledge` - Acknowledge an alert

## WebSocket Events

### Client -> Server
- `subscribe:weather` - Subscribe to weather updates
- `subscribe:alerts` - Subscribe to weather alerts
- `subscribe:forecast` - Subscribe to forecast updates
- `subscribe:analytics` - Subscribe to analytics updates
- `subscribe:irrigation` - Subscribe to irrigation recommendations
- `unsubscribe:*` - Unsubscribe from updates
- `query:current` - Query current weather
- `query:stations` - Query weather stations

### Server -> Client
- `weather:update` - Real-time weather data
- `alert:new` - New weather alert
- `forecast:update` - Updated forecast
- `analytics:update` - Updated analytics
- `irrigation:recommendation` - New irrigation recommendation

## MQTT Topics

### Publishing
- `weather/data/{stationId}` - Weather readings
- `weather/alerts/{type}` - Weather alerts
- `weather/forecast/{lat}_{lng}` - Weather forecasts
- `weather/analytics/{lat}_{lng}` - Analytics data
- `weather/irrigation/{lat}_{lng}` - Irrigation recommendations
- `weather/service/status` - Service status

### Subscribing
- `weather/commands/+` - Service commands
- `weather/request/+` - Data requests
- `sensor/weather/+/data` - Sensor data

## Environment Variables

```bash
# Server
PORT=3055
NODE_ENV=production
LOG_LEVEL=info

# Databases
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_DATABASE=aos_weather
TIMESCALE_USER=weather_user
TIMESCALE_PASSWORD=password

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=weather_integration
POSTGRES_USER=weather_user
POSTGRES_PASSWORD=password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# MQTT
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_PROTOCOL=mqtt
MQTT_USERNAME=
MQTT_PASSWORD=

# Security
JWT_SECRET=your-jwt-secret

# CORS
CORS_ORIGIN=http://localhost:3000,http://localhost:3001

# Service URLs
NOTIFICATION_SERVICE_URL=http://notification-service:3012
ALERT_SERVICE_URL=http://alert-service:3013

# Weather Thresholds
HIGH_TEMP_THRESHOLD=40
LOW_TEMP_THRESHOLD=10
HEAVY_RAIN_THRESHOLD=50
HIGH_WIND_SPEED_THRESHOLD=60
FROST_WARNING_TEMP=5
ALERT_COOLDOWN_MINUTES=30
```

## Docker Deployment

```bash
# Build image
docker build -t weather-monitoring-service .

# Run container
docker run -d \
  --name weather-monitoring \
  -p 3055:3055 \
  --env-file .env \
  weather-monitoring-service
```

## Crop Database

The service includes pre-configured crop coefficients for common Thai crops:

- **Rice**: Seedling (Kc=1.05), Vegetative (Kc=1.20), Reproductive (Kc=1.35), Maturity (Kc=0.95)
- **Sugarcane**: Initial (Kc=0.40), Development (Kc=0.75), Peak (Kc=1.25), Maturity (Kc=0.75)
- **Cassava**: Initial (Kc=0.30), Development (Kc=0.60), Peak (Kc=1.10), Maturity (Kc=0.50)

## Alert Types

- `EXTREME_HEAT` - Temperature exceeds threshold
- `EXTREME_COLD` - Temperature below threshold
- `HEAVY_RAIN` - Rainfall exceeds threshold
- `STRONG_WIND` - Wind speed exceeds threshold
- `FROST_WARNING` - Risk of frost
- `DROUGHT_WARNING` - Extended dry period
- `STORM_WARNING` - Severe weather expected

## Data Sources

1. **TMD (Thai Meteorological Department)**: Official weather data
2. **AOS (Aeronautical Observation Station)**: Aviation weather data
3. **OpenWeather**: Supplementary weather data
4. **Custom Sensors**: IoT weather stations

## Performance Considerations

- Caches current weather data for 5 minutes
- Caches analytics results for 1 hour
- Caches irrigation recommendations for 1 hour
- Uses connection pooling for database efficiency
- Implements data quality scoring for sensor readings
- Alert cooldown prevents spam (configurable)