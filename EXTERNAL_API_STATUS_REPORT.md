# Munbon External API Status Report

**Date**: September 10, 2025  
**Verified By**: Claude Code

## Executive Summary

The Munbon External API V2.0 production endpoints are currently **NOT WORKING**. All endpoints tested return HTTP 502 (Bad Gateway) errors, indicating the backend services behind the AWS API Gateway are down or misconfigured.

## Verification Results

### 🔴 Production API Status: DOWN

All endpoints at `https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1` return:
```json
{
  "message": "Internal server error"
}
```
HTTP Status: 502 (Bad Gateway)

### Endpoints Tested

#### Water Level Data API
- ❌ `/public/water-levels/latest` - 502 Error
- ❌ `/public/water-levels/timeseries?date=10/09/2568` - 502 Error  
- ❌ `/public/water-levels/statistics?date=10/09/2568` - 502 Error

#### Moisture Data API
- ❌ `/public/moisture/latest` - 502 Error
- ❌ `/public/moisture/timeseries?date=10/09/2568` - 502 Error
- ❌ `/public/moisture/statistics?date=10/09/2568` - 502 Error

#### AOS Meteorological Data API
- ❌ `/public/aos/latest` - 502 Error
- ❌ `/public/aos/timeseries?date=10/09/2568` - 502 Error
- ❌ `/public/aos/statistics?date=10/09/2568` - 502 Error

## Currently Working Endpoints

Based on the codebase analysis, these endpoints are operational:

### 1. ✅ Moisture Data Ingestion (Direct EC2)
**URL**: `http://43.208.201.191:8080/api/sensor-data/moisture/munbon-m2m-moisture`  
**Method**: POST  
**Status**: WORKING  
**Purpose**: Receives moisture sensor data directly from field gateways  
**Note**: This is an internal ingestion endpoint, not the public API

### 2. ✅ Water Level Data Ingestion (AWS Lambda)
**URL**: `https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridr-water-level/telemetry`  
**Method**: POST  
**Status**: WORKING (Dev environment)  
**Purpose**: Receives water level telemetry data  
**Note**: This is a development endpoint, not the production public API

## Root Cause Analysis

The 502 errors indicate that:

1. **API Gateway is functioning** - It's returning structured error responses
2. **Backend services are down** - The Lambda function or internal unified API service is not responding
3. **Possible issues**:
   - Lambda function timeout or error
   - Internal unified API service (port 3000) is down
   - Database connection issues from Lambda
   - Network connectivity between AWS and EC2 instance

## Recommendations

1. **Check Lambda Function Logs**
   ```bash
   aws logs tail /aws/lambda/munbon-external-api-prod --follow
   ```

2. **Verify Internal Unified API**
   - Check if service is running on port 3000
   - Verify database connections
   - Check API key validation (`X-Internal-Key: munbon-internal-f3b89263126548`)

3. **Test Internal Architecture Path**
   - API Gateway → Lambda → Internal API → Databases
   - Identify where the chain is broken

4. **Fallback Options**
   - Use direct EC2 endpoints for data ingestion (moisture: port 8080)
   - Use development endpoints if available
   - Consider implementing a health check endpoint

## Alternative Access Methods

While the public API is down, data can be accessed via:

1. **Direct Database Access** (if authorized)
   - TimescaleDB on EC2: `43.208.201.191:5432`
   - Requires proper credentials

2. **Internal Services** (if within network)
   - Moisture monitoring service
   - Water level monitoring service
   - Direct sensor data ingestion endpoints

## Verification Script

A verification script has been created at:
`/Users/subhajlimanond/dev/munbon2-backend/verify-external-api-v2.sh`

Run it anytime to check the current status of all endpoints.