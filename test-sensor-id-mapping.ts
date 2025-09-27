import { formatWaterLevelSensorId, extractWaterLevelSensorId } from './services/sensor-data/src/utils/sensor-id-formatter.js';

// Test cases
const testCases = [
  { input: '2216617412385143', expected: 'AWD-5177' }, // hex of 2216617412385143 ends in 5177
  { input: 'AWD-B7E6', expected: 'AWD-B7E6' }, // Already formatted
  { input: '00:11:22:33:44:55', expected: 'AWD-4455' }, // MAC address
  { input: '222410831183230', expected: 'AWD-517E' }, // Another numeric ID
];

console.log('Testing sensor ID formatting...\n');

testCases.forEach(test => {
  try {
    const result = formatWaterLevelSensorId(test.input);
    console.log(`Input: ${test.input}`);
    console.log(`Expected: ${test.expected}`);
    console.log(`Result: ${result}`);
    console.log(`Status: ${result === test.expected ? '✅ PASS' : '❌ FAIL'}\n`);
  } catch (error) {
    console.log(`Input: ${test.input}`);
    console.log(`Error: ${error instanceof Error ? error.message : String(error)}\n`);
  }
});

// Test telemetry data extraction
console.log('\nTesting telemetry data extraction...\n');

const telemetryTests = [
  {
    name: 'Numeric sensor ID at root',
    data: {
      sensorId: '2216617412385143',
      data: { level: 100 }
    }
  },
  {
    name: 'MAC address in data',
    data: {
      data: { 
        level: 100,
        macAddress: '00:11:22:33:44:55'
      }
    }
  },
  {
    name: 'Already formatted sensor ID',
    data: {
      sensorId: 'AWD-TEST',
      data: { level: 100 }
    }
  }
];

telemetryTests.forEach(test => {
  try {
    const result = extractWaterLevelSensorId(test.data);
    console.log(`Test: ${test.name}`);
    console.log(`Result: ${result}\n`);
  } catch (error) {
    console.log(`Test: ${test.name}`);
    console.log(`Error: ${error instanceof Error ? error.message : String(error)}\n`);
  }
});