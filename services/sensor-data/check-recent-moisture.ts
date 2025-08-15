import { Pool } from 'pg';
import * as dotenv from 'dotenv';

dotenv.config();

const pool = new Pool({
  host: process.env.TIMESCALE_HOST || 'localhost',
  port: parseInt(process.env.TIMESCALE_PORT || '5433'),
  database: process.env.TIMESCALE_DB || 'munbon_timescale',
  user: process.env.TIMESCALE_USER || 'postgres',
  password: process.env.TIMESCALE_PASSWORD || 'postgres'
});

async function checkRecentMoistureData() {
  try {
    // Check all moisture readings from today
    console.log('=== Checking moisture_readings table for today\'s data ===');
    const todayResult = await pool.query(`
      SELECT 
        time,
        sensor_id,
        moisture_surface_pct,
        moisture_deep_pct,
        temp_surface_c,
        temp_deep_c,
        ambient_humidity_pct,
        ambient_temp_c,
        flood_status,
        voltage,
        quality_score
      FROM moisture_readings 
      WHERE time >= CURRENT_DATE
      ORDER BY time DESC
    `);
    
    console.log(`Found ${todayResult.rows.length} moisture readings from today`);
    if (todayResult.rows.length > 0) {
      console.table(todayResult.rows);
    }
    
    // Check specific sensor IDs we've been testing
    console.log('\n=== Checking specific test sensor IDs ===');
    const testSensorIds = ['0001-000D', '0002-001A', '0002-001B', '0002'];
    
    for (const sensorId of testSensorIds) {
      const result = await pool.query(`
        SELECT 
          time,
          sensor_id,
          moisture_surface_pct,
          moisture_deep_pct,
          temp_surface_c,
          temp_deep_c
        FROM moisture_readings 
        WHERE sensor_id = $1
        ORDER BY time DESC
        LIMIT 3
      `, [sensorId]);
      
      console.log(`\nSensor ${sensorId}: ${result.rows.length} records`);
      if (result.rows.length > 0) {
        console.table(result.rows);
      }
    }
    
    // Check sensor_readings for comparison
    console.log('\n=== Checking sensor_readings table for moisture data ===');
    const sensorResult = await pool.query(`
      SELECT 
        time,
        sensor_id,
        sensor_type,
        value->>'humid_hi' as surface_moisture,
        value->>'humid_low' as deep_moisture,
        value->>'temp_hi' as temp_surface,
        value->>'temp_low' as temp_deep
      FROM sensor_readings 
      WHERE sensor_type = 'moisture'
        AND time >= CURRENT_DATE
      ORDER BY time DESC
      LIMIT 10
    `);
    
    console.log(`\nFound ${sensorResult.rows.length} moisture readings in sensor_readings table`);
    if (sensorResult.rows.length > 0) {
      console.table(sensorResult.rows);
    }
    
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await pool.end();
  }
}

checkRecentMoistureData();