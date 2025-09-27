const axios = require('axios');

const BASE_URL = 'http://localhost:4003/api/v1/water-control';

// Test data
const testZoneId = '01-02'; // Munbon Zone 2
const testSectionId = '01-02-03-04';
const testGateId = 'RMC1';

// Color codes for output
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m'
};

// Helper function to make requests
async function makeRequest(method, endpoint, data = null) {
  try {
    const config = {
      method,
      url: `${BASE_URL}${endpoint}`,
      headers: {
        'Content-Type': 'application/json'
      }
    };

    if (data) {
      if (method === 'GET') {
        config.params = data;
      } else {
        config.data = data;
      }
    }

    const response = await axios(config);
    return { success: true, data: response.data };
  } catch (error) {
    return { 
      success: false, 
      error: error.response ? error.response.data : error.message 
    };
  }
}

// Test functions
const tests = {
  // 1. Test weekly schedule endpoint
  testWeeklySchedule: async () => {
    console.log(`\n${colors.blue}Testing Weekly Schedule Endpoint${colors.reset}`);
    console.log('GET /zones/:zoneId/weekly-schedule');
    
    const result = await makeRequest('GET', `/zones/${testZoneId}/weekly-schedule`);
    
    if (result.success) {
      console.log(`${colors.green}✓ Success${colors.reset}`);
      console.log('Response:', JSON.stringify(result.data, null, 2));
    } else {
      console.log(`${colors.red}✗ Failed${colors.reset}`);
      console.log('Error:', result.error);
    }
    
    return result.success;
  },

  // 2. Test current week endpoint
  testCurrentWeek: async () => {
    console.log(`\n${colors.blue}Testing Current Week Endpoint${colors.reset}`);
    console.log('GET /zones/:zoneId/current-week');
    
    const result = await makeRequest('GET', `/zones/${testZoneId}/current-week`);
    
    if (result.success) {
      console.log(`${colors.green}✓ Success${colors.reset}`);
      console.log('Response summary:');
      if (result.data.data) {
        const data = result.data.data;
        console.log(`- Zone: ${data.weekly_control?.zone_id}`);
        console.log(`- Total Demand: ${data.weekly_control?.total_demand_m3} m³`);
        console.log(`- Automatic Gates: ${data.summary?.total_automatic_gates}`);
        console.log(`- Manual Gates: ${data.summary?.total_manual_gates}`);
        console.log(`- Status: ${data.weekly_control?.status}`);
      }
    } else {
      console.log(`${colors.red}✗ Failed${colors.reset}`);
      console.log('Error:', result.error);
    }
    
    return result.success;
  },

  // 3. Test gate schedule endpoint
  testGateSchedule: async () => {
    console.log(`\n${colors.blue}Testing Gate Schedule Endpoint${colors.reset}`);
    console.log(`GET /gates/${testGateId}/schedule`);
    
    const result = await makeRequest('GET', `/gates/${testGateId}/schedule`);
    
    if (result.success) {
      console.log(`${colors.green}✓ Success${colors.reset}`);
      console.log(`Found ${result.data.data?.length || 0} schedule entries for gate ${testGateId}`);
    } else {
      console.log(`${colors.red}✗ Failed${colors.reset}`);
      console.log('Error:', result.error);
    }
    
    return result.success;
  },

  // 4. Test section schedule endpoint
  testSectionSchedule: async () => {
    console.log(`\n${colors.blue}Testing Section Schedule Endpoint${colors.reset}`);
    console.log(`GET /sections/${testSectionId}/schedule`);
    
    const result = await makeRequest('GET', `/sections/${testSectionId}/schedule`, {
      include_gate_details: 'true'
    });
    
    if (result.success) {
      console.log(`${colors.green}✓ Success${colors.reset}`);
      if (result.data.data) {
        console.log(`Section: ${result.data.data.section_id}`);
        console.log(`Total Operations: ${result.data.data.total_operations}`);
      }
    } else {
      console.log(`${colors.red}✗ Failed${colors.reset}`);
      console.log('Error:', result.error);
    }
    
    return result.success;
  },

  // 5. Test manual gate job orders endpoint
  testManualGateJobOrders: async () => {
    console.log(`\n${colors.blue}Testing Manual Gate Job Orders Endpoint${colors.reset}`);
    console.log('GET /job-orders/manual-gates');
    
    const result = await makeRequest('GET', '/job-orders/manual-gates', {
      zone_id: testZoneId,
      status: 'pending'
    });
    
    if (result.success) {
      console.log(`${colors.green}✓ Success${colors.reset}`);
      console.log(`Found ${result.data.data?.length || 0} pending job orders`);
      if (result.data.data?.length > 0) {
        const firstOrder = result.data.data[0];
        console.log('Sample job order:');
        console.log(`- Gate: ${firstOrder.gate_id}`);
        console.log(`- Opening Height: ${firstOrder.opening_height_cm} cm`);
        console.log(`- Duration: ${firstOrder.operation_duration_hours} hours`);
        console.log(`- Operator: ${firstOrder.operator?.name || 'Not assigned'}`);
      }
    } else {
      console.log(`${colors.red}✗ Failed${colors.reset}`);
      console.log('Error:', result.error);
    }
    
    return result.success;
  },

  // 6. Test status overview endpoint
  testStatusOverview: async () => {
    console.log(`\n${colors.blue}Testing Status Overview Endpoint${colors.reset}`);
    console.log('GET /status/overview');
    
    const result = await makeRequest('GET', '/status/overview', {
      zone_id: testZoneId
    });
    
    if (result.success) {
      console.log(`${colors.green}✓ Success${colors.reset}`);
      console.log('Overview:', JSON.stringify(result.data.data, null, 2));
    } else {
      console.log(`${colors.red}✗ Failed${colors.reset}`);
      console.log('Error:', result.error);
    }
    
    return result.success;
  },

  // 7. Test validation error
  testValidationError: async () => {
    console.log(`\n${colors.blue}Testing Validation Error Handling${colors.reset}`);
    console.log('GET /zones/invalid-zone/weekly-schedule');
    
    const result = await makeRequest('GET', '/zones/invalid-zone/weekly-schedule');
    
    if (!result.success && result.error?.error?.code === 'VALIDATION_ERROR') {
      console.log(`${colors.green}✓ Validation correctly rejected invalid zone ID${colors.reset}`);
      console.log('Error details:', result.error.error.details);
      return true;
    } else {
      console.log(`${colors.red}✗ Validation did not work as expected${colors.reset}`);
      return false;
    }
  }
};

// Main test runner
async function runAllTests() {
  console.log('🚀 Starting REST API Tests for Water Control BFF');
  console.log('================================================');
  console.log(`Base URL: ${BASE_URL}`);
  console.log('================================================');

  // Check service health first
  try {
    const health = await axios.get('http://localhost:4003/health');
    console.log(`${colors.green}✓ Service is healthy${colors.reset}`);
  } catch (error) {
    console.log(`${colors.red}✗ Service is not running on port 4003${colors.reset}`);
    return;
  }

  const results = {
    passed: 0,
    failed: 0
  };

  // Run all tests
  for (const [testName, testFunc] of Object.entries(tests)) {
    const passed = await testFunc();
    if (passed) {
      results.passed++;
    } else {
      results.failed++;
    }
    
    // Small delay between tests
    await new Promise(resolve => setTimeout(resolve, 500));
  }

  // Summary
  console.log('\n================================================');
  console.log('Test Summary:');
  console.log(`${colors.green}Passed: ${results.passed}${colors.reset}`);
  console.log(`${colors.red}Failed: ${results.failed}${colors.reset}`);
  console.log(`Total: ${results.passed + results.failed}`);
  console.log('================================================');
}

// Run specific test
async function runTest(testName) {
  if (tests[testName]) {
    await tests[testName]();
  } else {
    console.log(`Unknown test: ${testName}`);
    console.log('Available tests:', Object.keys(tests).join(', '));
  }
}

// Check command line arguments
const args = process.argv.slice(2);
if (args.length > 0) {
  runTest(args[0]);
} else {
  runAllTests().catch(console.error);
}