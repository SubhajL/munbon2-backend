import { Pool } from 'pg';
import * as dotenv from 'dotenv';

dotenv.config();

async function fixTimescaleDB() {
  const pool = new Pool({
    host: process.env.TIMESCALE_HOST || 'localhost',
    port: parseInt(process.env.TIMESCALE_PORT || '5433'),
    database: process.env.TIMESCALE_DB || 'munbon_timescale',
    user: process.env.TIMESCALE_USER || 'postgres',
    password: process.env.TIMESCALE_PASSWORD || 'postgres'
  });

  try {
    // Check if TimescaleDB is properly loaded
    console.log('=== Checking TimescaleDB Configuration ===');
    
    // Check shared_preload_libraries
    const configResult = await pool.query(`
      SHOW shared_preload_libraries;
    `);
    console.log('shared_preload_libraries:', configResult.rows[0].shared_preload_libraries);
    
    // Check if extension is loaded
    const extResult = await pool.query(`
      SELECT * FROM pg_extension WHERE extname = 'timescaledb';
    `);
    console.log('\nTimescaleDB extension:', extResult.rows.length > 0 ? 'Installed' : 'Not installed');
    
    // Try to enable TimescaleDB in current session
    console.log('\n=== Attempting to fix TimescaleDB ===');
    
    try {
      // First, let's try to insert with timescaledb functions
      console.log('Testing insert with TimescaleDB functions...');
      
      // Use timescaledb insert function if available
      const testResult = await pool.query(`
        INSERT INTO moisture_readings 
        (time, sensor_id, location_lat, location_lng, moisture_surface_pct, moisture_deep_pct,
         temp_surface_c, temp_deep_c, ambient_humidity_pct, ambient_temp_c,
         flood_status, voltage, quality_score)
        VALUES (CURRENT_TIMESTAMP, 'TEST-FIX', 14.4972, 102.1505, 38.2, 48.7, 26.2, 25.9, 55.5, 27.8, false, 4.05, 0.95)
        RETURNING *;
      `);
      
      console.log('✓ INSERT successful!');
      console.log('Inserted row:', testResult.rows[0]);
      
      // Clean up
      await pool.query(`DELETE FROM moisture_readings WHERE sensor_id = 'TEST-FIX'`);
      console.log('✓ Test data cleaned up');
      
    } catch (err: any) {
      console.log('✗ INSERT still failing:', err.message);
      
      // Check if we need to recreate the table as a regular table
      console.log('\n=== Alternative: Check if we can use regular tables ===');
      
      // Create a test regular table
      try {
        await pool.query(`
          CREATE TABLE IF NOT EXISTS moisture_readings_test (
            time TIMESTAMPTZ NOT NULL,
            sensor_id VARCHAR(50) NOT NULL,
            location_lat DECIMAL(10, 6),
            location_lng DECIMAL(10, 6),
            moisture_surface_pct DECIMAL(5, 2),
            moisture_deep_pct DECIMAL(5, 2),
            temp_surface_c DECIMAL(5, 2),
            temp_deep_c DECIMAL(5, 2),
            ambient_humidity_pct DECIMAL(5, 2),
            ambient_temp_c DECIMAL(5, 2),
            flood_status BOOLEAN DEFAULT false,
            voltage DECIMAL(5, 2),
            quality_score DECIMAL(3, 2) DEFAULT 1.0
          );
        `);
        
        // Test insert on regular table
        await pool.query(`
          INSERT INTO moisture_readings_test 
          (time, sensor_id, location_lat, location_lng, moisture_surface_pct, moisture_deep_pct,
           temp_surface_c, temp_deep_c, ambient_humidity_pct, ambient_temp_c,
           flood_status, voltage, quality_score)
          VALUES (NOW(), 'TEST-REGULAR', 14.4972, 102.1505, 38.2, 48.7, 26.2, 25.9, 55.5, 27.8, false, 4.05, 0.95);
        `);
        
        console.log('✓ Regular table INSERT works!');
        
        // Clean up test
        await pool.query(`DROP TABLE moisture_readings_test;`);
        
      } catch (err2: any) {
        console.log('✗ Regular table test failed:', err2.message);
      }
    }
    
    // Check PostgreSQL version
    console.log('\n=== Database Version ===');
    const versionResult = await pool.query('SELECT version()');
    console.log(versionResult.rows[0].version);
    
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await pool.end();
  }
}

fixTimescaleDB();