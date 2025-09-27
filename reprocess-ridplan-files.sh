#!/bin/bash

# Reprocess recent RidPlanning files from S3
# Files from the last few days that are likely to contain data_ridplan folder

echo "Starting to reprocess RidPlanning files from S3..."
echo "Date: $(date)"
echo ""

# Array of files to reprocess (most recent ones that are >1MB, likely containing the 3 folders)
declare -a FILES=(
    "shape-files/2025-09-10/0a5e83b2-bb6c-4cbb-a734-6cdd2dddd276/data_upload__20250910.zip"
    "shape-files/2025-09-09/b702dad9-c0b4-42f4-89a4-800ce8122094/data_upload__20250909.zip"
    "shape-files/2025-09-08/832f493b-4680-4304-95a9-a28fc6d73dc5/data_upload__20250908.zip"
    "shape-files/2025-09-07/3dec6305-06eb-4e8d-87e8-2e77814afdeb/data_upload__20250907.zip"
    "shape-files/2025-09-07/8f2b16f8-a111-4027-915c-cb03d91f7332/data_upload__20250907.zip"
    "shape-files/2025-09-06/a82aeb84-ec75-4221-b154-1326910f432f/data_upload__20250906.zip"
    "shape-files/2025-09-05/19a58b05-0a6a-4cda-9ea4-a0c12e78e1a9/data_upload__20250905.zip"
    "shape-files/2025-09-03/22dddfd3-d107-4b66-83d0-45ab5a78f415/data_upload__20250903.zip"
    "shape-files/2025-09-03/86133023-1cd2-4c31-804e-89f78300513d/data_upload__20250903.zip"
    "shape-files/2025-09-01/4008b42c-6e79-4171-8a52-8f282e47c780/data_upload__20250901.zip"
    "shape-files/2025-08-29/3b6a6a97-1a6a-4181-b2c1-8e0e55ba6bbc/data_upload__20250829.zip"
    "shape-files/2025-08-28/0fe0b1dd-208c-42f9-90ce-e0e8ccd88bd8/data_upload__20250828.zip"
    "shape-files/2025-08-27/385c1a40-394e-4a19-88af-48274c6c2a2e/data_upload__20250827.zip"
    "shape-files/2025-08-25/7ce9eea7-8623-4bfe-a98c-03b0a79beb53/data_upload__20250825.zip"
    "shape-files/2025-08-24/e8afe9f7-7424-40af-844d-61324e530bdc/data_upload__20250824.zip"
    "shape-files/2025-08-22/a8fc843a-451c-41ff-8918-6c64319d7e45/data_upload__20250822.zip"
)

BUCKET="munbon-gis-shape-files"
QUEUE_URL="https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-gis-shapefile-queue"
REGION="ap-southeast-1"

# Function to send message to SQS
send_message() {
    local s3_key=$1
    local file_name=$(basename $s3_key)
    local upload_id=$(echo $s3_key | cut -d'/' -f3)
    
    echo "Sending message for: $file_name (Upload ID: $upload_id)"
    
    aws sqs send-message \
        --queue-url $QUEUE_URL \
        --region $REGION \
        --message-body "{
            \"uploadId\": \"$upload_id\",
            \"fileName\": \"$file_name\",
            \"s3Key\": \"$s3_key\",
            \"s3Bucket\": \"$BUCKET\",
            \"type\": \"shape-file\",
            \"metadata\": {
                \"reprocessed\": true,
                \"reprocessedAt\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
                \"source\": \"manual-reprocess\"
            }
        }" \
        --message-attributes '{
            "uploadType": {"StringValue": "ridplan-reprocess", "DataType": "String"}
        }' \
        --output json > /dev/null
    
    if [ $? -eq 0 ]; then
        echo "✓ Message sent successfully"
    else
        echo "✗ Failed to send message"
    fi
    echo ""
}

# Send messages for all files
echo "Sending ${#FILES[@]} messages to SQS queue..."
echo ""

for file in "${FILES[@]}"; do
    send_message "$file"
    # Small delay to avoid overwhelming the queue
    sleep 0.5
done

echo ""
echo "Reprocessing initiated for ${#FILES[@]} files"
echo "Monitor processing with:"
echo "  ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 'pm2 logs shapefile-queue-processor --lines 50'"
echo ""
echo "Check agricultural_plots table with:"
echo "  ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 \"docker exec postgres_timescale_postgis psql -U postgres -d munbon_dev -c 'SELECT COUNT(*) FROM gis.agricultural_plots'\""