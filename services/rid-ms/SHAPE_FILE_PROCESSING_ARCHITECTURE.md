# Shape File Processing Architecture

## Overview

This document explains how shape files are stored, processed, and updated when received at different intervals (daily, weekly, bi-weekly).

## Storage Locations

### 1. Raw File Storage (S3)
```
s3://munbon-shape-files-prod/
└── shape-files/
    └── {date}/
        └── {uploadId}/
            └── {filename}.zip
```

Example:
```
s3://munbon-shape-files-prod/shape-files/2024-03-15/550e8400-e29b-41d4/ridmb_parcels.zip
```

### 2. Metadata Storage (DynamoDB)
```
Table: rid-ms-shapefiles-prod
├── id: 550e8400-e29b-41d4 (Partition Key)
├── fileName: ridmb_parcels.zip
├── uploadTime: 2024-03-15T10:30:00Z
├── status: uploaded | processing | completed | failed
├── processingInterval: daily | weekly | bi-weekly
├── s3Key: shape-files/2024-03-15/550e8400-e29b-41d4/ridmb_parcels.zip
└── metadata: { zone, uploadedBy, description }
```

### 3. Parcel Data Storage (DynamoDB)
```
Table: rid-ms-parcels-prod
├── id: UUID (Partition Key)
├── shapeFileId: 550e8400-e29b-41d4 (GSI)
├── parcelId: RID-12345
├── zone: Zone1
├── validFrom: 2024-03-15T00:00:00Z
├── validTo: null (current version)
├── geometry: { type: "Polygon", coordinates: [...] }
├── attributes: {
│   ├── OWNER: "John Doe"
│   ├── CROP_TYPE: "Rice"
│   ├── AREA: 1234.56
│   └── WATER_DEMAND_METHOD: "AWD"
│ }
└── waterDemand: {
    ├── method: "AWD"
    ├── dailyDemand: 125.5
    └── lastCalculated: 2024-03-15T10:35:00Z
  }
```

## Processing Flow

### Phase 1: Upload & Queue
1. ZIP file uploaded via API
2. Stored in S3 with unique path
3. Metadata saved to DynamoDB
4. Message sent to SQS queue

### Phase 2: Extract & Process
```javascript
// SQS Message Handler (to be implemented)
async function processShapeFile(message) {
  const { s3Bucket, s3Key, uploadId } = message;
  
  // 1. Download ZIP from S3
  const zipFile = await s3.getObject({ Bucket: s3Bucket, Key: s3Key });
  
  // 2. Extract files
  const extracted = await extractZip(zipFile.Body);
  
  // 3. Parse shape files
  const parcels = await parseShapeFile(extracted['.shp'], extracted['.dbf']);
  
  // 4. Transform coordinates (UTM to WGS84)
  const transformedParcels = parcels.map(transformCoordinates);
  
  // 5. Update database
  await updateParcels(uploadId, transformedParcels);
}
```

### Phase 3: Data Update Strategy

#### Daily Updates
```javascript
// Mark previous day's parcels as historical
await markParcelsAsHistorical(zone, yesterday);

// Insert new parcels
await insertParcels(newParcels, { validFrom: today });
```

#### Weekly Updates
```javascript
// Keep last 4 weeks of data
await archiveParcelsOlderThan(zone, fourWeeksAgo);

// Update current week
await replaceParcels(zone, newParcels);
```

#### Bi-Weekly Updates
```javascript
// Full replacement strategy
await archiveAllParcels(zone);
await insertParcels(newParcels);
```

## Version Management

### Temporal Data Model
Each parcel has:
- `validFrom`: When this version became active
- `validTo`: When replaced (null = current)

```sql
-- Get current parcels
SELECT * FROM parcels 
WHERE validTo IS NULL;

-- Get parcels at specific date
SELECT * FROM parcels 
WHERE validFrom <= '2024-03-01' 
AND (validTo IS NULL OR validTo > '2024-03-01');
```

## Water Demand Calculation

### Triggered After Each Update
```javascript
async function calculateWaterDemand(parcelId) {
  const parcel = await getParcel(parcelId);
  const cropCoefficient = CROP_COEFFICIENTS[parcel.cropType];
  const efficiency = IRRIGATION_EFFICIENCIES[parcel.waterDemandMethod];
  
  const waterDemand = {
    daily: parcel.area * cropCoefficient * EVAPOTRANSPIRATION / efficiency,
    method: parcel.waterDemandMethod,
    lastCalculated: new Date()
  };
  
  await updateParcelWaterDemand(parcelId, waterDemand);
}
```

## Query Patterns

### 1. Get Latest Parcels by Zone
```javascript
const params = {
  TableName: 'rid-ms-parcels-prod',
  IndexName: 'zone-index',
  KeyConditionExpression: 'zone = :zone',
  FilterExpression: 'validTo = :null',
  ExpressionAttributeValues: {
    ':zone': 'Zone1',
    ':null': null
  }
};
```

### 2. Get Upload History
```javascript
const params = {
  TableName: 'rid-ms-shapefiles-prod',
  IndexName: 'status-uploadTime-index',
  KeyConditionExpression: 'status = :status',
  ScanIndexForward: false, // newest first
  Limit: 20
};
```

### 3. Track Processing Progress
```javascript
// Check if today's file was processed
const todaysUpload = await dynamodb.query({
  TableName: 'rid-ms-shapefiles-prod',
  FilterExpression: 'begins_with(uploadTime, :today)',
  ExpressionAttributeValues: {
    ':today': '2024-03-15'
  }
});
```

## Handling Updates

### Duplicate Prevention
```javascript
// Check if file was already processed today
const existingUpload = await checkTodaysUpload(fileName);
if (existingUpload && existingUpload.status === 'completed') {
  return { message: 'File already processed today' };
}
```

### Incremental Updates
For daily updates, only process changed parcels:
```javascript
const changes = await compareWithPrevious(newParcels, previousParcels);
await updateChangedParcels(changes.modified);
await insertNewParcels(changes.added);
await markDeletedParcels(changes.removed);
```

## Data Retention

### S3 Lifecycle Rules
```yaml
Rules:
  - Id: DeleteOldUploads
    Status: Enabled
    ExpirationInDays: 90  # Keep 3 months
    
  - Id: MoveToGlacier
    Status: Enabled
    Transitions:
      - Days: 30
        StorageClass: GLACIER
```

### DynamoDB Archival
- Current parcels: Always available
- Historical parcels: Keep 6 months
- Archived to S3 Glacier for compliance

## Monitoring & Alerts

### CloudWatch Metrics
- Upload count by interval type
- Processing time per file
- Failed processing attempts
- Storage usage trends

### Alarms
- No daily update received by 9 AM
- Processing failure rate > 5%
- S3 storage > 80% of limit