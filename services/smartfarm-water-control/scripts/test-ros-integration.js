
const axios = require('axios');
require('dotenv').config();

// Configuration from environment
const ROS_API_URL = process.env.ROS_API_URL || 'http://localhost:3001';
const ROS_API_KEY = process.env.ROS_API_KEY || '';
const ROS_ENDPOINT = process.env.ROS_CALCULATION_ENDPOINT || '/api/v1/ros/demand/calculate';

// Test data matching smart farm requirements
const testRequest = {
  cropType: "rice",
  calculationDate: new Date().toISOString().split('T')[0],
  calculationPeriod: 1, // Daily
  plantings: [
    {
      plantingDate: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0], // 30 days ago
      areaRai: 2.5,
      growthDays: null // Let ROS calculate
    }
  ],
  nonAgriculturalDemands: []
};

console.log('Testing ROS Integration');
console.log('======================');
console.log(`URL: ${ROS_API_URL}${ROS_ENDPOINT}`);
console.log(`API Key: ${ROS_API_KEY ? '***' + ROS_API_KEY.slice(-4) : 'NOT SET'}`);
console.log('\nRequest payload:', JSON.stringify(testRequest, null, 2));

async function testROSIntegration() {
  try {
    const startTime = Date.now();

    const response = await axios.post(
      `${ROS_API_URL}${ROS_ENDPOINT}`,
      testRequest,
      {
        headers: {
          'X-API-Key': ROS_API_KEY,
          'Content-Type': 'application/json',
        },
        timeout: 30000 // 30 seconds
      }
    );

    const duration = Date.now() - startTime;

    console.log('\n✅ SUCCESS');
    console.log(`Response time: ${duration}ms`);
    console.log('\nResponse structure:');

    const responseData = response.data;

    // Check expected fields based on waterPlanningService expectations
    const expectedFields = [
      'waterRequirement',
      'effectiveRainfall',
      'netIrrigation',
      'cropDetails'
    ];

    expectedFields.forEach(field => {
      if (responseData[field]) {
        console.log(`  ✓ ${field}: Present`);
        if (field === 'netIrrigation' && responseData[field].amount_m3) {
          console.log(`    - amount_m3: ${responseData[field].amount_m3}`);
        }
        if (field === 'cropDetails') {
          console.log(`    - et0: ${responseData[field].et0}`);
          console.log(`    - weightedKc: ${responseData[field].weightedKc}`);
        }
      } else {
        console.log(`  ✗ ${field}: MISSING`);
      }
    });

    console.log('\nFull response:', JSON.stringify(responseData, null, 2));

    // Check if response structure matches expected format
    if (responseData.netIrrigation && responseData.netIrrigation.amount_m3 !== undefined) {
      console.log('\n✅ Response structure compatible with Smart Farm service');
    } else {
      console.log('\n⚠️  Response structure may need adaptation');
      console.log('Expected: response.netIrrigation.amount_m3');
    }

  } catch (error) {
    console.error('\n❌ FAILED');

    if (error.response) {
      console.error('Response error:', {
        status: error.response.status,
        statusText: error.response.statusText,
        data: error.response.data
      });
    } else if (error.request) {
      console.error('No response received:', error.message);
      console.error('Is the ROS service running on', ROS_API_URL, '?');
    } else {
      console.error('Request error:', error.message);
    }
  }
}

// Run the test
testROSIntegration();