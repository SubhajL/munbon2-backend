# Deploy RID-MS SHAPE File Service to AWS

## Quick Deploy Steps

1. **Install Serverless Framework globally** (if not already installed):
```bash
npm install -g serverless
```

2. **Build the TypeScript code**:
```bash
npm run build
```

3. **Configure AWS credentials** (if not already configured):
```bash
serverless config credentials --provider aws --key YOUR_ACCESS_KEY --secret YOUR_SECRET_KEY
```

4. **Deploy to AWS**:
```bash
npm run deploy
```

## After Deployment

Once deployed, you'll get URLs like:

- **Upload SHAPE file**: 
  ```
  POST https://YOUR-API-ID.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/shapefiles/upload
  ```

- **Get SHAPE file metadata**:
  ```
  GET https://YOUR-API-ID.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/shapefiles/{id}
  ```

- **List SHAPE files**:
  ```
  GET https://YOUR-API-ID.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/shapefiles
  ```

- **Get parcels from SHAPE file**:
  ```
  GET https://YOUR-API-ID.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/shapefiles/{id}/parcels
  ```

- **Export as GeoJSON**:
  ```
  GET https://YOUR-API-ID.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/shapefiles/{id}/export/geojson
  ```

## Testing SHAPE File Upload

```bash
# Example upload using curl
curl -X POST https://YOUR-API-ID.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/shapefiles/upload \
  -H "Content-Type: multipart/form-data" \
  -F "shapefile=@/path/to/your/shapefile.zip" \
  -F "description=Zone 1 irrigation parcels" \
  -F "waterDemandMethod=RID-MS" \
  -F "processingInterval=daily"
```

## Important Notes

1. The service creates:
   - An S3 bucket for storing SHAPE files
   - An SQS queue for processing files asynchronously
   - Lambda functions for handling uploads and processing

2. Make sure you have:
   - AWS credentials configured
   - Proper IAM permissions for Lambda, S3, SQS, and API Gateway

3. To remove the deployment:
   ```bash
   npm run remove
   ```