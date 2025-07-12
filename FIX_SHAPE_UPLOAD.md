# Shape File Upload - MIGRATION COMPLETE ✅

## Important Update
Shape file uploads have been **migrated from sensor-data to GIS service** where they architecturally belong.

## What Changed

### Old Architecture (Deprecated)
- ❌ Endpoint: `POST /api/v1/rid-ms/upload` 
- ❌ Token: `munbon-ridms-shape`
- ❌ Service: sensor-data
- ❌ Bucket: `munbon-shape-files-dev`

### New Architecture (Current)
- ✅ Endpoint: `POST /api/v1/gis/shapefiles/upload`
- ✅ Token: `munbon-gis-shapefile`
- ✅ Service: GIS service
- ✅ Bucket: `munbon-gis-shape-files`

## How to Upload Shape Files Now

### Option 1: GIS Service API (Recommended)
```bash
curl -X POST http://localhost:3007/api/v1/gis/shapefiles/upload \
  -H "Authorization: Bearer munbon-gis-shapefile" \
  -F "file=@your-shapefile.zip" \
  -F "waterDemandMethod=RID-MS" \
  -F "processingInterval=weekly" \
  -F "zone=Zone1"
```

### Option 2: GIS Lambda (Production)
```bash
# Deploy the Lambda first
cd services/gis/deployments/aws-lambda
npm install
npm run deploy:dev

# Then use the API Gateway endpoint
curl -X POST https://YOUR_API_ID.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/gis/shapefile/upload \
  -H "Authorization: Bearer munbon-gis-shapefile" \
  -F "file=@your-shapefile.zip"
```

## Migration Complete ✅

### What Was Done
1. ✅ Created GIS shape file upload endpoints
2. ✅ Added shape file processing with coordinate transformation
3. ✅ Created GIS SQS queue for async processing
4. ✅ Created GIS Lambda deployment
5. ✅ Removed shape file handling from sensor-data
6. ✅ Created migration script for existing files
7. ✅ Created test script for end-to-end testing

### Testing
```bash
# Test the new upload endpoint
cd services/gis
./test-shape-upload.sh path/to/shapefile.zip

# Start queue processor to process uploads
npm run queue:processor
```

## Documentation
See [SHAPE_FILE_MIGRATION.md](./SHAPE_FILE_MIGRATION.md) for:
- Detailed migration guide
- API documentation
- Infrastructure setup
- Troubleshooting

## Old Endpoint Status
The old sensor-data endpoint (`/api/v1/rid-ms/upload`) now returns:
```json
{
  "statusCode": 410,
  "error": "This endpoint has been deprecated",
  "message": "Shape file uploads have been moved to the GIS service",
  "newEndpoint": "/api/v1/gis/shapefile/upload"
}
```