#!/usr/bin/env node

const { Pool } = require('pg');

async function testInsert() {
  const pool = new Pool({
    host: 'localhost',
    port: 5433,
    database: 'sensor_data',
    user: 'postgres',
    password: 'postgres'
  });

  try {
    // Test direct insert
    const result = await pool.query(`
      INSERT INTO sensor.sensors (sensor_id, sensor_type, location_lat, location_lng, metadata)
      VALUES ($1, $2, $3, $4, $5)
      ON CONFLICT (sensor_id) 
      DO UPDATE SET 
        location_lat = $3,
        location_lng = $4,
        metadata = sensor.sensors.metadata || $5,
        updated_at = NOW();
    `, [
      '00001-00001',
      'moisture',
      13.7563,
      100.5018,
      { manufacturer: 'M2M', test: true }
    ]);
    
    console.log('Insert successful:', result);
    
    // Query the data
    const queryResult = await pool.query('SELECT * FROM sensor.sensors WHERE sensor_id = $1', ['00001-00001']);
    console.log('Data:', queryResult.rows[0]);
    
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await pool.end();
  }
}

testInsert();