const { Pool } = require('pg');

const pool = new Pool({
  host: 'localhost',
  port: 5433,
  database: 'munbon_timescale',
  user: 'postgres',
  password: 'postgres'
});

// Map device ID to AWD ID
function getAWDId(deviceId) {
  const mapping = {
    '22166174123108163': 'AWD-6CA3',
    '2216617412314704': 'AWD-9304',
    '2216617412313572': 'AWD-8748',
    '22241083117959': 'AWD-45C7',
    '22241083118390': 'AWD-47B6'
  };
  return mapping[deviceId] || deviceId;
}

async function checkWaterLevelData() {
  try {
    console.log('Checking water level data in the database...\n');
    
    // 1. Check total water level sensors
    const sensorCount = await pool.query(`
      SELECT COUNT(DISTINCT sensor_id) as count
      FROM sensor_registry
      WHERE sensor_type = 'water-level'
    `);
    console.log(`Total water level sensors registered: ${sensorCount.rows[0].count}`);
    
    // 2. Check total water level readings
    const readingCount = await pool.query(`
      SELECT COUNT(*) as count
      FROM water_level_readings
    `);
    console.log(`Total water level readings: ${readingCount.rows[0].count}`);
    
    // 3. Check recent readings (last 24 hours)
    const recentReadings = await pool.query(`
      SELECT 
        sensor_id,
        COUNT(*) as reading_count,
        MIN(time) as first_reading,
        MAX(time) as last_reading,
        AVG(level_cm) as avg_level,
        MIN(level_cm) as min_level,
        MAX(level_cm) as max_level
      FROM water_level_readings
      WHERE time > NOW() - INTERVAL '24 hours'
      GROUP BY sensor_id
      ORDER BY last_reading DESC
    `);
    
    console.log(`\nWater level sensors with data in last 24 hours: ${recentReadings.rows.length}`);
    
    if (recentReadings.rows.length > 0) {
      console.log('\n=== Recent Sensor Activity (Last 24 Hours) ===');
      recentReadings.rows.forEach(row => {
        const awdId = getAWDId(row.sensor_id);
        console.log(`\nSensor: ${awdId} (${row.sensor_id})`);
        console.log(`  Readings: ${row.reading_count}`);
        console.log(`  First: ${new Date(row.first_reading).toLocaleString()}`);
        console.log(`  Last: ${new Date(row.last_reading).toLocaleString()}`);
        console.log(`  Level - Avg: ${parseFloat(row.avg_level).toFixed(2)}cm, Min: ${row.min_level}cm, Max: ${row.max_level}cm`);
      });
    }
    
    // 4. Check latest readings
    const latestReadings = await pool.query(`
      SELECT 
        r.sensor_id,
        r.time,
        r.level_cm,
        r.voltage,
        r.location_lat,
        r.location_lng,
        s.metadata
      FROM water_level_readings r
      JOIN sensor_registry s ON r.sensor_id = s.sensor_id
      ORDER BY r.time DESC
      LIMIT 10
    `);
    
    console.log('\n=== Latest 10 Water Level Readings ===');
    latestReadings.rows.forEach(row => {
      const awdId = getAWDId(row.sensor_id);
      console.log(`${new Date(row.time).toLocaleString()} - ${awdId}: ${row.level_cm}cm (${row.voltage}V)`);
      if (row.location_lat && row.location_lng) {
        console.log(`  Location: ${row.location_lat}, ${row.location_lng}`);
      }
    });
    
    // 5. Check sensors with automatic registration
    const autoRegistered = await pool.query(`
      SELECT 
        sensor_id,
        last_seen,
        metadata,
        location_lat,
        location_lng
      FROM sensor_registry
      WHERE sensor_type = 'water-level'
      AND created_at > NOW() - INTERVAL '1 hour'
      ORDER BY created_at DESC
    `);
    
    if (autoRegistered.rows.length > 0) {
      console.log(`\n=== Recently Auto-Registered Sensors (Last Hour) ===`);
      autoRegistered.rows.forEach(row => {
        const awdId = getAWDId(row.sensor_id);
        console.log(`${awdId} (${row.sensor_id}) - Registered at ${new Date(row.last_seen).toLocaleString()}`);
        if (row.metadata) {
          console.log(`  Metadata: ${JSON.stringify(row.metadata)}`);
        }
      });
    }
    
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await pool.end();
  }
}

checkWaterLevelData();