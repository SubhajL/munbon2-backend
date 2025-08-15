const { Client } = require('pg');

// Database configuration
const pgClient = new Client({
  host: 'localhost',
  port: 5433,
  database: 'munbon_timescale',
  user: 'postgres',
  password: 'postgres'
});

async function checkSensorTimestamps() {
  try {
    await pgClient.connect();
    console.log('Connected to TimescaleDB\n');
    
    // Define the sensors to check
    const sensors = [
      { awdId: 'AWD-6CA3', deviceId: '22166174123108163' },
      { awdId: 'AWD-9304', deviceId: '2216617412314704' },
      { awdId: 'AWD-8748', deviceId: '2216617412313572' }
    ];
    
    for (const sensor of sensors) {
      console.log(`=== ${sensor.awdId} (${sensor.deviceId}) ===`);
      
      // Check for both AWD and device ID formats
      const query = `
        SELECT 
          sensor_id,
          MIN(time) as first_record,
          MAX(time) as last_record,
          COUNT(*) as total_records,
          MIN(level_cm) as min_level,
          MAX(level_cm) as max_level,
          AVG(level_cm) as avg_level
        FROM water_level_readings
        WHERE sensor_id IN ($1, $2)
        GROUP BY sensor_id
        ORDER BY sensor_id
      `;
      
      const result = await pgClient.query(query, [sensor.awdId, sensor.deviceId]);
      
      if (result.rows.length === 0) {
        console.log('No records found in database\n');
      } else {
        for (const row of result.rows) {
          console.log(`Sensor ID: ${row.sensor_id}`);
          console.log(`Total records: ${row.total_records}`);
          console.log(`First record: ${row.first_record ? new Date(row.first_record).toISOString() : 'N/A'}`);
          console.log(`Last record: ${row.last_record ? new Date(row.last_record).toISOString() : 'N/A'}`);
          
          if (row.first_record && row.last_record) {
            const duration = new Date(row.last_record) - new Date(row.first_record);
            const hours = Math.floor(duration / (1000 * 60 * 60));
            const minutes = Math.floor((duration % (1000 * 60 * 60)) / (1000 * 60));
            console.log(`Time span: ${hours} hours, ${minutes} minutes`);
          }
          
          console.log(`Water level range: ${row.min_level} - ${row.max_level} cm (avg: ${parseFloat(row.avg_level).toFixed(2)} cm)`);
          console.log();
        }
      }
    }
    
    // Also check if there are any recent records (last hour)
    console.log('=== Recent Activity (Last Hour) ===');
    const recentQuery = `
      SELECT 
        sensor_id,
        COUNT(*) as recent_records,
        MAX(time) as latest_time,
        MAX(level_cm) as latest_level
      FROM water_level_readings
      WHERE sensor_id IN ($1, $2, $3, $4, $5, $6)
        AND time > NOW() - INTERVAL '1 hour'
      GROUP BY sensor_id
      ORDER BY latest_time DESC
    `;
    
    const recentResult = await pgClient.query(recentQuery, [
      'AWD-6CA3', '22166174123108163',
      'AWD-9304', '2216617412314704', 
      'AWD-8748', '2216617412313572'
    ]);
    
    if (recentResult.rows.length === 0) {
      console.log('No recent activity in the last hour');
    } else {
      for (const row of recentResult.rows) {
        const minutesAgo = Math.floor((new Date() - new Date(row.latest_time)) / (1000 * 60));
        console.log(`${row.sensor_id}: ${row.recent_records} records, latest ${minutesAgo} minutes ago (Level: ${row.latest_level} cm)`);
      }
    }
    
  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await pgClient.end();
  }
}

checkSensorTimestamps().catch(console.error);