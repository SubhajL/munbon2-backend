const AWS = require('aws-sdk');

AWS.config.update({ region: 'ap-southeast-1' });
const sqs = new AWS.SQS();
const dynamodb = new AWS.DynamoDB.DocumentClient();

async function traceShapeFile() {
  const uploadId = '4db50588-1762-4830-b09f-ae5e2ab4dbf9';
  
  console.log(`Tracing shape file upload: ${uploadId}\n`);
  
  // Check DynamoDB if table exists
  const tableName = 'munbon-shape-files-dev';
  try {
    const result = await dynamodb.get({
      TableName: tableName,
      Key: { id: uploadId }
    }).promise();
    
    if (result.Item) {
      console.log('Found in DynamoDB:');
      console.log(JSON.stringify(result.Item, null, 2));
    } else {
      console.log('Not found in DynamoDB table');
    }
  } catch (error) {
    if (error.code === 'ResourceNotFoundException') {
      console.log('DynamoDB table does not exist');
    } else {
      console.log('DynamoDB error:', error.message);
    }
  }
  
  // Check for messages with this upload ID
  console.log('\nSearching queues for this upload ID...');
  
  const mainQueueUrl = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';
  const dlqUrl = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-dlq';
  
  // Sample messages from both queues
  for (const [queueName, queueUrl] of [['Main Queue', mainQueueUrl], ['DLQ', dlqUrl]]) {
    console.log(`\nChecking ${queueName}...`);
    let found = false;
    
    for (let i = 0; i < 20 && !found; i++) {
      const { Messages } = await sqs.receiveMessage({
        QueueUrl: queueUrl,
        MaxNumberOfMessages: 10,
        VisibilityTimeout: 0,
        WaitTimeSeconds: 1
      }).promise();
      
      if (Messages) {
        for (const msg of Messages) {
          try {
            const body = JSON.parse(msg.Body);
            if (body.uploadId === uploadId || 
                body.s3Key?.includes(uploadId) ||
                body.fileName === 'ridplan_rice_20250702.zip') {
              console.log('FOUND MESSAGE:');
              console.log(JSON.stringify(body, null, 2));
              found = true;
              break;
            }
          } catch (e) {}
        }
      }
    }
    
    if (!found) {
      console.log('Not found in this queue');
    }
  }
}

traceShapeFile().catch(console.error);