const { Pool } = require('pg');

const pool = new Pool({
  host: 'localhost',
  port: 5433,
  database: 'munbon_timescale',
  user: 'postgres',
  password: 'postgres'
});

async function checkFloodSensor() {
  try {
    console.log('Checking flood sensor registration and data...\n');
    
    // Check if MS-00001-00002 was registered
    const registryResult = await pool.query(`
      SELECT sensor_id, sensor_type, last_seen, metadata 
      FROM sensor_registry 
      WHERE sensor_id = 'MS-00001-00002'
    `);
    
    if (registryResult.rows.length > 0) {
      console.log('✅ FLOOD SENSOR REGISTERED:');
      console.log('===========================');
      const sensor = registryResult.rows[0];
      console.log(`ID: ${sensor.sensor_id}`);
      console.log(`Type: ${sensor.sensor_type}`);
      console.log(`Last Seen: ${sensor.last_seen}`);
      console.log(`Metadata: ${JSON.stringify(sensor.metadata, null, 2)}`);
    } else {
      console.log('❌ Flood sensor MS-00001-00002 not found in registry');
    }
    
    // Check flood readings
    const readingsResult = await pool.query(`
      SELECT sensor_id, time, moisture_surface_pct, moisture_deep_pct, 
             flood_status, ambient_temp_c, ambient_humidity_pct
      FROM moisture_readings 
      WHERE sensor_id = 'MS-00001-00002'
      ORDER BY time DESC 
      LIMIT 1
    `);
    
    if (readingsResult.rows.length > 0) {
      console.log('\n✅ FLOOD READING SAVED:');
      console.log('======================');
      const reading = readingsResult.rows[0];
      console.log(`Sensor: ${reading.sensor_id}`);
      console.log(`Time: ${reading.time}`);
      console.log(`Surface Moisture: ${reading.moisture_surface_pct}%`);
      console.log(`Deep Moisture: ${reading.moisture_deep_pct}%`);
      console.log(`Ambient Temp: ${reading.ambient_temp_c}°C`);
      console.log(`Ambient Humidity: ${reading.ambient_humidity_pct}%`);
      console.log(`🚨 FLOOD STATUS: ${reading.flood_status ? 'YES - FLOOD DETECTED!' : 'NO'}`);
    } else {
      console.log('\n❌ No readings found for flood sensor');
    }
    
    // Check recent alerts (if alerts table exists)
    try {
      const alertsResult = await pool.query(`
        SELECT COUNT(*) as count FROM information_schema.tables 
        WHERE table_name = 'alerts'
      `);
      
      if (alertsResult.rows[0].count > 0) {
        const alerts = await pool.query(`
          SELECT * FROM alerts 
          WHERE sensor_id = 'MS-00001-00002' 
          AND alert_type = 'FLOOD_DETECTED'
          ORDER BY created_at DESC 
          LIMIT 1
        `);
        
        if (alerts.rows.length > 0) {
          console.log('\n✅ FLOOD ALERT GENERATED');
        }
      }
    } catch (e) {
      // Alerts table might not exist yet
    }
    
  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await pool.end();
  }
}

checkFloodSensor();