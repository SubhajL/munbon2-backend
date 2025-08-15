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

// Unique test data
const testData = {
  "date": "2025/07/30",
  "time": new Date().toISOString().split('T')[1].substring(0, 8),
  "sensor": [
    {
      "date": "2025/07/30",
      "time": new Date().toISOString().split('T')[1].substring(0, 8),
      "flood": "no",
      "temp_hi": "29.00",
      "amb_temp": "33.00",
      "humid_hi": "50",
      "temp_low": "28.50",
      "amb_humid": "70.0",
      "humid_low": "57",
      "sensor_id": "00001",
      "sensor_batt": "400"
    }
  ],
  "gw_batt": "380",
  "latitude": "13.7563",
  "msg_type": "interval",
  "longitude": "100.5018",
  "gateway_id": "99999",  // Unique ID for tracing
  "humidity": "70.00",
  "heat_index": "39.00",
  "temperature": "33.00"
};

async function traceFlow() {
  console.log('TRACING MOISTURE DATA FLOW');
  console.log('==========================\n');
  
  try {
    // Get initial count
    const before = await pool.query(`
      SELECT COUNT(*) as count 
      FROM sensor_readings 
      WHERE sensor_id LIKE '%99999%'
    `);
    
    console.log('1. Initial state:');
    console.log(`   sensor_readings with "99999": ${before.rows[0].count}\n`);
    
    // Send test data
    console.log('2. Sending test data to CloudFlare endpoint...');
    const response = await axios.post(
      'http://localhost:3003/api/v1/munbon-m2m-moisture/telemetry',
      testData,
      { headers: { 'Content-Type': 'application/json' } }
    );
    
    console.log(`   Response: ${response.status} ${response.statusText}\n`);
    
    // Wait and check multiple times
    for (let i = 1; i <= 3; i++) {
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      const check = await pool.query(`
        SELECT 
          sensor_id,
          sensor_type,
          time,
          value->>'gateway_id' as gw_id,
          jsonb_array_length(value->'sensor') as sensor_count
        FROM sensor_readings 
        WHERE sensor_id LIKE '%99999%'
        ORDER BY time DESC
      `);
      
      console.log(`3. After ${i} second(s):`);
      console.log(`   Total entries: ${check.rows.length}`);
      
      check.rows.forEach((row, idx) => {
        console.log(`   ${idx + 1}. ${row.sensor_id} at ${new Date(row.time).toLocaleTimeString()}`);
        console.log(`      Gateway ID in data: ${row.gw_id}`);
        console.log(`      Sensor array length: ${row.sensor_count || 'N/A'}`);
      });
      
      // Also check moisture_readings
      const moisture = await pool.query(`
        SELECT sensor_id, COUNT(*) as count
        FROM moisture_readings 
        WHERE sensor_id LIKE '%99999%'
        GROUP BY sensor_id
      `);
      
      console.log(`   moisture_readings:`);
      if (moisture.rows.length === 0) {
        console.log('      None yet');
      } else {
        moisture.rows.forEach(row => {
          console.log(`      ${row.sensor_id}: ${row.count} entries`);
        });
      }
      console.log('');
    }
    
    // Final analysis
    console.log('4. ANALYSIS:');
    console.log('   If we see multiple sensor_readings entries, the endpoint is being called multiple times');
    console.log('   If we see "99999-undefined", the old code path is still executing');
    console.log('   Expected: Only MS-99999-00001 in moisture_readings, no undefined entries');
    
    await pool.end();
    
  } catch (error) {
    console.error('Error:', error.response?.data || error.message);
    await pool.end();
  }
}

traceFlow();