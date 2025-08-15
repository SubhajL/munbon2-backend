import { Pool } from 'pg';
import * as dotenv from 'dotenv';

dotenv.config();

async function checkHypertableStatus() {
  const pool = new Pool({
    host: process.env.TIMESCALE_HOST || 'localhost',
    port: parseInt(process.env.TIMESCALE_PORT || '5433'),
    database: process.env.TIMESCALE_DB || 'munbon_timescale',
    user: process.env.TIMESCALE_USER || 'postgres',
    password: process.env.TIMESCALE_PASSWORD || 'postgres'
  });

  try {
    // Check TimescaleDB extension
    console.log('=== Checking TimescaleDB Extension ===');
    const extResult = await pool.query(`
      SELECT extname, extversion 
      FROM pg_extension 
      WHERE extname = 'timescaledb';
    `);
    console.table(extResult.rows);
    
    // Check hypertables
    console.log('\n=== Checking Hypertables ===');
    const hypertablesQuery = `
      SELECT hypertable_schema, hypertable_name, chunk_time_interval
      FROM timescaledb_information.hypertables
      WHERE hypertable_schema = 'public';
    `;
    
    const hypertablesResult = await pool.query(hypertablesQuery);
    console.table(hypertablesResult.rows);
    
    // Check if tables are actually hypertables
    console.log('\n=== Checking Table Types ===');
    const tableTypes = await pool.query(`
      SELECT 
        t.table_name,
        CASE 
          WHEN h.hypertable_name IS NOT NULL THEN 'Hypertable'
          ELSE 'Regular Table'
        END as table_type
      FROM information_schema.tables t
      LEFT JOIN timescaledb_information.hypertables h 
        ON t.table_name = h.hypertable_name 
        AND t.table_schema = h.hypertable_schema
      WHERE t.table_schema = 'public' 
        AND t.table_name IN ('sensor_readings', 'water_level_readings', 'moisture_readings')
      ORDER BY t.table_name;
    `);
    console.table(tableTypes.rows);
    
    // Check moisture_readings structure
    console.log('\n=== Moisture Readings Table Structure ===');
    const structureQuery = `
      SELECT column_name, data_type, is_nullable
      FROM information_schema.columns
      WHERE table_name = 'moisture_readings'
      ORDER BY ordinal_position;
    `;
    
    const structureResult = await pool.query(structureQuery);
    console.table(structureResult.rows);
    
    // Test different insert methods
    console.log('\n=== Testing Insert Methods ===');
    
    // Method 1: Direct insert (which failed before)
    try {
      await pool.query(`
        INSERT INTO moisture_readings 
        (time, sensor_id, location_lat, location_lng, moisture_surface_pct, moisture_deep_pct,
         temp_surface_c, temp_deep_c, ambient_humidity_pct, ambient_temp_c,
         flood_status, voltage, quality_score)
        VALUES (NOW(), 'TEST-METHOD1', 14.4972, 102.1505, 38.2, 48.7, 26.2, 25.9, 55.5, 27.8, false, 4.05, 0.95);
      `);
      console.log('✓ Method 1 (Direct INSERT): Success');
      await pool.query(`DELETE FROM moisture_readings WHERE sensor_id = 'TEST-METHOD1'`);
    } catch (err: any) {
      console.log('✗ Method 1 (Direct INSERT): Failed -', err.message);
    }
    
    // Check if we need to create a regular table instead of hypertable
    console.log('\n=== Checking if moisture_readings is a hypertable ===');
    const isHypertableQuery = `
      SELECT COUNT(*) as is_hypertable
      FROM timescaledb_information.hypertables
      WHERE hypertable_name = 'moisture_readings';
    `;
    
    const isHypertableResult = await pool.query(isHypertableQuery);
    const isHypertable = parseInt(isHypertableResult.rows[0].is_hypertable) > 0;
    console.log('moisture_readings is hypertable:', isHypertable);
    
    // Check water_level_readings for comparison
    console.log('\n=== Recent Water Level Data (for comparison) ===');
    const waterLevelQuery = `
      SELECT time, sensor_id, level_cm, voltage
      FROM water_level_readings
      WHERE time >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
      ORDER BY time DESC
      LIMIT 5;
    `;
    
    const waterLevelResult = await pool.query(waterLevelQuery);
    console.log(`Found ${waterLevelResult.rows.length} water level records in the last hour`);
    if (waterLevelResult.rows.length > 0) {
      console.table(waterLevelResult.rows);
    }
    
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await pool.end();
  }
}

checkHypertableStatus();