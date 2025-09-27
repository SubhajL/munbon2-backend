#!/bin/bash

echo "=== ZIP File Upload Test Script ==="
echo "Date: $(date)"
echo ""

# Configuration
GIS_API_URL=${GIS_API_URL:-"http://localhost:3007/api/v1"}
EXTERNAL_TOKEN=${EXTERNAL_TOKEN:-"munbon-gis-shapefile"}

# Check if zip file is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <path-to-file.zip>"
    echo "Note: This script accepts both .zip (shapefile) and .gpkg (geopackage) files"
    exit 1
fi

ZIP_FILE=$1
if [ ! -f "$ZIP_FILE" ]; then
    echo "Error: File not found: $ZIP_FILE"
    exit 1
fi

FILE_NAME=$(basename "$ZIP_FILE")
FILE_EXT="${FILE_NAME##*.}"

echo "Configuration:"
echo "- API URL: $GIS_API_URL"
echo "- File: $ZIP_FILE"
echo "- File type: .$FILE_EXT"
echo "- Token: ${EXTERNAL_TOKEN:0:10}..."
echo ""

# Test 1: Upload with authentication (main endpoint)
echo "1. Testing authenticated upload endpoint..."
echo "   POST $GIS_API_URL/shapefiles/upload"
echo ""

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  "$GIS_API_URL/shapefiles/upload" \
  -H "Authorization: Bearer $EXTERNAL_TOKEN" \
  -F "file=@$ZIP_FILE" \
  -F "waterDemandMethod=RID-MS" \
  -F "processingInterval=weekly" \
  -F "zone=Zone1" \
  -F "description=Test upload - $FILE_NAME")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 202 ]; then
    echo "✅ Upload successful (HTTP 202 - Accepted)"
    echo "Response:"
    echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"
    UPLOAD_ID=$(echo "$BODY" | jq -r '.data.uploadId' 2>/dev/null || echo "$BODY" | grep -o '"uploadId":"[^"]*' | cut -d'"' -f4)
    echo ""
    echo "Upload ID: $UPLOAD_ID"
else
    echo "❌ Upload failed with HTTP $HTTP_CODE"
    echo "Response: $BODY"
fi

echo ""
echo "----------------------------------------"
echo ""

# Test 2: External upload endpoint
echo "2. Testing external upload endpoint..."
echo "   POST $GIS_API_URL/shapefiles/external/upload"
echo ""

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  "$GIS_API_URL/shapefiles/external/upload" \
  -H "Authorization: Bearer $EXTERNAL_TOKEN" \
  -F "file=@$ZIP_FILE" \
  -F "waterDemandMethod=ROS" \
  -F "processingInterval=daily" \
  -F "zone=Zone2" \
  -F "description=External test upload - $FILE_NAME" \
  -F "metadata[source]=test-script")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 202 ]; then
    echo "✅ External upload successful (HTTP 202)"
    echo "Response:"
    echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"
    EXTERNAL_UPLOAD_ID=$(echo "$BODY" | jq -r '.uploadId' 2>/dev/null || echo "$BODY" | grep -o '"uploadId":"[^"]*' | cut -d'"' -f4)
    echo ""
    echo "Upload ID: $EXTERNAL_UPLOAD_ID"
else
    echo "❌ External upload failed with HTTP $HTTP_CODE"
    echo "Response: $BODY"
fi

echo ""
echo "----------------------------------------"
echo ""

# Check upload status if we have an upload ID
if [ -n "$UPLOAD_ID" ]; then
    echo "3. Checking upload status..."
    sleep 2  # Wait a bit for processing to start
    
    STATUS_RESPONSE=$(curl -s -X GET \
      "$GIS_API_URL/shapefiles/uploads/$UPLOAD_ID" \
      -H "Authorization: Bearer $EXTERNAL_TOKEN")
    
    echo "Status response:"
    echo "$STATUS_RESPONSE" | jq '.' 2>/dev/null || echo "$STATUS_RESPONSE"
fi

echo ""
echo "----------------------------------------"
echo ""

# Check AWS resources
if command -v aws &> /dev/null; then
    echo "4. Checking AWS resources..."
    
    # Check S3 bucket
    echo "   Checking S3 bucket..."
    BUCKET_NAME="munbon-gis-shape-files"
    if aws s3 ls "s3://$BUCKET_NAME" 2>&1 | grep -q "NoSuchBucket"; then
        echo "   ❌ S3 bucket '$BUCKET_NAME' not found"
    else
        echo "   ✅ S3 bucket exists"
        echo "   Recent uploads:"
        aws s3 ls "s3://$BUCKET_NAME/shape-files/" --recursive | sort -r | head -5
    fi
    
    echo ""
    
    # Check SQS queue
    echo "   Checking SQS queue..."
    QUEUE_NAME="munbon-gis-shapefile-queue"
    QUEUE_URL=$(aws sqs get-queue-url --queue-name "$QUEUE_NAME" 2>/dev/null | jq -r '.QueueUrl')
    
    if [ -n "$QUEUE_URL" ]; then
        echo "   ✅ SQS queue exists"
        QUEUE_ATTRS=$(aws sqs get-queue-attributes --queue-url "$QUEUE_URL" \
          --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible)
        
        MSG_COUNT=$(echo "$QUEUE_ATTRS" | jq -r '.Attributes.ApproximateNumberOfMessages')
        IN_FLIGHT=$(echo "$QUEUE_ATTRS" | jq -r '.Attributes.ApproximateNumberOfMessagesNotVisible')
        
        echo "   Messages in queue: $MSG_COUNT"
        echo "   Messages in flight: $IN_FLIGHT"
    else
        echo "   ❌ SQS queue '$QUEUE_NAME' not found"
    fi
else
    echo "4. AWS CLI not available - skipping AWS resource checks"
fi

echo ""
echo "=== Summary ==="
echo "File upload test completed."
echo ""
echo "The system accepts both:"
echo "- .zip files (containing shapefiles: .shp, .dbf, .shx, .prj)"
echo "- .gpkg files (GeoPackage format)"
echo ""
echo "Processing flow:"
echo "1. File uploaded to S3: shape-files/<date>/<uploadId>/<filename>"
echo "2. Message sent to SQS queue for async processing"
echo "3. Queue processor extracts and processes the file"
echo "4. Data saved to PostgreSQL database"
echo ""
echo "Next steps:"
echo "1. Monitor queue processor logs"
echo "2. Check database for processed parcels/zones"
echo "3. Use upload ID to track processing status"