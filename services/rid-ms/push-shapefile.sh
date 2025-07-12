#!/bin/bash

# RID-MS Shape File Push Script
# Usage: ./push-shapefile.sh <zipfile> [environment]
# Example: ./push-shapefile.sh parcels.zip prod

set -e

# Configuration
DEFAULT_ENV="dev"
DEFAULT_TOKEN="munbon-ridms-shape"

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
case $ENVIRONMENT in
    "dev")
        API_URL="https://api-dev.munbon.com/api/external/shapefile/push"
        ;;
    "staging")
        API_URL="https://api-staging.munbon.com/api/external/shapefile/push"
        ;;
    "prod")
        API_URL="https://api.munbon.com/api/external/shapefile/push"
        ;;
    *)
        echo -e "${RED}Error: Invalid environment: $ENVIRONMENT${NC}"
        echo "Valid environments: dev, staging, prod"
        exit 1
        ;;
esac

echo -e "${YELLOW}Pushing shape file to RID-MS Service...${NC}"
echo "File: $ZIP_FILE"
echo "Environment: $ENVIRONMENT"
echo "API URL: $API_URL"
echo ""

# Get file size
FILE_SIZE=$(ls -lh "$ZIP_FILE" | awk '{print $5}')
echo "File size: $FILE_SIZE"

# Check file size (max 75MB before base64 encoding)
MAX_SIZE=78643200  # 75MB in bytes
ACTUAL_SIZE=$(stat -f%z "$ZIP_FILE" 2>/dev/null || stat -c%s "$ZIP_FILE" 2>/dev/null)
if [ $ACTUAL_SIZE -gt $MAX_SIZE ]; then
    echo -e "${RED}Error: File size exceeds 75MB limit${NC}"
    exit 1
fi

# Base64 encode the file
echo "Encoding file..."
BASE64_CONTENT=$(base64 < "$ZIP_FILE" | tr -d '\n')

# Get filename
FILENAME=$(basename "$ZIP_FILE")

# Get current date for metadata
UPLOAD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Prepare JSON payload
JSON_PAYLOAD=$(cat <<EOF
{
  "fileName": "$FILENAME",
  "fileContent": "$BASE64_CONTENT",
  "waterDemandMethod": "RID-MS",
  "processingInterval": "weekly",
  "metadata": {
    "uploadedBy": "push-shapefile-script",
    "uploadDate": "$UPLOAD_DATE",
    "environment": "$ENVIRONMENT",
    "originalSize": "$FILE_SIZE"
  }
}
EOF
)

# Create temporary file for payload
TEMP_FILE=$(mktemp)
echo "$JSON_PAYLOAD" > "$TEMP_FILE"

# Send request
echo "Sending request to API..."
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DEFAULT_TOKEN" \
  -d "@$TEMP_FILE")

# Clean up temp file
rm -f "$TEMP_FILE"

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