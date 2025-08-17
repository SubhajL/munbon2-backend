# RID-MS Service Deployment Instructions

## Option 1: Quick Manual Deploy

1. **Install dependencies first**:
```bash
# Install serverless globally
npm install -g serverless

# Install AWS Lambda types
npm install --save-dev @types/node @types/aws-lambda
```

2. **Create the dist directory**:
```bash
mkdir -p dist/lambda
```

3. **Compile the simple handler**:
```bash
npx tsc src/lambda/simple-handler.ts --outDir dist --skipLibCheck --esModuleInterop --target ES2018 --module commonjs
```

4. **Deploy to AWS**:
```bash
serverless deploy --config serverless-simple.yml
```

## Option 2: Fix All Dependencies

Run the fix script:
```bash
chmod +x fix-build-errors.sh
./fix-build-errors.sh
```

Then deploy:
```bash
npm run deploy
```

## Option 3: Quick Deploy Script

```bash
chmod +x quick-deploy.sh
./quick-deploy.sh
```

## What Gets Deployed

After deployment, you'll have these endpoints:

1. **Upload SHAPE file**: 
   - POST `https://{api-id}.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/shapefiles/upload`

2. **Get SHAPE file metadata**:
   - GET `https://{api-id}.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/shapefiles/{id}`

3. **List SHAPE files**:
   - GET `https://{api-id}.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/shapefiles`

4. **Get parcels**:
   - GET `https://{api-id}.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/shapefiles/{id}/parcels`

5. **Export as GeoJSON**:
   - GET `https://{api-id}.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/shapefiles/{id}/export/geojson`

## Important Notes

- The deployed endpoints are placeholders that return success messages
- Full functionality requires:
  - Database connection (PostgreSQL with PostGIS)
  - S3 bucket permissions
  - SQS queue for processing
- These will be configured after initial deployment

## Testing After Deployment

Test the upload endpoint:
```bash
curl -X POST https://{api-id}.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/shapefiles/upload \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

Expected response:
```json
{
  "message": "Shape file upload endpoint is ready",
  "info": "This endpoint will handle SHAPE file uploads once connected to S3 and database"
}
```