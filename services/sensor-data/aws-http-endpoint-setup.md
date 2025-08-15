# AWS API Gateway HTTP Endpoint for Legacy Moisture Sensors

## Overview
Create an HTTP-only endpoint in AWS API Gateway for devices that can't handle modern HTTPS/TLS.

## Step 1: Create Lambda Function (if not already exists)

```javascript
// lambda-moisture-http-handler.js
exports.handler = async (event) => {
    try {
        const token = event.pathParameters.token;
        const body = JSON.parse(event.body);
        
        // Log for debugging
        console.log('Received moisture data:', {
            token,
            gateway_id: body.gateway_id,
            sensor_count: body.sensor ? body.sensor.length : 0
        });
        
        // Put message in SQS queue
        const AWS = require('aws-sdk');
        const sqs = new AWS.SQS();
        
        const params = {
            QueueUrl: process.env.SQS_QUEUE_URL,
            MessageBody: JSON.stringify({
                token,
                data: body,
                timestamp: new Date().toISOString()
            })
        };
        
        await sqs.sendMessage(params).promise();
        
        return {
            statusCode: 200,
            body: JSON.stringify({
                status: 'success',
                message: 'Telemetry received',
                timestamp: new Date().toISOString()
            })
        };
    } catch (error) {
        console.error('Error:', error);
        return {
            statusCode: 500,
            body: JSON.stringify({ error: 'Internal server error' })
        };
    }
};
```

## Step 2: Create HTTP API Gateway

### Using AWS CLI:

```bash
# Create HTTP API (not REST API)
aws apigatewayv2 create-api \
  --name "munbon-moisture-http" \
  --protocol-type HTTP \
  --description "HTTP endpoint for legacy moisture sensors"

# Note the API ID from response
API_ID=<your-api-id>

# Create integration with Lambda
aws apigatewayv2 create-integration \
  --api-id $API_ID \
  --integration-type AWS_PROXY \
  --integration-uri arn:aws:lambda:ap-southeast-1:YOUR_ACCOUNT:function:moisture-http-handler \
  --payload-format-version 2.0

# Create route
aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "POST /api/v1/{token}/telemetry" \
  --target "integrations/$INTEGRATION_ID"

# Create stage
aws apigatewayv2 create-stage \
  --api-id $API_ID \
  --stage-name "prod" \
  --auto-deploy
```

### Using AWS Console:

1. **Go to API Gateway Console**
   - Choose "Build" under **HTTP API** (not REST API)
   - Name: `munbon-moisture-http`

2. **Configure Routes**
   - Method: POST
   - Path: `/api/v1/{token}/telemetry`
   - Integration: Lambda function

3. **Configure Stages**
   - Stage name: `prod`
   - Auto-deploy: Yes

4. **IMPORTANT: Disable HTTPS**
   - In the API settings, you'll get an endpoint like:
     `https://abc123.execute-api.ap-southeast-1.amazonaws.com`
   - For HTTP-only, you need to use CloudFormation or CDK

## Step 3: Alternative - Use Application Load Balancer (ALB)

Since API Gateway always uses HTTPS, use ALB for true HTTP:

```yaml
# CloudFormation template for HTTP-only ALB
AWSTemplateFormatVersion: '2010-09-09'
Resources:
  HTTPLoadBalancer:
    Type: AWS::ElasticLoadBalancingV2::LoadBalancer
    Properties:
      Name: munbon-moisture-http-alb
      Type: application
      Scheme: internet-facing
      IpAddressType: ipv4
      
  HTTPListener:
    Type: AWS::ElasticLoadBalancingV2::Listener
    Properties:
      LoadBalancerArn: !Ref HTTPLoadBalancer
      Port: 80
      Protocol: HTTP  # HTTP only, no HTTPS
      DefaultActions:
        - Type: forward
          TargetGroupArn: !Ref LambdaTargetGroup
          
  LambdaTargetGroup:
    Type: AWS::ElasticLoadBalancingV2::TargetGroup
    Properties:
      TargetType: lambda
      Targets:
        - Id: !GetAtt MoistureLambda.Arn
```

## Step 4: Simplest Solution - EC2 with HTTP Server

```bash
# On a small EC2 instance (t2.micro)
#!/bin/bash

# Install Node.js
curl -sL https://rpm.nodesource.com/setup_18.x | sudo bash -
sudo yum install nodejs -y

# Create HTTP relay server
cat > /home/ec2-user/moisture-http-relay.js << 'EOF'
const express = require('express');
const AWS = require('aws-sdk');
const app = express();
const sqs = new AWS.SQS();

app.use(express.json());

app.post('/api/v1/:token/telemetry', async (req, res) => {
  try {
    await sqs.sendMessage({
      QueueUrl: process.env.SQS_QUEUE_URL,
      MessageBody: JSON.stringify({
        token: req.params.token,
        data: req.body,
        timestamp: new Date().toISOString()
      })
    }).promise();
    
    res.json({
      status: 'success',
      message: 'Telemetry received',
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

app.listen(80, '0.0.0.0', () => {
  console.log('HTTP server running on port 80');
});
EOF

# Run with PM2
npm install -g pm2 express aws-sdk
pm2 start moisture-http-relay.js
```

## Recommendation

For your legacy devices, I recommend:

1. **Quick Solution**: Use a small EC2 instance with HTTP on port 80
   - Cost: ~$5/month for t2.micro
   - Give manufacturer: `http://your-ec2-ip/api/v1/munbon-m2m-moisture/telemetry`

2. **Scalable Solution**: Use Network Load Balancer (NLB) with TCP passthrough
   - NLB can handle HTTP without forcing HTTPS
   - Can scale automatically

The EC2 approach is simplest and will definitely work with your legacy devices!