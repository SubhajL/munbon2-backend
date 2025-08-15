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

async function processWaterLevelData(data) {
  try {
    // Send to API endpoint which has automatic registration
    const response = await axios.post(
      'http://localhost:3003/api/v1/water-level/telemetry',
      data,
      {
        headers: { 'Content-Type': 'application/json' }
      }
    );
    
    return response.data;
  } catch (error) {
    // If token endpoint fails, try direct API processing
    if (error.response?.status === 404 || error.response?.status === 401) {
      // Use the sensor data service directly
      const serviceResponse = await axios.post(
        'http://localhost:3003/api/v1/sensors/data',
        data,
        {
          headers: { 
            'Content-Type': 'application/json',
            'X-API-Key': 'munbon-internal-key-2024'
          }
        }
      );
      return serviceResponse.data;
    }
    throw error;
  }
}

async function processSQSMessages(limit = 10) {
  console.log('Starting water level data processing with automatic sensor registration...\n');
  
  let processed = 0;
  let errors = 0;
  
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
            continue;
          }
          
          // Process through API with automatic registration
          await processWaterLevelData(body);
          
          const awdId = getAWDId(body.deviceID);
          console.log(`✅ Processed ${awdId} - Level: ${body.level}cm at ${body.timestamp || new Date().toISOString()}`);
          
          // Delete message from queue
          await sqs.deleteMessage({
            QueueUrl: queueUrl,
            ReceiptHandle: message.ReceiptHandle
          }).promise();
          
          processed++;
        } catch (error) {
          console.error(`❌ Error processing message:`, error.message);
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
  console.log(`Errors: ${errors}`);
  console.log(`Messages remaining in queue: ${attributes.Attributes.ApproximateNumberOfMessages}`);
  
  // Show recent water level readings
  const result = await pool.query(`
    SELECT 
      sensor_id,
      time,
      level_cm,
      voltage,
      location_lat,
      location_lng
    FROM water_level_readings
    WHERE time > NOW() - INTERVAL '1 hour'
    ORDER BY time DESC
    LIMIT 5
  `);
  
  if (result.rows.length > 0) {
    console.log('\n=== Recent Water Level Readings ===');
    result.rows.forEach(row => {
      console.log(`${row.sensor_id}: ${row.level_cm}cm at ${row.time} (${row.voltage}V)`);
    });
  }
  
  await pool.end();
}

// Get limit from command line or default to 50
const limit = parseInt(process.argv[2]) || 50;
processSQSMessages(limit).catch(console.error);