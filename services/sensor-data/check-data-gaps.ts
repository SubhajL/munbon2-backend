import { Client } from 'pg';

async function checkDataGaps() {
  const localClient = new Client({
    host: 'localhost',
    port: 5433,
    database: 'munbon_timescale',
    user: 'postgres',
    password: 'postgres'
  });

  const ec2Client = new Client({
    host: '43.209.22.250',
    port: 5432,
    database: 'sensor_data',
    user: 'postgres',
    password: 'P@ssw0rd123!'
  });

  try {
    await localClient.connect();
    await ec2Client.connect();

    console.log('🔍 Checking data gaps...\n');

    // Check water level data - using 'time' column for local, 'timestamp' for EC2
    const waterLevelQueryLocal = `
      SELECT 
        date_trunc('hour', time) as hour,
        COUNT(*) as records,
        MAX(time) as latest,
        MIN(time) as earliest
      FROM water_level_readings
      WHERE time > NOW() - INTERVAL '24 hours'
      GROUP BY hour
      ORDER BY hour DESC
      LIMIT 20
    `;

    const waterLevelQueryEC2 = `
      SELECT 
        date_trunc('hour', timestamp) as hour,
        COUNT(*) as records,
        MAX(timestamp) as latest,
        MIN(timestamp) as earliest
      FROM water_level_readings
      WHERE timestamp > NOW() - INTERVAL '24 hours'
      GROUP BY hour
      ORDER BY hour DESC
      LIMIT 20
    `;

    console.log('📊 Water Level Data (Last 24 hours):');
    console.log('Local Database:');
    const localWater = await localClient.query(waterLevelQueryLocal);
    localWater.rows.forEach(row => {
      console.log(`  ${row.hour.toISOString()} - ${row.records} records`);
    });

    console.log('\nEC2 Database:');
    const ec2Water = await ec2Client.query(waterLevelQueryEC2);
    ec2Water.rows.forEach(row => {
      console.log(`  ${row.hour.toISOString()} - ${row.records} records`);
    });

    // Check moisture data - same pattern
    const moistureQueryLocal = `
      SELECT 
        date_trunc('hour', time) as hour,
        COUNT(*) as records,
        MAX(time) as latest,
        MIN(time) as earliest
      FROM moisture_readings
      WHERE time > NOW() - INTERVAL '24 hours'
      GROUP BY hour
      ORDER BY hour DESC
      LIMIT 20
    `;

    const moistureQueryEC2 = `
      SELECT 
        date_trunc('hour', timestamp) as hour,
        COUNT(*) as records,
        MAX(timestamp) as latest,
        MIN(timestamp) as earliest
      FROM moisture_readings
      WHERE timestamp > NOW() - INTERVAL '24 hours'
      GROUP BY hour
      ORDER BY hour DESC
      LIMIT 20
    `;

    console.log('\n📊 Moisture Data (Last 24 hours):');
    console.log('Local Database:');
    const localMoisture = await localClient.query(moistureQueryLocal);
    localMoisture.rows.forEach(row => {
      console.log(`  ${row.hour.toISOString()} - ${row.records} records`);
    });

    console.log('\nEC2 Database:');
    const ec2Moisture = await ec2Client.query(moistureQueryEC2);
    ec2Moisture.rows.forEach(row => {
      console.log(`  ${row.hour.toISOString()} - ${row.records} records`);
    });

    // Check for any errors in recent data
    console.log('\n🔍 Checking recent sensor_data entries:');
    const recentDataQueryLocal = `
      SELECT 
        time as timestamp,
        sensor_id,
        reading_type,
        raw_data::text
      FROM sensor_data
      ORDER BY time DESC
      LIMIT 10
    `;

    const localRecent = await localClient.query(recentDataQueryLocal);
    console.log('\nLocal - Last 10 sensor_data entries:');
    localRecent.rows.forEach(row => {
      const dataTimestamp = row.raw_data ? JSON.parse(row.raw_data).timestamp : 'N/A';
      console.log(`  ${row.timestamp.toISOString()} - ${row.sensor_id} - ${row.reading_type} (data timestamp: ${dataTimestamp})`);
    });

    // Check last successful write times
    const lastWriteQueryLocal = `
      SELECT 
        'water_level' as type,
        MAX(time) as last_write
      FROM water_level_readings
      UNION ALL
      SELECT 
        'moisture' as type,
        MAX(time) as last_write
      FROM moisture_readings
      UNION ALL
      SELECT 
        'sensor_data' as type,
        MAX(time) as last_write
      FROM sensor_data
    `;

    const lastWriteQueryEC2 = `
      SELECT 
        'water_level' as type,
        MAX(timestamp) as last_write
      FROM water_level_readings
      UNION ALL
      SELECT 
        'moisture' as type,
        MAX(timestamp) as last_write
      FROM moisture_readings
      UNION ALL
      SELECT 
        'sensor_data' as type,
        MAX(created_at) as last_write
      FROM sensor_data
    `;

    console.log('\n\n🕐 Last successful writes:');
    console.log('\nLocal Database:');
    const localLastWrites = await localClient.query(lastWriteQueryLocal);
    localLastWrites.rows.forEach(row => {
      const hoursAgo = (Date.now() - row.last_write.getTime()) / (1000 * 60 * 60);
      console.log(`  ${row.type}: ${row.last_write.toISOString()} (${hoursAgo.toFixed(1)} hours ago)`);
    });

    console.log('\nEC2 Database:');
    const ec2LastWrites = await ec2Client.query(lastWriteQueryEC2);
    ec2LastWrites.rows.forEach(row => {
      const hoursAgo = (Date.now() - row.last_write.getTime()) / (1000 * 60 * 60);
      console.log(`  ${row.type}: ${row.last_write.toISOString()} (${hoursAgo.toFixed(1)} hours ago)`);
    });

    // Now check if sensor data is arriving but not being processed
    console.log('\n\n🔍 Checking if sensor data is arriving in raw sensor_data table:');
    const rawDataCheckLocal = `
      SELECT 
        date_trunc('hour', time) as hour,
        COUNT(*) as total_records,
        COUNT(CASE WHEN reading_type = 'water_level' THEN 1 END) as water_level_records,
        COUNT(CASE WHEN reading_type = 'moisture' THEN 1 END) as moisture_records
      FROM sensor_data
      WHERE time > NOW() - INTERVAL '12 hours'
      GROUP BY hour
      ORDER BY hour DESC
    `;

    const localRawData = await localClient.query(rawDataCheckLocal);
    console.log('\nLocal - Raw sensor_data by hour:');
    localRawData.rows.forEach(row => {
      console.log(`  ${row.hour.toISOString()} - Total: ${row.total_records}, Water: ${row.water_level_records}, Moisture: ${row.moisture_records}`);
    });

  } catch (error) {
    console.error('Error:', error);
  } finally {
    await localClient.end();
    await ec2Client.end();
  }
}

checkDataGaps();