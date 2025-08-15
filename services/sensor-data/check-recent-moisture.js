const { Pool } = require('pg');

const pool = new Pool({
  host: 'localhost',
  port: 5433,
  database: 'munbon_timescale',
  user: 'postgres',
  password: 'postgres'
});

async function checkRecentMoisture() {
  try {
    console.log('=== Checking for Recent Moisture Data ===\n');
    console.log('Current time:', new Date().toLocaleString());
    console.log('CloudFlare endpoint: https://munbon-moisture.beautifyai.io/api/v1/munbon-m2m-moisture/telemetry\n');
    
    // 1. Check last 24 hours of moisture data
    const last24h = await pool.query(`
      SELECT 
        DATE_TRUNC('hour', time) as hour,
        COUNT(*) as readings,
        COUNT(DISTINCT sensor_id) as sensors,
        ARRAY_AGG(DISTINCT sensor_id) as sensor_list
      FROM moisture_readings
      WHERE time > NOW() - INTERVAL '24 hours'
      GROUP BY DATE_TRUNC('hour', time)
      ORDER BY hour DESC
    `);
    
    if (last24h.rows.length === 0) {
      console.log('❌ NO MOISTURE DATA in the last 24 hours\n');
    } else {
      console.log('Moisture Data by Hour (Last 24h):');
      console.log('Hour                     | Readings | Sensors | Sensor IDs');
      console.log('-------------------------|----------|---------|------------');
      last24h.rows.forEach(row => {
        console.log(
          `${new Date(row.hour).toLocaleString()} | ` +
          `${row.readings.toString().padStart(8)} | ` +
          `${row.sensors.toString().padStart(7)} | ` +
          `${row.sensor_list.join(', ')}`
        );
      });
    }
    
    // 2. Check the very latest moisture readings
    const latest = await pool.query(`
      SELECT 
        sensor_id,
        time,
        moisture_surface_pct,
        moisture_deep_pct,
        flood_status,
        ambient_temp_c,
        ambient_humidity_pct
      FROM moisture_readings
      ORDER BY time DESC
      LIMIT 5
    `);
    
    console.log('\n\nLatest 5 Moisture Readings:');
    console.log('Time                     | Sensor         | Surface | Deep  | Ambient      | Flood');
    console.log('-------------------------|----------------|---------|-------|--------------|------');
    latest.rows.forEach(row => {
      console.log(
        `${new Date(row.time).toLocaleString()} | ` +
        `${row.sensor_id.padEnd(14)} | ` +
        `${row.moisture_surface_pct}%`.padEnd(7) + ' | ' +
        `${row.moisture_deep_pct}%`.padEnd(5) + ' | ' +
        `${row.ambient_temp_c}°C, ${row.ambient_humidity_pct}%`.padEnd(12) + ' | ' +
        `${row.flood_status ? '🚨YES' : 'No'}`
      );
    });
    
    // 3. Check gateway activity
    const gateways = await pool.query(`
      SELECT 
        sensor_id,
        last_seen,
        metadata
      FROM sensor_registry
      WHERE sensor_type = 'gateway'
      ORDER BY last_seen DESC
      LIMIT 5
    `);
    
    console.log('\n\nGateway Activity:');
    console.log('Gateway    | Last Seen               | Ambient Conditions');
    console.log('-----------|-------------------------|-------------------');
    gateways.rows.forEach(row => {
      const ambient = row.metadata ? 
        `${row.metadata.temperature}°C, ${row.metadata.humidity}%, HI: ${row.metadata.heatIndex}` : 
        'No data';
      console.log(
        `${row.sensor_id.padEnd(10)} | ` +
        `${new Date(row.last_seen).toLocaleString()} | ` +
        ambient
      );
    });
    
    // 4. Check time since last data
    const lastData = await pool.query(`
      SELECT 
        MAX(time) as last_time,
        NOW() - MAX(time) as time_ago
      FROM moisture_readings
    `);
    
    if (lastData.rows[0].last_time) {
      const lastTime = new Date(lastData.rows[0].last_time);
      const timeAgo = lastData.rows[0].time_ago;
      
      console.log('\n\n📊 SUMMARY:');
      console.log(`Last moisture data received: ${lastTime.toLocaleString()}`);
      
      // Parse the interval
      const days = timeAgo.days || 0;
      const hours = timeAgo.hours || 0;
      const minutes = Math.floor(timeAgo.seconds / 60) || 0;
      
      if (days > 0) {
        console.log(`Time since last data: ${days} days, ${hours} hours ago`);
      } else if (hours > 0) {
        console.log(`Time since last data: ${hours} hours, ${minutes % 60} minutes ago`);
      } else {
        console.log(`Time since last data: ${minutes} minutes ago`);
      }
      
      if (hours === 0 && minutes < 5) {
        console.log('\n✅ RECEIVING RECENT DATA - System is active');
      } else if (hours < 1) {
        console.log('\n⚠️  Data received within the last hour');
      } else {
        console.log('\n❌ NO RECENT DATA - Last data is more than 1 hour old');
      }
    }
    
    // 5. Check sensor registration activity
    const newSensors = await pool.query(`
      SELECT COUNT(*) as count
      FROM sensor_registry
      WHERE sensor_type IN ('moisture', 'gateway')
      AND created_at > NOW() - INTERVAL '1 hour'
    `);
    
    console.log(`\nNew sensor registrations (last hour): ${newSensors.rows[0].count}`);
    
  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await pool.end();
  }
}

checkRecentMoisture();