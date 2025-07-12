// Example: Unified API on Oracle Cloud sending data to AWS

const { SQSClient, SendMessageCommand } = require('@aws-sdk/client-sqs');
const axios = require('axios');

// Configure AWS SDK with credentials
const sqsClient = new SQSClient({ 
  region: 'ap-southeast-1',
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
  }
});

class AWSIntegration {
  // Option 1: Send to SQS Queue
  async sendToSQS(data) {
    try {
      const command = new SendMessageCommand({
        QueueUrl: 'https://sqs.ap-southeast-1.amazonaws.com/YOUR_ACCOUNT/sensor-data-queue',
        MessageBody: JSON.stringify(data),
        MessageAttributes: {
          source: {
            DataType: 'String',
            StringValue: 'oracle-unified-api'
          }
        }
      });
      
      const response = await sqsClient.send(command);
      console.log('Sent to SQS:', response.MessageId);
      return response;
    } catch (error) {
      console.error('SQS Error:', error);
      throw error;
    }
  }

  // Option 2: Call Lambda via API Gateway
  async callLambdaAPI(endpoint, data) {
    try {
      const response = await axios.post(
        `https://your-api-id.execute-api.ap-southeast-1.amazonaws.com/prod${endpoint}`,
        data,
        {
          headers: {
            'X-API-Key': process.env.AWS_API_KEY,
            'Content-Type': 'application/json'
          }
        }
      );
      return response.data;
    } catch (error) {
      console.error('Lambda API Error:', error);
      throw error;
    }
  }

  // Option 3: Direct Lambda Invocation
  async invokeLambda(functionName, payload) {
    const { LambdaClient, InvokeCommand } = require('@aws-sdk/client-lambda');
    
    const lambdaClient = new LambdaClient({ 
      region: 'ap-southeast-1',
      credentials: {
        accessKeyId: process.env.AWS_ACCESS_KEY_ID,
        secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
      }
    });

    const command = new InvokeCommand({
      FunctionName: functionName,
      Payload: JSON.stringify(payload),
      InvocationType: 'Event' // Async invocation
    });

    const response = await lambdaClient.send(command);
    return response;
  }
}

// Usage in your unified API routes
app.post('/api/v1/sensors/data', async (req, res) => {
  const aws = new AWSIntegration();
  
  try {
    // Process data locally
    const processedData = await processServiceData(req.body);
    
    // Send to AWS for further processing
    await aws.sendToSQS(processedData);
    
    res.json({ success: true, message: 'Data queued for processing' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = AWSIntegration;