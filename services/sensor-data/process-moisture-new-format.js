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

// Function to parse Thailand date/time format to UTC timestamp
function parseThailandDateTime(date, time) {
  // date format: "2025/05/05", time format: "10:30:00" (UTC)
  const [year, month, day] = date.split('/').map(Number);
  const [hour, minute, second] = time.split(':').map(Number);
  
  // Create UTC date
  const utcDate = new Date(Date.UTC(year, month - 1, day, hour, minute, second));
  
  // Thailand is UTC+7, so we need to subtract 7 hours from the provided UTC time
  // to get the actual UTC time (since the device is sending local time as UTC)
  return utcDate;
}

// Process new moisture sensor format
async function processMoistureData(body) {
  const results = {
    processed: 0,
    errors: 0,
    sensors: []
  };

  try {
    // Extract gateway-level data
    const gatewayData = {
      gateway_id: body.gateway_id,
      msg_type: body.msg_type,
      timestamp: parseThailandDateTime(body.date, body.time),
      location: {
        lat: parseFloat(body.latitude),
        lng: parseFloat(body.longitude)
      },
      ambient: {
        temperature: parseFloat(body.temperature),
        humidity: parseFloat(body.humidity),
        heat_index: parseFloat(body.heat_index)
      },
      battery: parseInt(body.gw_batt) / 100  // Convert to voltage
    };

    // First, ensure gateway is registered
    const gatewayId = `GW-${body.gateway_id.padStart(5, '0')}`;
    await pgClient.query(`
      INSERT INTO sensor_registry (
        sensor_id, sensor_type, manufacturer, last_seen,
        location_lat, location_lng, metadata, is_active
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
      ON CONFLICT (sensor_id) DO UPDATE SET
        last_seen = EXCLUDED.last_seen,
        location_lat = EXCLUDED.location_lat,
        location_lng = EXCLUDED.location_lng,
        metadata = EXCLUDED.metadata
    `, [
      gatewayId,
      'gateway',
      'M2M',
      gatewayData.timestamp,
      gatewayData.location.lat,
      gatewayData.location.lng,
      JSON.stringify({
        msgType: body.msg_type,
        ambient: gatewayData.ambient,
        battery: gatewayData.battery
      }),
      true
    ]);

    // Process each sensor in the array
    if (body.sensor && Array.isArray(body.sensor)) {
      for (const sensor of body.sensor) {
        try {
          // Create sensor ID format
          const sensorId = `MS-${body.gateway_id.padStart(5, '0')}-${sensor.sensor_id.padStart(5, '0')}`;
          
          // Parse sensor timestamp
          const sensorTimestamp = sensor.date && sensor.time 
            ? parseThailandDateTime(sensor.date, sensor.time)
            : gatewayData.timestamp;

          // Register sensor if needed
          await pgClient.query(`
            INSERT INTO sensor_registry (
              sensor_id, sensor_type, manufacturer, last_seen,
              location_lat, location_lng, metadata, is_active
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (sensor_id) DO UPDATE SET
              last_seen = EXCLUDED.last_seen,
              metadata = EXCLUDED.metadata
          `, [
            sensorId,
            'moisture',
            'M2M',
            sensorTimestamp,
            gatewayData.location.lat,
            gatewayData.location.lng,
            JSON.stringify({
              gatewayId: gatewayId,
              sensorNumber: sensor.sensor_id,
              floodCapable: true
            }),
            true
          ]);

          // Insert moisture reading
          await pgClient.query(`
            INSERT INTO moisture_readings (
              time, sensor_id, 
              moisture_surface_pct, moisture_deep_pct,
              temp_surface_c, temp_deep_c,
              ambient_humidity_pct, ambient_temp_c,
              flood_status, voltage,
              location_lat, location_lng,
              quality_score
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
          `, [
            sensorTimestamp,
            sensorId,
            parseFloat(sensor.humid_hi),
            parseFloat(sensor.humid_low),
            parseFloat(sensor.temp_hi),
            parseFloat(sensor.temp_low),
            parseFloat(sensor.amb_humid),
            parseFloat(sensor.amb_temp),
            sensor.flood === 'yes',
            parseInt(sensor.sensor_batt) / 100,
            gatewayData.location.lat,
            gatewayData.location.lng,
            calculateQualityScore(sensor)
          ]);

          results.processed++;
          results.sensors.push({
            sensorId,
            flood: sensor.flood,
            moistureHi: sensor.humid_hi,
            moistureLow: sensor.humid_low,
            timestamp: sensorTimestamp.toISOString()
          });

          console.log(`✅ Processed moisture sensor ${sensorId}: Hi=${sensor.humid_hi}%, Low=${sensor.humid_low}%, Flood=${sensor.flood}`);

        } catch (sensorError) {
          console.error(`❌ Error processing sensor ${sensor.sensor_id}:`, sensorError.message);
          results.errors++;
        }
      }
    }

  } catch (error) {
    console.error('Error processing moisture data:', error);
    throw error;
  }

  return results;
}

// Calculate quality score based on sensor data
function calculateQualityScore(sensor) {
  let score = 1.0;

  // Check moisture values
  const moistureHi = parseFloat(sensor.humid_hi);
  const moistureLow = parseFloat(sensor.humid_low);
  
  if (isNaN(moistureHi) || moistureHi < 0 || moistureHi > 100) score -= 0.2;
  if (isNaN(moistureLow) || moistureLow < 0 || moistureLow > 100) score -= 0.2;
  
  // Check temperature values
  const tempHi = parseFloat(sensor.temp_hi);
  const tempLow = parseFloat(sensor.temp_low);
  
  if (isNaN(tempHi) || tempHi < -10 || tempHi > 60) score -= 0.1;
  if (isNaN(tempLow) || tempLow < -10 || tempLow > 60) score -= 0.1;
  
  // Check battery
  const battery = parseInt(sensor.sensor_batt);
  if (isNaN(battery) || battery < 360) score -= 0.2; // Below 3.6V
  
  return Math.max(0, score);
}

// Process messages from SQS
async function processMessages() {
  try {
    await pgClient.connect();
    console.log('✅ Connected to TimescaleDB');
    
    let totalProcessed = 0;
    let totalErrors = 0;
    let moistureMessages = 0;
    
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
          
          // Check if it's moisture sensor data with new format
          if (body.sensorType === 'moisture' && body.data && body.data.gateway_id && body.data.sensor) {
            moistureMessages++;
            const result = await processMoistureData(body.data);
            totalProcessed += result.processed;
            totalErrors += result.errors;
            
            // Delete message from queue if processed successfully
            if (result.processed > 0) {
              await sqs.deleteMessage({
                QueueUrl: QUEUE_URL,
                ReceiptHandle: message.ReceiptHandle
              }).promise();
            }
          }
        } catch (error) {
          console.error(`❌ Error processing message: ${error.message}`);
          totalErrors++;
        }
      }
    }
    
    console.log(`\n=== Summary ===`);
    console.log(`Moisture messages found: ${moistureMessages}`);
    console.log(`Sensors processed: ${totalProcessed}`);
    console.log(`Errors: ${totalErrors}`);
    
    // Check the queue status
    const queueAttrs = await sqs.getQueueAttributes({
      QueueUrl: QUEUE_URL,
      AttributeNames: ['ApproximateNumberOfMessages']
    }).promise();
    
    console.log(`\nMessages remaining in queue: ${queueAttrs.Attributes.ApproximateNumberOfMessages}`);
    
    // Show latest moisture data in database
    const result = await pgClient.query(`
      SELECT sensor_id, COUNT(*) as readings, 
             MAX(time) as latest,
             AVG(moisture_surface_pct) as avg_surface,
             AVG(moisture_deep_pct) as avg_deep,
             BOOL_OR(flood_status) as any_flood
      FROM moisture_readings 
      WHERE time > NOW() - INTERVAL '1 hour'
      GROUP BY sensor_id
      ORDER BY sensor_id
    `);
    
    if (result.rows.length > 0) {
      console.log('\nLatest moisture sensor data (last hour):');
      result.rows.forEach(row => {
        console.log(`${row.sensor_id}: ${row.readings} readings, Surface: ${parseFloat(row.avg_surface).toFixed(1)}%, Deep: ${parseFloat(row.avg_deep).toFixed(1)}%, Flood: ${row.any_flood ? 'YES' : 'No'}`);
      });
    }
    
  } catch (error) {
    console.error('Fatal error:', error);
  } finally {
    await pgClient.end();
  }
}

// Test with sample data
async function testWithSampleData() {
  const sampleData = {
    gateway_id: "00001",
    msg_type: "interval",
    date: "2025/07/29",
    time: "10:30:00",
    latitude: "13.12345",
    longitude: "100.54621",
    temperature: "38.50",
    humidity: "55",
    heat_index: "41.35",
    gw_batt: "372",
    sensor: [
      {
        sensor_id: "00001",
        date: "2025/07/29",
        time: "10:29:15",
        flood: "no",
        amb_humid: "60",
        amb_temp: "40.50",
        humid_hi: "50",
        temp_hi: "25.50",
        humid_low: "72",
        temp_low: "25.00",
        sensor_batt: "395"
      }
    ]
  };

  console.log('Testing with sample data...\n');
  console.log('Sample data:', JSON.stringify(sampleData, null, 2));

  try {
    await pgClient.connect();
    const result = await processMoistureData(sampleData);
    console.log('\nTest result:', result);
  } catch (error) {
    console.error('Test failed:', error);
  } finally {
    await pgClient.end();
  }
}

// Check command line arguments
if (process.argv.includes('--test')) {
  testWithSampleData().catch(console.error);
} else {
  processMessages().catch(console.error);
}