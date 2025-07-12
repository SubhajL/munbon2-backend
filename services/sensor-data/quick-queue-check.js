const { SQSClient, GetQueueAttributesCommand } = require('@aws-sdk/client-sqs');
const sqs = new SQSClient({ region: 'ap-southeast-1' });

async function quickCheck() {
  try {
    const command = new GetQueueAttributesCommand({
      QueueUrl: 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue',
      AttributeNames: ['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible']
    });
    const result = await sqs.send(command);
    
    console.log(`Messages in queue: ${result.Attributes.ApproximateNumberOfMessages}`);
    console.log(`Messages being processed: ${result.Attributes.ApproximateNumberOfMessagesNotVisible}`);
    
    // Calculate processing progress
    const initial = 3103;
    const current = parseInt(result.Attributes.ApproximateNumberOfMessages);
    const processed = initial - current;
    const percentage = ((processed / initial) * 100).toFixed(1);
    
    console.log(`\nProgress: ${processed} / ${initial} messages processed (${percentage}%)`);
    
    if (current < 100) {
      console.log('\n🎯 Your SHAPE file message should be processed soon!');
    } else {
      const estimatedPosition = current - 10; // Your message was near the end
      console.log(`\n⏳ Approximately ${estimatedPosition} messages ahead of your SHAPE file`);
    }
    
  } catch (error) {
    console.error('Error:', error.message);
  }
}

quickCheck();