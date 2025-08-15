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

async function processAllMessages() {
  try {
    await pgClient.connect();
    console.log('✅ Connected to TimescaleDB');
    
    let totalProcessed = 0;
    let totalErrors = 0;
    let batchNumber = 0;
    
    // Keep processing until queue is empty
    while (true) {
      batchNumber++;
      
      const response = await sqs.receiveMessage({
        QueueUrl: QUEUE_URL,
        MaxNumberOfMessages: 10,
        VisibilityTimeout: 30,
        WaitTimeSeconds: 1
      }).promise();
      
      if (!response.Messages || response.Messages.length === 0) {
        console.log('No more messages in queue!');
        break;
      }
      
      console.log(`\nBatch ${batchNumber}: Processing ${response.Messages.length} messages...`);
      
      for (const message of response.Messages) {
        try {
          const body = JSON.parse(message.Body);
          
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
              0.9,
              body.location?.lat || body.data.latitude || null,
              body.location?.lng || body.data.longitude || null
            ];
            
            await pgClient.query(insertQuery, values);
            
            // Update sensor registry
            await pgClient.query(
              'UPDATE sensor_registry SET last_seen = $1 WHERE sensor_id = $2',
              [timestamp, body.sensorId]
            );
            
            totalProcessed++;
            
            // Delete message from queue
            await sqs.deleteMessage({
              QueueUrl: QUEUE_URL,
              ReceiptHandle: message.ReceiptHandle
            }).promise();
          }
        } catch (error) {
          console.error(`Error: ${error.message}`);
          totalErrors++;
        }
      }
      
      // Show progress every 10 batches
      if (batchNumber % 10 === 0) {
        console.log(`Progress: ${totalProcessed} processed, ${totalErrors} errors`);
      }
    }
    
    console.log(`\n✅ PROCESSING COMPLETE`);
    console.log(`Total messages processed: ${totalProcessed}`);
    console.log(`Total errors: ${totalErrors}`);
    console.log(`Total batches: ${batchNumber}`);
    
    // Check final queue status
    const queueAttrs = await sqs.getQueueAttributes({
      QueueUrl: QUEUE_URL,
      AttributeNames: ['ApproximateNumberOfMessages']
    }).promise();
    
    console.log(`\nMessages remaining in queue: ${queueAttrs.Attributes.ApproximateNumberOfMessages}`);
    
    // Show latest data in database
    const result = await pgClient.query(`
      SELECT sensor_id, COUNT(*) as readings, 
             MAX(time) as latest, 
             MIN(time) as earliest
      FROM water_level_readings 
      WHERE time > NOW() - INTERVAL '1 day'
      GROUP BY sensor_id
    `);
    
    console.log('\nDatabase summary (last 24 hours):');
    result.rows.forEach(row => {
      console.log(`${row.sensor_id}: ${row.readings} readings, latest: ${row.latest}`);
    });
    
  } catch (error) {
    console.error('Fatal error:', error);
  } finally {
    await pgClient.end();
  }
}

processAllMessages().catch(console.error);