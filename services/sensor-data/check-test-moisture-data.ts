import { Pool } from 'pg';

const ec2Pool = new Pool({
  host: '43.208.201.191',
  port: 5432,
  database: 'sensor_data',
  user: 'postgres',
  password: '__ROTATED_DB_PASSWORD__',
  connectionTimeoutMillis: 5000,
});

async function checkTestData() {
  try {
    // Check for our test data
    const result = await ec2Pool.query(`
      SELECT 
        time,
        sensor_id,
        moisture_surface_pct,
        temp_surface_c,
        voltage,
        location_lat,
        location_lng
      FROM moisture_readings 
      WHERE sensor_id LIKE 'TEST-%'
      ORDER BY time DESC
      LIMIT 5
    `);
    
    console.log('Test moisture data:', result.rows.length);
    if (result.rows.length > 0) {
      console.table(result.rows);
    }
    
    // Also check today's data
    const todayResult = await ec2Pool.query(`
      SELECT 
        COUNT(*) as count,
        MAX(time) as latest_reading
      FROM moisture_readings 
      WHERE time >= CURRENT_DATE
    `);
    
    console.log('\nToday\'s moisture data summary:');
    console.table(todayResult.rows);
    
  } finally {
    await ec2Pool.end();
  }
}

checkTestData();