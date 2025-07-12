const { execSync } = require('child_process');

function runQuery(query, title) {
  console.log(`\n${title}`);
  console.log('='.repeat(title.length));
  try {
    const result = execSync(
      `docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "${query}"`,
      { encoding: 'utf8' }
    );
    console.log(result);
  } catch (error) {
    console.error('Query failed:', error.message);
  }
}

console.log('🔍 Checking TimescaleDB Data');
console.log('============================');

// Check sensor registry
runQuery(
  `SELECT sensor_id, sensor_type, manufacturer, last_seen, is_active 
   FROM sensor_registry 
   ORDER BY last_seen DESC 
   LIMIT 10;`,
  '1. Registered Sensors (Latest 10)'
);

// Check generic sensor readings
runQuery(
  `SELECT time, sensor_id, sensor_type, 
          value->>'level' as water_level_cm,
          value->>'humid_hi' as top_moisture,
          value->>'humid_low' as bottom_moisture,
          quality_score
   FROM sensor_readings 
   ORDER BY time DESC 
   LIMIT 10;`,
  '2. Generic Sensor Readings (Latest 10)'
);

// Check water level readings
runQuery(
  `SELECT time, sensor_id, level_cm, voltage, rssi, quality_score
   FROM water_level_readings 
   ORDER BY time DESC 
   LIMIT 10;`,
  '3. Water Level Readings (Latest 10)'
);

// Check moisture readings
runQuery(
  `SELECT time, sensor_id, moisture_surface_pct, moisture_deep_pct, ambient_temp_c, quality_score
   FROM moisture_readings 
   ORDER BY time DESC 
   LIMIT 10;`,
  '4. Moisture Readings (Latest 10)'
);

// Summary statistics
runQuery(
  `SELECT 
     sensor_type,
     COUNT(DISTINCT sensor_id) as unique_sensors,
     COUNT(*) as total_readings,
     MIN(time) as oldest_reading,
     MAX(time) as newest_reading
   FROM sensor_readings
   GROUP BY sensor_type;`,
  '5. Summary Statistics by Sensor Type'
);

// Check for recent data (last hour)
runQuery(
  `SELECT 
     sensor_type,
     COUNT(*) as readings_last_hour
   FROM sensor_readings
   WHERE time > NOW() - INTERVAL '1 hour'
   GROUP BY sensor_type;`,
  '6. Readings in Last Hour'
);

// Check SQS Queue
console.log('\n7. Checking SQS Queue Status');
console.log('============================');
try {
  execSync('node check-sqs.js', { stdio: 'inherit' });
} catch (error) {
  console.log('Could not check SQS status');
}