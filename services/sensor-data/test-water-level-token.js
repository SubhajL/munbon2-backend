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
    // Use the token-based telemetry endpoint
    console.log('\nSending to token-based telemetry endpoint...');
    const response = await axios.post(
      'http://localhost:3003/api/v1/munbon-water-level/telemetry',
      waterLevelData,
      {
        headers: { 
          'Content-Type': 'application/json'
        }
      }
    );
    
    console.log('✅ Success:', response.data);
    
    // Check if sensor was registered
    const { Pool } = require('pg');
    const pool = new Pool({
      host: 'localhost',
      port: 5433,
      database: 'munbon_timescale',
      user: 'postgres',
      password: 'postgres'
    });
    
    const registryResult = await pool.query(`
      SELECT sensor_id, sensor_type, last_seen, metadata
      FROM sensor_registry
      WHERE sensor_id = $1
    `, [waterLevelData.deviceID]);
    
    if (registryResult.rows.length > 0) {
      console.log('\n✅ Sensor automatically registered:');
      console.log(registryResult.rows[0]);
    }
    
    // Check if reading was saved
    const readingResult = await pool.query(`
      SELECT sensor_id, time, level_cm, voltage, location_lat, location_lng
      FROM water_level_readings
      WHERE sensor_id = $1
      ORDER BY time DESC
      LIMIT 1
    `, [waterLevelData.deviceID]);
    
    if (readingResult.rows.length > 0) {
      console.log('\n✅ Water level reading saved:');
      console.log(readingResult.rows[0]);
    }
    
    await pool.end();
    
  } catch (error) {
    console.error('❌ Failed:', error.response?.data || error.message);
  }
}

testWaterLevelIngestion();