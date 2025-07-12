#!/bin/bash

# RID-MS Shape File Direct Upload Script
# Usage: ./push-shapefile-direct.sh <zipfile> [environment]
# Example: ./push-shapefile-direct.sh parcels.zip prod

set -e

# Configuration
DEFAULT_ENV="dev"
TOKEN="munbon-ridms-shape"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check parameters
if [ $# -lt 1 ]; then
    echo -e "${RED}Error: Missing required parameter${NC}"
    echo "Usage: $0 <zipfile> [environment]"
    echo "Example: $0 parcels.zip prod"
    exit 1
fi

ZIP_FILE="$1"
ENVIRONMENT="${2:-$DEFAULT_ENV}"

# Validate zip file exists
if [ ! -f "$ZIP_FILE" ]; then
    echo -e "${RED}Error: File not found: $ZIP_FILE${NC}"
    exit 1
fi

# Validate file is a zip
if ! file "$ZIP_FILE" | grep -q "Zip archive"; then
    echo -e "${RED}Error: File is not a valid zip archive: $ZIP_FILE${NC}"
    exit 1
fi

# Set API endpoint based on environment
API_ID="c0zc2kfzd6"  # Your actual API Gateway ID
case $ENVIRONMENT in
    "dev")
        API_URL="https://${API_ID}.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/rid-ms/upload"
        ;;
    "staging")
        API_URL="https://${API_ID}.execute-api.ap-southeast-1.amazonaws.com/staging/api/v1/rid-ms/upload"
        ;;
    "prod")
        API_URL="https://${API_ID}.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/rid-ms/upload"
        ;;
    *)
        echo -e "${RED}Error: Invalid environment: $ENVIRONMENT${NC}"
        echo "Valid environments: dev, staging, prod"
        exit 1
        ;;
esac

echo -e "${YELLOW}Pushing shape file directly (no base64 encoding!)...${NC}"
echo "File: $ZIP_FILE"
echo "Environment: $ENVIRONMENT"
echo "API URL: $API_URL"
echo ""

# Get file size
FILE_SIZE=$(ls -lh "$ZIP_FILE" | awk '{print $5}')
echo "File size: $FILE_SIZE"

# Get filename
FILENAME=$(basename "$ZIP_FILE")

# Send the file directly using multipart/form-data
echo "Uploading file..."
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL" \
  -H "Authorization: Bearer ${TOKEN}" \
  -F "file=@${ZIP_FILE}" \
  -F "waterDemandMethod=RID-MS" \
  -F "processingInterval=weekly" \
  -F "uploadedBy=RID-NakhonRatchasima" \
  -F "description=Shape file upload from $(date)")

# Extract HTTP status code
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$RESPONSE" | sed '$d')

# Check response
if [ "$HTTP_CODE" -eq "200" ]; then
    echo -e "${GREEN}Success!${NC}"
    echo "Response:"
    echo "$RESPONSE_BODY" | python -m json.tool 2>/dev/null || echo "$RESPONSE_BODY"
    
    # Extract upload ID if available
    UPLOAD_ID=$(echo "$RESPONSE_BODY" | grep -o '"uploadId":"[^"]*' | cut -d'"' -f4)
    if [ ! -z "$UPLOAD_ID" ]; then
        echo ""
        echo -e "${GREEN}Upload ID: $UPLOAD_ID${NC}"
        echo "Save this ID to track processing status"
    fi
else
    echo -e "${RED}Error: Request failed with status code $HTTP_CODE${NC}"
    echo "Response:"
    echo "$RESPONSE_BODY" | python -m json.tool 2>/dev/null || echo "$RESPONSE_BODY"
    exit 1
fi