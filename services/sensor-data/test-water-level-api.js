const axios = require('axios');

// Sample water level data from SQS
const waterLevelData = {
  "deviceID": "22241083117959",
  "level": -40,
  "timestamp": new Date().toISOString(),
  "voltage": 383,
  "RSSI": -85,
  "latitude": 14.00273,
  "longitude": 100.62697,
  "macAddress": "AA:BB:CC:DD:EE:FF"
};

async function testWaterLevelIngestion() {
  console.log('Testing water level sensor data ingestion with automatic registration...\n');
  console.log('Sensor ID:', waterLevelData.deviceID);
  console.log('Level:', waterLevelData.level, 'cm');
  console.log('Location:', waterLevelData.latitude, ',', waterLevelData.longitude);
  console.log('Voltage:', waterLevelData.voltage / 100, 'V');
  
  try {
    // Try through the sensor data endpoint
    console.log('\n1. Testing through general sensor endpoint...');
    const response = await axios.post(
      'http://localhost:3003/api/v1/sensors/data',
      waterLevelData,
      {
        headers: { 
          'Content-Type': 'application/json'
        }
      }
    );
    
    console.log('✅ Success:', response.data);
    
  } catch (error) {
    console.error('❌ Failed:', error.response?.data || error.message);
  }
}

testWaterLevelIngestion();