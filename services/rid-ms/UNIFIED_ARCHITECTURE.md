# RID-MS Unified Architecture with Sensor Data Service

## Overview

Instead of creating a separate serverless infrastructure for RID-MS, we've integrated it into the existing sensor-data service that already handles water level and moisture sensors. This provides a unified, zero-cost ingestion architecture.

## Architecture

```
                    ┌──────────────────┐
                    │  External APIs   │
                    └──────────────────┘
                             │
                             ▼
         ┌─────────────────────────────────────────┐
         │         AWS API Gateway                 │
         │                                         │
         │  POST /api/v1/{token}/telemetry        │
         └─────────────────────────────────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  Lambda Function │
                    │  (Token Valid.)  │
                    └──────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
    Water Level         Moisture            Shape Files
    Token: munbon-     Token: munbon-      Token: munbon-
    ridr-water-level   m2m-moisture        ridms-shape
         │                   │                   │
         └───────────────────┴───────────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │    AWS SQS       │
                    │  (Message Queue) │
                    └──────────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Local Consumer   │
                    │    Service       │
                    └──────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
    TimescaleDB         TimescaleDB         S3 + DynamoDB
    (Water Levels)      (Moisture)          (Shape Files)
```

## Key Benefits

1. **Unified Endpoint**: All external data (sensors + shape files) use the same API Gateway
2. **Zero-Cost**: Leverages existing AWS free tier infrastructure
3. **Consistent Authentication**: Token-based auth for all data types
4. **Shared Infrastructure**: Reuses Lambda, SQS, and monitoring
5. **Simplified Maintenance**: One serverless deployment to manage

## How It Works

### 1. Shape File Push (External)
```bash
POST https://api.munbon.com/api/v1/munbon-ridms-shape/telemetry
Content-Type: application/json

{
  "fileName": "parcels_zone1.zip",
  "fileContent": "<base64-encoded-zip>",
  "waterDemandMethod": "AWD",
  "processingInterval": "weekly",
  "metadata": {
    "zone": "Zone1",
    "uploadedBy": "RID-NakhonRatchasima"
  }
}
```

### 2. Lambda Validation
- Validates token: `munbon-ridms-shape`
- Detects shape file format
- Sends to SQS queue

### 3. Local Processing
- SQS consumer receives message
- Uploads zip file to S3
- Stores metadata in DynamoDB/TimescaleDB
- Triggers shape file processing (separate service)

## Configuration Changes

### Sensor Data Service Updates

1. **Lambda Handler** (`handler.ts`):
   - Added shape file detection
   - Added ShapeFileData interface
   - Updated telemetry processing

2. **SQS Processor** (`sqs-processor.ts`):
   - Added processShapeFileData function
   - Handles S3 upload
   - Stores metadata

3. **Environment Variables**:
   ```bash
   SHAPE_FILE_BUCKET=munbon-shape-files
   SHAPE_FILE_TABLE=rid-ms-shapefiles
   ```

## Migration from Standalone RID-MS

### What Changes:
- **Ingestion Endpoint**: From `/api/external/shapefile/push` to `/api/v1/munbon-ridms-shape/telemetry`
- **Token Location**: From Authorization header to URL path
- **Infrastructure**: From separate CloudFormation to shared sensor-data service

### What Stays the Same:
- Request format (base64-encoded zip)
- Processing flow (S3 → Processing)
- Data access APIs

## Usage Examples

### Using Unified Script
```bash
./push-shapefile-unified.sh parcels.zip prod
```

### Direct API Call
```bash
# Encode file
base64 parcels.zip > parcels_base64.txt

# Send to unified endpoint
curl -X POST https://api.munbon.com/api/v1/munbon-ridms-shape/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "fileName": "parcels.zip",
    "fileContent": "'$(cat parcels_base64.txt)'",
    "waterDemandMethod": "AWD"
  }'
```

## Processing Architecture

### Phase 1: Ingestion (Serverless - Free)
- API Gateway receives push
- Lambda validates and queues
- Zero cost within AWS free tier

### Phase 2: Storage (Serverless - Free)
- S3 stores zip files
- DynamoDB stores metadata
- Both within free tier limits

### Phase 3: Processing (Requires Compute)
- Separate service monitors S3/DynamoDB
- Processes shape files when detected
- Extracts parcels and calculates water demand
- This part requires infrastructure

## Next Steps

1. **Shape File Processing Service**:
   - Monitor S3 for new uploads
   - Extract and process shape files
   - Calculate water demand
   - Store results in database

2. **Data Access APIs**:
   - Expose processed parcel data
   - Provide water demand calculations
   - Support GIS visualization

3. **Water Demand Computation Service**:
   - Orchestrate calculations across methods
   - Handle mixed-method scenarios
   - Provide unified API for planning

## Advantages Over Separate Infrastructure

1. **Cost**: No additional AWS resources needed
2. **Complexity**: Simpler to maintain one serverless stack
3. **Monitoring**: Unified CloudWatch logs and metrics
4. **Security**: Single authentication system
5. **Scalability**: Proven architecture handling sensor data

## Conclusion

By integrating RID-MS into the existing sensor-data service, we achieve:
- True zero-cost ingestion (AWS free tier)
- Simplified architecture
- Consistent data flow patterns
- Reduced operational overhead

The shape files follow the same path as sensor data, making the system easier to understand and maintain.