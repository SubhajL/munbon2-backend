# Reliability Improvements for Sensor Data Service

## 🔒 Message Processing Reliability

### Changes Implemented:

1. **Conditional Message Deletion**
   - Messages are only deleted from SQS after successful database writes
   - Failed messages remain in queue for retry
   - Prevents data loss during database outages

2. **Transaction Support**
   - All database operations wrapped in transactions
   - If any operation fails, entire transaction rolls back
   - Ensures data consistency

3. **Enhanced Error Handling**
   - Detailed error logging with message IDs
   - Clear indication when messages will be retried
   - Proper error propagation to prevent premature deletion

## 📋 How It Works

### Success Flow:
1. Consumer receives message from SQS
2. Begins database transaction
3. Inserts/updates sensor registry
4. Inserts sensor readings
5. Inserts specific sensor data (water level/moisture)
6. Commits transaction
7. Deletes message from SQS ✅

### Failure Flow:
1. Consumer receives message from SQS
2. Begins database transaction
3. Any database operation fails
4. Transaction rolls back automatically
5. Error is logged
6. Message is NOT deleted from SQS ❌
7. Message becomes visible again after timeout
8. Consumer retries on next poll

## 🧪 Testing Error Scenarios

### Test 1: Database Validation Error
```bash
node test-error-handling.js
```

### Test 2: Database Connection Failure
```bash
# Stop database
docker stop munbon-timescaledb

# Send test data (will fail)
npm run test:send

# Check messages remain in queue
npm run check:sqs

# Restart database
docker start munbon-timescaledb

# Messages will be automatically reprocessed
```

### Test 3: Partial Failure
If processing succeeds for sensor registry but fails for readings:
- Entire transaction rolls back
- No partial data in database
- Message stays in queue for retry

## 🔍 Monitoring

### Check Failed Messages:
```bash
# View consumer logs for errors
tail -f consumer.log | grep -E "Error|error|retry|rollback"

# Check SQS queue status
npm run check:sqs

# Check Dead Letter Queue (if configured)
aws sqs get-queue-attributes \
  --queue-url <DLQ-URL> \
  --attribute-names ApproximateNumberOfMessages
```

## 🚀 Benefits

1. **Zero Data Loss**: Messages persist until successfully processed
2. **Automatic Recovery**: System self-heals when database comes back online
3. **Data Integrity**: No partial writes due to transactions
4. **Visibility**: Clear logging of retry attempts
5. **Scalability**: Can handle temporary spikes without losing data

## ⚙️ Configuration

### SQS Settings (Recommended):
- **Visibility Timeout**: 30 seconds (time to process message)
- **Max Receive Count**: 5 (retry attempts before DLQ)
- **Message Retention**: 4 days (time to fix issues)

### Dead Letter Queue:
Configure a DLQ for messages that fail after max retries:
```javascript
{
  RedrivePolicy: {
    deadLetterTargetArn: "arn:aws:sqs:region:account:dlq-name",
    maxReceiveCount: 5
  }
}
```

## 📊 Metrics to Monitor

1. **SQS ApproximateNumberOfMessagesNotVisible**: Messages being processed
2. **SQS ApproximateNumberOfMessages**: Messages waiting
3. **Consumer Error Rate**: Failed processing attempts
4. **Database Transaction Rollback Rate**: Failed writes
5. **DLQ Message Count**: Permanently failed messages