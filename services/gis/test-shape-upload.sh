#!/bin/bash

# Test script for GIS shape file upload end-to-end

echo "GIS Shape File Upload Test"
echo "=========================="
echo ""

# Check if shape file is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <path-to-shapefile.zip>"
    exit 1
fi

SHAPEFILE=$1
if [ ! -f "$SHAPEFILE" ]; then
    echo "Error: File not found: $SHAPEFILE"
    exit 1
fi

# Configuration
GIS_API_URL=${GIS_API_URL:-"http://localhost:3007/api/v1"}
GIS_TOKEN=${GIS_TOKEN:-"munbon-gis-shapefile"}

echo "Configuration:"
echo "- API URL: $GIS_API_URL"
echo "- Token: $GIS_TOKEN"
echo "- File: $SHAPEFILE"
echo ""

# Test 1: External API with auth token
echo "Test 1: External API Upload (with auth)"
echo "--------------------------------------"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  "$GIS_API_URL/shapefiles/upload" \
  -H "Authorization: Bearer $GIS_TOKEN" \
  -F "file=@$SHAPEFILE" \
  -F "waterDemandMethod=RID-MS" \
  -F "processingInterval=weekly" \
  -F "zone=Zone1" \
  -F "description=Test upload from script")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 200 ]; then
    echo "✅ Upload successful!"
    echo "Response: $BODY"
    UPLOAD_ID=$(echo "$BODY" | grep -o '"uploadId":"[^"]*' | cut -d'"' -f4)
    echo "Upload ID: $UPLOAD_ID"
else
    echo "❌ Upload failed with HTTP $HTTP_CODE"
    echo "Response: $BODY"
fi

echo ""

# Test 2: Internal API without auth
echo "Test 2: Internal API Upload (no auth)"
echo "------------------------------------"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  "$GIS_API_URL/shapefiles/internal/upload" \
  -F "file=@$SHAPEFILE" \
  -F "waterDemandMethod=ROS" \
  -F "processingInterval=daily" \
  -F "zone=Zone2" \
  -F "description=Internal test upload")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 200 ]; then
    echo "✅ Upload successful!"
    echo "Response: $BODY"
else
    echo "❌ Upload failed with HTTP $HTTP_CODE"
    echo "Response: $BODY"
fi

echo ""

# Test 3: Check queue processor status
echo "Test 3: Queue Processor Check"
echo "----------------------------"
if pgrep -f "shapefile-queue-processor" > /dev/null; then
    echo "✅ Queue processor is running"
else
    echo "⚠️  Queue processor is not running"
    echo "Start it with: npm run queue:processor"
fi

echo ""

# Test 4: Check AWS resources (if AWS CLI is available)
if command -v aws &> /dev/null; then
    echo "Test 4: AWS Resources Check"
    echo "--------------------------"
    
    # Check S3 bucket
    if aws s3 ls s3://munbon-gis-shape-files 2>&1 | grep -q "NoSuchBucket"; then
        echo "❌ S3 bucket 'munbon-gis-shape-files' does not exist"
    else
        echo "✅ S3 bucket exists"
        echo "Recent uploads:"
        aws s3 ls s3://munbon-gis-shape-files/shape-files/ --recursive | tail -5
    fi
    
    # Check SQS queue
    QUEUE_URL=$(aws sqs get-queue-url --queue-name munbon-gis-shapefile-queue 2>/dev/null | jq -r '.QueueUrl')
    if [ -n "$QUEUE_URL" ]; then
        echo "✅ SQS queue exists: $QUEUE_URL"
        MSG_COUNT=$(aws sqs get-queue-attributes --queue-url "$QUEUE_URL" --attribute-names ApproximateNumberOfMessages | jq -r '.Attributes.ApproximateNumberOfMessages')
        echo "Messages in queue: $MSG_COUNT"
    else
        echo "❌ SQS queue 'munbon-gis-shapefile-queue' does not exist"
    fi
else
    echo "ℹ️  AWS CLI not found, skipping AWS resource checks"
fi

echo ""
echo "Test complete!"
echo ""
echo "Next steps:"
echo "1. Check the queue processor logs for processing status"
echo "2. Query the GIS database to verify shape file data was saved"
echo "3. Check the parcels and zones tables for extracted data"