const axios = require('axios');

const BFF_URL = 'http://localhost:4003/graphql';

// Test queries and mutations
const tests = {
  // 1. Get automatic gates configuration
  getAutomaticGates: {
    query: `
      query GetAutomaticGates {
        getAutomaticGates {
          alias
          stationCode
          levels {
            l1
            l2
            l3
            l4
          }
          cumulativeLevels {
            level_1
            level_2
            level_3
            level_4
          }
        }
      }
    `
  },

  // 2. Control automatic gate
  controlAutomaticGate: {
    query: `
      mutation ControlGate($input: AutomaticGateControlInput!) {
        controlAutomaticGate(input: $input) {
          commandId
          scadaCommandId
          gateName
          targetLevel
          gateLevel
          startDateTime
          status
        }
      }
    `,
    variables: {
      input: {
        gateName: "RMC1",
        targetLevel: 2,
        reason: "Test water demand adjustment"
      }
    }
  },

  // 3. Control gate sequence (e.g., from Level 3 to Level 1)
  controlGateSequence: {
    query: `
      mutation ControlSequence($input: GateSequenceInput!) {
        controlGateSequence(input: $input) {
          commandId
          gateName
          targetLevel
          gateLevel
          startDateTime
          status
        }
      }
    `,
    variables: {
      input: {
        gateName: "LMC1",
        fromLevel: 3,
        toLevel: 1,
        intervalMinutes: 5
      }
    }
  },

  // 4. Create manual gate job order
  createManualJobOrder: {
    query: `
      mutation CreateJobOrder($input: ManualGateJobOrderInput!) {
        createManualGateJobOrder(input: $input) {
          id
          type
          operatorName
          executionDate
          gates {
            gateName
            location
            zone
            currentHeight
            targetHeight
            openTime
            closeTime
            instructions
          }
          status
        }
      }
    `,
    variables: {
      input: {
        operatorName: "ทีมภาคสนาม Zone 1",
        gates: [
          {
            gateName: "Manual-Gate-01",
            location: "คลอง LMC กม. 5+200",
            zone: 1,
            currentHeight: 0,
            targetHeight: 50,
            openTime: "08:00",
            closeTime: "16:00"
          }
        ]
      }
    }
  },

  // 5. Get water demand calculations
  getWaterDemandCalcs: {
    query: `
      query GetWaterDemand($params: WaterDemandInput) {
        getWaterDemandCalculations(params: $params) {
          recommendations {
            automaticGates {
              gateName
              targetLevel
              reason
              priority
            }
            manualGates {
              gateName
              targetHeight
              openTime
              closeTime
              reason
            }
            warnings {
              type
              message
            }
          }
        }
      }
    `,
    variables: {
      params: {
        zone: 1,
        includeScheduled: true
      }
    }
  },

  // 6. Get service status
  getServiceStatus: {
    query: `
      query GetStatus {
        getServiceStatus {
          flowMonitoring
          gravityOptimizer
          scheduledFieldOps
          waterLevel
          alertService
        }
        getSystemHealth {
          status
          uptime
          memoryUsage
          activeConnections
          lastCheck
        }
      }
    `
  },

  // 7. Emergency stop test
  emergencyStop: {
    query: `
      mutation EmergencyStop($reason: String!) {
        executeEmergencyStop(reason: $reason) {
          success
          stoppedGates
          message
          timestamp
        }
      }
    `,
    variables: {
      reason: "Test emergency stop - high water level detected"
    }
  }
};

// Execute test
async function runTest(testName, testConfig) {
  console.log(`\n=== Running test: ${testName} ===`);
  
  try {
    const response = await axios.post(BFF_URL, {
      query: testConfig.query,
      variables: testConfig.variables || {}
    }, {
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (response.data.errors) {
      console.error('GraphQL Errors:', JSON.stringify(response.data.errors, null, 2));
    } else {
      console.log('Result:', JSON.stringify(response.data.data, null, 2));
    }
  } catch (error) {
    console.error('Request failed:', error.message);
    if (error.response) {
      console.error('Response:', error.response.data);
    }
  }
}

// Main test runner
async function runAllTests() {
  console.log('Starting Water Control BFF Service Tests...');
  console.log('Make sure the service is running on port 4003');
  console.log('================================================');

  // Test connectivity first
  try {
    const health = await axios.get('http://localhost:4003/health');
    console.log('✅ Service is healthy:', health.data);
  } catch (error) {
    console.error('❌ Service is not running on port 4003');
    return;
  }

  // Run tests in sequence
  await runTest('Get Automatic Gates', tests.getAutomaticGates);
  await runTest('Get Service Status', tests.getServiceStatus);
  await runTest('Control Automatic Gate', tests.controlAutomaticGate);
  await runTest('Control Gate Sequence', tests.controlGateSequence);
  await runTest('Create Manual Job Order', tests.createManualJobOrder);
  await runTest('Get Water Demand Calculations', tests.getWaterDemandCalcs);
  
  // Skip emergency stop in normal testing
  console.log('\n⚠️  Skipping emergency stop test (uncomment to test)');
  // await runTest('Emergency Stop', tests.emergencyStop);

  console.log('\n✅ All tests completed');
}

// Run tests
runAllTests().catch(console.error);