#!/usr/bin/env node

const axios = require('axios');
require('dotenv').config();

// Configuration from environment
const SENSOR_API_URL = process.env.SENSOR_DATA_SERVICE_URL || 'http://localhost:3015';
const SENSOR_API_KEY = process.env.SENSOR_DATA_API_KEY || '';

// Test sensor IDs from smart farm configuration
const testSensors = {
  waterLevel: ['AWD-SF01', 'AWD-SF02', 'AWD-SF03'],
  moisture: ['MOIST-SF06-001', 'MOIST-SF07-001', 'MOIST-SF08-001']
};

console.log('Testing Sensor Data Integration');
console.log('==============================');
console.log(`URL: ${SENSOR_API_URL}`);
console.log(`API Key: ${SENSOR_API_KEY ? '***' + SENSOR_API_KEY.slice(-4) : 'NOT SET'}\n`);

async function testEndpoint(endpoint, sensorId) {
  try {
    const url = `${SENSOR_API_URL}${endpoint}`;
    const params = sensorId ? { sensor_id: sensorId } : {};

    console.log(`Testing: ${endpoint}${sensorId ? ` for ${sensorId}` : ''}`);

    const response = await axios.get(url, {
      params,
      headers: {
        'X-API-Key': SENSOR_API_KEY,
        'Accept': 'application/json',
      },
      timeout: 5000
    });

    if (response.data) {
      console.log('  ✅ Success');

      // Check response structure
      if (response.data.data) {
        if (Array.isArray(response.data.data)) {
          console.log(`  📊 Received ${response.data.data.length} records`);
          if (response.data.data.length > 0) {
            const sample = response.data.data[0];
            console.log('  📋 Sample record:', JSON.stringify(sample, null, 2).split('\n').slice(0, 5).join('\n'));
          }
        } else {
          console.log('  📋 Data:', JSON.stringify(response.data.data, null, 2).split('\n').slice(0, 5).join('\n'));
        }
      }
    }
  } catch (error) {
    console.log('  ❌ Failed');
    if (error.response) {
      console.log(`     Status: ${error.response.status} ${error.response.statusText}`);
      if (error.response.data) {
        console.log(`     Error: ${JSON.stringify(error.response.data)}`);
      }
    } else {
      console.log(`     Error: ${error.message}`);
    }
  }
  console.log('');
}

async function testSensorClient() {
  // Test health endpoint first
  console.log('1. Testing Service Health\n');
  await testEndpoint('/health');

  // Test water level endpoints
  console.log('2. Testing Water Level Endpoints\n');
  for (const sensorId of testSensors.waterLevel) {
    await testEndpoint('/api/v1/public/water-levels/latest', sensorId);
  }

  // Test moisture endpoints
  console.log('3. Testing Moisture Endpoints\n');
  for (const sensorId of testSensors.moisture) {
    await testEndpoint('/api/v1/public/moisture/latest', sensorId);
  }

  // Test timeseries endpoints (with date range)
  console.log('4. Testing Timeseries Endpoints\n');

  const endDate = new Date();
  const startDate = new Date(endDate.getTime() - 24 * 60 * 60 * 1000); // 24 hours ago

  try {
    const response = await axios.get(`${SENSOR_API_URL}/api/v1/public/moisture/timeseries`, {
      params: {
        sensor_id: testSensors.moisture[0],
        start: startDate.toISOString(),
        end: endDate.toISOString(),
        limit: 10
      },
      headers: {
        'X-API-Key': SENSOR_API_KEY,
        'Accept': 'application/json',
      },
      timeout: 10000
    });

    console.log(`  ✅ Timeseries data available for ${testSensors.moisture[0]}`);
    if (response.data && response.data.data) {
      console.log(`  📊 Received ${response.data.data.length} historical records`);
    }
  } catch (error) {
    console.log('  ⚠️  Timeseries endpoint not accessible');
  }
}

// Integration test with SensorClient
async function testSensorClientIntegration() {
  console.log('\n5. Testing SensorClient Integration\n');

  const { SensorClient } = require('../src/services/sensorClient');

  const client = new SensorClient({
    serviceUrl: SENSOR_API_URL,
    apiKey: SENSOR_API_KEY
  });

  // Test getting a sensor reading
  for (const sensorId of [...testSensors.waterLevel.slice(0, 1), ...testSensors.moisture.slice(0, 1)]) {
    try {
      console.log(`Testing SensorClient.getSensorReading('${sensorId}')`);
      const reading = await client.getSensorReading(sensorId);

      if (reading) {
        console.log('  ✅ Reading retrieved:', {
          type: reading.type,
          value: reading.value,
          unit: reading.unit,
          timestamp: reading.timestamp
        });
      } else {
        console.log('  ⚠️  No reading returned');
      }
    } catch (error) {
      console.log('  ❌ Error:', error.message);
    }
  }
}

// Run all tests
async function main() {
  await testSensorClient();
  await testSensorClientIntegration();

  console.log('\nIntegration Test Summary');
  console.log('=======================');
  console.log('\nTo complete integration:');
  console.log('1. Ensure external-api service is running on port 3015');
  console.log('2. Set SENSOR_DATA_API_KEY in your .env file');
  console.log('3. Verify sensor IDs match registered sensors in the system');
  console.log('4. Check that sensors are actively sending data');
}

main().catch(console.error);