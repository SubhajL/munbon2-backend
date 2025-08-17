# RID-MS Service

Royal Irrigation Department - Management System Service for processing SHAPE files and managing water demand calculations for the Munbon Irrigation Project.

## Overview

The RID-MS Service follows a hybrid architecture pattern for:
- **Ingestion**: Processing SHAPE files pushed via External API (AWS Lambda)
- **Storage**: Storing spatial parcel data in PostgreSQL with PostGIS extension
- **Processing**: SQS-based processor for shape file parsing and coordinate transformation
- **Exposure**: Providing REST APIs for GIS visualization and water demand data access

### External Push Mechanism

External parties (like the Royal Irrigation Department) can push SHAPE files using:
- **Endpoint**: `POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/rid-ms/upload`
- **Authentication**: Bearer token `munbon-ridms-shape`
- **Format**: Direct file upload (multipart/form-data) - no base64 encoding needed
- **Flow**: API Gateway → Lambda → S3 → SQS → Processor → PostgreSQL

See deployment documentation for detailed integration guide.

## Architecture

### Architecture Components

1. **AWS Infrastructure**
   - **S3 Bucket**: `munbon-shape-files-{stage}` - Stores uploaded ZIP files
   - **SQS Queue**: Processes shape file messages asynchronously
   - **Lambda**: File upload handler (integrated with sensor-data service)
   - **API Gateway**: Single endpoint shared with other sensor services

2. **PostgreSQL/PostGIS Database**
   - **shape_file_uploads**: Upload tracking and status
   - **parcels**: Spatial data with versioning (valid_from/valid_to)
   - **water_demand_calculations**: Daily water demand calculations
   - **zone_summaries**: Aggregated statistics by zone

3. **Processing Service**
   - Node.js SQS consumer (runs in Docker container)
   - Downloads from S3, extracts ZIP, parses shape files
   - Transforms coordinates from UTM Zone 48N to WGS84
   - Stores parcels with temporal versioning

4. **API Service**
   - Node.js Express API (Port 3048)
   - Provides REST endpoints for data access
   - GeoJSON export for visualization

### Water Demand Calculation Methods

1. **RID-MS (Royal Irrigation Department - Management System)**
   - Traditional surface irrigation method
   - Irrigation efficiency: 65%
   - Standard crop coefficients

2. **ROS (Reservoir Operation Study)**
   - Improved water management method
   - Irrigation efficiency: 75%
   - Optimized for reservoir operations

3. **AWD (Alternate Wet and Dry)**
   - Most efficient method
   - Irrigation efficiency: 85%
   - 30% water reduction during drying periods

## Deployment

See [AWS Deployment Guide](deployments/aws/DEPLOYMENT_GUIDE.md) for detailed instructions.

### Quick Start

1. **Deploy Infrastructure**
```bash
aws cloudformation create-stack \
  --stack-name rid-ms-infrastructure \
  --template-body file://deployments/aws/cloudformation.yaml
```

2. **Deploy Lambda Functions**
```bash
npm run build
npm run deploy:lambda
```

3. **Start API Service**
```bash
npm run start
```

## Configuration

Environment variables for the API service:

```bash
# AWS Configuration
AWS_REGION=ap-southeast-1
SHAPE_FILE_TABLE=rid-ms-shapefiles-${ENV}
PARCEL_TABLE=rid-ms-parcels-${ENV}
WATER_DEMAND_TABLE=rid-ms-water-demand-${ENV}
UPLOAD_BUCKET=rid-ms-uploads-${ENV}
PROCESSED_BUCKET=rid-ms-processed-${ENV}

# Service Configuration
NODE_ENV=production
PORT=3048
```

## API Endpoints

### Data Access APIs

#### Get Upload URL
```http
POST /api/v1/rid-ms/upload-url
Content-Type: application/json

{
  "fileName": "parcels_2024.zip",
  "waterDemandMethod": "AWD",
  "processingInterval": "weekly"
}
```

#### List Shape Files
```http
GET /api/v1/rid-ms/shapefiles?status=processed&limit=20
```

#### Get Shape File Details
```http
GET /api/v1/rid-ms/shapefiles/:id
```

#### Get Parcels by Zone
```http
GET /api/v1/rid-ms/zones/:zone/parcels?waterDemandMethod=AWD
```

#### Get Water Demand Summary
```http
GET /api/v1/rid-ms/zones/:zone/water-demand-summary
```

#### Get GeoJSON for Visualization
```http
GET /api/v1/rid-ms/shapefiles/:shapeFileId/geojson?includeWaterDemand=true
```

#### Update Water Demand Method
```http
PUT /api/v1/rid-ms/parcels/water-demand-method
Content-Type: application/json

{
  "parcelIds": ["parcel-1", "parcel-2"],
  "method": "AWD"
}
```

## Data Flow

### External Push Flow
1. **Push**: External party sends base64-encoded ZIP file to API endpoint with token
2. **Validation**: API Gateway Lambda validates token and request
3. **Storage**: File stored in S3 with unique ID
4. **Queue**: Message sent to SQS for processing
5. **Processing**: Lambda extracts parcels and transforms coordinates from UTM to WGS84
6. **Storage**: Parcel data saved to DynamoDB
7. **Calculation**: Water demand processor calculates demand for each parcel
8. **Notification**: Completion notification sent (future feature)

### Data Access Flow
1. **Request**: Frontend requests data via API
2. **Query**: API service queries DynamoDB
3. **Transform**: Data formatted for response
4. **Response**: JSON data returned to frontend

## Water Demand Computation Service

Based on requirement #7, you need a separate **Water Demand Computation Service** that:

1. **Orchestrates** water demand calculations across different methods
2. **Handles** mixed-method scenarios (different parcels using different methods)
3. **Provides** unified API for frontend water demand planning

This service would:
- Receive computation requests from frontend
- Query parcels from RID-MS service
- Apply appropriate calculation method per parcel
- Aggregate results by zone/area
- Return unified water demand plan

**Recommended**: Create a new task for "Water Demand Computation Service" that acts as an orchestration layer above RID-MS, ROS, and AWD calculation engines.

## Integration with Other Services

### GIS Service Integration
The RID-MS service sends processed spatial data to the GIS service for visualization.

### Water Demand Computation Service
Based on your requirement #7, a separate Water Demand Computation Service (Task not yet defined) will:
- Receive water demand computation requests from frontend
- Orchestrate calculations across RID-MS, ROS, and AWD methods
- Handle mixed-method calculations for different parcels
- Provide unified API for frontend water demand planning

## Development

### Running Locally
```bash
npm run dev
```

### Running Tests
```bash
npm test
```

### Building for Production
```bash
npm run build
```

### Docker Build
```bash
docker build -t rid-ms-service .
```

## Monitoring

The service exposes metrics at:
- Health check: `GET /api/v1/health`
- Metrics: Prometheus format via `/metrics`

## Error Handling

- Failed shape file processing is logged and marked in database
- Parcels with errors are tracked separately
- Kafka events notify other services of processing results

## Security

- File uploads are validated for type and size
- API endpoints require authentication
- Uploaded files are scanned for malicious content
- Database queries use parameterized statements

## Future Enhancements

1. Support for additional shape file formats
2. Real-time processing progress via WebSocket
3. Machine learning for water demand prediction
4. Integration with satellite imagery for crop detection
5. Mobile app support for field data collection