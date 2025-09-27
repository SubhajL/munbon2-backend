# Lambda to EC2 API Proxy - Status Report

## Current Status

### ✅ What's Working:
1. **EC2 API Service** - Running on port 8081 and responding correctly
   - Water level endpoints: Working (returning empty data)
   - Moisture endpoints: Working (returning empty data)
   - AOS endpoints: MSSQL connection failing but service running

2. **Lambda Functions Updated** - All 9 functions updated with proxy code
   - Code deployment: Successful
   - Handler configuration: Fixed (index.handler)
   - Timeout increased: 30 seconds

### ❌ What's Not Working:
1. **API Key Validation** - Lambda returning "Invalid API key"
   - The proxy code has hardcoded API keys that don't match
   - Need to either remove validation or use correct keys

2. **Network Connectivity** - Lambda cannot reach EC2 on port 8081
   - Even if API key passes, Lambda will timeout trying to reach EC2
   - Port 8081 might be open but not accessible from AWS Lambda IPs

## The Problems

### Problem 1: API Key Mismatch
The Lambda proxy code validates against:
```javascript
const VALID_API_KEYS = {
    'rid-ms-prod-key1': 'RID Main System',
    'tmd-weather-key2': 'Thai Meteorological Department',
    'university-key3': 'University Research'
};
```

But the API Gateway is passing a different format or the validation logic is wrong.

### Problem 2: Network Path
```
Lambda (AWS Network) → ❌ → EC2 Port 8081 (Public IP)
```

Even though port 8081 is "open", it might:
- Only allow specific IPs (not Lambda)
- Have additional firewall rules
- Be blocked by EC2 network ACLs

## Solutions

### Quick Fix: Remove API Key Validation in Lambda
Update Lambda to just pass through without validation:
```javascript
// Remove this validation
// if (!apiKey || !VALID_API_KEYS[apiKey]) {
//     return { statusCode: 401, body: JSON.stringify({ error: 'Invalid API key' }) };
// }
```

### Better Fix: Use Different Architecture
1. **Option A**: Deploy API to AWS API Gateway directly
   - No EC2 needed
   - Native AWS integration
   
2. **Option B**: Use Application Load Balancer
   - ALB can reach EC2 internally
   - Lambda connects to ALB
   
3. **Option C**: Put Lambda in VPC
   - Configure Lambda to be in same VPC as EC2
   - Use private IP communication

## Immediate Action Items

1. **Test if Lambda can reach EC2 at all**:
   - Remove API key validation
   - Add better error logging
   - See actual connection error

2. **Verify Security Group**:
   - Must allow 0.0.0.0/0 on port 8081
   - Check for additional network ACLs
   - Verify EC2 instance firewall

3. **Consider Alternative**:
   - Since EC2 API works, just document it as the endpoint
   - Skip Lambda proxy altogether
   - Use: http://43.208.201.191:8081/api/v1/

## Conclusion
The Lambda proxy approach is hitting network connectivity issues between Lambda and EC2. The simplest solution is to use the EC2 API directly at http://43.208.201.191:8081/api/v1/ since it's already working.