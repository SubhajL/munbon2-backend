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

async function checkMoistureReadings() {
  try {
    // Check latest moisture readings
    const result = await pool.query(`
      SELECT 
        time,
        sensor_id,
        moisture_surface_pct,
        moisture_deep_pct,
        temp_surface_c,
        temp_deep_c,
        ambient_humidity_pct,
        flood_status,
        voltage
      FROM moisture_readings 
      WHERE sensor_id LIKE '0001%' 
      ORDER BY time DESC 
      LIMIT 5
    `);
    
    console.log('Latest moisture readings:');
    console.table(result.rows);
    
    // Check sensor_readings for comparison
    const sensorResult = await pool.query(`
      SELECT 
        time,
        sensor_id,
        value->>'humid_hi' as surface_moisture,
        value->>'humid_low' as deep_moisture,
        value->>'temp_hi' as temp_surface,
        value->>'temp_low' as temp_deep
      FROM sensor_readings 
      WHERE sensor_id LIKE '0001%' 
        AND sensor_type = 'moisture'
      ORDER BY time DESC 
      LIMIT 5
    `);
    
    console.log('\nSensor readings (generic table):');
    console.table(sensorResult.rows);
    
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await pool.end();
  }
}

checkMoistureReadings();