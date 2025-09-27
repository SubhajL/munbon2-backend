# GeoPackage Processor Worker

This worker service processes RID-MS water requirements and manual water level data from GeoPackage files and imports them directly into the EC2 PostgreSQL database.

## Features

- **Automatic Processing**: Monitors upload directory for new `.gpkg` files
- **Batch Processing**: Processes data in configurable batches for efficiency
- **Error Handling**: Continues processing other files if one fails
- **File Management**: Moves processed files to a separate directory
- **Database Integration**: Writes directly to EC2 PostgreSQL/TimescaleDB

## Architecture

```
┌─────────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Upload Directory  │────>│  Worker Process  │────>│  PostgreSQL DB  │
│ /geopackage-uploads │     │   (PM2 Managed)  │     │   munbon_dev    │
└─────────────────────┘     └──────────────────┘     └─────────────────┘
                                     │
                                     ▼
                            ┌──────────────────┐
                            │ Processed Files  │
                            │/geopackage-proc. │
                            └──────────────────┘
```

## File Types Supported

1. **RID-MS Parcels** (data_ridplan)
   - Detected by keywords: `ridplan`, `rice`, `parcel`
   - Stored in: `gis.parcels` table as JSONB
   - Fields: area, water requirements, crop cycle, etc.

2. **Water Level Readings** (data_water_level)
   - Detected by keywords: `water_level`, `water`
   - Stored in: `ros_gis.manual_water_level_readings`
   - Fields: location, water level (mm→m), date, coordinates

## Deployment

### 1. Initial Setup

Deploy the worker to EC2:
```bash
./deploy-geopackage-processor.sh
```

This will:
- Create necessary directories
- Install dependencies (pg, csv-parser, gdal-bin)
- Start the worker with PM2
- Save PM2 configuration

### 2. Upload GeoPackage Files

Upload files for processing:
```bash
./upload-geopackages.sh
```

Or manually:
```bash
scp -i ~/dev/th-lab01.pem your_file.gpkg ubuntu@43.208.201.191:/home/ubuntu/geopackage-uploads/
```

### 3. Monitor Status

Check processing status:
```bash
./check-import-status.sh
```

## Configuration

Environment variables (set in `ecosystem.geopackage.config.js`):

- `UPLOAD_DIR`: Directory to monitor for new files (default: `/home/ubuntu/geopackage-uploads`)
- `PROCESSED_DIR`: Directory for processed files (default: `/home/ubuntu/geopackage-processed`)
- `TEMP_DIR`: Temporary directory for CSV conversion (default: `/tmp/geopackage-processing`)
- `POLL_INTERVAL`: How often to check for new files in ms (default: 30000)
- `BATCH_SIZE`: Number of records to process at once (default: 1000)
- `POSTGRES_PASSWORD`: Database password

## PM2 Management

View worker status:
```bash
ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 'pm2 status geopackage-processor'
```

View logs:
```bash
ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 'pm2 logs geopackage-processor'
```

Restart worker:
```bash
ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 'pm2 restart geopackage-processor'
```

Stop worker:
```bash
ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 'pm2 stop geopackage-processor'
```

## Database Schema

### gis.parcels (JSONB storage)
```json
{
  "type": "rid_ms_parcel",
  "source": "geopackage_processor",
  "import_date": "2025-09-05T12:00:00Z",
  "parcel_data": {
    "parcel_seq": "20006",
    "zone_area": "6",
    "area_rai": 6552.02,
    "batch_date": 20250810,
    "plant_id": "rice",
    "geometry_wkt": "MULTIPOLYGON(...)"
  }
}
```

### ros_gis.manual_water_level_readings
```sql
- location_id: UUID from crop_id
- section_id: 'MB-001' (default)
- plot_id: Project name
- water_level_m: Converted from mm
- reading_date: Date of reading
- coordinates: PostGIS point geometry
- volunteer_name: 'GeoPackage Import'
- geopackage_source: Source filename
```

## Troubleshooting

### Worker not processing files
1. Check worker is running: `pm2 status`
2. Check logs: `pm2 logs geopackage-processor`
3. Verify file permissions in upload directory
4. Ensure `.gpkg` extension is correct

### Database connection errors
1. Verify PostgreSQL is running
2. Check password in ecosystem config
3. Ensure database `munbon_dev` exists
4. Check network connectivity

### ogr2ogr conversion failures
1. Ensure GDAL is installed: `ogr2ogr --version`
2. Check GeoPackage file is valid
3. Review error logs for specific issues

## Logs Location

- Application logs: `/home/ubuntu/.pm2/logs/geopackage-processor-out.log`
- Error logs: `/home/ubuntu/.pm2/logs/geopackage-processor-error.log`
- PM2 logs: `pm2 logs geopackage-processor`