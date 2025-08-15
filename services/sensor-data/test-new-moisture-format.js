#!/usr/bin/env node

const axios = require('axios');

// Test data based on the new format from manufacturer PDF
const testData = {
  gateway_id: "00001",
  msg_type: "interval",
  date: "2025/07/29",
  time: new Date().toISOString().split('T')[1].split('.')[0], // Current UTC time
  latitude: "13.12345",
  longitude: "100.54621",
  temperature: "38.50",    // NEW: Gateway ambient temperature
  humidity: "55",          // NEW: Gateway ambient humidity  
  heat_index: "41.35",     // NEW: Gateway heat index
  gw_batt: "372",         // Gateway battery (3.72V)
  sensor: [
    {
      sensor_id: "00001",
      date: "2025/07/29",
      time: new Date().toISOString().split('T')[1].split('.')[0],
      flood: "no",          // NEW: Flood detection
      amb_humid: "60",      // NEW: Sensor ambient humidity
      amb_temp: "40.50",    // NEW: Sensor ambient temperature
      humid_hi: "50",       // Soil moisture near surface
      temp_hi: "25.50",     // Soil temperature near surface
      humid_low: "72",      // Soil moisture at depth
      temp_low: "25.00",    // Soil temperature at depth
      sensor_batt: "395"    // Sensor battery (3.95V)
    },
    {
      sensor_id: "00002",
      date: "2025/07/29",
      time: new Date(Date.now() - 120000).toISOString().split('T')[1].split('.')[0], // 2 min ago
      flood: "yes",         // Flood detected!
      amb_humid: "55",
      amb_temp: "38.50",
      humid_hi: "95",       // Very wet surface (flood)
      temp_hi: "25.00",
      humid_low: "90",      // Very wet deep soil
      temp_low: "24.50",
      sensor_batt: "412"
    }
  ]
};

console.log('Testing New Moisture Sensor Format');
console.log('===================================\n');

console.log('1. NEW FIELDS IN THIS FORMAT:');
console.log('   Gateway Level:');
console.log('   - temperature: Ambient temperature at gateway');
console.log('   - humidity: Ambient humidity at gateway');
console.log('   - heat_index: Heat index at gateway');
console.log('   \n   Sensor Level:');
console.log('   - flood: Surface water detection ("yes"/"no")');
console.log('   - amb_humid: Ambient humidity at sensor location');
console.log('   - amb_temp: Ambient temperature at sensor location');
console.log('   - Individual date/time per sensor');
console.log('\n2. TEST DATA:');
console.log(JSON.stringify(testData, null, 2));

// Test endpoints
const endpoints = [
  {
    name: 'Local Ingestion Service (Port 3003)',
    url: 'http://localhost:3003/api/v1/munbon-m2m-moisture/telemetry',
    method: 'POST'
  },
  {
    name: 'CloudFlare Tunnel',
    url: 'https://munbon-moisture.beautifyai.io/api/v1/munbon-m2m-moisture/telemetry',
    method: 'POST'
  }
];

console.log('\n3. TESTING ENDPOINTS:');

async function testEndpoint(endpoint) {
  try {
    console.log(`\n   Testing: ${endpoint.name}`);
    console.log(`   URL: ${endpoint.url}`);
    
    const response = await axios({
      method: endpoint.method,
      url: endpoint.url,
      data: testData,
      headers: {
        'Content-Type': 'application/json'
      },
      timeout: 5000
    });
    
    console.log(`   ✅ Success: ${response.status} ${response.statusText}`);
    console.log(`   Response:`, response.data);
    
  } catch (error) {
    if (error.code === 'ECONNREFUSED') {
      console.log(`   ❌ Failed: Service not running on ${endpoint.url}`);
    } else if (error.response) {
      console.log(`   ❌ Failed: ${error.response.status} ${error.response.statusText}`);
      console.log(`   Error:`, error.response.data);
    } else {
      console.log(`   ❌ Failed:`, error.message);
    }
  }
}

// Test all endpoints
async function runTests() {
  for (const endpoint of endpoints) {
    await testEndpoint(endpoint);
  }
  
  console.log('\n4. CHECK DATA PROCESSING:');
  console.log('   Expected sensor IDs in database:');
  console.log('   - Gateway: GW-00001');
  console.log('   - Sensor 1: MS-00001-00001 (No flood)');
  console.log('   - Sensor 2: MS-00001-00002 (Flood detected)');
  console.log('\n   Run this to check database:');
  console.log('   psql -h localhost -p 5433 -U postgres -d munbon_timescale -c "');
  console.log('     SELECT sensor_id, last_seen, metadata FROM sensor_registry WHERE sensor_type IN (\'gateway\', \'moisture\') ORDER BY last_seen DESC LIMIT 5;');
  console.log('   "');
  console.log('\n   Check moisture readings:');
  console.log('   psql -h localhost -p 5433 -U postgres -d munbon_timescale -c "');
  console.log('     SELECT sensor_id, time, surface_moisture_pct, deep_moisture_pct, flood_detected FROM moisture_readings ORDER BY time DESC LIMIT 5;');
  console.log('   "');
}

// Run tests
runTests().catch(console.error);