# Unified Sensor Endpoints Documentation

All sensor data endpoints are now consolidated on the same EC2 server at `http://43.208.201.191:8080`

## Overview

The unified sensor server provides HTTP endpoints for three types of sensor data:
1. **Moisture Data** - Soil moisture sensors
2. **Water Level Data** - Water level telemetry
3. **AOS Weather Data** - Automated Observation System meteorological data

## Endpoints

### Base URL
```
http://43.208.201.191:8080
```

### 1. Moisture Data Endpoint

**URL**: `/api/sensor-data/moisture/:token`  
**Method**: POST  
**Content-Type**: `text/plain` or `application/json`  
**Example Token**: `munbon-m2m-moisture`

**Request Body**:
```json
{
  "gw_id": "0003",
  "gateway_msg_type": "Interval",
  "gateway_date": "2025/08/02",
  "gateway_utc": "06:54:14",
  "gps_lat": "13.94551",
  "gps_lng": "100.73405",
  "gw_temp": "37.10",
  "gw_himid": "43.40",
  "sensor": [
    {
      "sensor_id": "13",
      "humid_hi": "008",
      "humid_low": "006",
      "temp_hi": "29.00",
      "temp_low": "29.50",
      "amb_humid": "33.7",
      "amb_temp": "38.2",
      "flood": "no",
      "sensor_batt": "404"
    }
  ]
}
```

**cURL Example**:
```bash
curl -X POST http://43.208.201.191:8080/api/sensor-data/moisture/munbon-m2m-moisture \
  -H "Content-Type: application/json" \
  -d '{"gw_id":"0003","sensor":[{"sensor_id":"13","humid_hi":"75","humid_low":"68"}]}'
```

### 2. Water Level Data Endpoint

**URL**: `/api/sensor-data/water-level/:token`  
**Method**: POST  
**Content-Type**: `application/json`  
**Example Token**: `munbon-water-level`

**Request Body**:
```json
{
  "sensorType": "water-level",
  "sensorId": "AWD-B75A",
  "timestamp": "2025-09-10T10:30:00.000Z",
  "data": {
    "level": 150,
    "voltage": 390,
    "RSSI": -65,
    "macAddress": "00:11:22:33:44:55"
  },
  "location": {
    "lat": 14.3754,
    "lng": 102.8756
  },
  "metadata": {
    "source": "api-test"
  }
}
```

**cURL Example**:
```bash
curl -X POST http://43.208.201.191:8080/api/sensor-data/water-level/munbon-water-level \
  -H "Content-Type: application/json" \
  -d '{"sensorId":"AWD-B75A","timestamp":"2025-09-10T10:30:00.000Z","data":{"level":150,"voltage":390}}'
```

### 3. AOS Weather Data Endpoint

**URL**: `/api/sensor-data/aos/:token`  
**Method**: POST  
**Content-Type**: `application/json`  
**Example Token**: `munbon-aos-weather`

**Request Body**:
```json
{
  "station_id": "AOS-001",
  "timestamp": "2025-09-10T10:30:00.000Z",
  "location": {
    "lat": 13.7563,
    "lng": 100.5018
  },
  "data": {
    "rainfall_mm": 2.5,
    "temperature_celsius": 28.5,
    "humidity_percentage": 75,
    "wind_speed_ms": 3.2,
    "wind_direction_degrees": 180,
    "pressure_hpa": 1013.25,
    "solar_radiation_wm2": 650,
    "evapotranspiration_mm": 4.2
  }
}
```

**cURL Example**:
```bash
curl -X POST http://43.208.201.191:8080/api/sensor-data/aos/munbon-aos-weather \
  -H "Content-Type: application/json" \
  -d '{"station_id":"AOS-001","data":{"temperature_celsius":28.5,"rainfall_mm":2.5}}'
```

### 4. Statistics Endpoint

**URL**: `/api/stats`  
**Method**: GET  
**Purpose**: View ingestion statistics

**Response**:
```json
{
  "service": "Unified Sensor Data Ingestion",
  "version": "2.0.0",
  "uptime": 3600,
  "timestamp": "2025-09-10T10:30:00.000Z",
  "statistics": {
    "moisture": {
      "received": 100,
      "processed": 98,
      "errors": 2
    },
    "waterLevel": {
      "received": 50,
      "processed": 50,
      "errors": 0
    },
    "aos": {
      "received": 30,
      "processed": 29,
      "errors": 1
    }
  }
}
```

### 5. Health Check Endpoint

**URL**: `/health`  
**Method**: GET  
**Purpose**: Check service health and database connectivity

**Response**:
```json
{
  "status": "healthy",
  "service": "unified-sensor-endpoint",
  "database": "connected",
  "timestamp": "2025-09-10T10:30:00.000Z",
  "ec2_ip": "43.208.201.191",
  "features": {
    "textPlainSupport": true,
    "jsonSupport": true,
    "moistureEndpoint": true,
    "waterLevelEndpoint": true,
    "aosEndpoint": true
  }
}
```

## Database Tables

### 1. moisture_readings
- Stores soil moisture sensor data
- TimescaleDB hypertable with 1-day chunks

### 2. water_level_readings  
- Stores water level telemetry data
- TimescaleDB hypertable with 1-day chunks

### 3. aos_weather_data
- Stores meteorological station data
- TimescaleDB hypertable with 1-day chunks

## Deployment

1. **Deploy to EC2**:
   ```bash
   ./deploy-unified-sensor-endpoints.sh
   ```

2. **Test all endpoints**:
   ```bash
   ./test-unified-endpoints.sh
   ```

3. **View logs**:
   ```bash
   ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 'pm2 logs unified-sensor'
   ```

4. **Check status**:
   ```bash
   ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 'pm2 status'
   ```

## Migration from Old Endpoints

### Previous Endpoints:
- Moisture: `http://43.208.201.191:8080/api/sensor-data/moisture/:token` ✅ (Same)
- Water Level: `https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridr-water-level/telemetry`
- AOS: Not implemented

### New Unified Endpoints:
- Moisture: `http://43.208.201.191:8080/api/sensor-data/moisture/:token` ✅ (No change)
- Water Level: `http://43.208.201.191:8080/api/sensor-data/water-level/:token` 🆕
- AOS: `http://43.208.201.191:8080/api/sensor-data/aos/:token` 🆕

## Benefits of Unified Endpoints

1. **Single Server**: All sensor data goes to one server
2. **Consistent Format**: Similar request/response patterns
3. **Direct Database Write**: No Lambda/SQS overhead
4. **Real-time Processing**: Immediate database insertion
5. **Unified Monitoring**: Single PM2 process to monitor
6. **Simplified Architecture**: Reduced complexity

## Notes

- The server accepts both `text/plain` and `application/json` content types
- All timestamps are stored in UTC
- Database uses TimescaleDB for efficient time-series storage
- The `:token` parameter can be used for basic routing/authentication