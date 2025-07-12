#!/usr/bin/env node

const AWS = require('aws-sdk');
const sqs = new AWS.SQS({ region: 'ap-southeast-1' });

const QUEUE_URL = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';
const MAC_ADDRESS = '16186C1FB7E6';

async function findWaterLevelMessages() {
  console.log(`🔍 Searching for water level messages from MAC: ${MAC_ADDRESS}\n`);
  
  try {
    const params = {
      QueueUrl: QUEUE_URL,
      MaxNumberOfMessages: 10,
      VisibilityTimeout: 0  // Don't hide messages
    };
    
    let found = false;
    let totalChecked = 0;
    const messagesToCheck = 200; // Check up to 200 messages
    
    while (totalChecked < messagesToCheck) {
      const result = await sqs.receiveMessage(params).promise();
      
      if (!result.Messages || result.Messages.length === 0) {
        break;
      }
      
      for (const message of result.Messages) {
        totalChecked++;
        try {
          const body = JSON.parse(message.Body);
          
          // Check if it's a water level message
          if (body.type === 'water-level' || body.sensorType === 'water-level') {
            // Check for MAC address in various places
            const hasMAC = 
              body.deviceId?.includes(MAC_ADDRESS) ||
              body.sensorId?.includes(MAC_ADDRESS) ||
              body.metadata?.macAddress?.includes(MAC_ADDRESS) ||
              JSON.stringify(body).includes(MAC_ADDRESS);
            
            if (hasMAC) {
              found = true;
              console.log(`✅ Found message from ${MAC_ADDRESS}:`);
              console.log('Timestamp:', body.timestamp || body.data?.timestamp);
              console.log('Sensor ID:', body.sensorId);
              console.log('Water Level:', body.data?.level, 'cm');
              console.log('Location:', body.location);
              console.log('Full message:', JSON.stringify(body, null, 2));
              console.log('---');
            }
          }
        } catch (e) {
          // Skip invalid messages
        }
      }
      
      process.stdout.write(`\rChecked ${totalChecked} messages...`);
    }
    
    console.log(`\n\nTotal messages checked: ${totalChecked}`);
    
    if (!found) {
      console.log(`❌ No messages found from MAC ${MAC_ADDRESS}`);
      console.log('\nChecking for ANY recent water level messages...');
      
      // Show a few recent water level messages
      const recentParams = {
        QueueUrl: QUEUE_URL,
        MaxNumberOfMessages: 5,
        VisibilityTimeout: 0
      };
      
      const recent = await sqs.receiveMessage(recentParams).promise();
      if (recent.Messages) {
        console.log('\nRecent water level messages:');
        for (const msg of recent.Messages) {
          try {
            const body = JSON.parse(msg.Body);
            if (body.type === 'water-level' || body.sensorType === 'water-level') {
              console.log(`- ${body.timestamp}: Sensor ${body.sensorId}, Level: ${body.data?.level}cm`);
            }
          } catch (e) {}
        }
      }
    }
    
  } catch (error) {
    console.error('Error:', error.message);
  }
}

findWaterLevelMessages();