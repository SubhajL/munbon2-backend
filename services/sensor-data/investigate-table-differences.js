#!/usr/bin/env node

const { Pool } = require('pg');

const pool = new Pool({
  host: 'localhost',
  port: 5433,
  database: 'munbon_timescale',
  user: 'postgres',
  password: 'postgres'
});

async function investigateTables() {
  try {
    console.log('INVESTIGATING SENSOR_READINGS vs MOISTURE_READINGS TABLES');
    console.log('========================================================\n');
    
    // 1. Check what's in sensor_readings but NOT in moisture_readings
    const onlyInSensorReadings = await pool.query(`
      SELECT 
        sr.sensor_id,
        sr.sensor_type,
        COUNT(*) as count,
        MAX(sr.time) as last_reading,
        sr.value::text as sample_data
      FROM sensor_readings sr
      LEFT JOIN moisture_readings mr ON sr.sensor_id = mr.sensor_id AND sr.time = mr.time
      WHERE sr.sensor_type = 'moisture' 
        AND mr.sensor_id IS NULL
        AND sr.time > NOW() - INTERVAL '7 days'
      GROUP BY sr.sensor_id, sr.sensor_type, sr.value
      ORDER BY last_reading DESC
      LIMIT 10
    `);
    
    console.log('1. MOISTURE DATA IN sensor_readings BUT NOT IN moisture_readings:');
    console.log('----------------------------------------------------------------');
    if (onlyInSensorReadings.rows.length > 0) {
      onlyInSensorReadings.rows.forEach(row => {
        console.log(`\nSensor: ${row.sensor_id} (${row.sensor_type})`);
        console.log(`Count: ${row.count}, Last: ${row.last_reading}`);
        console.log(`Sample data: ${row.sample_data?.substring(0, 200)}...`);
      });
    } else {
      console.log('All moisture sensor_readings have corresponding moisture_readings entries');
    }
    
    // 2. Check UNKNOWN sensor types and analyze their data structure
    const unknownSensors = await pool.query(`
      SELECT 
        sensor_id,
        sensor_type,
        time,
        value::text as raw_data,
        jsonb_pretty(value) as pretty_data
      FROM sensor_readings 
      WHERE sensor_type = 'UNKNOWN'
        AND time > NOW() - INTERVAL '7 days'
      ORDER BY time DESC
      LIMIT 5
    `);
    
    console.log('\n\n2. UNKNOWN SENSOR TYPES - Let\'s analyze their data:');
    console.log('--------------------------------------------------');
    if (unknownSensors.rows.length > 0) {
      unknownSensors.rows.forEach((row, idx) => {
        console.log(`\n${idx + 1}. Sensor ID: ${row.sensor_id}`);
        console.log(`   Time: ${row.time}`);
        console.log(`   Raw data structure:`);
        console.log(row.pretty_data);
        
        // Try to guess the type based on data structure
        const data = JSON.parse(row.raw_data);
        if (data.deviceID && data.level !== undefined) {
          console.log('   ⚡ LIKELY WATER LEVEL - has deviceID and level fields');
        } else if (data.gateway_id || data.sensor) {
          console.log('   💧 LIKELY MOISTURE - has gateway_id or sensor fields');
        } else {
          console.log('   ❓ UNKNOWN FORMAT - doesn\'t match expected patterns');
        }
      });
    } else {
      console.log('No unknown sensor types found');
    }
    
    // 3. Check the data processing flow
    console.log('\n\n3. DATA FLOW ANALYSIS:');
    console.log('---------------------');
    console.log('From the code (sensor-data.service.ts):');
    console.log('1. ALL data goes to sensor_readings table first');
    console.log('2. Then specific data goes to specialized tables:');
    console.log('   - Water level data → water_level_readings');
    console.log('   - Moisture data → moisture_readings');
    console.log('3. If sensor type is UNKNOWN, it only stays in sensor_readings\n');
    
    // 4. Check why GW001-undefined exists
    const gw001Data = await pool.query(`
      SELECT 
        sensor_id,
        time,
        jsonb_pretty(value) as data
      FROM sensor_readings 
      WHERE sensor_id LIKE 'GW001%'
      ORDER BY time DESC
      LIMIT 2
    `);
    
    console.log('\n4. INVESTIGATING GW001-undefined:');
    console.log('--------------------------------');
    if (gw001Data.rows.length > 0) {
      gw001Data.rows.forEach(row => {
        console.log(`\nTime: ${row.time}`);
        console.log('Data structure:');
        console.log(row.data);
      });
    }
    
    // 5. Compare counts
    const counts = await pool.query(`
      SELECT 
        'sensor_readings' as table_name,
        COUNT(*) as total,
        COUNT(CASE WHEN sensor_type = 'moisture' THEN 1 END) as moisture,
        COUNT(CASE WHEN sensor_type = 'water_level' OR sensor_type = 'water-level' THEN 1 END) as water_level,
        COUNT(CASE WHEN sensor_type = 'UNKNOWN' THEN 1 END) as unknown
      FROM sensor_readings
      WHERE time > NOW() - INTERVAL '7 days'
      
      UNION ALL
      
      SELECT 
        'moisture_readings' as table_name,
        COUNT(*) as total,
        COUNT(*) as moisture,
        0 as water_level,
        0 as unknown
      FROM moisture_readings
      WHERE time > NOW() - INTERVAL '7 days'
      
      UNION ALL
      
      SELECT 
        'water_level_readings' as table_name,
        COUNT(*) as total,
        0 as moisture,
        COUNT(*) as water_level,
        0 as unknown
      FROM water_level_readings
      WHERE time > NOW() - INTERVAL '7 days'
    `);
    
    console.log('\n\n5. TABLE COUNTS (Last 7 days):');
    console.log('-----------------------------');
    counts.rows.forEach(row => {
      console.log(`${row.table_name}:`);
      console.log(`  Total: ${row.total}`);
      if (row.moisture > 0) console.log(`  Moisture: ${row.moisture}`);
      if (row.water_level > 0) console.log(`  Water Level: ${row.water_level}`);
      if (row.unknown > 0) console.log(`  Unknown: ${row.unknown}`);
    });
    
    await pool.end();
    
    console.log('\n\n📊 SUMMARY:');
    console.log('-----------');
    console.log('- sensor_readings: Stores ALL incoming data (first stop)');
    console.log('- moisture_readings: Only stores successfully processed moisture data');
    console.log('- GW001-undefined: Likely a malformed sensor ID (should be MS-xxxxx-xxxxx)');
    console.log('- UNKNOWN records: Failed type detection, need to check data structure');
    
  } catch (err) {
    console.error('Error:', err);
    await pool.end();
  }
}

investigateTables();