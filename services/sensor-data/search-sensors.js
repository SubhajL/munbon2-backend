const AWS = require('aws-sdk');
const sqs = new AWS.SQS({ region: 'ap-southeast-1' });

async function searchSensors() {
  const queueUrl = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';
  const targetSensors = ['AWD-B75A', 'AWD-B33B', 'AWD-B7E6'];
  const foundSensors = new Map();
  let processedCount = 0;
  
  console.log('Searching for sensors:', targetSensors.join(', '));
  console.log('\nSearching through messages...');
  
  // Process messages in batches
  for (let i = 0; i < 20; i++) {
    try {
      const result = await sqs.receiveMessage({
        QueueUrl: queueUrl,
        MaxNumberOfMessages: 10,
        VisibilityTimeout: 0,
        WaitTimeSeconds: 1
      }).promise();
      
      if (!result.Messages || result.Messages.length === 0) {
        console.log('No more messages in batch', i + 1);
        continue;
      }
      
      for (const message of result.Messages) {
        processedCount++;
        const body = JSON.parse(message.Body);
        
        // Check macAddress field (last 4 characters)
        if (body.data && body.data.macAddress) {
          const macAddress = body.data.macAddress.toUpperCase();
          const lastFour = macAddress.slice(-4);
          const sensorName = 'AWD-' + lastFour;
          
          if (targetSensors.includes(sensorName)) {
            if (!foundSensors.has(sensorName)) {
              foundSensors.set(sensorName, []);
            }
            foundSensors.get(sensorName).push({
              deviceId: body.sensorId || body.data.deviceId,
              macAddress: body.data.macAddress,
              location: body.location || {lat: body.data.latitude, lng: body.data.longitude},
              level: body.data.level,
              voltage: body.data.voltage,
              timestamp: body.timestamp
            });
          }
        }
      }
    } catch (error) {
      console.error('Error in batch', i + 1, ':', error.message);
    }
  }
  
  console.log('\n=== SEARCH RESULTS ===');
  console.log('Messages checked:', processedCount);
  console.log('Target sensors:', targetSensors.join(', '));
  
  targetSensors.forEach(sensor => {
    console.log('\n' + sensor + ':');
    if (foundSensors.has(sensor)) {
      const readings = foundSensors.get(sensor);
      console.log('  ✅ FOUND -', readings.length, 'messages');
      const latest = readings.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))[0];
      console.log('  Latest reading:');
      console.log('    Device ID:', latest.deviceId);
      console.log('    MAC Address:', latest.macAddress);
      console.log('    Location:', `${latest.location.lat}, ${latest.location.lng}`);
      console.log('    Level:', latest.level, 'cm');
      console.log('    Voltage:', latest.voltage / 100, 'V');
      console.log('    Timestamp:', new Date(latest.timestamp).toISOString());
    } else {
      console.log('  ❌ NOT FOUND in checked messages');
    }
  });
}

searchSensors().catch(console.error);