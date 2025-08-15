const { Pool } = require('pg');

const pool = new Pool({
  host: 'localhost',
  port: 5433,
  database: 'munbon_timescale',
  user: 'postgres',
  password: 'postgres'
});

async function monitorMoistureRequests() {
  console.log('=== Monitoring Moisture Sensor Requests ===\n');
  console.log('CloudFlare URL: https://munbon-moisture.beautifyai.io');
  console.log('Local endpoint: http://localhost:3003/api/v1/munbon-m2m-moisture/telemetry\n');
  
  let lastReadingTime = null;
  let readingCount = 0;
  
  // Get initial count
  const initialCount = await pool.query(`
    SELECT 
      COUNT(*) as total,
      MAX(time) as last_time
    FROM moisture_readings
  `);
  
  lastReadingTime = initialCount.rows[0].last_time;
  readingCount = parseInt(initialCount.rows[0].total);
  
  console.log(`Starting monitor...`);
  console.log(`Initial readings: ${readingCount}`);
  console.log(`Last reading: ${lastReadingTime ? new Date(lastReadingTime).toLocaleString() : 'None'}\n`);
  console.log('Watching for new moisture data...\n');
  
  // Check every 5 seconds
  setInterval(async () => {
    try {
      // Check for new readings
      const newData = await pool.query(`
        SELECT 
          sensor_id,
          time,
          moisture_surface_pct,
          moisture_deep_pct,
          flood_status,
          location_lat,
          location_lng
        FROM moisture_readings
        WHERE time > $1
        ORDER BY time DESC
      `, [lastReadingTime || new Date(0)]);
      
      if (newData.rows.length > 0) {
        console.log(`\n🆕 NEW MOISTURE DATA RECEIVED! (${new Date().toLocaleTimeString()})`);
        console.log('=' .repeat(50));
        
        newData.rows.forEach(reading => {
          console.log(`Sensor: ${reading.sensor_id}`);
          console.log(`Time: ${new Date(reading.time).toLocaleString()}`);
          console.log(`Surface: ${reading.moisture_surface_pct}%, Deep: ${reading.moisture_deep_pct}%`);
          console.log(`Location: ${reading.location_lat}, ${reading.location_lng}`);
          console.log(`Flood: ${reading.flood_status ? '🚨 YES' : 'No'}`);
          console.log('-'.repeat(30));
        });
        
        readingCount += newData.rows.length;
        lastReadingTime = newData.rows[0].time;
        
        // Check if gateway was also updated
        const gatewayUpdate = await pool.query(`
          SELECT sensor_id, last_seen, metadata
          FROM sensor_registry
          WHERE sensor_type = 'gateway'
          AND last_seen > NOW() - INTERVAL '1 minute'
          ORDER BY last_seen DESC
          LIMIT 1
        `);
        
        if (gatewayUpdate.rows.length > 0) {
          const gw = gatewayUpdate.rows[0];
          console.log(`\nGateway Update: ${gw.sensor_id}`);
          if (gw.metadata?.temperature) {
            console.log(`Ambient: ${gw.metadata.temperature}°C, ${gw.metadata.humidity}% humidity`);
          }
        }
        
        console.log(`\nTotal readings: ${readingCount}`);
        console.log('=' .repeat(50) + '\n');
      } else {
        process.stdout.write('.');
      }
    } catch (error) {
      console.error('\nError checking database:', error.message);
    }
  }, 5000);
  
  // Check CloudFlare tunnel health every 30 seconds
  setInterval(async () => {
    try {
      const axios = require('axios');
      const response = await axios.get('https://munbon-moisture.beautifyai.io/health', {
        timeout: 5000
      });
      // Tunnel is healthy, no need to log unless there's an issue
    } catch (error) {
      console.error('\n⚠️  CloudFlare tunnel issue:', error.message);
    }
  }, 30000);
  
  console.log('Press Ctrl+C to stop monitoring\n');
}

// Handle graceful shutdown
process.on('SIGINT', async () => {
  console.log('\n\nStopping monitor...');
  await pool.end();
  process.exit(0);
});

monitorMoistureRequests();