#!/usr/bin/env node

/**
 * End-to-end test for moisture data flow
 * Tests: EC2 HTTP endpoint -> SQS -> Consumer -> Dual-write to both databases
 */

const http = require('http');

// Test data matching the expected format
const moistureData = {
  gw_id: "999",
  gateway_msg_type: "data",
  gateway_date: new Date().toLocaleDateString('en-GB').replace(/\//g, '/'), // "05/08/2025"
  gateway_utc: Math.floor(Date.now() / 1000).toString(),
  gps_lat: "14.9631",
  gps_lng: "102.0970",
  gw_temp: "28.5",
  gw_himid: "65.2",
  gw_head_index: "30.1",
  gw_batt: "380", // 3.8V
  sensor: [{
    sensor_id: "E2E-001",
    sensor_msg_type: "data",
    sensor_date: new Date().toLocaleDateString('en-GB').replace(/\//g, '/'),
    sensor_utc: Math.floor(Date.now() / 1000).toString(),
    sensor_himid_surface: "45.5",
    sensor_himid_deep: "52.3",
    sensor_temp_surface: "26.8",
    sensor_temp_deep: "25.4",
    sensor_temp_ambient: "27.2",
    sensor_himid_ambient: "63.8",
    sensor_flooding: "no",
    sensor_batt: "360"
  }]
};

function sendMoistureData() {
  const data = JSON.stringify(moistureData);
  
  const options = {
    hostname: '43.209.22.250',
    port: 8080,
    path: '/api/sensor-data/moisture/munbon-m2m-moisture',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Content-Length': data.length
    }
  };

  console.log('Sending moisture data to EC2 HTTP endpoint...');
  console.log('URL:', `http://${options.hostname}:${options.port}${options.path}`);
  console.log('Data:', JSON.stringify(moistureData, null, 2));

  const req = http.request(options, (res) => {
    let body = '';
    
    res.on('data', (chunk) => {
      body += chunk;
    });
    
    res.on('end', () => {
      console.log('\nResponse:');
      console.log('Status:', res.statusCode);
      console.log('Headers:', res.headers);
      console.log('Body:', body);
      
      if (res.statusCode === 200) {
        console.log('\n✅ Successfully sent moisture data to EC2 endpoint');
        console.log('\nNext steps to verify:');
        console.log('1. Check SQS queue for message');
        console.log('2. Check consumer logs for processing');
        console.log('3. Check both local and EC2 databases for data');
        
        // Wait a bit then check databases
        setTimeout(checkDatabases, 5000);
      } else {
        console.log('\n❌ Failed to send moisture data');
      }
    });
  });

  req.on('error', (error) => {
    console.error('Error sending request:', error);
  });

  req.write(data);
  req.end();
}

async function checkDatabases() {
  console.log('\n📊 Checking databases for the test data...');
  
  // Check local database
  const { exec } = require('child_process');
  const sensorId = `MS-00999-E2E-001`;
  
  exec(`PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d munbon_timescale -c "SELECT sensor_id, time, moisture_surface_pct, moisture_deep_pct FROM moisture_readings WHERE sensor_id = '${sensorId}' ORDER BY time DESC LIMIT 1"`, (error, stdout, stderr) => {
    if (error) {
      console.error('Error checking local database:', error);
      return;
    }
    console.log('\nLocal Database Result:');
    console.log(stdout || 'No data found');
  });
  
  // Note: EC2 database check would need proper credentials
  console.log('\nTo check EC2 database manually, run:');
  console.log(`PGPASSWORD='<password>' psql -h 43.209.22.250 -p 5432 -U postgres -d sensor_data -c "SELECT sensor_id, time, moisture_surface_pct, moisture_deep_pct FROM moisture_readings WHERE sensor_id = '${sensorId}' ORDER BY time DESC LIMIT 1"`);
}

// Send the test data
sendMoistureData();