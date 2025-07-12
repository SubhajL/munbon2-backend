#!/bin/bash

echo "Checking S3 for uploaded SHAPE files..."
echo "======================================"

BUCKET="munbon-shape-files-dev"
UPLOAD_ID="32d19024-76ec-44b1-b8e0-7ca560b081a3"

# Check if file exists in S3
echo "Looking for recent upload with ID: $UPLOAD_ID"
aws s3 ls "s3://${BUCKET}/shape-files/2025-06-29/${UPLOAD_ID}/" --recursive

echo ""
echo "All files in the bucket today:"
aws s3 ls "s3://${BUCKET}/shape-files/2025-06-29/" --recursive

echo ""
echo "To download a file:"
echo "aws s3 cp s3://${BUCKET}/shape-files/2025-06-29/${UPLOAD_ID}/test.zip ./downloaded-test.zip"