# RID-MS External API Documentation

## Overview

The RID-MS External API allows authorized external parties (such as the Royal Irrigation Department) to push SHAPE files for processing. This API follows a similar pattern to IoT sensor data ingestion, using token-based authentication and base64-encoded file content.

## Authentication

All requests must include a Bearer token in the Authorization header:

```
Authorization: Bearer munbon-ridms-shape
```

## API Endpoint

### Push Shape File

**Endpoint**: `POST /api/external/shapefile/push`

**Description**: Upload a zipped SHAPE file for processing

**Headers**:
- `Content-Type: application/json`
- `Authorization: Bearer munbon-ridms-shape`

**Request Body**:
```json
{
  "fileName": "parcels_zone1_2024.zip",
  "fileContent": "<base64-encoded-zip-file>",
  "waterDemandMethod": "AWD",
  "processingInterval": "weekly",
  "metadata": {
    "zone": "Zone1",
    "uploadedBy": "RID-NakhonRatchasima",
    "description": "Weekly parcel update for Zone 1"
  }
}
```

**Parameters**:
- `fileName` (required): Name of the zip file. Must end with `.zip`
- `fileContent` (required): Base64-encoded content of the zip file
- `waterDemandMethod` (optional): Calculation method - "RID-MS", "ROS", or "AWD" (default: "RID-MS")
- `processingInterval` (optional): Processing frequency - "daily", "weekly", or "bi-weekly" (default: "weekly")
- `metadata` (optional): Additional metadata object with custom fields

**Response** (Success - 200):
```json
{
  "success": true,
  "uploadId": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Shape file uploaded successfully and queued for processing",
  "fileName": "parcels_zone1_2024.zip",
  "uploadedAt": "2024-03-15T10:30:00.000Z"
}
```

**Error Responses**:

401 Unauthorized:
```json
{
  "error": "Missing authorization header"
}
```

403 Forbidden:
```json
{
  "error": "Invalid authorization token"
}
```

400 Bad Request:
```json
{
  "error": "Missing required fields: fileName and fileContent"
}
```

500 Internal Server Error:
```json
{
  "error": "Internal server error",
  "message": "Error details"
}
```

## Example Usage

### Using cURL

```bash
# Prepare your shape file
zip parcels.zip *.shp *.shx *.dbf *.prj

# Convert to base64
base64 parcels.zip > parcels_base64.txt

# Send to API
curl -X POST https://api.munbon.com/api/external/shapefile/push \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer munbon-ridms-shape" \
  -d '{
    "fileName": "parcels.zip",
    "fileContent": "'$(cat parcels_base64.txt)'",
    "waterDemandMethod": "AWD",
    "processingInterval": "weekly",
    "metadata": {
      "zone": "Zone1",
      "uploadedBy": "RID-Office"
    }
  }'
```

### Using Python

```python
import requests
import base64
import json

# Read and encode the zip file
with open('parcels.zip', 'rb') as f:
    file_content = base64.b64encode(f.read()).decode('utf-8')

# Prepare the request
url = 'https://api.munbon.com/api/external/shapefile/push'
headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer munbon-ridms-shape'
}
data = {
    'fileName': 'parcels.zip',
    'fileContent': file_content,
    'waterDemandMethod': 'AWD',
    'processingInterval': 'weekly',
    'metadata': {
        'zone': 'Zone1',
        'uploadedBy': 'RID-Office'
    }
}

# Send the request
response = requests.post(url, headers=headers, json=data)
print(response.json())
```

### Using Node.js

```javascript
const fs = require('fs');
const axios = require('axios');

// Read and encode the zip file
const fileContent = fs.readFileSync('parcels.zip').toString('base64');

// Send the request
axios.post('https://api.munbon.com/api/external/shapefile/push', {
  fileName: 'parcels.zip',
  fileContent: fileContent,
  waterDemandMethod: 'AWD',
  processingInterval: 'weekly',
  metadata: {
    zone: 'Zone1',
    uploadedBy: 'RID-Office'
  }
}, {
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer munbon-ridms-shape'
  }
})
.then(response => {
  console.log('Success:', response.data);
})
.catch(error => {
  console.error('Error:', error.response.data);
});
```

## File Format Requirements

The uploaded file must be a ZIP archive containing the following required SHAPE file components:
- `.shp` - Shape format file
- `.shx` - Shape index file
- `.dbf` - Attribute format file

Optional but recommended:
- `.prj` - Projection format file (assumed to be UTM Zone 48N if not provided)

## Shape File Attribute Requirements

The SHAPE file should contain parcels with the following attributes (case-insensitive):

**Required**:
- `PARCEL_ID` or `ID` - Unique identifier for the parcel

**Recommended**:
- `ZONE` - Irrigation zone identifier
- `SUBZONE` - Sub-zone identifier
- `LAND_USE` - Type of land use
- `CROP_TYPE` - Current crop type
- `OWNER` - Land owner information
- `PLANTING_DATE` - Crop planting date
- `HARVEST_DATE` - Expected harvest date
- `WATER_DEMAND_METHOD` - Override method per parcel (RID-MS, ROS, or AWD)

## Processing Flow

1. **Upload**: Your application sends the shape file to the API endpoint
2. **Validation**: The API validates the token and file format
3. **Storage**: The file is stored in AWS S3 with a unique ID
4. **Queue**: A processing message is sent to SQS
5. **Processing**: Lambda functions extract parcels and calculate water demand
6. **Storage**: Results are stored in DynamoDB
7. **Notification**: (Future) Webhook notification of completion

## Rate Limits

- Maximum file size: 100 MB (after base64 encoding)
- Maximum requests per minute: 10
- Maximum concurrent uploads: 5

## Best Practices

1. **File Size**: Compress shape files efficiently before zipping
2. **Batch Processing**: Group multiple shape files into one zip when possible
3. **Error Handling**: Implement retry logic with exponential backoff
4. **Monitoring**: Track upload IDs for status checking (future feature)
5. **Coordinate System**: Ensure files use UTM Zone 48N or include proper .prj file

## Support

For technical support or to report issues:
- Email: munbon-support@rid.go.th
- Phone: +66 2 xxx xxxx

## Changelog

- **v1.0.0** (2024-03-15): Initial release with basic push functionality