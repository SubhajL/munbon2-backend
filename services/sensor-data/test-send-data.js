const https = require('https');

// API Endpoints
const WATER_LEVEL_URL = 'https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridr-water-level/telemetry';
const MOISTURE_URL = 'https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-m2m-moisture/telemetry';

// Generate random water level data (RID-R format)
function generateWaterLevelData(index) {
  const baseTime = Date.now() - (10 - index) * 60000; // Spread over 10 minutes
  return {
    deviceID: `7b184f4f-3d97-4c0c-a888-55b839aab7a${index.toString().padStart(2, '0')}`,
    macAddress: `1A2B3C4D5E${index.toString(16).toUpperCase().padStart(2, '0')}`,
    latitude: 13.7563 + (Math.random() - 0.5) * 0.01,
    longitude: 100.5018 + (Math.random() - 0.5) * 0.01,
    RSSI: -60 - Math.floor(Math.random() * 30),
    voltage: 380 + Math.floor(Math.random() * 40),
    level: 5 + Math.floor(Math.random() * 20), // Water level 5-25 cm
    timestamp: baseTime
  };
}

// Generate random moisture data (M2M format)
function generateMoistureData(index) {
  const now = new Date(Date.now() - (10 - index) * 60000);
  const dateStr = now.toISOString().split('T')[0].replace(/-/g, '/');
  const timeStr = now.toTimeString().split(' ')[0];
  
  return {
    gateway_id: `0000${index}`.slice(-5),
    msg_type: "interval",
    date: dateStr,
    time: timeStr,
    latitude: (13.7563 + (Math.random() - 0.5) * 0.01).toFixed(5),
    longitude: (100.5018 + (Math.random() - 0.5) * 0.01).toFixed(5),
    gw_batt: (350 + Math.floor(Math.random() * 50)).toString(),
    sensor: [{
      sensor_id: `0000${index}`.slice(-5),
      flood: Math.random() > 0.9 ? "yes" : "no",
      amb_humid: (50 + Math.floor(Math.random() * 30)).toString(),
      amb_temp: (25 + Math.random() * 10).toFixed(2),
      humid_hi: (20 + Math.floor(Math.random() * 60)).toString(), // Top soil moisture
      temp_hi: (25 + Math.random() * 5).toFixed(2),
      humid_low: (30 + Math.floor(Math.random() * 50)).toString(), // Bottom soil moisture
      temp_low: (24 + Math.random() * 4).toFixed(2),
      sensor_batt: (380 + Math.floor(Math.random() * 20)).toString()
    }]
  };
}

// Send data to API
function sendData(url, data, type) {
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url);
    const postData = JSON.stringify(data);
    
    const options = {
      hostname: urlObj.hostname,
      port: 443,
      path: urlObj.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData)
      }
    };
    
    const req = https.request(options, (res) => {
      let body = '';
      res.on('data', (chunk) => body += chunk);
      res.on('end', () => {
        resolve({
          statusCode: res.statusCode,
          body: body,
          type: type,
          data: data
        });
      });
    });
    
    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

// Main execution
async function main() {
  console.log('=== Sending Test Data to AWS API ===\n');
  
  // Send water level data
  console.log('1. Sending 10 Water Level readings...');
  const waterLevelPromises = [];
  for (let i = 1; i <= 10; i++) {
    const data = generateWaterLevelData(i);
    console.log(`   - Water Level ${i}: Device ${data.deviceID}, Level: ${data.level} cm`);
    waterLevelPromises.push(sendData(WATER_LEVEL_URL, data, 'water-level'));
    await new Promise(resolve => setTimeout(resolve, 500)); // 500ms delay between requests
  }
  
  // Send moisture data
  console.log('\n2. Sending 10 Moisture readings...');
  const moisturePromises = [];
  for (let i = 1; i <= 10; i++) {
    const data = generateMoistureData(i);
    const topMoisture = data.sensor[0].humid_hi;
    const bottomMoisture = data.sensor[0].humid_low;
    console.log(`   - Moisture ${i}: Gateway ${data.gateway_id}, Top: ${topMoisture}%, Bottom: ${bottomMoisture}%`);
    moisturePromises.push(sendData(MOISTURE_URL, data, 'moisture'));
    await new Promise(resolve => setTimeout(resolve, 500)); // 500ms delay between requests
  }
  
  // Wait for all requests to complete
  console.log('\n3. Waiting for all requests to complete...');
  const allResults = await Promise.all([...waterLevelPromises, ...moisturePromises]);
  
  // Display results
  console.log('\n4. Results:');
  let successCount = 0;
  let failureCount = 0;
  
  allResults.forEach((result, index) => {
    if (result.statusCode === 200 || result.statusCode === 201) {
      successCount++;
    } else {
      failureCount++;
      console.log(`   ❌ Failed: ${result.type} - Status: ${result.statusCode}, Body: ${result.body}`);
    }
  });
  
  console.log(`\n   ✅ Success: ${successCount}/20`);
  console.log(`   ❌ Failed: ${failureCount}/20`);
  
  // Wait a bit for processing
  console.log('\n5. Waiting 10 seconds for data to be processed...');
  await new Promise(resolve => setTimeout(resolve, 10000));
  
  console.log('\n6. Check data in TimescaleDB:');
  console.log('   Run: npm run check:data');
  console.log('   Or manually: docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "SELECT * FROM sensor_readings ORDER BY time DESC LIMIT 20;"');
}

// Run the script
main().catch(console.error);