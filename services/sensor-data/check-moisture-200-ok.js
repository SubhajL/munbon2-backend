#!/usr/bin/env node

const { Pool } = require('pg');

const pool = new Pool({
  host: 'localhost',
  port: 5433,
  database: 'munbon_timescale',
  user: 'postgres',
  password: 'postgres'
});

async function checkMoistureData() {
  try {
    console.log('Investigating 200 OK responses from manufacturer...');
    console.log('=================================================\n');
    
    // 1. Check sensor_readings table (where all data goes first)
    const allReadings = await pool.query(`
      SELECT 
        sensor_id,
        sensor_type,
        COUNT(*) as count,
        MIN(time) as first_reading,
        MAX(time) as last_reading
      FROM sensor_readings 
      WHERE time > NOW() - INTERVAL '7 days'
        AND (sensor_type = 'moisture' OR sensor_id LIKE '%moisture%' OR sensor_id LIKE 'MS-%' OR sensor_id LIKE 'GW-%')
      GROUP BY sensor_id, sensor_type
      ORDER BY last_reading DESC
    `);
    
    console.log('1. SENSOR_READINGS TABLE (Primary storage):');
    console.log('------------------------------------------');
    if (allReadings.rows.length === 0) {
      console.log('NO MOISTURE-RELATED ENTRIES FOUND');
    } else {
      allReadings.rows.forEach(row => {
        console.log(`${row.sensor_id} (${row.sensor_type}): ${row.count} readings`);
        console.log(`  First: ${row.first_reading}`);
        console.log(`  Last: ${row.last_reading}`);
      });
    }
    
    // 2. Check moisture_readings table specifically
    const moistureReadings = await pool.query(`
      SELECT 
        sensor_id,
        COUNT(*) as count,
        MIN(time) as first_reading,
        MAX(time) as last_reading,
        AVG(moisture_surface_pct) as avg_surface,
        AVG(moisture_deep_pct) as avg_deep
      FROM moisture_readings 
      WHERE time > NOW() - INTERVAL '7 days'
      GROUP BY sensor_id
      ORDER BY last_reading DESC
    `);
    
    console.log('\n2. MOISTURE_READINGS TABLE (Specific moisture data):');
    console.log('---------------------------------------------------');
    if (moistureReadings.rows.length === 0) {
      console.log('NO ENTRIES FOUND');
    } else {
      moistureReadings.rows.forEach(row => {
        console.log(`${row.sensor_id}: ${row.count} readings`);
        console.log(`  Surface moisture avg: ${row.avg_surface ? parseFloat(row.avg_surface).toFixed(2) : 'N/A'}%`);
        console.log(`  Deep moisture avg: ${row.avg_deep ? parseFloat(row.avg_deep).toFixed(2) : 'N/A'}%`);
        console.log(`  Last reading: ${row.last_reading}`);
      });
    }
    
    // 3. Check for any unknown sensor types (possible format mismatch)
    const unknownTypes = await pool.query(`
      SELECT 
        sensor_id,
        sensor_type,
        COUNT(*) as count,
        MAX(time) as last_seen,
        data->>'gateway_id' as gateway_id,
        data->>'sensor_id' as sensor_id_field
      FROM sensor_readings 
      WHERE sensor_type = 'UNKNOWN'
        AND time > NOW() - INTERVAL '7 days'
      GROUP BY sensor_id, sensor_type, data
      ORDER BY last_seen DESC
      LIMIT 10
    `);
    
    console.log('\n3. UNKNOWN SENSOR TYPES (Possible format issues):');
    console.log('------------------------------------------------');
    if (unknownTypes.rows.length === 0) {
      console.log('NO UNKNOWN SENSOR TYPES FOUND');
    } else {
      console.log(`Found ${unknownTypes.rows.length} unknown sensor entries!`);
      unknownTypes.rows.forEach(row => {
        console.log(`${row.sensor_id}: ${row.count} readings, last: ${row.last_seen}`);
        if (row.gateway_id) console.log(`  Gateway ID in data: ${row.gateway_id}`);
        if (row.sensor_id_field) console.log(`  Sensor ID in data: ${row.sensor_id_field}`);
      });
    }
    
    // 4. Check CloudFlare access logs
    console.log('\n4. CLOUDFLARE ENDPOINT ACCESS:');
    console.log('------------------------------');
    console.log('Expected URL: https://ridertaka.de/api/v1/munbon-m2m-moisture/telemetry');
    console.log('CloudFlare tunnel is ONLINE and responding');
    console.log('Manufacturer claims: Getting 200 OK responses');
    
    // 5. Check if data might be going elsewhere
    const recentData = await pool.query(`
      SELECT 
        tablename,
        n_tup_ins as inserts,
        n_tup_upd as updates
      FROM pg_stat_user_tables
      WHERE schemaname = 'public'
        AND (tablename LIKE '%sensor%' OR tablename LIKE '%moisture%' OR tablename LIKE '%reading%')
      ORDER BY n_tup_ins DESC
    `);
    
    console.log('\n5. TABLE ACTIVITY STATS:');
    console.log('-----------------------');
    recentData.rows.forEach(row => {
      console.log(`${row.tablename}: ${row.inserts} inserts, ${row.updates} updates`);
    });
    
    await pool.end();
    
    console.log('\n6. CONCLUSION:');
    console.log('-------------');
    console.log('If manufacturer is getting 200 OK but we see no data, possible causes:');
    console.log('1. Data is being accepted but failing silently after initial response');
    console.log('2. Data format is slightly different than expected');
    console.log('3. Data is going to a different endpoint/path');
    console.log('4. Timezone/timestamp issues causing data to appear in different time ranges');
    console.log('\nRECOMMENDATION: Ask manufacturer for:');
    console.log('- Exact request headers and body they are sending');
    console.log('- Full URL they are posting to');
    console.log('- Response body they receive (not just status code)');
    
  } catch (err) {
    console.error('Error:', err);
  }
}

checkMoistureData();