# Sensor Endpoint Token Specification

## Recommended Tokens

### 1. Moisture Endpoint Tokens
**Base URL**: `http://43.208.201.191:8080/api/sensor-data/moisture/:token`

| Token | Purpose | Example Usage |
|-------|---------|---------------|
| `munbon-moisture-field` | Field moisture sensors in agricultural areas | Primary production use |
| `munbon-moisture-gate` | Moisture sensors near water gates | Gate area monitoring |
| `munbon-moisture-test` | Testing and development | Development/testing |

### 2. Water Level Endpoint Tokens
**Base URL**: `http://43.208.201.191:8080/api/sensor-data/water-level/:token`

| Token | Purpose | Example Usage |
|-------|---------|---------------|
| `munbon-level-gate` | Water level sensors at gates | Gate water level monitoring |
| `munbon-level-canal` | Canal water level monitoring | Canal system monitoring |
| `munbon-level-reservoir` | Reservoir level monitoring | Reservoir management |
| `munbon-level-test` | Testing and development | Development/testing |

### 3. AOS Weather Endpoint Tokens
**Base URL**: `http://43.208.201.191:8080/api/sensor-data/aos/:token`

| Token | Purpose | Example Usage |
|-------|---------|---------------|
| `munbon-aos-field` | Field weather stations | Agricultural weather data |
| `munbon-aos-gate` | Weather stations at gates | Gate area weather |
| `munbon-aos-tmd` | TMD integration data | Thai Meteorological Dept |
| `munbon-aos-test` | Testing and development | Development/testing |

## Token Naming Convention

The token structure follows this pattern:
```
munbon-[datatype]-[location/source]
```

Where:
- `munbon` - Project identifier
- `datatype` - Type of sensor data (moisture, level, aos)
- `location/source` - Specific location or data source

## Example cURL Commands with Recommended Tokens

### Moisture Data
```bash
# Field moisture sensor
curl -X POST http://43.208.201.191:8080/api/sensor-data/moisture/munbon-moisture-field \
  -H "Content-Type: application/json" \
  -d '{"gw_id":"0003","sensor":[{"sensor_id":"13","humid_hi":"75"}]}'

# Gate area moisture sensor
curl -X POST http://43.208.201.191:8080/api/sensor-data/moisture/munbon-moisture-gate \
  -H "Content-Type: application/json" \
  -d '{"gw_id":"0004","sensor":[{"sensor_id":"14","humid_hi":"82"}]}'
```

### Water Level Data
```bash
# Gate water level
curl -X POST http://43.208.201.191:8080/api/sensor-data/water-level/munbon-level-gate \
  -H "Content-Type: application/json" \
  -d '{"sensorId":"AWD-B75A","data":{"level":150,"voltage":390}}'

# Canal water level
curl -X POST http://43.208.201.191:8080/api/sensor-data/water-level/munbon-level-canal \
  -H "Content-Type: application/json" \
  -d '{"sensorId":"AWD-C001","data":{"level":200,"voltage":385}}'
```

### AOS Weather Data
```bash
# Field weather station
curl -X POST http://43.208.201.191:8080/api/sensor-data/aos/munbon-aos-field \
  -H "Content-Type: application/json" \
  -d '{"station_id":"AOS-F01","data":{"temperature_celsius":28.5,"rainfall_mm":2.5}}'

# Gate weather station
curl -X POST http://43.208.201.191:8080/api/sensor-data/aos/munbon-aos-gate \
  -H "Content-Type: application/json" \
  -d '{"station_id":"AOS-G01","data":{"temperature_celsius":29.2,"humidity_percentage":75}}'
```

## Benefits of Structured Tokens

1. **Clear Purpose**: Each token clearly indicates data type and source
2. **Future Filtering**: Enables filtering by location/type
3. **Access Control**: Can implement token-based permissions
4. **Monitoring**: Easy to track data sources in logs
5. **Rate Limiting**: Can apply different limits per token

## Migration from Old Tokens

| Old Token | New Recommended Token |
|-----------|----------------------|
| `munbon-m2m-moisture` | `munbon-moisture-field` |
| Generic water level token | `munbon-level-gate` |
| Generic AOS token | `munbon-aos-field` |

## Token Validation (Future Enhancement)

While tokens are currently not validated, the structured naming enables future features:
- Token whitelisting
- Rate limiting per token
- Source-specific data validation
- Access control and API key mapping
- Usage statistics per token