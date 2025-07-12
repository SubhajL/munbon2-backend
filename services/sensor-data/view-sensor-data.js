const { execSync } = require('child_process');

console.log('📊 Sensor Data Summary');
console.log('======================\n');

// Water Level Data
const waterLevelQuery = `
SELECT 
  time,
  sensor_id,
  (value->>'level')::float as level_cm,
  location_lat,
  location_lng,
  quality_score
FROM sensor_readings 
WHERE sensor_type = 'water-level'
ORDER BY time DESC 
LIMIT 10;
`;

console.log('💧 Water Level Sensors (Latest 10 readings)');
console.log('==========================================');
try {
  const result = execSync(
    `docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "${waterLevelQuery}"`,
    { encoding: 'utf8' }
  );
  console.log(result);
} catch (error) {
  console.error('Query failed');
}

// Moisture Data
const moistureQuery = `
SELECT 
  time,
  sensor_id,
  CASE 
    WHEN value->>'type' = 'top_soil_moisture' THEN 'Top'
    WHEN value->>'type' = 'bottom_soil_moisture' THEN 'Bottom'
  END as layer,
  COALESCE((value->>'humid_hi')::float, (value->>'humid_low')::float) as moisture_pct,
  COALESCE((value->>'temp_hi')::float, (value->>'temp_low')::float) as temp_c,
  location_lat,
  location_lng,
  quality_score
FROM sensor_readings 
WHERE sensor_type = 'moisture'
ORDER BY time DESC 
LIMIT 20;
`;

console.log('🌱 Moisture Sensors (Latest 20 readings)');
console.log('=======================================');
try {
  const result = execSync(
    `docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "${moistureQuery}"`,
    { encoding: 'utf8' }
  );
  console.log(result);
} catch (error) {
  console.error('Query failed');
}

// Summary by sensor
const summaryQuery = `
SELECT 
  s.sensor_id,
  s.sensor_type,
  COUNT(r.*) as total_readings,
  MAX(r.time) as latest_reading,
  CASE 
    WHEN s.sensor_type = 'water-level' THEN 
      ROUND(AVG((r.value->>'level')::float), 2)::text || ' cm'
    WHEN s.sensor_type = 'moisture' THEN 
      ROUND(AVG(COALESCE((r.value->>'humid_hi')::float, (r.value->>'humid_low')::float)), 2)::text || ' %'
  END as avg_value
FROM sensor_registry s
LEFT JOIN sensor_readings r ON s.sensor_id = r.sensor_id
WHERE s.last_seen > NOW() - INTERVAL '1 hour'
GROUP BY s.sensor_id, s.sensor_type
ORDER BY s.sensor_type, s.sensor_id;
`;

console.log('📈 Sensor Summary (Active in last hour)');
console.log('======================================');
try {
  const result = execSync(
    `docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "${summaryQuery}"`,
    { encoding: 'utf8' }
  );
  console.log(result);
} catch (error) {
  console.error('Query failed');
}