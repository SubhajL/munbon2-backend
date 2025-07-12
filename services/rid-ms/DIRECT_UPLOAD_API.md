# RID-MS Direct File Upload API

## Overview

This API allows third parties to upload shape files directly without base64 encoding. Files are sent as standard multipart/form-data, just like uploading a file through a web form.

## Endpoint

```
POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/rid-ms/upload
```

## Authentication

Include the Bearer token in the Authorization header:
```
Authorization: Bearer munbon-ridms-shape
```

## Request Format

- **Method**: POST
- **Content-Type**: multipart/form-data
- **Body**: Form data with file and optional metadata

## Form Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| file | File | Yes | The ZIP file containing shape files |
| waterDemandMethod | String | No | Method: "RID-MS", "ROS", or "AWD" (default: "RID-MS") |
| processingInterval | String | No | Interval: "daily", "weekly", or "bi-weekly" (default: "weekly") |
| zone | String | No | Zone identifier (e.g., "Zone1") |
| uploadedBy | String | No | Uploader identification |
| description | String | No | Description of the upload |

## Example Usage

### Using cURL (Recommended)
```bash
curl -X POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/rid-ms/upload \
  -H "Authorization: Bearer munbon-ridms-shape" \
  -F "file=@ridmb_parcels_2024.zip" \
  -F "uploadedBy=RID-NakhonRatchasima" \
  -F "description=Weekly parcel update"
```

### Using the Push Script
```bash
./push-shapefile-direct.sh ridmb_parcels_2024.zip prod
```

### Using Postman
1. Set method to POST
2. Set URL to the endpoint above
3. Go to Authorization tab, select "Bearer Token", enter: `munbon-ridms-shape`
4. Go to Body tab, select "form-data"
5. Add a field with key "file", change type to "File", select your ZIP file
6. Add any optional fields as text

### Using Python
```python
import requests

url = 'https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/rid-ms/upload'
headers = {
    'Authorization': 'Bearer munbon-ridms-shape'
}

with open('ridmb_parcels_2024.zip', 'rb') as f:
    files = {'file': ('ridmb_parcels_2024.zip', f, 'application/zip')}
    data = {
        'uploadedBy': 'RID-NakhonRatchasima',
        'description': 'Weekly update'
    }
    
    response = requests.post(url, headers=headers, files=files, data=data)
    print(response.json())
```

### Using PHP
```php
$curl = curl_init();
$file = new CURLFile('ridmb_parcels_2024.zip', 'application/zip', 'ridmb_parcels_2024.zip');

curl_setopt_array($curl, [
    CURLOPT_URL => 'https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/rid-ms/upload',
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
    CURLOPT_HTTPHEADER => [
        'Authorization: Bearer munbon-ridms-shape'
    ],
    CURLOPT_POSTFIELDS => [
        'file' => $file,
        'uploadedBy' => 'RID-NakhonRatchasima',
        'description' => 'Weekly update'
    ]
]);

$response = curl_exec($curl);
curl_close($curl);
echo $response;
```

## Response

### Success (200 OK)
```json
{
  "success": true,
  "uploadId": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Shape file uploaded successfully and queued for processing",
  "fileName": "ridmb_parcels_2024.zip",
  "fileSize": 1048576,
  "uploadedAt": "2024-03-15T10:30:00.000Z"
}
```

### Error Responses

**401 Unauthorized**
```json
{
  "error": "Missing authorization header"
}
```

**403 Forbidden**
```json
{
  "error": "Invalid authorization token"
}
```

**400 Bad Request**
```json
{
  "error": "No file uploaded"
}
```

**400 Bad Request**
```json
{
  "error": "Only .zip files are accepted"
}
```

## File Requirements

1. **Format**: ZIP archive containing shape files
2. **Required files in ZIP**:
   - `.shp` - Shape geometry
   - `.dbf` - Attribute data
   - `.shx` - Shape index
3. **Optional files**:
   - `.prj` - Projection information
4. **Maximum size**: 100 MB

## Processing Flow

1. **Upload**: File sent directly to API (no encoding needed)
2. **Storage**: File stored in AWS S3
3. **Queue**: Processing job added to queue
4. **Processing**: Shape files extracted and processed asynchronously
5. **Results**: Available through data access APIs

## Advantages of Direct Upload

1. **Simpler**: No base64 encoding required
2. **Efficient**: 25% less data transfer
3. **Standard**: Uses normal HTTP file upload
4. **Compatible**: Works with any HTTP client
5. **Faster**: No encoding/decoding overhead

## Notes

- The endpoint accepts only one file per request
- All zones data should be included in the single ZIP file
- Processing is asynchronous - upload returns immediately
- Use the returned `uploadId` to track processing status (future feature)