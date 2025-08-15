const AWS = require('aws-sdk');
const { Client } = require('pg');

// Configure AWS
AWS.config.update({ region: 'ap-southeast-1' });
const sqs = new AWS.SQS();

// Database configuration
const pgClient = new Client({
  host: 'localhost',
  port: 5433,
  database: 'munbon_timescale',
  user: 'postgres',
  password: 'postgres'
});

const QUEUE_URL = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';

async function processMessages() {
  try {
    await pgClient.connect();
    console.log('✅ Connected to TimescaleDB');
    
    let processedCount = 0;
    let errorCount = 0;
    
    // Process messages in batches
    for (let batch = 0; batch < 10; batch++) {
      console.log(`\nProcessing batch ${batch + 1}...`);
      
      const response = await sqs.receiveMessage({
        QueueUrl: QUEUE_URL,
        MaxNumberOfMessages: 10,
        VisibilityTimeout: 30,
        WaitTimeSeconds: 2
      }).promise();
      
      if (!response.Messages || response.Messages.length === 0) {
        console.log('No more messages to process');
        break;
      }
      
      console.log(`Received ${response.Messages.length} messages`);
      
      for (const message of response.Messages) {
        try {
          const body = JSON.parse(message.Body);
          
          // Insert into water_level_readings if it's water level data
          if (body.sensorType === 'water-level' && body.data) {
            const insertQuery = `
              INSERT INTO water_level_readings (
                time, sensor_id, level_cm, voltage, rssi, 
                temperature, quality_score, location_lat, location_lng
              ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9
              )
            `;
            
            const timestamp = new Date(body.timestamp);
            const values = [
              timestamp,
              body.sensorId,
              body.data.level || 0,
              body.data.voltage / 100 || 0,
              body.data.RSSI || 0,
              body.data.temperature || null,
              0.9, // quality score
              body.location?.lat || body.data.latitude || null,
              body.location?.lng || body.data.longitude || null
            ];
            
            await pgClient.query(insertQuery, values);
            
            // Update sensor registry
            await pgClient.query(
              'UPDATE sensor_registry SET last_seen = $1 WHERE sensor_id = $2',
              [timestamp, body.sensorId]
            );
            
            console.log(`✅ Processed: ${body.sensorId} - Level: ${body.data.level}cm at ${timestamp.toISOString()}`);
            processedCount++;
            
            // Delete message from queue
            await sqs.deleteMessage({
              QueueUrl: QUEUE_URL,
              ReceiptHandle: message.ReceiptHandle
            }).promise();
          }
        } catch (error) {
          console.error(`❌ Error processing message: ${error.message}`);
          errorCount++;
        }
      }
    }
    
    console.log(`\n=== Summary ===`);
    console.log(`Messages processed: ${processedCount}`);
    console.log(`Errors: ${errorCount}`);
    
    // Check the queue status
    const queueAttrs = await sqs.getQueueAttributes({
      QueueUrl: QUEUE_URL,
      AttributeNames: ['ApproximateNumberOfMessages']
    }).promise();
    
    console.log(`Messages remaining in queue: ${queueAttrs.Attributes.ApproximateNumberOfMessages}`);
    
  } catch (error) {
    console.error('Fatal error:', error);
  } finally {
    await pgClient.end();
  }
}

// Run the processor
processMessages().catch(console.error);