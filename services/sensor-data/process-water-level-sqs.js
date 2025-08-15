const axios = require('axios');
const AWS = require('aws-sdk');
const { Pool } = require('pg');

// Configure AWS
AWS.config.update({
  region: 'ap-southeast-1',
  accessKeyId: process.env.AWS_ACCESS_KEY_ID,
  secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
});

const sqs = new AWS.SQS();
const queueUrl = 'https://sqs.ap-southeast-1.amazonaws.com/331862178144/munbon-sensor-ingestion-dev-queue';

// Database connection
const pool = new Pool({
  host: 'localhost',
  port: 5433,
  database: 'munbon_timescale',
  user: 'postgres',
  password: 'postgres'
});

// Map device ID to AWD ID
function getAWDId(deviceId) {
  const mapping = {
    '22166174123108163': 'AWD-6CA3',
    '2216617412314704': 'AWD-9304',
    '2216617412313572': 'AWD-8748',
    '22241083117959': 'AWD-45C7',
    '22241083118390': 'AWD-47B6'
  };
  return mapping[deviceId] || deviceId;
}

async function processSQSMessages(limit = 50) {
  console.log('Processing water level data from SQS with automatic sensor registration...\n');
  
  let processed = 0;
  let errors = 0;
  let skipped = 0;
  
  while (processed < limit) {
    const params = {
      QueueUrl: queueUrl,
      MaxNumberOfMessages: Math.min(10, limit - processed),
      WaitTimeSeconds: 5
    };
    
    try {
      const data = await sqs.receiveMessage(params).promise();
      
      if (!data.Messages || data.Messages.length === 0) {
        console.log('No more messages in queue');
        break;
      }
      
      console.log(`\nProcessing batch of ${data.Messages.length} messages...`);
      
      for (const message of data.Messages) {
        try {
          const body = JSON.parse(message.Body);
          
          // Check if it's water level data
          if (!body.deviceID || body.level === undefined) {
            console.log('⏭️  Skipping non-water-level message');
            skipped++;
            
            // Delete non-water-level message from queue
            await sqs.deleteMessage({
              QueueUrl: queueUrl,
              ReceiptHandle: message.ReceiptHandle
            }).promise();
            continue;
          }
          
          // Send to API endpoint with automatic registration
          const response = await axios.post(
            'http://localhost:3003/api/v1/munbon-water-level/telemetry',
            body,
            {
              headers: { 'Content-Type': 'application/json' }
            }
          );
          
          const awdId = getAWDId(body.deviceID);
          console.log(`✅ Processed ${awdId} (${body.deviceID}) - Level: ${body.level}cm at ${body.timestamp || new Date().toISOString()}`);
          
          // Delete successfully processed message from queue
          await sqs.deleteMessage({
            QueueUrl: queueUrl,
            ReceiptHandle: message.ReceiptHandle
          }).promise();
          
          processed++;
        } catch (error) {
          console.error(`❌ Error processing message:`, error.response?.data || error.message);
          errors++;
        }
      }
    } catch (error) {
      console.error('Error receiving messages:', error);
      break;
    }
  }
  
  // Check queue status
  const attributes = await sqs.getQueueAttributes({
    QueueUrl: queueUrl,
    AttributeNames: ['ApproximateNumberOfMessages']
  }).promise();
  
  console.log('\n=== Summary ===');
  console.log(`Messages processed: ${processed}`);
  console.log(`Messages skipped: ${skipped}`);
  console.log(`Errors: ${errors}`);
  console.log(`Messages remaining in queue: ${attributes.Attributes.ApproximateNumberOfMessages}`);
  
  // Show recent water level readings
  const result = await pool.query(`
    SELECT 
      s.sensor_id,
      COALESCE(s.metadata->>'awdId', s.sensor_id) as display_id,
      r.time,
      r.level_cm,
      r.voltage,
      r.location_lat,
      r.location_lng
    FROM water_level_readings r
    JOIN sensor_registry s ON r.sensor_id = s.sensor_id
    WHERE r.time > NOW() - INTERVAL '1 hour'
    ORDER BY r.time DESC
    LIMIT 10
  `);
  
  if (result.rows.length > 0) {
    console.log('\n=== Recent Water Level Readings (Last Hour) ===');
    result.rows.forEach(row => {
      console.log(`${row.display_id}: ${row.level_cm}cm at ${new Date(row.time).toLocaleString()} (${row.voltage}V)`);
    });
  }
  
  // Show sensor registry
  const sensorsResult = await pool.query(`
    SELECT 
      sensor_id,
      sensor_type,
      last_seen,
      location_lat,
      location_lng,
      metadata
    FROM sensor_registry
    WHERE sensor_type = 'water-level'
    AND last_seen > NOW() - INTERVAL '24 hours'
    ORDER BY last_seen DESC
    LIMIT 5
  `);
  
  console.log('\n=== Recently Active Water Level Sensors ===');
  sensorsResult.rows.forEach(row => {
    const awdId = getAWDId(row.sensor_id);
    console.log(`${awdId} (${row.sensor_id}): Last seen ${new Date(row.last_seen).toLocaleString()}`);
    if (row.location_lat && row.location_lng) {
      console.log(`  Location: ${row.location_lat}, ${row.location_lng}`);
    }
  });
  
  await pool.end();
}

// Get limit from command line or default to 50
const limit = parseInt(process.argv[2]) || 50;
processSQSMessages(limit).catch(console.error);