# Munbon Sensor Endpoints - Quick Reference

**Base URL**: `http://43.208.201.191:8080`

## Moisture Data
```bash
# Field moisture sensors
POST /api/sensor-data/moisture/munbon-moisture-field

# Gate moisture sensors  
POST /api/sensor-data/moisture/munbon-moisture-gate

# Test/Development
POST /api/sensor-data/moisture/munbon-moisture-test
```

## Water Level Data
```bash
# Gate water levels
POST /api/sensor-data/water-level/munbon-level-gate

# Canal water levels
POST /api/sensor-data/water-level/munbon-level-canal

# Reservoir levels
POST /api/sensor-data/water-level/munbon-level-reservoir

# Test/Development
POST /api/sensor-data/water-level/munbon-level-test
```

## AOS Weather Data
```bash
# Field weather stations
POST /api/sensor-data/aos/munbon-aos-field

# Gate weather stations
POST /api/sensor-data/aos/munbon-aos-gate

# TMD integration
POST /api/sensor-data/aos/munbon-aos-tmd

# Test/Development
POST /api/sensor-data/aos/munbon-aos-test
```

## Monitoring
```bash
# Statistics
GET /api/stats

# Health check
GET /health
```

## Token Pattern
`munbon-[datatype]-[location]`
- `datatype`: moisture, level, aos
- `location`: field, gate, canal, reservoir, tmd, test