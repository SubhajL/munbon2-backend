import { Pool } from 'pg';
import * as dotenv from 'dotenv';

dotenv.config();

async function testDatabaseConnection() {
  const pool = new Pool({
    host: process.env.TIMESCALE_HOST || 'localhost',
    port: parseInt(process.env.TIMESCALE_PORT || '5433'),
    database: process.env.TIMESCALE_DB || 'munbon_timescale',
    user: process.env.TIMESCALE_USER || 'postgres',
    password: process.env.TIMESCALE_PASSWORD || 'postgres'
  });

  try {
    // Test connection
    console.log('Testing TimescaleDB connection...');
    const result = await pool.query('SELECT NOW()');
    console.log('Connected successfully at:', result.rows[0].now);
    
    // Check if tables exist
    const tablesQuery = `
      SELECT tablename 
      FROM pg_tables 
      WHERE schemaname = 'public' 
      AND tablename IN ('sensor_readings', 'moisture_readings', 'water_level_readings')
      ORDER BY tablename;
    `;
    
    const tablesResult = await pool.query(tablesQuery);
    console.log('\nExisting tables:');
    tablesResult.rows.forEach(row => console.log('  -', row.tablename));
    
    // Check recent sensor_readings
    const recentQuery = `
      SELECT time, sensor_id, sensor_type 
      FROM sensor_readings 
      WHERE time >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
      ORDER BY time DESC
      LIMIT 5;
    `;
    
    const recentResult = await pool.query(recentQuery);
    console.log(`\nRecent sensor_readings (last hour): ${recentResult.rows.length} records`);
    if (recentResult.rows.length > 0) {
      console.table(recentResult.rows);
    }
    
    // Test insert
    console.log('\n--- Testing direct insert to moisture_readings ---');
    const testInsert = `
      INSERT INTO moisture_readings 
      (time, sensor_id, location_lat, location_lng, moisture_surface_pct, moisture_deep_pct,
       temp_surface_c, temp_deep_c, ambient_humidity_pct, ambient_temp_c,
       flood_status, voltage, quality_score)
      VALUES (NOW(), 'TEST-001', 14.4972, 102.1505, 38.2, 48.7, 26.2, 25.9, 55.5, 27.8, false, 4.05, 0.95)
      RETURNING *;
    `;
    
    const insertResult = await pool.query(testInsert);
    console.log('Test insert successful:', insertResult.rows[0]);
    
    // Verify the insert
    const verifyQuery = `
      SELECT * FROM moisture_readings WHERE sensor_id = 'TEST-001' ORDER BY time DESC LIMIT 1;
    `;
    
    const verifyResult = await pool.query(verifyQuery);
    console.log('\nVerified insert:', verifyResult.rows.length > 0 ? 'Found' : 'Not found');
    
    // Clean up test data
    await pool.query(`DELETE FROM moisture_readings WHERE sensor_id = 'TEST-001'`);
    console.log('Cleaned up test data');
    
  } catch (error) {
    console.error('Database error:', error);
  } finally {
    await pool.end();
  }
}

testDatabaseConnection();