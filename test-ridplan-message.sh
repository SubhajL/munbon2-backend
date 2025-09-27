#!/bin/bash

# Send test message to SQS for ridplan data processing
aws sqs send-message \
  --queue-url https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-gis-shapefile-queue \
  --region ap-southeast-1 \
  --message-body '{
    "uploadId": "test-ridplan-'$(date +%s)'",
    "fileName": "RidPlanning_Munbon2.zip",
    "s3Key": "uploads/RidPlanning_Munbon2.zip",
    "s3Bucket": "munbon-gis-shape-files"
  }' \
  --message-attributes '{
    "uploadType": {"StringValue": "ridplan", "DataType": "String"}
  }'

echo "Test message sent to queue"