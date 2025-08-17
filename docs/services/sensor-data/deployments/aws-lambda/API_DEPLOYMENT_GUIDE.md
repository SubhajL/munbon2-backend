# AWS Free Tier Deployment Guide for Sensor Data API

## Overview
This guide explains how to deploy the Sensor Data API to AWS Free Tier alongside the existing Lambda functions for data ingestion.

## Current Architecture
- **Data Ingestion**: AWS Lambda + API Gateway (already implemented)
- **Data Storage**: Local TimescaleDB
- **API Server**: Express.js running locally on port 3001

## Proposed AWS Free Tier Architecture

### Option 1: Lambda Functions (Recommended for Free Tier)
Convert REST API endpoints to Lambda functions similar to the existing data ingestion setup.

**Pros:**
- 1 million free requests per month
- 400,000 GB-seconds of compute time per month
- No need to manage servers
- Auto-scaling built-in

**Cons:**
- 15-minute maximum execution time
- Cold start latency
- Need to refactor code for Lambda

**Implementation:**
```typescript
// handler.ts for API endpoints
import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import { createConnection } from './db';
import { waterLevelHandlers } from './handlers/water-level';
import { moistureHandlers } from './handlers/moisture';

export const handler = async (
  event: APIGatewayProxyEvent
): Promise<APIGatewayProxyResult> => {
  const path = event.path;
  const method = event.httpMethod;
  
  // Route to appropriate handler
  if (path.startsWith('/api/v1/water-levels')) {
    return waterLevelHandlers(event);
  } else if (path.startsWith('/api/v1/moisture')) {
    return moistureHandlers(event);
  }
  
  return {
    statusCode: 404,
    body: JSON.stringify({ error: 'Not found' })
  };
};
```

### Option 2: EC2 t2.micro Instance
Run the Express.js server on a free tier EC2 instance.

**Pros:**
- 750 hours per month (enough for 1 instance 24/7)
- Full control over the environment
- Can run existing code with minimal changes

**Cons:**
- Only 1 vCPU and 1 GB RAM
- Limited to 30 GB storage
- Need to manage server updates and security

### Option 3: Elastic Beanstalk
Deploy using AWS Elastic Beanstalk with t2.micro instance.

**Pros:**
- Easier deployment than raw EC2
- Auto-handles load balancing and scaling (within free tier limits)
- Built-in monitoring

**Cons:**
- Same resource limits as EC2
- Additional services may exceed free tier

## Database Considerations

### Current Issue
TimescaleDB is running locally, not accessible from AWS.

### Solutions:

1. **Amazon RDS PostgreSQL** (Partially Free)
   - 750 hours of db.t2.micro instance
   - 20 GB storage
   - But NO TimescaleDB extension in RDS
   - Would need to modify queries

2. **Self-hosted on EC2** (Limited)
   - Install PostgreSQL + TimescaleDB on t2.micro
   - Very limited resources for database

3. **Hybrid Approach** (Recommended)
   - Keep TimescaleDB local or on a dedicated server
   - Use AWS Lambda/EC2 as API layer only
   - Secure connection via VPN or SSH tunnel

## Recommended Migration Path

### Phase 1: Lambda API Endpoints
1. Create Lambda functions for read-only API endpoints
2. Use existing API Gateway setup
3. Connect to TimescaleDB via secure tunnel

### Phase 2: Caching Layer
1. Use ElastiCache Redis (free tier: 750 hours)
2. Cache frequently accessed data
3. Reduce database load

### Phase 3: Static Data Delivery
1. Generate periodic data snapshots
2. Store in S3 (5 GB free)
3. Serve via CloudFront CDN (50 GB transfer free)

## Cost Optimization Tips

1. **API Gateway Caching**: Reduce Lambda invocations
2. **Response Compression**: Minimize data transfer
3. **Batch Requests**: Combine multiple queries
4. **Scheduled Aggregations**: Pre-compute heavy queries

## Limitations to Consider

1. **Concurrent Executions**: Lambda limits concurrent executions
2. **Response Size**: API Gateway limits response to 10 MB
3. **Timeout**: 30 seconds for API Gateway
4. **Database Connections**: Lambda functions can exhaust connection pools

## Implementation Steps

1. **Refactor Code for Lambda**
   ```bash
   cd services/sensor-data/deployments/aws-lambda
   npm install @types/aws-lambda
   ```

2. **Create Serverless Configuration**
   ```yaml
   # serverless.yml addition
   functions:
     sensorDataApi:
       handler: api-handler.handler
       events:
         - http:
             path: /api/v1/{proxy+}
             method: ANY
             cors: true
   ```

3. **Deploy**
   ```bash
   serverless deploy
   ```

## Alternative: Keep API Local
If AWS Free Tier is too limiting:
- Use ngrok or similar for temporary public access
- Set up a lightweight VPS (DigitalOcean, Linode) for $5/month
- Use Cloudflare Tunnel for secure access to local server

## Conclusion
AWS Free Tier is feasible for the API but requires:
- Architectural changes (serverless)
- Database connectivity solution
- Acceptance of performance limitations
- Careful monitoring to avoid charges

The existing Lambda setup for data ingestion shows this approach works, but consider if the limitations align with your performance requirements.