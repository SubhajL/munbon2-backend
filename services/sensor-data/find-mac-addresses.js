#!/usr/bin/env node

const fs = require('fs');
const readline = require('readline');
const path = require('path');

// MAC addresses to search for
const macAddresses = [
  '16186C1FB75A',
  '16186C1FB6B5',
  '16186C1FB8A4',
  '16186C1FB33B',
  '16186C1FB7E6',
  '16186C1FB9BE'
];

// Convert to lowercase for case-insensitive search
const macAddressesLower = macAddresses.map(mac => mac.toLowerCase());

console.log('🔍 Searching for MAC addresses in sensor data...\n');

const results = {};
macAddresses.forEach(mac => {
  results[mac] = {
    sensorIds: new Set(),
    deviceIds: new Set(),
    samples: []
  };
});

async function searchInFile(filePath) {
  const fileStream = fs.createReadStream(filePath);
  const rl = readline.createInterface({
    input: fileStream,
    crlfDelay: Infinity
  });

  for await (const line of rl) {
    try {
      const data = JSON.parse(line);
      const jsonString = JSON.stringify(data).toLowerCase();
      
      macAddressesLower.forEach((mac, index) => {
        if (jsonString.includes(mac)) {
          const originalMac = macAddresses[index];
          
          // Extract sensor ID and device ID
          if (data.sensorId) results[originalMac].sensorIds.add(data.sensorId);
          if (data.deviceId) results[originalMac].deviceIds.add(data.deviceId);
          if (data.data?.deviceId) results[originalMac].deviceIds.add(data.data.deviceId);
          
          // Store a sample if we don't have many
          if (results[originalMac].samples.length < 3) {
            results[originalMac].samples.push({
              timestamp: data.timestamp,
              sensorId: data.sensorId,
              deviceId: data.deviceId || data.data?.deviceId,
              type: data.sensorType || data.type,
              level: data.data?.level,
              location: data.location || data.data?.location,
              metadata: data.metadata
            });
          }
        }
      });
    } catch (e) {
      // Skip invalid JSON lines
    }
  }
}

async function searchAllFiles() {
  const dataDir = path.join(__dirname, 'data');
  
  // Search in telemetry files
  const files = fs.readdirSync(dataDir).filter(f => f.startsWith('telemetry_') && f.endsWith('.jsonl'));
  
  console.log(`Found ${files.length} telemetry files to search...\n`);
  
  for (const file of files) {
    process.stdout.write(`\rSearching ${file}...`);
    await searchInFile(path.join(dataDir, file));
  }
  
  console.log('\n\n📊 Results:\n');
  
  // Display results for each MAC address
  macAddresses.forEach(mac => {
    console.log(`MAC Address: ${mac}`);
    console.log('═'.repeat(50));
    
    const result = results[mac];
    
    if (result.sensorIds.size === 0 && result.deviceIds.size === 0) {
      console.log('❌ No matches found\n');
    } else {
      if (result.sensorIds.size > 0) {
        console.log(`✅ Sensor IDs: ${Array.from(result.sensorIds).join(', ')}`);
      }
      if (result.deviceIds.size > 0) {
        console.log(`✅ Device IDs: ${Array.from(result.deviceIds).join(', ')}`);
      }
      
      if (result.samples.length > 0) {
        console.log('\n📝 Sample data:');
        result.samples.forEach((sample, idx) => {
          console.log(`\n  Sample ${idx + 1}:`);
          console.log(`    Timestamp: ${sample.timestamp}`);
          console.log(`    Type: ${sample.type}`);
          if (sample.sensorId) console.log(`    Sensor ID: ${sample.sensorId}`);
          if (sample.deviceId) console.log(`    Device ID: ${sample.deviceId}`);
          if (sample.level !== undefined) console.log(`    Water Level: ${sample.level} cm`);
          if (sample.location) console.log(`    Location: ${JSON.stringify(sample.location)}`);
          if (sample.metadata) console.log(`    Metadata: ${JSON.stringify(sample.metadata)}`);
        });
      }
    }
    console.log();
  });
}

// Also check for sensor registration data
async function checkSensorRegistry() {
  console.log('\n🔍 Checking for sensor registry files...\n');
  
  // Look for sensor mapping files
  const possiblePaths = [
    path.join(__dirname, 'sensor-registry.json'),
    path.join(__dirname, '../config/sensors.json'),
    path.join(__dirname, '../data/sensor-mappings.json'),
    path.join(__dirname, '../../water-level-monitoring/config/sensors.json')
  ];
  
  for (const filePath of possiblePaths) {
    if (fs.existsSync(filePath)) {
      console.log(`Found registry file: ${filePath}`);
      const content = fs.readFileSync(filePath, 'utf8');
      const jsonString = content.toLowerCase();
      
      macAddressesLower.forEach((mac, index) => {
        if (jsonString.includes(mac)) {
          console.log(`\n✅ MAC ${macAddresses[index]} found in registry file!`);
          // Try to parse and show relevant section
          try {
            const data = JSON.parse(content);
            // Search for the MAC in the parsed data
            for (const [key, value] of Object.entries(data)) {
              if (JSON.stringify(value).toLowerCase().includes(mac)) {
                console.log(`   Found in section: ${key}`);
                console.log(`   Data: ${JSON.stringify(value, null, 2)}`);
              }
            }
          } catch (e) {
            console.log('   (Could not parse full details)');
          }
        }
      });
    }
  }
}

// Search in database queries
async function checkDatabaseQueries() {
  console.log('\n🔍 Checking SQL files for sensor registrations...\n');
  
  const sqlFiles = [
    '/Users/subhajlimanond/dev/munbon2-backend/services/sensor-data/register-water-sensor.sql',
    '/Users/subhajlimanond/dev/munbon2-backend/scripts/db/postgres/init-sensors.sql'
  ];
  
  for (const sqlFile of sqlFiles) {
    if (fs.existsSync(sqlFile)) {
      console.log(`Checking ${path.basename(sqlFile)}...`);
      const content = fs.readFileSync(sqlFile, 'utf8');
      const contentLower = content.toLowerCase();
      
      macAddressesLower.forEach((mac, index) => {
        if (contentLower.includes(mac)) {
          console.log(`\n✅ MAC ${macAddresses[index]} found in SQL file!`);
          // Extract the relevant lines
          const lines = content.split('\n');
          lines.forEach((line, lineIdx) => {
            if (line.toLowerCase().includes(mac)) {
              console.log(`   Line ${lineIdx + 1}: ${line.trim()}`);
            }
          });
        }
      });
    }
  }
}

async function main() {
  await searchAllFiles();
  await checkSensorRegistry();
  await checkDatabaseQueries();
  
  console.log('\n✅ Search complete!');
}

main().catch(console.error);