# AWS Lambda Data Exposure API

This extends the existing IoT data ingestion infrastructure to expose water level, moisture, and weather data through AWS API Gateway + Lambda.

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌────────────┐
│   External  │────▶│ API Gateway  │────▶│   Lambda    │────▶│ TimescaleDB│
│   Systems   │     │  (Public)    │     │  Functions  │     │    (RDS)   │
└─────────────┘     └──────────────┘     └─────────────┘     └────────────┘
       │                    │                     │                   ▲
       │                    │                     │                   │
   X-API-Key           /api/v1/public/*      Read Data          Sensor Data
```

## 🚀 Quick Deployment

### 1. Prerequisites
- AWS CLI configured with credentials
- Node.js 18+ installed
- Serverless Framework (`npm install -g serverless`)

### 2. Configure Database Access

#### Option A: Use RDS Free Tier (Recommended)
```bash
# Create RDS PostgreSQL instance (free tier)
aws rds create-db-instance \
  --db-instance-identifier munbon-sensor-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15.4 \
  --allocated-storage 20 \
  --master-username postgres \
  --master-user-password your-secure-password \
  --publicly-accessible \
  --backup-retention-period 0

# Wait for instance to be available, then get endpoint
aws rds describe-db-instances \
  --db-instance-identifier munbon-sensor-db \
  --query 'DBInstances[0].Endpoint.Address'
```

#### Option B: Use External Database
If you have TimescaleDB running elsewhere (e.g., on EC2, DigitalOcean), just update the connection details.

### 3. Set Environment Variables
```bash
# Create .env file
cat > .env << EOF
# Database Configuration
DB_HOST=your-rds-endpoint.amazonaws.com
DB_PORT=5432
DB_NAME=sensor_data
DB_USER=postgres
DB_PASSWORD=your-secure-password

# API Keys (comma-separated)
EXTERNAL_API_KEYS=rid-ms-prod-abc123,tmd-weather-xyz789,university-research-def456
EOF
```

### 4. Deploy to AWS
```bash
# Deploy both ingestion and data APIs
./deploy-all.sh
```

## 📋 API Endpoints

After deployment, you'll get endpoints like:

```
https://abc123.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/latest
https://abc123.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/moisture/latest
https://abc123.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/latest
```

## 🔑 API Key Management

### Generate API Keys
```javascript
// generate-api-keys.js
const crypto = require('crypto');

const organizations = [
  { name: 'rid-ms-prod', org: 'Royal Irrigation Department' },
  { name: 'tmd-weather', org: 'Thai Meteorological Department' },
  { name: 'university-research', org: 'Kasetsart University' },
  { name: 'mobile-app', org: 'Munbon Mobile' },
];

organizations.forEach(({ name, org }) => {
  const key = `${name}-${crypto.randomBytes(16).toString('hex')}`;
  console.log(`${org}: ${key}`);
});
```

### Update API Keys
```bash
# Update Lambda environment variables
aws lambda update-function-configuration \
  --function-name munbon-data-api-prod-waterLevelLatest \
  --environment Variables="{EXTERNAL_API_KEYS='key1,key2,key3'}"
```

## 📊 Example Usage

### cURL
```bash
# Get latest water levels
curl -H "X-API-Key: rid-ms-prod-abc123" \
  https://your-api.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/latest

# Get moisture data for specific date (Buddhist calendar)
curl -H "X-API-Key: rid-ms-prod-abc123" \
  "https://your-api.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/moisture/timeseries?date=12/06/2568"
```

### Python
```python
import requests

API_KEY = "rid-ms-prod-abc123"
BASE_URL = "https://your-api.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public"

# Get latest AOS weather data
response = requests.get(
    f"{BASE_URL}/aos/latest",
    headers={"X-API-Key": API_KEY}
)
data = response.json()
print(f"Found {data['station_count']} weather stations")
```

### JavaScript
```javascript
const API_KEY = 'mobile-app-xyz789';
const BASE_URL = 'https://your-api.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public';

// Get water level statistics
fetch(`${BASE_URL}/water-levels/statistics?date=12/06/2568`, {
  headers: { 'X-API-Key': API_KEY }
})
  .then(res => res.json())
  .then(data => console.log(data));
```

## 💰 Cost Optimization

### AWS Free Tier Coverage
- **API Gateway**: 1M requests/month free for 12 months
- **Lambda**: 1M requests + 400,000 GB-seconds free (permanent)
- **RDS**: 750 hours db.t3.micro/month free for 12 months

### Cost Estimates (After Free Tier)
- 10M API calls/month: ~$35/month
- 100M API calls/month: ~$350/month

### Cost Saving Tips
1. **Enable Caching**: Add API Gateway caching for frequently accessed data
2. **Use Lambda Layers**: Share database connections across functions
3. **Optimize Queries**: Add database indexes for common queries
4. **Set TTL**: Cache responses in CloudFront

## 🔒 Security Best Practices

### 1. API Key Rotation
```bash
# Rotate keys monthly
./scripts/rotate-api-keys.sh
```

### 2. IP Whitelisting (Optional)
```yaml
# In serverless-data-api.yml
provider:
  resourcePolicy:
    - Effect: Allow
      Principal: "*"
      Action: execute-api:Invoke
      Resource: execute-api:/*/*/*
      Condition:
        IpAddress:
          aws:SourceIp:
            - "203.0.113.0/24"  # RID office IPs
            - "198.51.100.0/24" # TMD office IPs
```

### 3. Enable WAF
```bash
# Attach AWS WAF to API Gateway for DDoS protection
aws wafv2 create-web-acl --name munbon-api-waf ...
```

## 📈 Monitoring

### CloudWatch Dashboards
```bash
# Create monitoring dashboard
aws cloudwatch put-dashboard \
  --dashboard-name MunbonDataAPI \
  --dashboard-body file://cloudwatch-dashboard.json
```

### Alarms
```bash
# High error rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name MunbonDataAPI-Errors \
  --alarm-description "Alert on high error rate" \
  --metric-name 4XXError \
  --namespace AWS/ApiGateway \
  --statistic Sum \
  --period 300 \
  --threshold 100 \
  --comparison-operator GreaterThanThreshold
```

## 🧪 Testing

### Local Testing
```bash
# Start offline mode
serverless offline --config serverless-data-api.yml

# Test locally
curl -H "X-API-Key: test-key" \
  http://localhost:3002/api/v1/public/water-levels/latest
```

### Load Testing
```bash
# Using k6
k6 run load-test.js
```

## 🔧 Troubleshooting

### Database Connection Issues
```bash
# Test connection from Lambda
aws lambda invoke \
  --function-name munbon-data-api-prod-waterLevelLatest \
  --payload '{}' \
  response.json
```

### Check Logs
```bash
# View Lambda logs
aws logs tail /aws/lambda/munbon-data-api-prod-waterLevelLatest --follow
```

## 🚀 Advanced Features

### 1. Response Caching
```yaml
# Add caching in serverless-data-api.yml
functions:
  waterLevelLatest:
    handler: data-exposure-handler.waterLevelLatest
    events:
      - http:
          caching:
            enabled: true
            ttlInSeconds: 300  # 5 minutes
```

### 2. Custom Domain
```bash
# Add custom domain
serverless create_domain --config serverless-data-api.yml
serverless deploy --config serverless-data-api.yml
```

### 3. Multi-Region Deployment
```bash
# Deploy to multiple regions
./deploy-all.sh --region ap-southeast-1
./deploy-all.sh --region ap-south-1
```

## 📝 Next Steps

1. **Set up monitoring**: CloudWatch dashboards and alarms
2. **Configure backups**: Automated RDS snapshots
3. **Add documentation**: Generate API docs with Swagger
4. **Implement versioning**: API version management
5. **Set up CI/CD**: Automated deployments with GitHub Actions