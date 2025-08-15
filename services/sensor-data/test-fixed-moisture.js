#!/usr/bin/env node

const axios = require('axios');

// Test with the exact format that was creating "undefined" sensor IDs
const moistureData = {
  "date": "2025/07/30",
  "time": new Date().toISOString().split('T')[1].substring(0, 8),
  "sensor": [
    {
      "date": "2025/07/30",
      "time": new Date().toISOString().split('T')[1].substring(0, 8),
      "flood": "no",
      "temp_hi": "26.50",
      "amb_temp": "31.50",
      "humid_hi": "45",
      "temp_low": "25.80",
      "amb_humid": "65.5",
      "humid_low": "58",
      "sensor_id": "00001",
      "sensor_batt": "395"
    },
    {
      "date": "2025/07/30",
      "time": new Date().toISOString().split('T')[1].substring(0, 8),
      "flood": "no",
      "temp_hi": "27.00",
      "amb_temp": "31.50",
      "humid_hi": "52",
      "temp_low": "26.50",
      "amb_humid": "65.5",
      "humid_low": "60",
      "sensor_id": "00002",
      "sensor_batt": "400"
    }
  ],
  "gw_batt": "372",
  "latitude": "13.7563",
  "msg_type": "interval",
  "longitude": "100.5018",
  "gateway_id": "00003",
  "humidity": "65.50",
  "heat_index": "37.00",
  "temperature": "31.50"
};

async function testFixedProcessing() {
  console.log('Testing Fixed Moisture Sensor Processing');
  console.log('========================================\n');
  
  console.log('1. Sending data that previously created "00003-undefined"...');
  console.log('   Gateway ID:', moistureData.gateway_id);
  console.log('   Sensor count:', moistureData.sensor.length);
  console.log('   Expected sensor IDs: MS-00003-00001, MS-00003-00002\n');
  
  try {
    const response = await axios.post(
      'http://localhost:3003/api/v1/munbon-m2m-moisture/telemetry',
      moistureData,
      { headers: { 'Content-Type': 'application/json' } }
    );
    
    console.log('2. Response:', response.status, response.statusText);
    console.log('   Data:', JSON.stringify(response.data, null, 2));
    
    // Wait a moment for processing
    console.log('\n3. Waiting 2 seconds for data processing...');
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    console.log('\n4. Expected Results:');
    console.log('   - sensor_readings table: Should have entry for "00003-array" (gateway data)');
    console.log('   - moisture_readings table: Should have 2 entries (MS-00003-00001, MS-00003-00002)');
    console.log('   - No more "undefined" sensor IDs!');
    
    console.log('\n5. To verify in database:');
    console.log(`
SELECT sensor_id, sensor_type, time 
FROM sensor_readings 
WHERE sensor_id LIKE '%00003%' 
ORDER BY time DESC 
LIMIT 5;

SELECT sensor_id, time, moisture_surface_pct, moisture_deep_pct 
FROM moisture_readings 
WHERE sensor_id LIKE '%00003%' 
ORDER BY time DESC 
LIMIT 5;
`);
    
  } catch (error) {
    console.error('Error:', error.response?.data || error.message);
  }
}

testFixedProcessing();