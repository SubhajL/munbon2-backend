const { SQSClient, GetQueueAttributesCommand } = require('@aws-sdk/client-sqs');

// Configure AWS SDK v3
const sqs = new SQSClient({ region: 'ap-southeast-1' });

const QUEUE_URL = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';

let previousCount = null;
let startTime = Date.now();
let initialCount = null;

async function checkProgress() {
  try {
    const command = new GetQueueAttributesCommand({
      QueueUrl: QUEUE_URL,
      AttributeNames: ['All']
    });
    const attributes = await sqs.send(command);

    const currentCount = parseInt(attributes.Attributes.ApproximateNumberOfMessages);
    const inFlight = parseInt(attributes.Attributes.ApproximateNumberOfMessagesNotVisible);
    const delayed = parseInt(attributes.Attributes.ApproximateNumberOfMessagesDelayed);
    
    if (initialCount === null) {
      initialCount = currentCount;
    }

    const now = new Date().toLocaleTimeString();
    const elapsedMinutes = ((Date.now() - startTime) / 1000 / 60).toFixed(1);
    
    console.log(`[${now}] Queue Status:`);
    console.log(`  Messages Available: ${currentCount}`);
    console.log(`  Messages In Flight: ${inFlight} (being processed)`);
    console.log(`  Messages Delayed: ${delayed}`);
    
    if (previousCount !== null) {
      const processed = previousCount - currentCount;
      const totalProcessed = initialCount - currentCount;
      const rate = processed > 0 ? processed : 0;
      
      console.log(`  Messages processed in last interval: ${rate}`);
      console.log(`  Total processed: ${totalProcessed} (${((totalProcessed/initialCount)*100).toFixed(1)}%)`);
      
      if (rate > 0) {
        const remainingMinutes = (currentCount / rate / 60).toFixed(1);
        console.log(`  Estimated time to clear queue: ${remainingMinutes} minutes`);
      }
    }
    
    console.log(`  Running for: ${elapsedMinutes} minutes`);
    console.log('---');
    
    previousCount = currentCount;
    
    // Stop if queue is empty
    if (currentCount === 0) {
      console.log('✅ Queue is now empty!');
      process.exit(0);
    }
    
  } catch (error) {
    console.error('Error checking queue:', error.message);
  }
}

// Check immediately, then every 10 seconds
console.log('Monitoring SQS queue progress...');
console.log('Initial check at:', new Date().toLocaleString());
console.log('---');

checkProgress();
setInterval(checkProgress, 10000); // Check every 10 seconds

// Handle Ctrl+C gracefully
process.on('SIGINT', () => {
  console.log('\nMonitoring stopped.');
  process.exit(0);
});