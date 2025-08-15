import { Pool } from 'pg';
import * as dotenv from 'dotenv';

dotenv.config();

async function testRawInsert() {
  const pool = new Pool({
    host: process.env.TIMESCALE_HOST || 'localhost',
    port: parseInt(process.env.TIMESCALE_PORT || '5433'),
    database: process.env.TIMESCALE_DB || 'munbon_timescale',
    user: process.env.TIMESCALE_USER || 'postgres',
    password: process.env.TIMESCALE_PASSWORD || 'postgres',
    // Add these options to ensure proper connection
    application_name: 'test_insert',
    statement_timeout: 30000,
  });

  try {
    console.log('=== Testing Database Connection ===');
    console.log('Config:', {
      host: pool.options.host,
      port: pool.options.port,
      database: pool.options.database,
      user: pool.options.user
    });
    
    // Test basic connection
    const testConn = await pool.query('SELECT current_database(), current_user, version()');
    console.log('Connected to:', testConn.rows[0].current_database);
    console.log('As user:', testConn.rows[0].current_user);
    
    // Check if TimescaleDB functions are available
    console.log('\n=== Checking TimescaleDB Functions ===');
    const funcCheck = await pool.query(`
      SELECT proname 
      FROM pg_proc 
      WHERE proname LIKE '%hypertable%' 
      LIMIT 5;
    `);
    console.log('TimescaleDB functions found:', funcCheck.rows.length);
    
    // Let's try a different approach - use sensor_readings table
    console.log('\n=== Testing sensor_readings (generic table) ===');
    try {
      const sensorResult = await pool.query(`
        INSERT INTO sensor_readings 
        (time, sensor_id, sensor_type, location_lat, location_lng, value, metadata, quality_score)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING *;
      `, [
        new Date(),
        'TEST-SENSOR',
        'moisture',
        14.4972,
        102.1505,
        { humid_hi: 38.2, humid_low: 48.7, temp_hi: 26.2, temp_low: 25.9 },
        { test: true },
        0.95
      ]);
      
      console.log('✓ sensor_readings INSERT successful!');
      console.log('Inserted:', sensorResult.rows[0]);
      
      // Clean up
      await pool.query(`DELETE FROM sensor_readings WHERE sensor_id = 'TEST-SENSOR'`);
      
    } catch (err: any) {
      console.log('✗ sensor_readings INSERT failed:', err.code, err.message);
    }
    
    // Check if we can query from the hypertables
    console.log('\n=== Querying Hypertables ===');
    
    // Query moisture_readings
    const moistureCount = await pool.query(`
      SELECT COUNT(*) as count FROM moisture_readings;
    `);
    console.log('moisture_readings count:', moistureCount.rows[0].count);
    
    // Query water_level_readings  
    const waterCount = await pool.query(`
      SELECT COUNT(*) as count FROM water_level_readings;
    `);
    console.log('water_level_readings count:', waterCount.rows[0].count);
    
    // Check latest entries
    console.log('\n=== Latest Entries ===');
    const latestMoisture = await pool.query(`
      SELECT time, sensor_id FROM moisture_readings ORDER BY time DESC LIMIT 3;
    `);
    console.log('Latest moisture readings:', latestMoisture.rows.length);
    if (latestMoisture.rows.length > 0) {
      console.table(latestMoisture.rows);
    }
    
    const latestWater = await pool.query(`
      SELECT time, sensor_id, level_cm FROM water_level_readings ORDER BY time DESC LIMIT 3;
    `);
    console.log('Latest water level readings:', latestWater.rows.length);
    if (latestWater.rows.length > 0) {
      console.table(latestWater.rows);
    }
    
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await pool.end();
  }
}

testRawInsert();