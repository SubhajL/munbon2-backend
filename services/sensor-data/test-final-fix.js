#!/usr/bin/env node

const axios = require('axios');
const { Pool } = require('pg');

const pool = new Pool({
  host: 'localhost',
  port: 5433,
  database: 'munbon_timescale',
  user: 'postgres',
  password: 'postgres'
});

// Test data that was creating "undefined" sensor IDs
const testData = {
  "date": "2025/07/30",
  "time": new Date().toISOString().split('T')[1].substring(0, 8),
  "sensor": [
    {
      "date": "2025/07/30",
      "time": new Date().toISOString().split('T')[1].substring(0, 8),
      "flood": "no",
      "temp_hi": "28.00",
      "amb_temp": "32.00",
      "humid_hi": "48",
      "temp_low": "27.50",
      "amb_humid": "68.0",
      "humid_low": "55",
      "sensor_id": "00001",
      "sensor_batt": "398"
    }
  ],
  "gw_batt": "375",
  "latitude": "13.7563",
  "msg_type": "interval",
  "longitude": "100.5018",
  "gateway_id": "00005",  // New gateway ID for clean test
  "humidity": "68.00",
  "heat_index": "38.00",
  "temperature": "32.00"
};

async function testFinalFix() {
  console.log('FINAL TEST: Moisture Sensor Fix Verification');
  console.log('==========================================\n');
  
  try {
    // Clean up any old test data
    await pool.query(`
      DELETE FROM sensor_readings 
      WHERE sensor_id LIKE '%00005%' 
        AND time > NOW() - INTERVAL '1 hour'
    `);
    
    console.log('1. Sending test data with gateway_id: 00005');
    console.log('   Expected result: NO undefined entries\n');
    
    const response = await axios.post(
      'http://localhost:3003/api/v1/munbon-m2m-moisture/telemetry',
      testData,
      { headers: { 'Content-Type': 'application/json' } }
    );
    
    console.log('2. Response:', response.status, response.statusText);
    
    // Wait for processing
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Check results
    console.log('\n3. Checking database results...\n');
    
    // Check sensor_readings
    const sr = await pool.query(`
      SELECT sensor_id, sensor_type, time 
      FROM sensor_readings 
      WHERE sensor_id LIKE '%00005%' 
      ORDER BY time DESC
    `);
    
    console.log('SENSOR_READINGS TABLE:');
    console.log('---------------------');
    if (sr.rows.length === 0) {
      console.log('✅ No entries (as expected for array format)');
    } else {
      sr.rows.forEach(row => {
        const hasUndefined = row.sensor_id.includes('undefined');
        console.log(`${hasUndefined ? '❌' : '✅'} ${row.sensor_id} (${row.sensor_type})`);
      });
    }
    
    // Check moisture_readings
    const mr = await pool.query(`
      SELECT sensor_id, moisture_surface_pct, moisture_deep_pct 
      FROM moisture_readings 
      WHERE sensor_id LIKE '%00005%' 
      ORDER BY time DESC
    `);
    
    console.log('\nMOISTURE_READINGS TABLE:');
    console.log('-----------------------');
    mr.rows.forEach(row => {
      console.log(`✅ ${row.sensor_id}: Surface=${row.moisture_surface_pct}%, Deep=${row.moisture_deep_pct}%`);
    });
    
    // Summary
    const hasUndefined = sr.rows.some(r => r.sensor_id.includes('undefined'));
    console.log('\n4. SUMMARY:');
    console.log('-----------');
    if (!hasUndefined && mr.rows.length > 0) {
      console.log('✅ SUCCESS! No undefined sensor IDs created');
      console.log('✅ Moisture data properly stored with correct sensor IDs');
      console.log('✅ The fix is working correctly!');
    } else if (hasUndefined) {
      console.log('❌ FAILED: Still creating undefined sensor IDs');
    } else if (mr.rows.length === 0) {
      console.log('❌ FAILED: No moisture readings created');
    }
    
    await pool.end();
    
  } catch (error) {
    console.error('Error:', error.response?.data || error.message);
    await pool.end();
  }
}

testFinalFix();