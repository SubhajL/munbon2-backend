# Deployed API Endpoints - Current Status

## Data Ingestion API (POST sensor data)
**API Gateway ID**: `c0zc2kfzd6`  
**Stage**: `dev`  
**Base URL**: `https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1`

### Endpoints:
- Water Level: `POST /munbon-ridr-water-level/telemetry`
- Moisture: `POST /munbon-m2m-moisture/telemetry`
- Shape Files: `POST /munbon-ridms-shape-file/telemetry`

### Example:
```bash
curl -X POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-m2m-moisture/telemetry \
  -H "Content-Type: application/json" \
  -d '{"gateway_id":"GW001","sensor":[...]}'
```

## Data Exposure API (GET sensor data)
**API Gateway ID**: `5e3l647kpd`  
**Stage**: `prod`  
**Base URL**: `https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1`

### Water Level Endpoints:
- Latest: `GET /public/water-levels/latest`
- Time Series: `GET /public/water-levels/timeseries?date=DD/MM/YYYY`
- Statistics: `GET /public/water-levels/statistics?date=DD/MM/YYYY`

### Moisture Endpoints:
- Latest: `GET /public/moisture/latest`
- Time Series: `GET /public/moisture/timeseries?date=DD/MM/YYYY`
- Statistics: `GET /public/moisture/statistics?date=DD/MM/YYYY`

### AOS Weather Endpoints:
- Latest: `GET /public/aos/latest`
- Time Series: `GET /public/aos/timeseries?date=DD/MM/YYYY`
- Statistics: `GET /public/aos/statistics?date=DD/MM/YYYY`

### Authentication:
All GET endpoints require API key in header:
```
X-API-Key: rid-ms-prod-key1
```

### Valid API Keys:
- `rid-ms-prod-key1` - RID Main System
- `tmd-weather-key2` - Thai Meteorological Department
- `university-key3` - University Research

### Example:
```bash
# Get latest AOS weather data
curl -H "X-API-Key: rid-ms-prod-key1" \
  https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/latest

# Get water level data for specific date (Buddhist calendar)
curl -H "X-API-Key: rid-ms-prod-key1" \
  "https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/timeseries?date=30/06/2568"
```

## Notes:
1. The URL `https://26ikiexzlc.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/public` appears to be from old documentation or a different deployment
2. Current active API Gateway IDs are:
   - `c0zc2kfzd6` for data ingestion (POST)
   - `5e3l647kpd` for data exposure (GET)
3. All dates use Buddhist calendar (BE = CE + 543)
4. The Data API uses `prod` stage, while Ingestion API uses `dev` stage