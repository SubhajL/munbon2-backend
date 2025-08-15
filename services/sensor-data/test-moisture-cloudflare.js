const axios = require('axios');

const testData = {
  "gateway_id": "00003",
  "msg_type": "interval",
  "date": new Date().toISOString().split('T')[0].replace(/-/g, '/'),
  "time": new Date().toISOString().slice(11, 19),
  "latitude": "13.756331",
  "longitude": "100.501765",
  "temperature": "32.50",
  "humidity": "65",
  "heat_index": "35.20",
  "gw_batt": "385",
  "sensor": [
    {
      "sensor_id": "00001",
      "date": new Date().toISOString().split('T')[0].replace(/-/g, '/'),
      "time": new Date().toISOString().slice(11, 19),
      "flood": "no",
      "amb_humid": "68",
      "amb_temp": "31.50",
      "humid_hi": "45",
      "temp_hi": "26.50",
      "humid_low": "65",
      "temp_low": "25.80",
      "sensor_batt": "401"
    }
  ]
};

async function testMoistureCloudflare() {
  console.log('Testing moisture sensor data through CloudFlare tunnel...\n');
  console.log('Gateway: GW-00003');
  console.log('Sensor: MS-00003-00001');
  console.log('Time:', new Date().toISOString());
  
  try {
    // Test through CloudFlare tunnel
    console.log('\nSending to CloudFlare tunnel...');
    const response = await axios.post(
      'https://munbon-moisture.beautifyai.io/api/v1/munbon-m2m-moisture/telemetry',
      testData,
      {
        headers: { 
          'Content-Type': 'application/json'
        },
        timeout: 10000
      }
    );
    
    console.log('✅ Success:', response.data);
    
    // Wait a moment for processing
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Check if data was saved
    const { Pool } = require('pg');
    const pool = new Pool({
      host: 'localhost',
      port: 5433,
      database: 'munbon_timescale',
      user: 'postgres',
      password: 'postgres'
    });
    
    // Check gateway
    const gatewayResult = await pool.query(`
      SELECT sensor_id, last_seen, metadata
      FROM sensor_registry
      WHERE sensor_id = 'GW-00003'
    `);
    
    if (gatewayResult.rows.length > 0) {
      console.log('\n✅ Gateway registered/updated:');
      console.log('   ID:', gatewayResult.rows[0].sensor_id);
      console.log('   Last seen:', new Date(gatewayResult.rows[0].last_seen).toLocaleString());
    }
    
    // Check moisture sensor
    const sensorResult = await pool.query(`
      SELECT sensor_id, last_seen, metadata
      FROM sensor_registry
      WHERE sensor_id = 'MS-00003-00001'
    `);
    
    if (sensorResult.rows.length > 0) {
      console.log('\n✅ Moisture sensor registered/updated:');
      console.log('   ID:', sensorResult.rows[0].sensor_id);
      console.log('   Last seen:', new Date(sensorResult.rows[0].last_seen).toLocaleString());
    }
    
    // Check reading
    const readingResult = await pool.query(`
      SELECT 
        sensor_id,
        time,
        moisture_surface_pct,
        moisture_deep_pct,
        ambient_temp_c,
        ambient_humidity_pct,
        flood_status
      FROM moisture_readings
      WHERE sensor_id = 'MS-00003-00001'
      ORDER BY time DESC
      LIMIT 1
    `);
    
    if (readingResult.rows.length > 0) {
      const reading = readingResult.rows[0];
      console.log('\n✅ Moisture reading saved:');
      console.log('   Time:', new Date(reading.time).toLocaleString());
      console.log('   Surface moisture:', reading.moisture_surface_pct + '%');
      console.log('   Deep moisture:', reading.moisture_deep_pct + '%');
      console.log('   Ambient:', reading.ambient_temp_c + '°C, ' + reading.ambient_humidity_pct + '% humidity');
      console.log('   Flood status:', reading.flood_status ? 'YES' : 'NO');
    }
    
    await pool.end();
    
  } catch (error) {
    console.error('❌ Failed:', error.response?.data || error.message);
    if (error.code === 'ECONNABORTED') {
      console.error('   Timeout - CloudFlare tunnel may be down');
    }
  }
}

testMoistureCloudflare();