# External API V2.0 - Final Status Report

## Current Situation

### AWS Lambda Endpoint (Production) - ❌ NOT WORKING
- **URL**: https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1
- **Status**: All endpoints returning HTTP 502 (Bad Gateway)
- **Error**: "Internal server error" - Lambda functions are failing
- **Authentication**: API Key header working correctly

### EC2 Alternative Implementation - ✅ PARTIALLY WORKING
- **URL**: http://43.208.201.191:8081/api/v1
- **Status**: Service running on port 8081
- **PostgreSQL**: ✅ Connected (Water Level & Moisture data)
- **MSSQL SCADA**: ❌ Connection failing ("Login failed for user 'sa'")

## Port Configuration
- **Port 8080**: Used by moisture data ingestion service (incoming sensor data)
- **Port 8081**: External API V2.0 (outgoing data API)
- These are two different services and cannot share the same port

## Options Moving Forward

### Option 1: Fix AWS Lambda Functions
- Investigate CloudWatch logs for Lambda errors
- Fix database connection issues in Lambda
- Restore original production endpoint

### Option 2: Use EC2 Implementation
- Fix MSSQL connection to moonup.hopto.org
- Open port 8081 in EC2 security group for external access
- Update all documentation to use new endpoint

### Option 3: Deploy to Different Infrastructure
- Use a different AWS account or region
- Deploy to a different cloud provider
- Set up proper load balancing

## Immediate Actions Needed

1. **For AWS Lambda**: Check CloudWatch logs to identify why Lambda functions are failing
2. **For EC2**: 
   - Fix MSSQL authentication to SCADA database
   - Open port 8081 in security group
   - Test all endpoints thoroughly

## Current Working Endpoints (EC2 - Local Access Only)

Water Level:
```bash
curl -H "X-API-Key: rid-ms-prod-key1" http://localhost:8081/api/v1/public/water-levels/latest
```

Moisture:
```bash
curl -H "X-API-Key: rid-ms-prod-key1" http://localhost:8081/api/v1/public/moisture/latest
```

AOS (Not working due to MSSQL connection):
```bash
curl -H "X-API-Key: rid-ms-prod-key1" http://localhost:8081/api/v1/public/aos/latest
```