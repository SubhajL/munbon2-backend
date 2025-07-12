const { SQSClient, GetQueueAttributesCommand, ReceiveMessageCommand } = require('@aws-sdk/client-sqs');

// Configure AWS SDK v3
const sqs = new SQSClient({ region: 'ap-southeast-1' });

const QUEUE_URL = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';
const SAMPLE_SIZE = 50; // Number of messages to sample

// Message type counters
const messageTypes = {
  'water-level': { count: 0, devices: new Set(), examples: [] },
  'moisture': { count: 0, devices: new Set(), examples: [] },
  'shape-file': { count: 0, files: [], uploadIds: [] },
  'unknown': { count: 0, types: [] }
};

async function analyzeQueue() {
  console.log('🔍 Analyzing SQS Queue...\n');

  // Get queue attributes
  try {
    const command = new GetQueueAttributesCommand({
      QueueUrl: QUEUE_URL,
      AttributeNames: ['All']
    });
    const attrs = await sqs.send(command);

    const totalMessages = parseInt(attrs.Attributes.ApproximateNumberOfMessages);
    const inFlight = parseInt(attrs.Attributes.ApproximateNumberOfMessagesNotVisible);
    const delayed = parseInt(attrs.Attributes.ApproximateNumberOfMessagesDelayed);

    console.log('📊 Overall Queue Statistics:');
    console.log('═══════════════════════════════════════');
    console.log(`Total Messages:        ${totalMessages.toLocaleString()}`);
    console.log(`Being Processed:       ${inFlight}`);
    console.log(`Delayed:               ${delayed}`);
    console.log('');

    if (totalMessages === 0) {
      console.log('✅ Queue is empty!');
      return;
    }

    // Sample messages
    console.log(`Sampling ${SAMPLE_SIZE} messages for type analysis...\n`);
    
    let sampled = 0;
    let attempts = 0;
    
    while (sampled < SAMPLE_SIZE && attempts < 10) {
      attempts++;
      
      const command = new ReceiveMessageCommand({
        QueueUrl: QUEUE_URL,
        MaxNumberOfMessages: 10,
        VisibilityTimeout: 0,
        MessageAttributeNames: ['All'],
        WaitTimeSeconds: 1
      });
      const result = await sqs.send(command);

      if (result.Messages) {
        for (const msg of result.Messages) {
          try {
            const body = JSON.parse(msg.Body);
            
            // Identify message type
            if (body.type === 'shape-file') {
              messageTypes['shape-file'].count++;
              if (body.fileName) messageTypes['shape-file'].files.push(body.fileName);
              if (body.uploadId) messageTypes['shape-file'].uploadIds.push(body.uploadId);
            } else if (body.sensorType?.includes('water-level') || body.tokenGroup?.includes('water-level')) {
              messageTypes['water-level'].count++;
              if (body.data?.deviceId) messageTypes['water-level'].devices.add(body.data.deviceId);
              if (messageTypes['water-level'].examples.length < 2) {
                messageTypes['water-level'].examples.push({
                  device: body.data?.deviceId,
                  level: body.data?.level,
                  time: body.timestamp
                });
              }
            } else if (body.sensorType?.includes('moisture') || body.tokenGroup?.includes('moisture')) {
              messageTypes['moisture'].count++;
              if (body.data?.deviceId) messageTypes['moisture'].devices.add(body.data.deviceId);
              if (messageTypes['moisture'].examples.length < 2) {
                messageTypes['moisture'].examples.push({
                  device: body.data?.deviceId,
                  moisture: body.data?.humid_hi,
                  time: body.timestamp
                });
              }
            } else {
              messageTypes['unknown'].count++;
              messageTypes['unknown'].types.push(body.sensorType || body.type || 'undefined');
            }
            
            sampled++;
          } catch (e) {
            messageTypes['unknown'].count++;
            sampled++;
          }
        }
      }
      
      process.stdout.write(`\rProcessed ${sampled}/${SAMPLE_SIZE} messages...`);
    }
    
    console.log('\n');

    // Calculate percentages and estimates
    const total = Object.values(messageTypes).reduce((sum, type) => sum + type.count, 0);
    
    console.log('📝 Message Type Breakdown:');
    console.log('═══════════════════════════════════════');
    
    // Water Level
    if (messageTypes['water-level'].count > 0) {
      const pct = ((messageTypes['water-level'].count / total) * 100).toFixed(1);
      const est = Math.round((messageTypes['water-level'].count / total) * totalMessages);
      console.log(`\n💧 Water Level Messages:`);
      console.log(`   Count in sample:     ${messageTypes['water-level'].count} (${pct}%)`);
      console.log(`   Estimated in queue:  ~${est.toLocaleString()}`);
      console.log(`   Unique devices:      ${messageTypes['water-level'].devices.size}`);
      if (messageTypes['water-level'].examples.length > 0) {
        console.log(`   Example: Device ${messageTypes['water-level'].examples[0].device}, Level: ${messageTypes['water-level'].examples[0].level}cm`);
      }
    }
    
    // Moisture
    if (messageTypes['moisture'].count > 0) {
      const pct = ((messageTypes['moisture'].count / total) * 100).toFixed(1);
      const est = Math.round((messageTypes['moisture'].count / total) * totalMessages);
      console.log(`\n🌱 Moisture Messages:`);
      console.log(`   Count in sample:     ${messageTypes['moisture'].count} (${pct}%)`);
      console.log(`   Estimated in queue:  ~${est.toLocaleString()}`);
      console.log(`   Unique devices:      ${messageTypes['moisture'].devices.size}`);
      if (messageTypes['moisture'].examples.length > 0) {
        console.log(`   Example: Device ${messageTypes['moisture'].examples[0].device}, Moisture: ${messageTypes['moisture'].examples[0].moisture}%`);
      }
    }
    
    // SHAPE Files
    if (messageTypes['shape-file'].count > 0) {
      const pct = ((messageTypes['shape-file'].count / total) * 100).toFixed(1);
      const est = Math.round((messageTypes['shape-file'].count / total) * totalMessages);
      console.log(`\n📁 SHAPE File Messages:`);
      console.log(`   Count in sample:     ${messageTypes['shape-file'].count} (${pct}%)`);
      console.log(`   Estimated in queue:  ~${est}`);
      console.log(`   Files found:`);
      messageTypes['shape-file'].files.forEach(f => console.log(`     - ${f}`));
      console.log(`   Upload IDs:`);
      messageTypes['shape-file'].uploadIds.forEach(id => console.log(`     - ${id}`));
    }
    
    // Unknown
    if (messageTypes['unknown'].count > 0) {
      const pct = ((messageTypes['unknown'].count / total) * 100).toFixed(1);
      console.log(`\n❓ Unknown Messages:`);
      console.log(`   Count in sample:     ${messageTypes['unknown'].count} (${pct}%)`);
      const uniqueTypes = [...new Set(messageTypes['unknown'].types)];
      console.log(`   Types: ${uniqueTypes.slice(0, 5).join(', ')}`);
    }
    
    // Summary
    console.log('\n📌 Summary:');
    console.log('───────────────────────────────────────');
    console.log(`Total messages in queue: ${totalMessages.toLocaleString()}`);
    console.log(`Messages sampled: ${total}`);
    
    // Look for recent SHAPE file
    if (messageTypes['shape-file'].uploadIds.includes('32d19024-76ec-44b1-b8e0-7ca560b081a3')) {
      console.log('\n🎯 YOUR SHAPE FILE IS IN THE QUEUE! Upload ID: 32d19024-76ec-44b1-b8e0-7ca560b081a3');
    } else if (messageTypes['shape-file'].count === 0 && totalMessages > 100) {
      console.log('\n⏳ Your SHAPE file might be further back in the queue (not in this sample)');
    }
    
    // Processing time estimate
    if (inFlight > 0) {
      console.log(`\n⚡ Active processing detected (${inFlight} messages in flight)`);
    } else {
      console.log('\n⚠️  No active processing detected. Consumer might not be running.');
    }

  } catch (error) {
    console.error('\n❌ Error:', error.message);
    if (error.code === 'CredentialsError') {
      console.error('   Make sure AWS credentials are configured');
    }
  }
}

// Run the analysis
analyzeQueue();