# Oracle + AWS Free Tier Analysis

## Typical Monthly Usage for Munbon Project

### Sensor Data Flow
```
Sensors → AWS Lambda → SQS → Lambda → Oracle API
         (Ingestion)        (Process)  (Store/Query)
```

### Estimated Usage
- **Sensors**: ~100 devices
- **Data Frequency**: Every 5 minutes
- **Monthly Messages**: 100 × 288/day × 30 = 864,000

### Free Tier Coverage

| Service | Free Tier | Munbon Usage | Within Limit? |
|---------|-----------|--------------|---------------|
| **Lambda Requests** | 1M/month | ~864K | ✅ YES |
| **Lambda Compute** | 400K GB-sec | ~50K GB-sec | ✅ YES |
| **SQS Requests** | 1M/month | ~864K | ✅ YES |
| **API Gateway** | 1M/month | ~100K (queries) | ✅ YES |
| **Oracle VM** | 24/7 | 24/7 | ✅ YES |

## Limitations to Consider

### 1. **Network Transfer**
```yaml
AWS → Internet: 
  - First 100GB/month: FREE (12 months)
  - After: $0.09/GB
  
Oracle → AWS:
  - Ingress: Always FREE
  - Oracle egress: 10TB/month FREE
```

### 2. **Request Patterns**
```yaml
Good Pattern (Within Free Tier):
  - Batch messages to reduce requests
  - Cache frequently accessed data
  - Use SQS for async processing

Bad Pattern (Exceeds Free Tier):
  - Individual request per sensor reading
  - No caching
  - Synchronous processing
```

### 3. **Data Storage**
```yaml
Oracle Block Storage: 200GB FREE
AWS S3: 5GB FREE (12 months)
Solution: Store data in Oracle, metadata in AWS
```

## Optimization Strategies

### 1. Batch Processing
```javascript
// Instead of sending each reading separately
// Batch multiple readings into one SQS message
const batchMessage = {
  timestamp: new Date(),
  readings: [
    { sensor_id: 'S001', value: 25.5 },
    { sensor_id: 'S002', value: 26.1 },
    // ... up to 10 readings
  ]
};

// This reduces SQS requests by 10x
await sqs.sendMessage({
  QueueUrl: queueUrl,
  MessageBody: JSON.stringify(batchMessage)
});
```

### 2. Smart Caching
```javascript
// Cache in Oracle VM memory
const cache = new Map();
const CACHE_TTL = 300000; // 5 minutes

app.get('/api/v1/sensors/latest', async (req, res) => {
  const cacheKey = 'latest-readings';
  const cached = cache.get(cacheKey);
  
  if (cached && cached.expires > Date.now()) {
    return res.json(cached.data);
  }
  
  // Fetch from database
  const data = await fetchLatestReadings();
  
  // Cache the result
  cache.set(cacheKey, {
    data,
    expires: Date.now() + CACHE_TTL
  });
  
  res.json(data);
});
```

### 3. Connection Pooling
```javascript
// Reuse connections to reduce overhead
const { Pool } = require('pg');

const pool = new Pool({
  max: 20, // max connections
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

// This prevents creating new connections for each request
```

## Cost Estimation

### Staying Within Free Tier
```
Monthly Costs:
- Oracle VM: $0 (forever free)
- Lambda: $0 (under 1M requests)
- SQS: $0 (under 1M requests)
- API Gateway: $0 (first 12 months)
- Data Transfer: $0 (under 100GB)

Total: $0/month
```

### After 12 Months
```
- API Gateway: ~$0.35 (100K requests)
- Everything else: $0

Total: <$1/month
```

## Architecture for Free Tier

```
[Sensors] → [Lambda Ingestion] → [SQS Queue] → [Lambda Processor]
                                                        ↓
                                               [Oracle Unified API]
                                                        ↓
                                               [TimescaleDB/MSSQL]
                                                        
[External Users] → [API Gateway] → [Lambda Proxy] → [Oracle API]
```

## Recommendations

1. **Use SQS for Buffering**
   - Prevents Lambda timeout issues
   - Allows batch processing
   - Stays within free tier

2. **Cache Aggressively**
   - Cache in Oracle VM RAM
   - Cache in Lambda memory
   - Reduce database queries

3. **Monitor Usage**
   ```bash
   # AWS CLI commands to check usage
   aws lambda list-functions --query 'Functions[*].[FunctionName,CodeSize]'
   aws cloudwatch get-metric-statistics \
     --namespace AWS/Lambda \
     --metric-name Invocations \
     --dimensions Name=FunctionName,Value=your-function \
     --statistics Sum \
     --start-time 2025-07-01T00:00:00Z \
     --end-time 2025-07-31T23:59:59Z \
     --period 2592000
   ```

4. **Set Billing Alerts**
   ```bash
   # Set alert at 80% of free tier
   aws cloudwatch put-metric-alarm \
     --alarm-name lambda-free-tier-warning \
     --alarm-description "Alert when approaching Lambda free tier" \
     --metric-name Invocations \
     --namespace AWS/Lambda \
     --statistic Sum \
     --period 2592000 \
     --threshold 800000 \
     --comparison-operator GreaterThanThreshold
   ```

## Conclusion

✅ **YES, both Oracle and AWS free tiers work together perfectly!**

With proper optimization (batching, caching), the Munbon project can run entirely on free tier resources from both Oracle and AWS.