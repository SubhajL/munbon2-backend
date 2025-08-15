const { Pool } = require('pg');

const pool = new Pool({
  host: 'localhost',
  port: 5433,
  database: 'munbon_timescale',
  user: 'postgres',
  password: 'postgres'
});

async function checkRegistration() {
  try {
    console.log('Checking sensor registry for automatic registration...\n');
    
    // Check sensor registry
    const registryResult = await pool.query(`
      SELECT sensor_id, sensor_type, last_seen, metadata 
      FROM sensor_registry 
      WHERE sensor_type IN ('gateway', 'moisture') 
      ORDER BY last_seen DESC 
      LIMIT 5
    `);
    
    console.log('SENSOR REGISTRY:');
    console.log('================');
    registryResult.rows.forEach(row => {
      console.log(`ID: ${row.sensor_id}`);
      console.log(`Type: ${row.sensor_type}`);
      console.log(`Last Seen: ${row.last_seen}`);
      console.log(`Metadata: ${JSON.stringify(row.metadata, null, 2)}`);
      console.log('---');
    });
    
    // Check moisture readings
    const readingsResult = await pool.query(`
      SELECT sensor_id, time, moisture_surface_pct, moisture_deep_pct, flood_status 
      FROM moisture_readings 
      ORDER BY time DESC 
      LIMIT 5
    `);
    
    console.log('\nMOISTURE READINGS:');
    console.log('==================');
    readingsResult.rows.forEach(row => {
      console.log(`Sensor: ${row.sensor_id}`);
      console.log(`Time: ${row.time}`);
      console.log(`Surface: ${row.moisture_surface_pct}%`);
      console.log(`Deep: ${row.moisture_deep_pct}%`);
      console.log(`Flood: ${row.flood_status ? 'YES' : 'NO'}`);
      console.log('---');
    });
    
  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await pool.end();
  }
}

checkRegistration();