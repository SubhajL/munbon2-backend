# Option 2: Use EC2 API Instead of Direct Database Connection (Detailed Explanation)

## Architecture Comparison

### Current (Broken) Architecture:
```
User → API Gateway → Lambda → ❌ → EC2 Database (Port 5432)
                              ↑
                     Security Group blocks Lambda IPs
```

### Proposed Architecture:
```
User → API Gateway → Lambda → HTTP Request → EC2 API (Port 8081) → Local Database
                                         ↑
                              Only need to open port 8081
```

## Why This Is Better

### 1. **Security Advantages**
- **No Direct Database Access**: External services never touch your database directly
- **API Authentication**: The API already has API key authentication (rid-ms-prod-key1, etc.)
- **Single Entry Point**: Only one port (8081) needs to be opened
- **Better Access Control**: API can implement rate limiting, logging, additional auth

### 2. **How It Works**

Instead of Lambda functions connecting to PostgreSQL:
```javascript
// Current Lambda code (BROKEN):
const pgClient = new Client({
  host: '43.208.201.191',  // Security group blocks this
  port: 5432,
  database: 'sensor_data'
});
await pgClient.connect(); // TIMEOUT!
```

Lambda would call your EC2 API:
```javascript
// Updated Lambda code (WILL WORK):
const response = await axios.get('http://43.208.201.191:8081/api/v1/public/water-levels/latest', {
  headers: {
    'x-api-key': 'internal-lambda-key'
  }
});
return response.data;
```

### 3. **Implementation Steps**

#### Step 1: Open Port 8081 in EC2 Security Group
```bash
# Find security group ID
INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=ip-address,Values=43.208.201.191" \
  --query 'Reservations[0].Instances[0].InstanceId' \
  --output text \
  --region ap-southeast-1)

SG_ID=$(aws ec2 describe-instances \
  --instance-ids $INSTANCE_ID \
  --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' \
  --output text \
  --region ap-southeast-1)

# Add rule to allow port 8081 from anywhere
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 8081 \
  --cidr 0.0.0.0/0 \
  --region ap-southeast-1 \
  --tag-specifications "ResourceType=security-group-rule,Tags=[{Key=Name,Value=External-API-Port}]"
```

#### Step 2: Update Lambda Functions
Each Lambda function needs to be updated to call the EC2 API instead of database directly:

**Old Lambda Function (Direct DB):**
```javascript
exports.handler = async (event) => {
  // Validate API key
  const apiKey = event.headers['x-api-key'];
  if (!isValidApiKey(apiKey)) {
    return { statusCode: 401, body: JSON.stringify({ error: 'Invalid API key' }) };
  }
  
  // Connect to database (THIS FAILS)
  const pgClient = new Client(dbConfig);
  await pgClient.connect();
  
  // Query database
  const result = await pgClient.query('SELECT * FROM water_level_readings...');
  
  return {
    statusCode: 200,
    body: JSON.stringify(formatResponse(result.rows))
  };
};
```

**New Lambda Function (API Proxy):**
```javascript
exports.handler = async (event) => {
  // Validate external API key
  const externalApiKey = event.headers['x-api-key'];
  if (!isValidApiKey(externalApiKey)) {
    return { statusCode: 401, body: JSON.stringify({ error: 'Invalid API key' }) };
  }
  
  // Call EC2 API with internal key
  try {
    const response = await axios({
      method: event.httpMethod,
      url: `http://43.208.201.191:8081${event.path}`,
      params: event.queryStringParameters,
      headers: {
        'x-api-key': process.env.INTERNAL_API_KEY // Special key for Lambda
      }
    });
    
    return {
      statusCode: response.status,
      headers: response.headers,
      body: JSON.stringify(response.data)
    };
  } catch (error) {
    return {
      statusCode: error.response?.status || 502,
      body: JSON.stringify({ 
        message: 'Internal server error',
        details: error.message 
      })
    };
  }
};
```

### 4. **Benefits of This Approach**

1. **Immediate Fix**: Just open one port and update Lambda code
2. **Better Security**: 
   - Database remains protected
   - API handles authentication
   - Can add rate limiting
   - Can log all access
3. **Easier Maintenance**:
   - One API to maintain instead of 9 Lambda functions
   - Database changes only affect EC2 API
   - Can update API without touching Lambda
4. **Performance**:
   - EC2 API already has connection pooling
   - Can add caching at API level
   - Lambda functions become lightweight proxies

### 5. **Architecture Diagram**

```
                           ┌─────────────────────┐
                           │   AWS API Gateway   │
                           │  (Public Endpoint)  │
                           └──────────┬──────────┘
                                      │
                           ┌──────────▼──────────┐
                           │   Lambda Functions  │
                           │  (Simple Proxies)   │
                           └──────────┬──────────┘
                                      │ HTTP Request
                                      │ Port 8081
                           ┌──────────▼──────────┐
                           │    EC2 Instance     │
                           │  43.208.201.191     │
                           ├─────────────────────┤
                           │  External API v2    │
                           │   (Port 8081)       │
                           └──────────┬──────────┘
                                      │ Localhost
                                      │ Port 5432
                           ┌──────────▼──────────┐
                           │  TimescaleDB/PGSQL  │
                           │   (Protected)       │
                           └─────────────────────┘
```

### 6. **Testing After Implementation**

```bash
# Test that port 8081 is open
curl -v http://43.208.201.191:8081/health

# Test API endpoints externally
curl -H "x-api-key: rid-ms-prod-key1" \
  http://43.208.201.191:8081/api/v1/public/water-levels/latest

# Test Lambda endpoint (should now work)
curl -H "x-api-key: rid-ms-prod-key1" \
  https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/latest
```

### 7. **Migration Path**

1. **Phase 1**: Open port 8081, test EC2 API directly
2. **Phase 2**: Update one Lambda function as proof of concept
3. **Phase 3**: Update remaining Lambda functions
4. **Phase 4**: Add monitoring and logging
5. **Phase 5**: Optimize with caching if needed

## Summary

This approach:
- ✅ Solves the immediate problem (Lambda can't reach database)
- ✅ More secure (only API port exposed, not database)
- ✅ Already partially working (EC2 API exists)
- ✅ Easier to maintain (single API codebase)
- ✅ Better architecture (proper API gateway pattern)