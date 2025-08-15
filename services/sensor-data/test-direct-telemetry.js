const axios = require('axios');

const testData = {
  "gateway_id": "00001",
  "msg_type": "interval",
  "date": "2025/07/29",
  "time": new Date().toISOString().slice(11, 19),
  "latitude": "13.12345",
  "longitude": "100.54621",
  "temperature": "38.50",
  "humidity": "55",
  "heat_index": "41.35",
  "gw_batt": "372",
  "sensor": [
    {
      "sensor_id": "00002",
      "date": "2025/07/29",
      "time": new Date().toISOString().slice(11, 19),
      "flood": "yes",
      "amb_humid": "55",
      "amb_temp": "38.50",
      "humid_hi": "95",
      "temp_hi": "25.00",
      "humid_low": "90",
      "temp_low": "24.50",
      "sensor_batt": "412"
    }
  ]
};

async function testDirect() {
  console.log('Testing telemetry endpoint...\n');
  
  // Try different endpoint variations
  const endpoints = [
    'http://localhost:3003/api/v1/munbon-m2m-moisture/telemetry',
    'http://localhost:3003/api/v1/munbon-m2m-moisture:Moisture Sensor/telemetry',
    'http://localhost:3003/api/v1/moisture/telemetry'
  ];
  
  for (const endpoint of endpoints) {
    console.log(`Testing: ${endpoint}`);
    try {
      const response = await axios.post(endpoint, testData, {
        headers: { 'Content-Type': 'application/json' }
      });
      console.log('✅ Success:', response.data);
      break;
    } catch (error) {
      console.log('❌ Failed:', error.response?.data || error.message);
    }
  }
  
  // Also try to check what routes are available
  console.log('\nTrying to access non-existent endpoint to see 404 response...');
  try {
    await axios.get('http://localhost:3003/api/v1/test-route-not-exists');
  } catch (error) {
    console.log('404 Response:', error.response?.status, error.response?.statusText);
  }
}

testDirect();