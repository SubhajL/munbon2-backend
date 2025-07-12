const AWS = require('aws-sdk');
AWS.config.update({ region: 'ap-southeast-1' });
const sqs = new AWS.SQS();

async function moveDLQToMain() {
  const dlqUrl = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-gis-shapefile-dlq';
  const mainUrl = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-gis-shapefile-queue';
  
  console.log('Moving messages from DLQ to main queue...');
  
  let moved = 0;
  while (true) {
    const { Messages } = await sqs.receiveMessage({
      QueueUrl: dlqUrl,
      MaxNumberOfMessages: 10,
      VisibilityTimeout: 60
    }).promise();
    
    if (!Messages || Messages.length === 0) break;
    
    for (const msg of Messages) {
      const body = JSON.parse(msg.Body);
      console.log(`Moving message: ${body.uploadId} - ${body.fileName}`);
      
      // Send to main queue
      await sqs.sendMessage({
        QueueUrl: mainUrl,
        MessageBody: msg.Body,
        MessageAttributes: msg.MessageAttributes
      }).promise();
      
      // Delete from DLQ
      await sqs.deleteMessage({
        QueueUrl: dlqUrl,
        ReceiptHandle: msg.ReceiptHandle
      }).promise();
      
      moved++;
    }
  }
  
  console.log(`Moved ${moved} messages from DLQ to main queue`);
}

moveDLQToMain().catch(console.error);