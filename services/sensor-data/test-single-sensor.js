const https = require('https');

// Send one water level and one moisture reading
const waterLevelData = {
  deviceID: "test-water-001",
  macAddress: "TEST123456",
  latitude: 13.7563,
  longitude: 100.5018,
  RSSI: -70,
  voltage: 385,
  level: 18,
  timestamp: Date.now()
};

const moistureData = {
  gateway_id: "test-001",
  msg_type: "interval",
  date: new Date().toISOString().split('T')[0].replace(/-/g, '/'),
  time: new Date().toTimeString().split(' ')[0],
  latitude: "13.7563",
  longitude: "100.5018",
  gw_batt: "372",
  sensor: [{
    sensor_id: "test-001",
    flood: "no",
    amb_humid: "65",
    amb_temp: "28.5",
    humid_hi: "55",
    temp_hi: "26.5",
    humid_low: "68",
    temp_low: "25.5",
    sensor_batt: "390"
  }]
};

async function sendData(url, data) {
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
  
  return new Promise((resolve, reject) => {
    const req = https.request(options, (res) => {
      let body = '';
      res.on('data', (chunk) => body += chunk);
      res.on('end', () => resolve({ statusCode: res.statusCode, body }));
    });
    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

async function test() {
  console.log('Sending test water level data...');
  const waterResult = await sendData(
    'https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridr-water-level/telemetry',
    waterLevelData
  );
  console.log('Water level response:', waterResult.statusCode);
  
  console.log('\nSending test moisture data...');
  const moistureResult = await sendData(
    'https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-m2m-moisture/telemetry',
    moistureData
  );
  console.log('Moisture response:', moistureResult.statusCode);
  
  console.log('\nCheck consumer logs: tail -f consumer.log | grep -E "Attempting|Successfully saved|Failed"');
}

test();