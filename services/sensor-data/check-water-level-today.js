#!/usr/bin/env node

const AWS = require('aws-sdk');
const sqs = new AWS.SQS({ region: 'ap-southeast-1' });

const MAIN_QUEUE_URL = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';
const DLQ_URL = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-dlq';

// Get today's date in UTC
const today = new Date().toISOString().split('T')[0];
console.log(`🔍 Checking for water level data from today (${today})\n`);

async function checkQueue(queueUrl, queueName) {
  console.log(`\n📊 Checking ${queueName}...`);
  
  try {
    // Get queue attributes
    const attributes = await sqs.getQueueAttributes({
      QueueUrl: queueUrl,
      AttributeNames: ['All']
    }).promise();
    
    console.log(`Total messages: ${attributes.Attributes.ApproximateNumberOfMessages}`);
    console.log(`In flight: ${attributes.Attributes.ApproximateNumberOfMessagesNotVisible}\n`);
    
    // Sample messages
    let waterLevelCount = 0;
    let todayCount = 0;
    let totalChecked = 0;
    const maxChecks = 20; // Check up to 200 messages (20 batches of 10)
    const waterLevelMessages = [];
    const deviceIds = new Set();
    
    for (let i = 0; i < maxChecks; i++) {
      const result = await sqs.receiveMessage({
        QueueUrl: queueUrl,
        MaxNumberOfMessages: 10,
        VisibilityTimeout: 0,
        WaitTimeSeconds: 1,
        MessageAttributeNames: ['All']
      }).promise();
      
      if (!result.Messages || result.Messages.length === 0) break;
      
      for (const message of result.Messages) {
        totalChecked++;
        try {
          const body = JSON.parse(message.Body);
          
          // Check if it's a water level message
          const isWaterLevel = 
            body.tokenGroup === 'water-level-munbon' ||
            body.token?.includes('water-level') ||
            body.type === 'water-level' ||
            body.sensorType === 'water-level' ||
            (body.data && typeof body.data.level !== 'undefined');
          
          if (isWaterLevel) {
            waterLevelCount++;
            
            const messageDate = (body.timestamp || body.uploadedAt || body.createdAt || '').split('T')[0];
            const deviceId = body.data?.deviceId || body.deviceId || body.sensorId || 'unknown';
            deviceIds.add(deviceId);
            
            if (messageDate === today) {
              todayCount++;
              if (waterLevelMessages.length < 5) {
                waterLevelMessages.push({
                  timestamp: body.timestamp,
                  deviceId: deviceId,
                  level: body.data?.level,
                  voltage: body.data?.voltage,
                  temperature: body.data?.temperature,
                  location: body.location || body.data?.location
                });
              }
            }
          }
        } catch (e) {
          // Skip invalid messages
        }
      }
      
      process.stdout.write(`\rChecked ${totalChecked} messages...`);
    }
    
    console.log(`\n\n✅ Water Level Summary for ${queueName}:`);
    console.log(`- Total water level messages found: ${waterLevelCount}`);
    console.log(`- Water level messages from today: ${todayCount}`);
    console.log(`- Unique devices: ${deviceIds.size}`);
    
    if (deviceIds.size > 0) {
      console.log(`\n📱 Device IDs found:`);
      Array.from(deviceIds).slice(0, 10).forEach(id => console.log(`  - ${id}`));
      if (deviceIds.size > 10) {
        console.log(`  ... and ${deviceIds.size - 10} more`);
      }
    }
    
    if (waterLevelMessages.length > 0) {
      console.log(`\n💧 Sample water level messages from today:`);
      waterLevelMessages.forEach((msg, idx) => {
        console.log(`\nMessage ${idx + 1}:`);
        console.log(`  Time: ${msg.timestamp}`);
        console.log(`  Device: ${msg.deviceId}`);
        console.log(`  Level: ${msg.level} cm`);
        console.log(`  Voltage: ${msg.voltage}%`);
        if (msg.temperature) console.log(`  Temperature: ${msg.temperature}°C`);
        if (msg.location) console.log(`  Location: ${JSON.stringify(msg.location)}`);
      });
    }
    
    // Estimate totals
    if (totalChecked > 0 && parseInt(attributes.Attributes.ApproximateNumberOfMessages) > 0) {
      const totalMessages = parseInt(attributes.Attributes.ApproximateNumberOfMessages);
      const estimatedWaterLevel = Math.round((waterLevelCount / totalChecked) * totalMessages);
      const estimatedToday = Math.round((todayCount / totalChecked) * totalMessages);
      
      console.log(`\n📈 Estimated totals:`);
      console.log(`  - Total water level messages in queue: ~${estimatedWaterLevel}`);
      console.log(`  - Water level messages from today: ~${estimatedToday}`);
    }
    
  } catch (error) {
    console.error(`Error checking ${queueName}:`, error.message);
  }
}

async function main() {
  // Check main queue
  await checkQueue(MAIN_QUEUE_URL, 'Main Queue');
  
  // Check DLQ
  await checkQueue(DLQ_URL, 'Dead Letter Queue (DLQ)');
  
  console.log('\n✅ Analysis complete!');
}

main().catch(console.error);