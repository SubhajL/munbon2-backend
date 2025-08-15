const AWS = require('aws-sdk');

// Configure AWS
AWS.config.update({ region: 'ap-southeast-1' });
const sqs = new AWS.SQS();

const QUEUE_URL = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';

async function countWaterLevelMessages() {
  try {
    console.log('Checking SQS queue for water level messages...\n');
    
    let totalMessages = 0;
    let waterLevelMessages = 0;
    let sensorCounts = new Map();
    let latestTimestamps = new Map();
    
    // Check up to 1000 messages to get a good sample
    for (let i = 0; i < 100; i++) {
      const response = await sqs.receiveMessage({
        QueueUrl: QUEUE_URL,
        MaxNumberOfMessages: 10,
        VisibilityTimeout: 5, // Short visibility to just peek
        WaitTimeSeconds: 1
      }).promise();
      
      if (!response.Messages || response.Messages.length === 0) {
        break;
      }
      
      for (const message of response.Messages) {
        totalMessages++;
        
        try {
          const body = JSON.parse(message.Body);
          
          if (body.sensorType === 'water-level') {
            waterLevelMessages++;
            
            // Count by sensor ID
            const sensorId = body.sensorId;
            sensorCounts.set(sensorId, (sensorCounts.get(sensorId) || 0) + 1);
            
            // Track latest timestamp
            const timestamp = new Date(body.timestamp);
            if (!latestTimestamps.has(sensorId) || timestamp > latestTimestamps.get(sensorId)) {
              latestTimestamps.set(sensorId, timestamp);
            }
          }
        } catch (e) {
          // Skip malformed messages
        }
      }
      
      // Don't actually delete messages, just checking
      // Messages will return to queue after visibility timeout
    }
    
    // Get total queue size
    const queueAttrs = await sqs.getQueueAttributes({
      QueueUrl: QUEUE_URL,
      AttributeNames: ['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible']
    }).promise();
    
    const totalInQueue = parseInt(queueAttrs.Attributes.ApproximateNumberOfMessages || 0);
    const notVisible = parseInt(queueAttrs.Attributes.ApproximateNumberOfMessagesNotVisible || 0);
    
    console.log('=== SQS Queue Status ===');
    console.log(`Total messages in queue: ${totalInQueue}`);
    console.log(`Messages being processed: ${notVisible}`);
    console.log(`Total available: ${totalInQueue + notVisible}\n`);
    
    if (totalMessages > 0) {
      const waterLevelPercentage = ((waterLevelMessages / totalMessages) * 100).toFixed(1);
      console.log(`=== Sample Analysis (${totalMessages} messages checked) ===`);
      console.log(`Water level messages: ${waterLevelMessages} (${waterLevelPercentage}%)`);
      console.log(`Estimated water level messages in queue: ${Math.round(totalInQueue * waterLevelMessages / totalMessages)}\n`);
      
      console.log('=== Water Level Sensors Found ===');
      const sortedSensors = Array.from(sensorCounts.entries()).sort((a, b) => b[1] - a[1]);
      
      for (const [sensorId, count] of sortedSensors) {
        const latest = latestTimestamps.get(sensorId);
        console.log(`${sensorId}: ${count} messages, latest: ${latest.toISOString()}`);
      }
    } else {
      console.log('No messages available for sampling');
    }
    
  } catch (error) {
    console.error('Error:', error.message);
  }
}

countWaterLevelMessages().catch(console.error);