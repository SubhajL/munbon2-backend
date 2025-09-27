# AWS Lambda External API V2.0 - Investigation Report

## Executive Summary
The AWS Lambda External API V2.0 endpoints are **valid but non-functional** due to Lambda backend failures. The API Gateway is working correctly, but all Lambda functions are returning HTTP 502 (Bad Gateway) errors.

## Investigation Findings

### 1. API Gateway Status - ✅ WORKING
- **Base URL**: `https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod`
- **Authentication**: Working correctly
- **Required Header**: `x-api-key` (lowercase)
- **Response**: Properly validates API keys and returns appropriate errors

### 2. Authentication - ✅ WORKING
- **Valid API Keys**:
  - `rid-ms-prod-key1` - RID Main System
  - `tmd-weather-key2` - Thai Meteorological Department  
  - `university-key3` - University Research
- **Key Finding**: Header must be lowercase `x-api-key`, not `X-API-Key`
- **Without API Key**: Returns `{"error":"Invalid API key"}`

### 3. Lambda Functions - ❌ ALL FAILING
All endpoints return HTTP 502 with `{"message": "Internal server error"}`:
- `/api/v1/public/water-levels/latest`
- `/api/v1/public/water-levels/timeseries`
- `/api/v1/public/water-levels/statistics`
- `/api/v1/public/moisture/latest`
- `/api/v1/public/moisture/timeseries`
- `/api/v1/public/moisture/statistics`
- `/api/v1/public/aos/latest`
- `/api/v1/public/aos/timeseries`
- `/api/v1/public/aos/statistics`

### 4. Error Details
```
HTTP/2 502
x-amzn-errortype: InternalServerErrorException
x-cache: Error from cloudfront
{"message": "Internal server error"}
```

### 5. API Structure Validation
- **Valid Path**: `/prod/api/v1/public/{resource}/{action}`
- **Invalid Paths**:
  - `/prod/api/v2/*` - Version 2 doesn't exist
  - `/prod/api/v1/{resource}` - Missing `/public` prefix
  - `/prod/health` - No health endpoint configured

## Root Cause Analysis

### Likely Causes of Lambda Failures:
1. **Database Connection Issues**
   - Lambda functions cannot connect to TimescaleDB
   - VPC/Security Group misconfiguration
   - Database credentials expired or invalid

2. **Lambda Environment Issues**
   - Missing environment variables
   - Insufficient Lambda permissions
   - Lambda timeout too short for database queries

3. **Code Issues**
   - Unhandled exceptions in Lambda code
   - Missing dependencies in Lambda deployment package
   - Version mismatch between code and database schema

## Recommendations

### Immediate Actions:
1. **Check CloudWatch Logs**
   ```bash
   aws logs tail /aws/lambda/[function-name] --follow
   ```

2. **Verify Lambda Environment Variables**
   - Database connection strings
   - API keys and secrets
   - VPC configuration

3. **Test Lambda Functions Directly**
   ```bash
   aws lambda invoke --function-name [function-name] output.json
   ```

### Alternative Solutions:
1. **Use EC2 Implementation** (Currently deployed)
   - Available at: `http://43.208.201.191:8081/api/v1`
   - Requires fixing MSSQL connection for AOS data
   - Needs security group update to allow external access

2. **Redeploy Lambda Functions**
   - Update deployment packages
   - Fix database connections
   - Add better error logging

3. **Create New Lambda Functions**
   - Fresh deployment with updated code
   - Proper VPC and security group configuration
   - Comprehensive error handling

## Conclusion
The API Gateway infrastructure is functional, but all Lambda functions are failing due to backend issues. The authentication system works correctly with lowercase headers. The EC2 alternative implementation provides a working solution while Lambda issues are resolved.