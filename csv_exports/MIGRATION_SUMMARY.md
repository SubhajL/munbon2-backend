# Database Migration Summary

## Successfully Migrated from Local to AWS EC2 (43.209.22.250:5432)

### sensor_data Database (Port 5433 → EC2)
✅ **Public Schema:**
- `sensor_readings`: 3 rows
- `sensor_registry`: 2 rows  
- `water_level_readings`: **6,212 rows** ✨
- `moisture_readings`: **21 rows** ✨

✅ **Sensor Schema:**
- `sensors`: 6 rows
- `readings`: 47 rows

**Total sensor_data records**: 6,291 rows

### munbon_dev Database (Port 5434 → EC2)
✅ **GIS Schema:**
- `agricultural_plots`: 15,069 rows (already existed on EC2)
- `canal_network`: 4 rows
- `control_structures`: 5 rows
- `irrigation_zones`: 8 rows
- `sensor_locations`: 1 row

✅ **ROS Schema:**
- `area_info`: 3 rows
- `effective_rainfall_monthly`: 24 rows
- `eto_monthly`: 12 rows
- `kc_weekly`: 93 rows
- `water_demand_calculations`: 16 rows

## Migration Method Used
1. CSV export/import for sensor data (handled TimescaleDB hypertables)
2. Python scripts for proper handling of data types and empty values
3. Batch inserts for performance (1000 rows at a time)

## Connection Details for DBeaver
- **Host**: 43.209.22.250
- **Port**: 5432
- **Username**: postgres
- **Password**: P@ssw0rd123!
- **Databases**: sensor_data, munbon_dev

## Notes
- TimescaleDB hypertables required special handling (SELECT * FROM table)
- Large geometry data in agricultural_plots was already on EC2
- All critical sensor data including water levels and moisture readings successfully migrated