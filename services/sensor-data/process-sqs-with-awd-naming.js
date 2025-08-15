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

// Function to convert MAC address to AWD sensor ID
function macToAwdId(macAddress) {
  if (!macAddress) return null;
  // Get last 4 characters of MAC address and convert to uppercase
  const lastFour = macAddress.toUpperCase().slice(-4);
  return `AWD-${lastFour}`;
}

async function processMessages() {
  try {
    await pgClient.connect();
    console.log('✅ Connected to TimescaleDB');
    
    let processedCount = 0;
    let errorCount = 0;
    const sensorMapping = new Map();
    
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
          
          // Process water level data
          if (body.sensorType === 'water-level' && body.data && body.data.macAddress) {
            // Convert MAC address to AWD format
            const awdSensorId = macToAwdId(body.data.macAddress);
            
            if (!awdSensorId) {
              console.error('No MAC address found for message');
              errorCount++;
              continue;
            }
            
            // Track the mapping
            sensorMapping.set(body.sensorId, awdSensorId);
            
            // First ensure the AWD sensor exists in registry
            const checkSensor = await pgClient.query(
              'SELECT sensor_id FROM sensor_registry WHERE sensor_id = $1',
              [awdSensorId]
            );
            
            if (checkSensor.rows.length === 0) {
              // Create AWD sensor entry if it doesn't exist
              await pgClient.query(`
                INSERT INTO sensor_registry (
                  sensor_id, sensor_type, manufacturer, last_seen, 
                  location_lat, location_lng, metadata, is_active
                ) VALUES (
                  $1, $2, $3, $4, $5, $6, $7, $8
                ) ON CONFLICT (sensor_id) DO NOTHING
              `, [
                awdSensorId,
                'water-level',
                'RID-R',
                new Date(body.timestamp),
                body.location?.lat || body.data.latitude || null,
                body.location?.lng || body.data.longitude || null,
                JSON.stringify({
                  macAddress: body.data.macAddress,
                  originalDeviceId: body.sensorId,
                  manufacturer: 'RID-R'
                }),
                true
              ]);
              console.log(`Created sensor registry entry for ${awdSensorId}`);
            }
            
            // Insert water level reading with AWD sensor ID
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
              awdSensorId,  // Use AWD naming instead of device ID
              body.data.level || 0,
              body.data.voltage / 100 || 0,
              body.data.RSSI || 0,
              body.data.temperature || null,
              0.9, // quality score
              body.location?.lat || body.data.latitude || null,
              body.location?.lng || body.data.longitude || null
            ];
            
            await pgClient.query(insertQuery, values);
            
            // Update sensor registry last_seen
            await pgClient.query(
              'UPDATE sensor_registry SET last_seen = $1 WHERE sensor_id = $2',
              [timestamp, awdSensorId]
            );
            
            console.log(`✅ Processed: ${awdSensorId} (was ${body.sensorId}) - Level: ${body.data.level}cm at ${timestamp.toISOString()}`);
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
    
    // Show sensor ID mappings
    console.log('\nSensor ID Mappings:');
    for (const [deviceId, awdId] of sensorMapping) {
      console.log(`  ${deviceId} → ${awdId}`);
    }
    
    // Check the queue status
    const queueAttrs = await sqs.getQueueAttributes({
      QueueUrl: QUEUE_URL,
      AttributeNames: ['ApproximateNumberOfMessages']
    }).promise();
    
    console.log(`\nMessages remaining in queue: ${queueAttrs.Attributes.ApproximateNumberOfMessages}`);
    
    // Show latest data in database
    const result = await pgClient.query(`
      SELECT sensor_id, COUNT(*) as readings, 
             MAX(time) as latest,
             MAX(level_cm) as level,
             MAX(voltage) as voltage
      FROM water_level_readings 
      WHERE sensor_id LIKE 'AWD-%'
        AND time > NOW() - INTERVAL '1 hour'
      GROUP BY sensor_id
      ORDER BY sensor_id
    `);
    
    console.log('\nLatest AWD sensor data (last hour):');
    result.rows.forEach(row => {
      console.log(`${row.sensor_id}: ${row.readings} readings, Level: ${row.level}cm, Voltage: ${row.voltage}V`);
    });
    
  } catch (error) {
    console.error('Fatal error:', error);
  } finally {
    await pgClient.end();
  }
}

// Run the processor
processMessages().catch(console.error);