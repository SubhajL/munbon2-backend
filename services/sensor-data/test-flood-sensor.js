const axios = require('axios');

const testData = {
  "gateway_id": "00001",
  "msg_type": "interval",
  "date": "2025/07/29",
  "time": new Date().toISOString().slice(11, 19), // Current UTC time
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
      "flood": "yes",  // FLOOD DETECTED
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

async function testFloodSensor() {
  console.log('Testing flood sensor automatic registration...\n');
  console.log('Sending data for sensor MS-00001-00002 with FLOOD DETECTED\n');
  
  try {
    const response = await axios.post(
      'http://localhost:3003/api/v1/munbon-m2m-moisture/telemetry',
      testData,
      {
        headers: { 
          'Content-Type': 'application/json'
        }
      }
    );
    
    console.log('Response:', response.data);
    console.log('\nCheck for alert generation and sensor registration...');
    
  } catch (error) {
    console.error('Error:', error.response?.data || error.message);
  }
}

testFloodSensor();