// Simple SQS check that uses environment variables from your Lambda deployment
const https = require('https');

// Get serverless info first
const { exec } = require('child_process');

exec('cd /Users/subhajlimanond/dev/munbon2-backend/services/sensor-data/deployments/aws-lambda && serverless info --verbose', (error, stdout, stderr) => {
  if (error) {
    console.error(`Error getting serverless info: ${error.message}`);
    return;
  }

  // Parse the output to find the queue URL
  const lines = stdout.split('\n');
  const queueUrlLine = lines.find(line => line.includes('SensorDataQueueUrl:'));
  
  if (queueUrlLine) {
    const queueUrl = queueUrlLine.split('SensorDataQueueUrl:')[1].trim();
    console.log(`Found Queue URL: ${queueUrl}`);
    console.log('\nTo check messages, run:');
    console.log(`aws sqs receive-message --queue-url "${queueUrl}" --max-number-of-messages 10`);
  } else {
    console.log('Could not find queue URL in serverless info output');
    console.log('\nFull output:');
    console.log(stdout);
  }
});