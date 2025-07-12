const { SQSClient, GetQueueAttributesCommand, ReceiveMessageCommand } = require('@aws-sdk/client-sqs');
const Table = require('cli-table3');
const chalkModule = require('chalk');
const chalk = new chalkModule.Chalk();

// Configure AWS SDK v3
const sqs = new SQSClient({ region: 'ap-southeast-1' });

const QUEUE_URL = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';
const SAMPLE_SIZE = 100; // Number of messages to sample for type analysis

// Message type categories
const messageTypes = {
  'water-level': { count: 0, tokens: new Set(), devices: new Set(), lastTimestamp: null },
  'moisture': { count: 0, tokens: new Set(), devices: new Set(), lastTimestamp: null },
  'shape-file': { count: 0, fileNames: new Set(), uploadIds: new Set(), lastTimestamp: null },
  'unknown': { count: 0, details: [] }
};

async function getQueueStatistics() {
  try {
    const command = new GetQueueAttributesCommand({
      QueueUrl: QUEUE_URL,
      AttributeNames: ['All']
    });
    const attributes = await sqs.send(command);

    return {
      available: parseInt(attributes.Attributes.ApproximateNumberOfMessages),
      inFlight: parseInt(attributes.Attributes.ApproximateNumberOfMessagesNotVisible),
      delayed: parseInt(attributes.Attributes.ApproximateNumberOfMessagesDelayed),
      total: parseInt(attributes.Attributes.ApproximateNumberOfMessages) + 
             parseInt(attributes.Attributes.ApproximateNumberOfMessagesNotVisible),
      createdTimestamp: attributes.Attributes.CreatedTimestamp,
      lastModifiedTimestamp: attributes.Attributes.LastModifiedTimestamp
    };
  } catch (error) {
    console.error('Error getting queue attributes:', error.message);
    return null;
  }
}

async function sampleMessages(sampleSize = SAMPLE_SIZE) {
  const sampledMessages = [];
  let attempts = 0;
  const maxAttempts = Math.ceil(sampleSize / 10); // 10 messages per receive

  console.log(chalk.yellow(`\nSampling ${sampleSize} messages from queue...`));

  while (sampledMessages.length < sampleSize && attempts < maxAttempts) {
    attempts++;
    
    try {
      const command = new ReceiveMessageCommand({
        QueueUrl: QUEUE_URL,
        MaxNumberOfMessages: 10,
        VisibilityTimeout: 0, // Don't hide messages
        MessageAttributeNames: ['All'],
        WaitTimeSeconds: 2
      });
      const result = await sqs.send(command);

      if (result.Messages) {
        sampledMessages.push(...result.Messages);
        process.stdout.write(chalk.gray(`\rSampled: ${sampledMessages.length}/${sampleSize} messages`));
      }
    } catch (error) {
      console.error(chalk.red('\nError sampling messages:'), error.message);
      break;
    }
  }

  console.log(chalk.green(`\n✓ Sampled ${sampledMessages.length} messages\n`));
  return sampledMessages;
}

function analyzeMessage(message) {
  try {
    const body = JSON.parse(message.Body);
    
    // Check for SHAPE file messages
    if (body.type === 'shape-file') {
      messageTypes['shape-file'].count++;
      if (body.fileName) messageTypes['shape-file'].fileNames.add(body.fileName);
      if (body.uploadId) messageTypes['shape-file'].uploadIds.add(body.uploadId);
      if (body.uploadedAt) messageTypes['shape-file'].lastTimestamp = body.uploadedAt;
      return;
    }

    // Check for sensor messages
    const sensorType = body.sensorType || body.tokenGroup;
    
    if (sensorType && sensorType.includes('water-level')) {
      messageTypes['water-level'].count++;
      if (body.token) messageTypes['water-level'].tokens.add(body.token);
      if (body.data?.deviceId) messageTypes['water-level'].devices.add(body.data.deviceId);
      if (body.timestamp) messageTypes['water-level'].lastTimestamp = body.timestamp;
    } else if (sensorType && sensorType.includes('moisture')) {
      messageTypes['moisture'].count++;
      if (body.token) messageTypes['moisture'].tokens.add(body.token);
      if (body.data?.deviceId) messageTypes['moisture'].devices.add(body.data.deviceId);
      if (body.timestamp) messageTypes['moisture'].lastTimestamp = body.timestamp;
    } else {
      messageTypes['unknown'].count++;
      messageTypes['unknown'].details.push({
        sensorType: body.sensorType,
        token: body.token,
        type: body.type,
        keys: Object.keys(body)
      });
    }
  } catch (error) {
    messageTypes['unknown'].count++;
    messageTypes['unknown'].details.push({ error: 'Failed to parse message' });
  }
}

function printResults(queueStats, sampleSize) {
  console.log(chalk.blue.bold('\n📊 SQS Queue Analysis Report'));
  console.log(chalk.blue('═'.repeat(80)));

  // Overall Queue Statistics
  console.log(chalk.cyan('\n📈 Overall Queue Statistics:'));
  const overallTable = new Table({
    head: ['Metric', 'Value'],
    colWidths: [30, 20]
  });

  overallTable.push(
    ['Total Messages', chalk.yellow(queueStats.available.toLocaleString())],
    ['Messages Being Processed', chalk.green(queueStats.inFlight.toLocaleString())],
    ['Delayed Messages', chalk.gray(queueStats.delayed.toLocaleString())],
    ['Queue Created', new Date(parseInt(queueStats.createdTimestamp) * 1000).toLocaleString()],
    ['Last Modified', new Date(parseInt(queueStats.lastModifiedTimestamp) * 1000).toLocaleString()]
  );

  console.log(overallTable.toString());

  // Message Type Breakdown
  console.log(chalk.cyan('\n📝 Message Type Breakdown (from sample):'));
  const typeTable = new Table({
    head: ['Message Type', 'Count', '% of Sample', 'Estimated Total', 'Details'],
    colWidths: [20, 10, 15, 20, 40]
  });

  const totalSampled = Object.values(messageTypes).reduce((sum, type) => sum + type.count, 0);
  
  // Water Level Messages
  if (messageTypes['water-level'].count > 0) {
    const percentage = ((messageTypes['water-level'].count / totalSampled) * 100).toFixed(1);
    const estimated = Math.round((messageTypes['water-level'].count / totalSampled) * queueStats.available);
    typeTable.push([
      chalk.blue('💧 Water Level'),
      messageTypes['water-level'].count,
      `${percentage}%`,
      estimated.toLocaleString(),
      `${messageTypes['water-level'].devices.size} devices, ${messageTypes['water-level'].tokens.size} tokens`
    ]);
  }

  // Moisture Messages
  if (messageTypes['moisture'].count > 0) {
    const percentage = ((messageTypes['moisture'].count / totalSampled) * 100).toFixed(1);
    const estimated = Math.round((messageTypes['moisture'].count / totalSampled) * queueStats.available);
    typeTable.push([
      chalk.green('🌱 Moisture'),
      messageTypes['moisture'].count,
      `${percentage}%`,
      estimated.toLocaleString(),
      `${messageTypes['moisture'].devices.size} devices, ${messageTypes['moisture'].tokens.size} tokens`
    ]);
  }

  // SHAPE File Messages
  if (messageTypes['shape-file'].count > 0) {
    const percentage = ((messageTypes['shape-file'].count / totalSampled) * 100).toFixed(1);
    const estimated = Math.round((messageTypes['shape-file'].count / totalSampled) * queueStats.available);
    typeTable.push([
      chalk.magenta('📁 SHAPE Files'),
      messageTypes['shape-file'].count,
      `${percentage}%`,
      estimated.toLocaleString(),
      `${messageTypes['shape-file'].uploadIds.size} uploads, Files: ${Array.from(messageTypes['shape-file'].fileNames).join(', ')}`
    ]);
  }

  // Unknown Messages
  if (messageTypes['unknown'].count > 0) {
    const percentage = ((messageTypes['unknown'].count / totalSampled) * 100).toFixed(1);
    const estimated = Math.round((messageTypes['unknown'].count / totalSampled) * queueStats.available);
    typeTable.push([
      chalk.red('❓ Unknown'),
      messageTypes['unknown'].count,
      `${percentage}%`,
      estimated.toLocaleString(),
      `Various types`
    ]);
  }

  console.log(typeTable.toString());

  // Detailed Device Information
  if (messageTypes['water-level'].devices.size > 0 || messageTypes['moisture'].devices.size > 0) {
    console.log(chalk.cyan('\n🔧 Device Information:'));
    
    if (messageTypes['water-level'].devices.size > 0) {
      console.log(chalk.blue(`\nWater Level Devices (${messageTypes['water-level'].devices.size}):`));
      const devices = Array.from(messageTypes['water-level'].devices).slice(0, 10);
      console.log(devices.join(', '));
      if (messageTypes['water-level'].devices.size > 10) {
        console.log(chalk.gray(`... and ${messageTypes['water-level'].devices.size - 10} more`));
      }
    }

    if (messageTypes['moisture'].devices.size > 0) {
      console.log(chalk.green(`\nMoisture Devices (${messageTypes['moisture'].devices.size}):`));
      const devices = Array.from(messageTypes['moisture'].devices).slice(0, 10);
      console.log(devices.join(', '));
      if (messageTypes['moisture'].devices.size > 10) {
        console.log(chalk.gray(`... and ${messageTypes['moisture'].devices.size - 10} more`));
      }
    }
  }

  // SHAPE File Details
  if (messageTypes['shape-file'].uploadIds.size > 0) {
    console.log(chalk.cyan('\n📦 SHAPE File Uploads:'));
    console.log(chalk.magenta('\nUpload IDs:'));
    Array.from(messageTypes['shape-file'].uploadIds).forEach(id => {
      console.log(`  - ${id}`);
    });
    console.log(chalk.magenta('\nFile Names:'));
    Array.from(messageTypes['shape-file'].fileNames).forEach(name => {
      console.log(`  - ${name}`);
    });
  }

  // Summary
  console.log(chalk.cyan('\n📌 Summary:'));
  console.log(chalk.gray('─'.repeat(80)));
  console.log(`Total messages in queue: ${chalk.yellow.bold(queueStats.available.toLocaleString())}`);
  console.log(`Sample size analyzed: ${chalk.gray(totalSampled)} messages`);
  
  if (messageTypes['shape-file'].count > 0) {
    const estimatedShapeFiles = Math.round((messageTypes['shape-file'].count / totalSampled) * queueStats.available);
    console.log(chalk.magenta.bold(`\n🎯 Estimated SHAPE files in queue: ${estimatedShapeFiles}`));
  }

  // Processing estimates
  const processingRate = queueStats.inFlight > 0 ? 50 : 0; // messages per second estimate
  if (processingRate > 0 && queueStats.available > 0) {
    const estimatedMinutes = (queueStats.available / processingRate / 60).toFixed(1);
    console.log(chalk.green(`\n⏱️  Estimated time to process all messages: ${estimatedMinutes} minutes`));
  }
}

async function main() {
  try {
    // Check if chalk is installed
    if (!chalk) {
      console.log('\nNote: Install chalk for colored output: npm install chalk');
    }

    console.log(chalk.yellow.bold('🔍 Analyzing SQS Queue...'));
    
    // Get queue statistics
    const queueStats = await getQueueStatistics();
    if (!queueStats) {
      console.error(chalk.red('Failed to get queue statistics'));
      return;
    }

    // Sample messages if queue is not empty
    if (queueStats.available > 0) {
      const samplesToTake = Math.min(SAMPLE_SIZE, queueStats.available);
      const sampledMessages = await sampleMessages(samplesToTake);
      
      // Analyze each message
      sampledMessages.forEach(message => analyzeMessage(message));
      
      // Print results
      printResults(queueStats, samplesToTake);
    } else {
      console.log(chalk.green('\n✓ Queue is empty! No messages to analyze.'));
    }

  } catch (error) {
    console.error(chalk.red('\nError:'), error.message);
  }
}

// Check if cli-table3 is available
try {
  require('cli-table3');
  require('chalk');
  main();
} catch (e) {
  console.log('\nInstalling required packages...');
  require('child_process').execSync('npm install cli-table3 chalk', { stdio: 'inherit' });
  console.log('\nPackages installed. Please run the script again.');
}