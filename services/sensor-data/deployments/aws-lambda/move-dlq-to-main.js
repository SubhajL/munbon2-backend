const AWS = require('aws-sdk');

AWS.config.update({ region: 'ap-southeast-1' });
const sqs = new AWS.SQS();

async function moveDLQMessages() {
  const dlqUrl = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-dlq';
  const mainQueueUrl = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';
  
  console.log('Moving messages from DLQ to main queue...\n');
  
  let totalMoved = 0;
  let batchCount = 0;
  
  while (true) {
    try {
      // Receive messages from DLQ
      const { Messages } = await sqs.receiveMessage({
        QueueUrl: dlqUrl,
        MaxNumberOfMessages: 10,
        VisibilityTimeout: 300, // 5 minutes to process
        WaitTimeSeconds: 1
      }).promise();
      
      if (!Messages || Messages.length === 0) {
        console.log('\nNo more messages in DLQ');
        break;
      }
      
      // Prepare messages for batch send
      const entries = Messages.map((msg, idx) => ({
        Id: `msg-${idx}`,
        MessageBody: msg.Body,
        MessageAttributes: msg.MessageAttributes || {}
      }));
      
      // Send to main queue
      await sqs.sendMessageBatch({
        QueueUrl: mainQueueUrl,
        Entries: entries
      }).promise();
      
      // Delete from DLQ
      const deleteEntries = Messages.map((msg) => ({
        Id: msg.MessageId,
        ReceiptHandle: msg.ReceiptHandle
      }));
      
      await sqs.deleteMessageBatch({
        QueueUrl: dlqUrl,
        Entries: deleteEntries
      }).promise();
      
      totalMoved += Messages.length;
      batchCount++;
      
      process.stdout.write(`\rMoved ${totalMoved} messages (${batchCount} batches)...`);
      
    } catch (error) {
      console.error('\nError:', error);
      break;
    }
  }
  
  console.log(`\n\nCompleted! Moved ${totalMoved} messages from DLQ to main queue.`);
  
  // Check final queue states
  const dlqAttrs = await sqs.getQueueAttributes({
    QueueUrl: dlqUrl,
    AttributeNames: ['ApproximateNumberOfMessages']
  }).promise();
  
  const mainAttrs = await sqs.getQueueAttributes({
    QueueUrl: mainQueueUrl,
    AttributeNames: ['ApproximateNumberOfMessages']
  }).promise();
  
  console.log(`\nFinal state:`);
  console.log(`  DLQ messages: ${dlqAttrs.Attributes.ApproximateNumberOfMessages}`);
  console.log(`  Main queue messages: ${mainAttrs.Attributes.ApproximateNumberOfMessages}`);
}

// Add confirmation prompt
const readline = require('readline');
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

rl.question('This will move all messages from DLQ to main queue. Continue? (y/n): ', (answer) => {
  if (answer.toLowerCase() === 'y') {
    moveDLQMessages().catch(console.error);
  } else {
    console.log('Cancelled');
    process.exit(0);
  }
  rl.close();
});