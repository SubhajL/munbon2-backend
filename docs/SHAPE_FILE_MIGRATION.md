# Shape File Migration from Sensor-Data to GIS Service

## Overview
Shape files have been migrated from the sensor-data service to the GIS service where they architecturally belong. This document outlines the changes and provides migration guidance.

## Why the Migration?
- **Architectural Correctness**: Shape files contain GIS data (parcels, zones, spatial boundaries), not sensor data
- **Service Boundaries**: Clear separation of concerns between sensor telemetry and spatial data processing
- **Specialized Processing**: GIS service has PostGIS and spatial processing capabilities

## What Changed

### 1. Removed from Sensor-Data Service
- ❌ `/api/v1/rid-ms/upload` endpoint (returns 410 Gone)
- ❌ Shape file processing in SQS consumer
- ❌ S3 bucket `munbon-shape-files-dev`
- ❌ Shape file type detection in telemetry handler

### 2. Added to GIS Service

#### New Endpoints
- ✅ `POST /api/v1/gis/shapefiles/upload` - External upload with auth
- ✅ `POST /api/v1/gis/shapefiles/internal/upload` - Internal upload (no auth)

#### New Infrastructure
- ✅ S3 bucket: `munbon-gis-shape-files`
- ✅ SQS queue: `munbon-gis-shapefile-queue`
- ✅ DLQ: `munbon-gis-shapefile-dlq`
- ✅ Lambda function for serverless uploads (optional)

#### Processing Capabilities
- ✅ Coordinate transformation (UTM Zone 48N → WGS84)
- ✅ Shape file parsing (.shp, .dbf, .prj)
- ✅ Parcel area calculation
- ✅ Zone assignment
- ✅ Database storage in PostGIS

## Migration Steps

### 1. Update Your API Calls

**Old endpoint:**
```bash
curl -X POST https://api.example.com/api/v1/rid-ms/upload \
  -H 'Authorization: Bearer munbon-ridms-shape' \
  -F 'file=@shapefile.zip'
```

**New endpoint:**
```bash
curl -X POST https://api.example.com/api/v1/gis/shapefiles/upload \
  -H 'Authorization: Bearer munbon-gis-shapefile' \
  -F 'file=@shapefile.zip' \
  -F 'waterDemandMethod=RID-MS' \
  -F 'zone=Zone1'
```

### 2. Update Authentication Token
- Old token: `munbon-ridms-shape`
- New token: `munbon-gis-shapefile`

### 3. Deploy GIS Infrastructure

```bash
# Local development
cd services/gis
npm install
npm run setup:aws    # Creates S3 bucket and SQS queues

# Start the service
npm run dev

# Start queue processor (in separate terminal)
npm run queue:processor
```

### 4. Deploy Lambda (Optional)

```bash
cd services/gis/deployments/aws-lambda
npm install
npm run deploy:dev
```

### 5. Migrate Existing Shape Files

```bash
cd services/gis
node scripts/migrate-shapefile.js
```

## API Changes

### Request Format
Both old and new APIs accept multipart/form-data with the same fields:
- `file` - The shape file (ZIP format)
- `waterDemandMethod` - RID-MS, ROS, or AWD
- `processingInterval` - daily, weekly, or bi-weekly
- `zone` - Zone identifier
- `description` - Optional description

### Response Format

**Success (200):**
```json
{
  "success": true,
  "uploadId": "uuid",
  "message": "Shape file uploaded successfully",
  "location": "s3://bucket/path/to/file.zip"
}
```

**Deprecated Endpoint (410):**
```json
{
  "error": "This endpoint has been deprecated",
  "message": "Shape file uploads have been moved to the GIS service",
  "newEndpoint": "/api/v1/gis/shapefile/upload",
  "documentation": "Please update your integration to use the GIS service endpoints"
}
```

## Testing

```bash
# Test shape file upload
cd services/gis
./test-shape-upload.sh path/to/shapefile.zip

# Check processing logs
docker logs -f munbon-gis-queue-processor

# Verify in database
psql -U postgres -d munbon_gis -c "SELECT * FROM shape_file_uploads ORDER BY uploaded_at DESC LIMIT 5;"
```

## Rollback Plan
If you need to temporarily use the old endpoint:
1. Restore `file-upload-handler.ts.backup` in sensor-data service
2. Redeploy sensor-data Lambda
3. Messages will go to sensor-data queue but won't be processed

## Support
For issues or questions:
1. Check GIS service logs: `docker logs munbon-gis-service`
2. Check queue processor logs: `docker logs munbon-gis-queue-processor`
3. Verify AWS resources exist: `aws s3 ls s3://munbon-gis-shape-files`
4. Check SQS queue: `aws sqs get-queue-attributes --queue-url <queue-url>`