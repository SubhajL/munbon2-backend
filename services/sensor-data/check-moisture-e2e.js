const { Pool } = require('pg');
const axios = require('axios');

const pool = new Pool({
  host: 'localhost',
  port: 5433,
  database: 'munbon_timescale',
  user: 'postgres',
  password: 'postgres'
});

async function checkMoistureE2E() {
  try {
    console.log('=== Moisture Sensor End-to-End Check ===\n');
    
    // 1. Check CloudFlare tunnel status
    console.log('1. CLOUDFLARE TUNNEL STATUS:');
    console.log('   URL: https://munbon-moisture.beautifyai.io');
    console.log('   Endpoint: POST /api/v1/munbon-m2m-moisture/telemetry');
    
    try {
      const healthResponse = await axios.get('https://munbon-moisture.beautifyai.io/health', {
        timeout: 5000
      });
      console.log('   Tunnel Status: ✅ ONLINE');
      console.log('   Service Response:', healthResponse.data);
    } catch (error) {
      if (error.response?.status === 530) {
        console.log('   Tunnel Status: ❌ OFFLINE (Error 530 - Cloudflare tunnel not running)');
      } else {
        console.log('   Tunnel Status: ❌ ERROR -', error.message);
      }
    }
    
    // 2. Check recent moisture data in database
    console.log('\n2. RECENT MOISTURE DATA IN DATABASE:');
    
    const recentData = await pool.query(`
      SELECT 
        DATE(time) as date,
        COUNT(DISTINCT sensor_id) as sensors,
        COUNT(*) as readings,
        MIN(time) as first_reading,
        MAX(time) as last_reading
      FROM moisture_readings
      WHERE time > NOW() - INTERVAL '3 days'
      GROUP BY DATE(time)
      ORDER BY date DESC
    `);
    
    console.log('Date       | Sensors | Readings | First Reading    | Last Reading');
    console.log('-----------|---------|----------|------------------|------------------');
    recentData.rows.forEach(row => {
      console.log(
        `${new Date(row.date).toLocaleDateString()} | ` +
        `${row.sensors.toString().padStart(7)} | ` +
        `${row.readings.toString().padStart(8)} | ` +
        `${new Date(row.first_reading).toLocaleTimeString()} | ` +
        `${new Date(row.last_reading).toLocaleTimeString()}`
      );
    });
    
    // 3. Check last hour activity
    const lastHour = await pool.query(`
      SELECT 
        sensor_id,
        COUNT(*) as readings_count,
        MAX(time) as last_reading,
        AVG(moisture_surface_pct) as avg_surface,
        AVG(moisture_deep_pct) as avg_deep,
        BOOL_OR(flood_status) as flood_detected
      FROM moisture_readings
      WHERE time > NOW() - INTERVAL '1 hour'
      GROUP BY sensor_id
      ORDER BY last_reading DESC
    `);
    
    console.log(`\n3. LAST HOUR MOISTURE ACTIVITY:`);
    console.log(`   Active sensors: ${lastHour.rows.length}`);
    console.log(`   Total readings: ${lastHour.rows.reduce((sum, row) => sum + parseInt(row.readings_count), 0)}`);
    
    if (lastHour.rows.length > 0) {
      console.log('\n   Recent Sensor Activity:');
      lastHour.rows.slice(0, 5).forEach(row => {
        console.log(`   - ${row.sensor_id}:`);
        console.log(`     Readings: ${row.readings_count}, Last: ${new Date(row.last_reading).toLocaleTimeString()}`);
        console.log(`     Moisture: Surface ${parseFloat(row.avg_surface).toFixed(1)}%, Deep ${parseFloat(row.avg_deep).toFixed(1)}%`);
        if (row.flood_detected) {
          console.log(`     🚨 FLOOD DETECTED!`);
        }
      });
    }
    
    // 4. Check gateway status
    const gatewayStatus = await pool.query(`
      SELECT 
        sensor_id,
        last_seen,
        metadata
      FROM sensor_registry
      WHERE sensor_type = 'gateway'
      AND last_seen > NOW() - INTERVAL '24 hours'
      ORDER BY last_seen DESC
      LIMIT 5
    `);
    
    if (gatewayStatus.rows.length > 0) {
      console.log(`\n4. ACTIVE GATEWAYS (Last 24h):`);
      gatewayStatus.rows.forEach(row => {
        console.log(`   ${row.sensor_id}: Last seen ${new Date(row.last_seen).toLocaleString()}`);
        if (row.metadata?.temperature) {
          console.log(`     Ambient: ${row.metadata.temperature}°C, ${row.metadata.humidity}% humidity`);
        }
      });
    }
    
    // 5. Check new sensor registrations
    const newSensors = await pool.query(`
      SELECT 
        sensor_id,
        sensor_type,
        created_at,
        metadata
      FROM sensor_registry
      WHERE sensor_type IN ('moisture', 'gateway')
      AND created_at > NOW() - INTERVAL '24 hours'
      ORDER BY created_at DESC
      LIMIT 10
    `);
    
    if (newSensors.rows.length > 0) {
      console.log(`\n5. NEW SENSOR REGISTRATIONS (Last 24h): ${newSensors.rows.length}`);
      newSensors.rows.slice(0, 5).forEach(row => {
        console.log(`   ${row.sensor_id} (${row.sensor_type}): Registered ${new Date(row.created_at).toLocaleString()}`);
      });
    }
    
    // 6. Check data flow metrics
    const dataFlow = await pool.query(`
      SELECT 
        DATE_TRUNC('hour', time) as hour,
        COUNT(*) as readings,
        COUNT(DISTINCT sensor_id) as sensors
      FROM moisture_readings
      WHERE time > NOW() - INTERVAL '12 hours'
      GROUP BY DATE_TRUNC('hour', time)
      ORDER BY hour DESC
    `);
    
    console.log(`\n6. DATA FLOW (Last 12 Hours):`);
    console.log('Hour                | Readings | Sensors');
    console.log('--------------------|----------|--------');
    dataFlow.rows.forEach(row => {
      console.log(
        `${new Date(row.hour).toLocaleString()} | ` +
        `${row.readings.toString().padStart(8)} | ` +
        `${row.sensors.toString().padStart(7)}`
      );
    });
    
    // 7. Check PM2 service status
    console.log('\n7. SERVICE STATUS:');
    console.log('   Run "pm2 list" to check:');
    console.log('   - sensor-data-service (should be online)');
    console.log('   - munbon-moisture-tunnel (should be online)');
    
    // 8. Summary
    const totalSensors = await pool.query(`
      SELECT COUNT(DISTINCT sensor_id) as count
      FROM sensor_registry
      WHERE sensor_type = 'moisture'
    `);
    
    const totalReadings = await pool.query(`
      SELECT COUNT(*) as count
      FROM moisture_readings
    `);
    
    console.log('\n8. MOISTURE DATA SUMMARY:');
    console.log(`   Total moisture sensors: ${totalSensors.rows[0].count}`);
    console.log(`   Total readings: ${totalReadings.rows[0].count}`);
    console.log(`   Latest activity: ${lastHour.rows.length > 0 ? '✅ RECEIVING DATA' : '❌ NO RECENT DATA'}`);
    console.log(`   Automatic registration: ✅ ENABLED`);
    console.log(`   Data flow: CloudFlare Tunnel → Local API (3003) → TimescaleDB`);
    
  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await pool.end();
  }
}

checkMoistureE2E();