const AWS = require('aws-sdk');

AWS.config.update({ region: 'ap-southeast-1' });
const sqs = new AWS.SQS();

async function analyzeDLQ() {
  const dlqUrl = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-dlq';
  
  console.log('Analyzing Dead Letter Queue...\n');
  
  // Get queue attributes first
  const { Attributes } = await sqs.getQueueAttributes({
    QueueUrl: dlqUrl,
    AttributeNames: ['All']
  }).promise();
  
  console.log(`Total messages in DLQ: ${Attributes.ApproximateNumberOfMessages}`);
  console.log(`Messages in flight: ${Attributes.ApproximateNumberOfMessagesNotVisible}\n`);
  
  // Analyze messages by type
  const messageTypes = {};
  const errorTypes = {};
  const dateRanges = {};
  const sensorTypes = {};
  let sampleMessages = [];
  let processedCount = 0;
  let shapeFileCount = 0;
  
  // Process messages in batches
  console.log('Sampling messages from DLQ...');
  
  for (let i = 0; i < 10; i++) { // Sample 10 batches of 10 messages each
    const { Messages } = await sqs.receiveMessage({
      QueueUrl: dlqUrl,
      MaxNumberOfMessages: 10,
      VisibilityTimeout: 0, // Don't hide messages
      WaitTimeSeconds: 1,
      MessageAttributeNames: ['All']
    }).promise();
    
    if (!Messages || Messages.length === 0) break;
    
    for (const message of Messages) {
      processedCount++;
      
      try {
        const body = JSON.parse(message.Body);
        
        // Count message types
        const type = body.type || body.sensorType || 'unknown';
        messageTypes[type] = (messageTypes[type] || 0) + 1;
        
        // Count sensor types for telemetry messages
        if (body.sensorType) {
          sensorTypes[body.sensorType] = (sensorTypes[body.sensorType] || 0) + 1;
        }
        
        // Track shape files specifically
        if (type === 'shape-file') {
          shapeFileCount++;
          if (sampleMessages.length < 3) {
            sampleMessages.push({
              type: 'shape-file',
              fileName: body.fileName,
              uploadId: body.uploadId,
              uploadedAt: body.uploadedAt,
              s3Key: body.s3Key
            });
          }
        }
        
        // Extract date
        const timestamp = body.timestamp || body.uploadedAt || body.createdAt;
        if (timestamp) {
          const date = new Date(timestamp).toISOString().split('T')[0];
          dateRanges[date] = (dateRanges[date] || 0) + 1;
        }
        
        // Sample other message types
        if (sampleMessages.length < 10 && type !== 'shape-file') {
          sampleMessages.push({
            type: type,
            sensorId: body.sensorId,
            timestamp: timestamp,
            sample: JSON.stringify(body).substring(0, 200) + '...'
          });
        }
        
      } catch (error) {
        errorTypes['parse-error'] = (errorTypes['parse-error'] || 0) + 1;
      }
    }
    
    process.stdout.write(`\rProcessed ${processedCount} messages...`);
  }
  
  console.log(`\n\nAnalysis complete. Sampled ${processedCount} messages.\n`);
  
  // Display results
  console.log('=== MESSAGE TYPES ===');
  Object.entries(messageTypes)
    .sort((a, b) => b[1] - a[1])
    .forEach(([type, count]) => {
      console.log(`${type}: ${count} messages (${((count/processedCount)*100).toFixed(1)}%)`);
    });
  
  console.log('\n=== SENSOR TYPES (for telemetry) ===');
  Object.entries(sensorTypes)
    .sort((a, b) => b[1] - a[1])
    .forEach(([type, count]) => {
      console.log(`${type}: ${count} messages`);
    });
  
  console.log('\n=== DATE DISTRIBUTION ===');
  const sortedDates = Object.entries(dateRanges)
    .sort((a, b) => a[0].localeCompare(b[0]));
  
  if (sortedDates.length > 0) {
    console.log(`Earliest: ${sortedDates[0][0]}`);
    console.log(`Latest: ${sortedDates[sortedDates.length - 1][0]}`);
    console.log('\nTop dates:');
    sortedDates
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .forEach(([date, count]) => {
        console.log(`  ${date}: ${count} messages`);
      });
  }
  
  console.log(`\n=== SHAPE FILES ===`);
  console.log(`Total shape files found: ${shapeFileCount}`);
  if (shapeFileCount > 0) {
    console.log('\nSample shape file messages:');
    sampleMessages
      .filter(m => m.type === 'shape-file')
      .forEach((msg, idx) => {
        console.log(`\nShape File ${idx + 1}:`);
        console.log(`  File: ${msg.fileName}`);
        console.log(`  Upload ID: ${msg.uploadId}`);
        console.log(`  Uploaded: ${msg.uploadedAt}`);
        console.log(`  S3 Key: ${msg.s3Key}`);
      });
  }
  
  console.log('\n=== SAMPLE OTHER MESSAGES ===');
  sampleMessages
    .filter(m => m.type !== 'shape-file')
    .slice(0, 5)
    .forEach((msg, idx) => {
      console.log(`\nMessage ${idx + 1}:`);
      console.log(`  Type: ${msg.type}`);
      console.log(`  Sensor ID: ${msg.sensorId || 'N/A'}`);
      console.log(`  Timestamp: ${msg.timestamp || 'N/A'}`);
      console.log(`  Preview: ${msg.sample}`);
    });
  
  // Estimate total by type
  console.log('\n=== ESTIMATED TOTALS ===');
  const totalMessages = parseInt(Attributes.ApproximateNumberOfMessages);
  const scaleFactor = totalMessages / processedCount;
  
  Object.entries(messageTypes)
    .sort((a, b) => b[1] - a[1])
    .forEach(([type, count]) => {
      const estimated = Math.round(count * scaleFactor);
      console.log(`${type}: ~${estimated} messages (estimated)`);
    });
  
  console.log(`\nShape files (estimated): ~${Math.round(shapeFileCount * scaleFactor)}`);
}

analyzeDLQ().catch(console.error);