const http = require('http');

// Test API endpoints
const API_BASE = 'http://localhost:3001';

async function testEndpoint(path, description) {
  return new Promise((resolve) => {
    console.log(`\nTesting: ${description}`);
    console.log(`GET ${API_BASE}${path}`);
    
    http.get(`${API_BASE}${path}`, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        console.log(`Status: ${res.statusCode}`);
        try {
          const json = JSON.parse(data);
          console.log('Response:', JSON.stringify(json, null, 2).substring(0, 200) + '...');
        } catch (e) {
          console.log('Response:', data.substring(0, 200));
        }
        resolve();
      });
    }).on('error', (err) => {
      console.log('Error:', err.message);
      resolve();
    });
  });
}

async function runTests() {
  console.log('=== Munbon Sensor Data API Test ===\n');
  
  // Test health endpoint
  await testEndpoint('/health', 'Health Check');
  
  // Test sensor endpoints
  await testEndpoint('/api/v1/sensors', 'List all sensors');
  await testEndpoint('/api/v1/sensors/RIDR001', 'Get specific sensor');
  await testEndpoint('/api/v1/sensors/RIDR001/latest', 'Get latest reading');
  
  // Test water level endpoints
  await testEndpoint('/api/v1/water-levels?limit=5', 'Get water level readings');
  await testEndpoint('/api/v1/water-levels/aggregated?interval=1h', 'Get aggregated water levels');
  
  // Test moisture endpoints
  await testEndpoint('/api/v1/moisture?limit=5', 'Get moisture readings');
  await testEndpoint('/api/v1/moisture/aggregated?interval=1h', 'Get aggregated moisture');
  
  // Test external API (should fail without API key)
  await testEndpoint('/api/v1/external/rid-ms/sensors', 'External API without auth');
  
  console.log('\n=== Test Complete ===');
}

// Wait for server to be ready
console.log('Waiting for server to start...');
setTimeout(runTests, 3000);