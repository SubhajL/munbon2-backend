#!/usr/bin/env node

const axios = require('axios');

// The problematic data you showed
const problematicData = {
  "gateway_id": "0",
  "msg_type": "1",
  "date": "2025-06-28",
  "time": "11:37:59",
  "latitude": "0",
  "longitude": "0",
  "gw_batt": "0",
  "sensor": [
    {
      "sensor_id": "",
      "flood": "",
      "amb_humid": "",
      "amb_temp": "",
      "humid_hi": "",
      "temp_hi": "",
      "humid_low": "",
      "temp_low": "",
      "sensor_batt": ""
    }
  ]
};

// Correct format example
const correctFormat = {
  "gateway_id": "GW001",  // Should be a valid gateway ID, not "0"
  "msg_type": "1",
  "date": "2025-06-30",
  "time": "14:30:00",
  "latitude": "14.3754",   // Should be valid coordinates
  "longitude": "102.8756", 
  "gw_batt": "85",        // Gateway battery percentage (0-100)
  "sensor": [
    {
      "sensor_id": "S001",   // MUST have a sensor ID
      "flood": "0",          // 0 = no flood, 1 = flood detected
      "amb_humid": "75.5",   // Ambient humidity %
      "amb_temp": "28.3",    // Ambient temperature °C
      "humid_hi": "85.2",    // High soil moisture %
      "temp_hi": "26.5",     // High soil temperature °C
      "humid_low": "45.8",   // Low soil moisture %
      "temp_low": "25.1",    // Low soil temperature °C
      "sensor_batt": "90"    // Sensor battery percentage
    },
    {
      "sensor_id": "S002",   // Multiple sensors can be in one message
      "flood": "0",
      "amb_humid": "76.2",
      "amb_temp": "28.5",
      "humid_hi": "83.5",
      "temp_hi": "26.8",
      "humid_low": "44.2",
      "temp_low": "25.3",
      "sensor_batt": "88"
    }
  ]
};

console.log('===== MOISTURE SENSOR DATA FORMAT VALIDATION =====\n');

console.log('❌ PROBLEMATIC DATA (What you sent):');
console.log(JSON.stringify(problematicData, null, 2));

console.log('\n🔍 ISSUES FOUND:');
console.log('1. gateway_id is "0" - should be a meaningful identifier like "GW001"');
console.log('2. latitude/longitude are "0" - should be actual coordinates');
console.log('3. sensor_id is empty ("") - MUST have a value like "S001"');
console.log('4. All sensor measurements are empty strings - should have numeric values');
console.log('5. This will be marked as "unknown" type by Lambda due to empty sensor_id\n');

console.log('✅ CORRECT FORMAT EXAMPLE:');
console.log(JSON.stringify(correctFormat, null, 2));

console.log('\n📋 FIELD DESCRIPTIONS:');
console.log('- gateway_id: Unique identifier for the gateway device');
console.log('- msg_type: Message type (usually "1" for sensor data)');
console.log('- date: Date in YYYY-MM-DD format');
console.log('- time: Time in HH:MM:SS format');
console.log('- latitude/longitude: GPS coordinates of the gateway');
console.log('- gw_batt: Gateway battery level (0-100)');
console.log('- sensor[]: Array of sensor readings, each containing:');
console.log('  - sensor_id: REQUIRED - Unique sensor identifier');
console.log('  - flood: Flood detection (0=no, 1=yes)');
console.log('  - amb_humid: Ambient humidity percentage');
console.log('  - amb_temp: Ambient temperature in Celsius');
console.log('  - humid_hi: High/surface soil moisture percentage');
console.log('  - temp_hi: High/surface soil temperature in Celsius');
console.log('  - humid_low: Low/deep soil moisture percentage');
console.log('  - temp_low: Low/deep soil temperature in Celsius');
console.log('  - sensor_batt: Sensor battery level (0-100)\n');

console.log('🔧 TO TEST WITH CORRECT FORMAT:');
console.log('curl -X POST \\');
console.log('  https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-m2m-moisture/telemetry \\');
console.log('  -H "Content-Type: application/json" \\');
console.log('  -d \'' + JSON.stringify(correctFormat) + '\'');

console.log('\n📊 PROCESSING FLOW:');
console.log('1. Data posted to API Gateway endpoint');
console.log('2. Lambda validates token (munbon-m2m-moisture) ✓');
console.log('3. Lambda detects sensor type:');
console.log('   - Your data: gateway_id="0", sensor=[], sensor_id="" → Type: "unknown" ❌');
console.log('   - Correct: gateway_id="GW001", sensor=[...], sensor_id="S001" → Type: "moisture" ✓');
console.log('4. Lambda sends to SQS queue');
console.log('5. Consumer processes and stores in TimescaleDB');

console.log('\n💡 WHY YOUR DATA WASN\'T STORED:');
console.log('The Lambda function logged "Received unknown data from unknown" because:');
console.log('- The sensor array has an empty sensor_id');
console.log('- This causes the data to be classified as "unknown" type');
console.log('- The consumer likely skips unknown sensor types\n');

// Function to validate moisture data
function validateMoistureData(data) {
  const errors = [];
  
  if (!data.gateway_id || data.gateway_id === "0") {
    errors.push('Invalid gateway_id: should not be "0" or empty');
  }
  
  if (!data.latitude || data.latitude === "0" || !data.longitude || data.longitude === "0") {
    errors.push('Invalid coordinates: latitude/longitude should not be "0"');
  }
  
  if (!data.sensor || !Array.isArray(data.sensor)) {
    errors.push('Missing or invalid sensor array');
  } else {
    data.sensor.forEach((s, idx) => {
      if (!s.sensor_id) {
        errors.push(`Sensor[${idx}]: Missing sensor_id (REQUIRED)`);
      }
      
      // Check if all measurements are empty
      const measurements = ['flood', 'amb_humid', 'amb_temp', 'humid_hi', 'temp_hi', 'humid_low', 'temp_low'];
      const allEmpty = measurements.every(field => !s[field] || s[field] === "");
      if (allEmpty) {
        errors.push(`Sensor[${idx}]: All measurements are empty`);
      }
    });
  }
  
  return errors;
}

console.log('🔍 VALIDATING YOUR DATA:');
const errors = validateMoistureData(problematicData);
if (errors.length > 0) {
  console.log('❌ Validation FAILED:');
  errors.forEach(err => console.log(`   - ${err}`));
} else {
  console.log('✅ Validation PASSED');
}

console.log('\n📝 RECOMMENDATIONS:');
console.log('1. Update sensor firmware/configuration to send proper sensor_id values');
console.log('2. Ensure GPS coordinates are correctly configured');
console.log('3. Verify sensor readings are being captured (not empty strings)');
console.log('4. Use meaningful gateway IDs instead of "0"');
console.log('5. Test with the correct format example above');