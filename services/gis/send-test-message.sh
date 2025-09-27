#!/bin/bash

# Send a test message to the shapefile queue
aws sqs send-message \
  --queue-url https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-gis-shapefile-queue \
  --message-body '{
    "uploadId": "test-discovery-001",
    "fileName": "test_rid_ms_data.zip",
    "s3Key": "uploads/test_rid_ms_data.zip",
    "uploadedBy": "discovery-test",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
  }' \
  --region ap-southeast-1

echo "Test message sent to discover RID-MS file format"