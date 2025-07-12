#!/bin/bash

# Check SQS messages for uploaded zip files

QUEUE_NAME="munbon-sensor-ingestion-dev-queue"
REGION="ap-southeast-1"

echo "Checking SQS queue: $QUEUE_NAME"
echo "================================"

# Get queue URL
QUEUE_URL=$(aws sqs get-queue-url --queue-name $QUEUE_NAME --region $REGION --query 'QueueUrl' --output text 2>/dev/null)

if [ $? -ne 0 ]; then
    echo "Error: Could not get queue URL. Make sure AWS CLI is configured."
    echo "Run: aws configure"
    exit 1
fi

echo "Queue URL: $QUEUE_URL"
echo ""

# Get queue attributes
echo "Queue Statistics:"
aws sqs get-queue-attributes \
    --queue-url $QUEUE_URL \
    --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible \
    --region $REGION \
    --output table

echo ""
echo "Receiving up to 10 messages (without deleting them):"
echo "---------------------------------------------------"

# Receive messages without deleting them
MESSAGES=$(aws sqs receive-message \
    --queue-url $QUEUE_URL \
    --max-number-of-messages 10 \
    --visibility-timeout 0 \
    --region $REGION \
    --output json)

if [ -z "$MESSAGES" ] || [ "$MESSAGES" = "null" ]; then
    echo "No messages in queue"
else
    echo "$MESSAGES" | jq -r '.Messages[] | "Message ID: \(.MessageId)\nBody: \(.Body | fromjson | {type, uploadId, fileName, uploadedAt, waterDemandMethod})\n---"'
fi

echo ""
echo "To delete a message after processing:"
echo "aws sqs delete-message --queue-url $QUEUE_URL --receipt-handle <RECEIPT_HANDLE>"