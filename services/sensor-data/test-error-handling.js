const https = require('https');

// API Endpoints
const WATER_LEVEL_URL = 'https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridr-water-level/telemetry';

console.log('=== Testing Error Handling & Message Retry ===\n');

// Test Case 1: Send invalid data that should fail DB validation
console.log('Test 1: Sending invalid water level data (negative level)');
const invalidData = {
  deviceID: "test-error-device-001",
  macAddress: "ERROR123456",
  latitude: 13.7563,
  longitude: 100.5018,
  RSSI: -70,
  voltage: 400,
  level: -999, // Invalid negative water level
  timestamp: Date.now()
};

function sendData(url, data) {
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
          body: body
        });
      });
    });
    
    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

async function runTests() {
  try {
    // Send invalid data
    console.log('Sending invalid data to trigger error...');
    const result = await sendData(WATER_LEVEL_URL, invalidData);
    console.log(`Response: ${result.statusCode}`);
    
    console.log('\n2. Expected behavior:');
    console.log('   - Lambda accepts the message and sends to SQS');
    console.log('   - Consumer receives message from SQS');
    console.log('   - Consumer attempts to process the data');
    console.log('   - Database write fails due to validation');
    console.log('   - Transaction rollbacks');
    console.log('   - Message is NOT deleted from SQS');
    console.log('   - Message becomes visible again after timeout');
    console.log('   - Consumer retries the message');
    
    console.log('\n3. To verify:');
    console.log('   - Check consumer logs: tail -f consumer.log | grep -E "error|Error|rollback"');
    console.log('   - Check SQS queue: npm run check:sqs');
    console.log('   - Messages should remain in queue or go to DLQ after max retries');
    
    console.log('\n4. Simulating database connection error:');
    console.log('   - Stop TimescaleDB: docker stop munbon-timescaledb');
    console.log('   - Send test data: npm run test:send');
    console.log('   - Messages should remain in SQS');
    console.log('   - Start TimescaleDB: docker start munbon-timescaledb');
    console.log('   - Messages should be processed successfully');
    
  } catch (error) {
    console.error('Test failed:', error);
  }
}

runTests();