const AWS = require('aws-sdk');
const sqs = new AWS.SQS({ region: 'ap-southeast-1' });

async function checkAllSensors() {
  const queueUrl = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';
  
  // Map of MAC addresses to sensor names
  const sensorMap = {
    '16186C1FB75A': 'AWD-B75A',
    '16186C1FB6B5': 'AWD-B6B5',
    '16186C1FB8A4': 'AWD-B8A4',
    '16186C1FB33B': 'AWD-B33B',
    '16186C1FB7E6': 'AWD-B7E6',
    '16186C1FB9BE': 'AWD-B9BE'
  };
  
  const foundData = {};
  Object.keys(sensorMap).forEach(mac => {
    foundData[mac] = [];
  });
  
  let processedCount = 0;
  let batchCount = 0;
  
  console.log('Searching for 6 water level sensors...\n');
  
  // Process more messages to find all sensors
  while (batchCount < 50) { // Check up to 500 messages
    try {
      const result = await sqs.receiveMessage({
        QueueUrl: queueUrl,
        MaxNumberOfMessages: 10,
        VisibilityTimeout: 0,
        WaitTimeSeconds: 0
      }).promise();
      
      if (!result.Messages || result.Messages.length === 0) {
        console.log(`No messages in batch ${batchCount + 1}`);
        break;
      }
      
      for (const message of result.Messages) {
        processedCount++;
        try {
          const body = JSON.parse(message.Body);
          
          if (body.data && body.data.macAddress) {
            const macUpper = body.data.macAddress.toUpperCase();
            
            if (sensorMap[macUpper]) {
              foundData[macUpper].push({
                sensorName: sensorMap[macUpper],
                deviceId: body.sensorId || body.data.deviceId,
                macAddress: body.data.macAddress,
                location: body.location || {lat: body.data.latitude, lng: body.data.longitude},
                level: body.data.level,
                voltage: body.data.voltage,
                rssi: body.data.RSSI,
                timestamp: body.timestamp || body.data.timestamp,
                sourceIp: body.sourceIp
              });
            }
          }
        } catch (parseError) {
          console.error('Error parsing message:', parseError.message);
        }
      }
      
      batchCount++;
      
      // Check if we found all sensors
      const foundCount = Object.values(foundData).filter(arr => arr.length > 0).length;
      if (foundCount === 6) {
        console.log('Found all 6 sensors! Stopping search.\n');
        break;
      }
    } catch (error) {
      console.error('Error in batch', batchCount + 1, ':', error.message);
      break;
    }
  }
  
  console.log('=== SENSOR STATUS REPORT ===');
  console.log(`Messages checked: ${processedCount}`);
  console.log(`Batches processed: ${batchCount}\n`);
  
  // Sort sensors by name for consistent output
  const sortedMacs = Object.keys(sensorMap).sort((a, b) => sensorMap[a].localeCompare(sensorMap[b]));
  
  sortedMacs.forEach(mac => {
    const sensorName = sensorMap[mac];
    const readings = foundData[mac];
    
    console.log(`\n${sensorName} (MAC: ${mac}):`);
    
    if (readings.length > 0) {
      // Sort by timestamp to get latest
      readings.sort((a, b) => {
        const timeA = new Date(a.timestamp).getTime();
        const timeB = new Date(b.timestamp).getTime();
        return timeB - timeA;
      });
      
      const latest = readings[0];
      const latestDate = new Date(latest.timestamp);
      
      console.log(`  ✅ FOUND - ${readings.length} messages in queue`);
      console.log(`  Latest Reading:`);
      console.log(`    Timestamp: ${latestDate.toISOString()} (${latestDate.toLocaleString('en-US', {timeZone: 'Asia/Bangkok'})} Bangkok)`);
      console.log(`    Device ID: ${latest.deviceId}`);
      console.log(`    Level: ${latest.level} cm`);
      console.log(`    Voltage: ${(latest.voltage / 100).toFixed(2)} V`);
      console.log(`    RSSI: ${latest.rssi} dBm`);
      console.log(`    Location: ${latest.location.lat}, ${latest.location.lng}`);
      console.log(`    Source IP: ${latest.sourceIp}`);
      
      // Show message distribution over time
      const hourAgo = Date.now() - (60 * 60 * 1000);
      const dayAgo = Date.now() - (24 * 60 * 60 * 1000);
      const recentHour = readings.filter(r => new Date(r.timestamp).getTime() > hourAgo).length;
      const recentDay = readings.filter(r => new Date(r.timestamp).getTime() > dayAgo).length;
      
      console.log(`    Messages: ${recentHour} in last hour, ${recentDay} in last 24h`);
    } else {
      console.log('  ❌ NOT FOUND in checked messages');
    }
  });
  
  // Summary
  const foundSensors = Object.values(foundData).filter(arr => arr.length > 0).length;
  console.log(`\n=== SUMMARY ===`);
  console.log(`Found ${foundSensors} of 6 sensors in SQS queue`);
  
  // Now check the database for comparison
  console.log('\n=== CHECKING DATABASE ===');
  const { Client } = require('pg');
  const client = new Client({
    host: 'localhost',
    port: 5433,
    database: 'munbon_timescale',
    user: 'postgres',
    password: 'postgres'
  });
  
  try {
    await client.connect();
    
    for (const mac of sortedMacs) {
      const sensorName = sensorMap[mac];
      
      // Query for this sensor's data
      const query = `
        SELECT sr.sensor_id, sr.last_seen, 
               COUNT(wlr.*) as total_readings,
               MAX(wlr.time) as latest_reading,
               MAX(wlr.level_cm) as latest_level
        FROM sensor_registry sr
        LEFT JOIN water_level_readings wlr ON sr.sensor_id = wlr.sensor_id
        WHERE sr.sensor_id = $1 OR sr.metadata::text LIKE $2
        GROUP BY sr.sensor_id, sr.last_seen
        ORDER BY sr.last_seen DESC
        LIMIT 1;
      `;
      
      const result = await client.query(query, [sensorName, `%${mac}%`]);
      
      if (result.rows.length > 0) {
        const row = result.rows[0];
        console.log(`\n${sensorName} in Database:`);
        console.log(`  Sensor ID: ${row.sensor_id}`);
        console.log(`  Total Readings: ${row.total_readings}`);
        if (row.latest_reading) {
          const dbDate = new Date(row.latest_reading);
          console.log(`  Latest DB Reading: ${dbDate.toISOString()} (${dbDate.toLocaleString('en-US', {timeZone: 'Asia/Bangkok'})} Bangkok)`);
        } else {
          console.log(`  Latest DB Reading: No readings yet`);
        }
      }
    }
    
    await client.end();
  } catch (dbError) {
    console.error('Database error:', dbError.message);
  }
}

checkAllSensors().catch(console.error);