#!/usr/bin/env node

const AWS = require('aws-sdk');
const sqs = new AWS.SQS({ region: 'ap-southeast-1' });
const fs = require('fs');
const path = require('path');
const readline = require('readline');

const QUEUE_URL = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';
const DLQ_URL = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-dlq';
const SENSOR_ID = '25050005';

async function searchInQueue(queueUrl, queueName) {
  console.log(`\n🔍 Searching in ${queueName}...`);
  
  try {
    const params = {
      QueueUrl: queueUrl,
      MaxNumberOfMessages: 10,
      VisibilityTimeout: 0
    };
    
    let found = false;
    let totalChecked = 0;
    const messagesToCheck = 100;
    
    while (totalChecked < messagesToCheck) {
      const result = await sqs.receiveMessage(params).promise();
      
      if (!result.Messages || result.Messages.length === 0) {
        break;
      }
      
      for (const message of result.Messages) {
        totalChecked++;
        try {
          const body = JSON.parse(message.Body);
          
          // Check various locations for the sensor ID
          const hasSensorId = 
            body.sensorId === SENSOR_ID ||
            body.data?.deviceId === SENSOR_ID ||
            body.data?.sensorId === SENSOR_ID ||
            body.deviceId === SENSOR_ID ||
            JSON.stringify(body).includes(SENSOR_ID);
          
          if (hasSensorId) {
            found = true;
            console.log(`\n✅ Found sensor ${SENSOR_ID}:`);
            console.log('Message ID:', message.MessageId);
            console.log('Timestamp:', body.timestamp || body.data?.timestamp);
            console.log('Sensor Type:', body.sensorType || body.type);
            console.log('Full message:', JSON.stringify(body, null, 2));
            console.log('---');
          }
        } catch (e) {
          // Skip invalid messages
        }
      }
      
      process.stdout.write(`\rChecked ${totalChecked} messages...`);
    }
    
    if (!found) {
      console.log(`\n❌ No messages found for sensor ${SENSOR_ID} in ${queueName}`);
    }
    
  } catch (error) {
    console.error(`Error searching ${queueName}:`, error.message);
  }
}

async function searchInDataFiles() {
  console.log(`\n📁 Searching in data files...`);
  
  const dataDir = path.join(__dirname, 'data');
  const files = fs.readdirSync(dataDir).filter(f => f.startsWith('telemetry_'));
  
  let totalFound = 0;
  
  for (const file of files) {
    const filePath = path.join(dataDir, file);
    const fileStream = fs.createReadStream(filePath);
    const rl = readline.createInterface({
      input: fileStream,
      crlfDelay: Infinity
    });
    
    let lineNumber = 0;
    let fileFound = 0;
    
    for await (const line of rl) {
      lineNumber++;
      try {
        const data = JSON.parse(line);
        
        if (JSON.stringify(data).includes(SENSOR_ID)) {
          if (fileFound === 0) {
            console.log(`\n📄 Found in ${file}:`);
          }
          fileFound++;
          totalFound++;
          console.log(`  Line ${lineNumber}: ${data.timestamp || data.data?.timestamp} - Type: ${data.sensorType || data.type}`);
          if (fileFound <= 3) {
            console.log(`  Data:`, JSON.stringify(data, null, 2).split('\n').map(l => '    ' + l).join('\n'));
          }
        }
      } catch (e) {
        // Skip invalid JSON lines
      }
    }
    
    if (fileFound > 3) {
      console.log(`  ... and ${fileFound - 3} more occurrences`);
    }
  }
  
  if (totalFound === 0) {
    console.log(`❌ No occurrences found in data files`);
  } else {
    console.log(`\n📊 Total found in data files: ${totalFound}`);
  }
}

async function searchInDatabase() {
  console.log(`\n🗄️ Checking database...`);
  
  const { exec } = require('child_process');
  const util = require('util');
  const execPromise = util.promisify(exec);
  
  try {
    // Check sensor registry
    const registryCmd = `docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "SELECT sensor_id, sensor_type, last_seen, metadata FROM sensor_registry WHERE sensor_id = '${SENSOR_ID}';"`;
    const { stdout: registryOut } = await execPromise(registryCmd);
    console.log('Sensor Registry:', registryOut.trim());
    
    // Check water level readings
    const waterCmd = `docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "SELECT COUNT(*) as count, MIN(time) as earliest, MAX(time) as latest FROM water_level_readings WHERE sensor_id = '${SENSOR_ID}';"`;
    const { stdout: waterOut } = await execPromise(waterCmd);
    console.log('Water Level Readings:', waterOut.trim());
    
    // Check moisture readings
    const moistureCmd = `docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "SELECT COUNT(*) as count, MIN(time) as earliest, MAX(time) as latest FROM moisture_readings WHERE sensor_id = '${SENSOR_ID}';"`;
    const { stdout: moistureOut } = await execPromise(moistureCmd);
    console.log('Moisture Readings:', moistureOut.trim());
    
  } catch (error) {
    console.error('Database error:', error.message);
  }
}

async function main() {
  console.log(`🔍 Comprehensive search for sensor ID: ${SENSOR_ID}`);
  console.log('='.repeat(60));
  
  // Search in queues
  await searchInQueue(QUEUE_URL, 'Main Queue');
  
  // Check if DLQ exists
  try {
    await searchInQueue(DLQ_URL, 'Dead Letter Queue');
  } catch (e) {
    console.log('\n❌ No Dead Letter Queue found');
  }
  
  // Search in data files
  await searchInDataFiles();
  
  // Search in database
  await searchInDatabase();
  
  console.log('\n✅ Search complete!');
}

main().catch(console.error);