#!/usr/bin/env node

const https = require('https');

// Test moisture sensor data - M2M format from PDF
const sensorData = {
  gateway_id: "00001",
  msg_type: "interval",
  date: new Date().toISOString().split('T')[0].replace(/-/g, '/'),
  time: new Date().toTimeString().split(' ')[0],
  latitude: "13.7563",
  longitude: "100.5018",
  gw_batt: "372",
  sensor: [
    {
      sensor_id: "00001",
      flood: "no",
      amb_humid: "65",
      amb_temp: "32.50",
      humid_hi: "45",  // Top soil moisture
      temp_hi: "28.50",
      humid_low: "58", // Bottom soil moisture
      temp_low: "27.00",
      sensor_batt: "395"
    }
  ]
};

// Lambda endpoint URL from deployment
const API_ENDPOINT = 'https://your-api-gateway-url.execute-api.ap-southeast-1.amazonaws.com/dev';
const TOKEN = 'munbon-m2m-moisture';

console.log('Test Moisture Sensor Data Flow');
console.log('==============================');
console.log('\n1. Sensor Data to be sent:');
console.log(JSON.stringify(sensorData, null, 2));

console.log('\n2. Data Flow:');
console.log('   - Moisture Sensor → AWS API Gateway');
console.log('   - API Gateway → Lambda Function');
console.log('   - Lambda → SQS Queue');
console.log('   - Local Consumer polls SQS');
console.log('   - Consumer → TimescaleDB');

console.log('\nTo test with actual Lambda (after deployment):');
console.log(`curl -X POST ${API_ENDPOINT}/api/v1/${TOKEN}/telemetry \\`);
console.log(`  -H "Content-Type: application/json" \\`);
console.log(`  -d '${JSON.stringify(sensorData)}'`);

console.log('\n3. Expected TimescaleDB tables:');
console.log('   - sensor_registry: Device registration');
console.log('   - moisture_readings: Moisture data with both top/bottom soil readings');
console.log('   - sensor_location_history: Track mobile sensor movements');

console.log('\n4. To check if data was saved (run in TimescaleDB):');
console.log(`
-- Check sensor registry
SELECT * FROM sensor_registry WHERE device_id = '00001';

-- Check moisture readings
SELECT * FROM moisture_readings 
WHERE device_id = '00001' 
ORDER BY timestamp DESC 
LIMIT 5;

-- Check aggregated data
SELECT 
  time_bucket('5 minutes', timestamp) AS bucket,
  AVG(soil_moisture_top) as avg_top,
  AVG(soil_moisture_bottom) as avg_bottom
FROM moisture_readings
WHERE device_id = '00001'
GROUP BY bucket
ORDER BY bucket DESC;
`);

// Simulate local testing without AWS
console.log('\n5. For local testing without AWS deployment:');
console.log('   - Use the mock MQTT broker in the main service');
console.log('   - Or directly insert into TimescaleDB for testing');

const localTestData = {
  deviceId: sensorData.gateway_id,
  sensorType: 'moisture',
  data: {
    timestamp: Date.now(),
    soilMoistureTop: parseFloat(sensorData.sensor[0].humid_hi),
    soilMoistureBottom: parseFloat(sensorData.sensor[0].humid_low),
    ambientHumidity: parseFloat(sensorData.sensor[0].amb_humid),
    ambientTemp: parseFloat(sensorData.sensor[0].amb_temp),
    soilTempTop: parseFloat(sensorData.sensor[0].temp_hi),
    soilTempBottom: parseFloat(sensorData.sensor[0].temp_low),
    batteryVoltage: parseInt(sensorData.sensor[0].sensor_batt),
    floodStatus: sensorData.sensor[0].flood === 'yes',
    latitude: parseFloat(sensorData.latitude),
    longitude: parseFloat(sensorData.longitude)
  }
};

console.log('\nProcessed data for TimescaleDB:');
console.log(JSON.stringify(localTestData, null, 2));