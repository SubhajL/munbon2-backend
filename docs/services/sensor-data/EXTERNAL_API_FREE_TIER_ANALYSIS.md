# External Data API - Free Tier Analysis

## External API Request Patterns

### Expected Usage
```
External Users → API Gateway → Lambda → Oracle Unified API
   (RID/TMD)      (Public)     (Proxy)    (Data Source)
```

### Realistic External API Usage

| Client | Endpoints Used | Frequency | Monthly Requests |
|--------|---------------|-----------|------------------|
| **RID System** | water-levels/latest | Every hour | 720 |
| | water-levels/timeseries | 2x daily | 60 |
| | water-levels/statistics | 1x daily | 30 |
| **TMD** | aos/latest | Every 30 min | 1,440 |
| | aos/statistics | 1x daily | 30 |
| **Universities** | All endpoints | 10x daily | 300 |
| **Testing/Dev** | All endpoints | Variable | ~500 |

**Total Monthly External Requests: ~3,080**

## Free Tier Coverage

| Service | Free Tier Limit | External API Usage | Status |
|---------|----------------|-------------------|---------|
| **API Gateway** | 1M requests/month (12 months) | ~3,080 | ✅ **0.3% used** |
| **Lambda Proxy** | 1M requests/month (forever) | ~3,080 | ✅ **0.3% used** |
| **Oracle → AWS** | 10TB bandwidth/month | <1GB | ✅ **0.01% used** |

## After 12 Months (API Gateway)

```
Cost = 3,080 requests × $3.50 per million
     = $0.01/month
```

## Scaling Scenarios

### Scenario 1: Normal Growth (10x)
- 30,000 requests/month
- Still only 3% of free tier
- Cost after 12 months: $0.10/month

### Scenario 2: High Usage (100x)
- 300,000 requests/month
- Still only 30% of free tier
- Cost after 12 months: $1.05/month

### Scenario 3: Extreme Usage (300x)
- 1,000,000 requests/month
- Reaching free tier limit
- Cost after 12 months: $3.50/month

## Data Transfer Calculation

### Typical Response Sizes
- Latest reading: ~2KB
- Time series (day): ~50KB
- Statistics: ~5KB

### Monthly Data Transfer
```
Average response: 10KB
Monthly requests: 3,080
Total transfer: 30.8MB/month

Oracle → Internet: FREE (10TB limit)
AWS → Internet: FREE (100GB limit for 12 months)
```

## Implementation for Free Tier

### 1. Efficient Lambda Proxy
```javascript
// Lambda function connecting to Oracle
exports.handler = async (event) => {
  const endpoint = process.env.ORACLE_ENDPOINT; // from Parameter Store
  
  // Forward request to Oracle
  const response = await fetch(`${endpoint}${event.path}`, {
    headers: {
      'X-Internal-Key': process.env.INTERNAL_KEY
    }
  });
  
  return {
    statusCode: 200,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'public, max-age=300' // 5 min cache
    },
    body: await response.text()
  };
};
```

### 2. Caching Strategy
```javascript
// Add caching headers to reduce requests
app.get('/api/v1/public/water-levels/latest', (req, res) => {
  res.set({
    'Cache-Control': 'public, max-age=300', // 5 minutes
    'ETag': generateETag(data),
    'Last-Modified': lastModified
  });
  res.json(data);
});
```

### 3. Rate Limiting (Optional)
```javascript
const rateLimit = require('express-rate-limit');

const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each API key to 100 requests per window
  keyGenerator: (req) => req.headers['x-api-key']
});

app.use('/api/v1/public', limiter);
```

## Cost Optimization Tips

1. **Enable CloudFront** (Optional)
   - 1TB/month free tier
   - Cache responses at edge
   - Reduce Lambda invocations

2. **Use HTTP Caching**
   - ETags for conditional requests
   - Cache-Control headers
   - Reduces duplicate data transfer

3. **Batch Endpoints** (If needed)
   ```javascript
   // Single endpoint for multiple data types
   GET /api/v1/public/batch?types=water,moisture,aos
   ```

## Monitoring Usage

```bash
# Check API Gateway usage
aws apigateway get-usage \
  --usage-plan-id YOUR_PLAN_ID \
  --start-date 2025-07-01 \
  --end-date 2025-07-31

# Check Lambda invocations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=munbon-data-api-prod-waterLevelLatest \
  --statistics Sum \
  --start-time 2025-07-01T00:00:00Z \
  --end-time 2025-07-31T23:59:59Z \
  --period 2592000
```

## Conclusion

For external data API requests:
- **Current usage (~3K/month)**: Practically FREE forever
- **Even at 100x growth**: Still under $1/month
- **No limitations** between Oracle ↔ AWS connection
- **Plenty of headroom** in free tier limits

The external API can run essentially free on both Oracle and AWS free tiers!