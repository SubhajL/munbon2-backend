# Munbon Backend Verification Report

## 1. Data Ingestion and External API Flow Verification

### Data Flow Architecture:
1. **Data Ingestion Path**:
   - IoT Sensors → AWS Lambda (handler.ts) → AWS SQS → Consumer (EC2) → PostgreSQL (EC2)
   - Lambda endpoint: `https://[api-id].execute-api.ap-southeast-1.amazonaws.com/[stage]/api/v1/{token}/telemetry`
   - SQS Queue: `https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue`

2. **Data Exposure Path** (External API):
   - External Request → AWS Lambda (data-exposure-handler.ts) → PostgreSQL (EC2) → Response
   - API endpoint: `https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1`

### Current Configuration Status:
- ✅ AWS Lambda functions updated to use EC2 database (43.209.12.182:5432)
- ✅ SQS Consumer configured in docker-compose.ec2-consolidated.yml
- ✅ AWS credentials added to .env.ec2
- ✅ Both ingestion and exposure using same PostgreSQL instance on EC2

## 2. Services Running on EC2

### Docker Services Configured:
```yaml
# From docker-compose.ec2-consolidated.yml
1. sensor-data (port 3001)
2. sensor-data-consumer (port 3002) - SQS consumer dashboard
3. auth (port 3002) - Note: port conflict with consumer
4. moisture-monitoring (port 3003)  
5. weather-monitoring (port 3004)
6. water-level-monitoring (port 3005)
7. gis (port 3006)
8. ros (port 3012)
9. rid-ms (port 3011)
10. awd-control (port 3013)
11. flow-monitoring (port 3014)
12. redis (port 6379) - Cache layer
13. nginx (optional, ports 80/443)
```

### Database Configuration:
- Single PostgreSQL instance: 43.209.12.182:5432
- Multiple schemas: auth, gis, ros, awd
- Separate database: sensor_data (with TimescaleDB extension)

## 3. Missing Configuration & Action Items

### ⚠️ Port Conflict Issue:
- **auth** and **sensor-data-consumer** both use port 3002
- Need to fix in docker-compose.ec2-consolidated.yml

### 🔧 Environment Variables to Update:
1. **External API Keys** (in .env.ec2):
   - TMD_API_KEY (Thai Meteorological Department)
   - LINE_CHANNEL_ACCESS_TOKEN
   - LINE_NOTIFY_TOKEN
   - SCADA credentials if using

2. **GitHub Secrets Required** (for automated deployment):
   - EC2_HOST: 43.209.12.182
   - EC2_USER: ubuntu (or your EC2 username)
   - EC2_SSH_KEY: Your private SSH key

### 📝 Additional Scripts/Configs Needed:

1. **Fix Port Conflict**:
   ```bash
   # Update auth service to use port 3008 instead of 3002
   ```

2. **Set GitHub Secrets** (if not done):
   ```bash
   ./scripts/setup-github-secrets.sh
   ```

3. **Manual EC2 Deployment** (if GitHub Actions not configured):
   ```bash
   # On EC2 instance:
   curl -s https://raw.githubusercontent.com/SubhajL/munbon2-backend/main/scripts/manual-ec2-deployment.sh | bash
   ```

4. **Database Initialization** (on EC2):
   ```bash
   # Create sensor_data database if not exists
   docker exec munbon-postgres psql -U postgres -c "CREATE DATABASE sensor_data;"
   docker exec munbon-postgres psql -U postgres -d sensor_data -c "CREATE EXTENSION IF NOT EXISTS postgis;"
   docker exec munbon-postgres psql -U postgres -d sensor_data -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
   ```

## 4. Deployment Status

### Automated Deployment:
- ✅ GitHub Actions workflow configured (deploy-ec2.yml)
- ✅ Duplicate workflows disabled
- ⚠️ Requires GitHub secrets to be set

### Current Deployment Method:
- Push to main branch → Triggers deploy-ec2.yml → Deploys to EC2
- Uses docker-compose.ec2.yml (not docker-compose.ec2-consolidated.yml)

### ⚠️ Important Note:
The GitHub Actions workflow uses `docker-compose.ec2.yml` but we've been working with `docker-compose.ec2-consolidated.yml`. Need to ensure the correct file is used.

## 5. Testing Commands

### Test Data Ingestion:
```bash
# Send test data to Lambda ingestion endpoint
curl -X POST https://[api-id].execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridr-water-level/telemetry \
  -H 'Content-Type: application/json' \
  -d '{"deviceID":"test-001","level":25,"latitude":13.7563,"longitude":100.5018,"macAddress":"AA:BB:CC:DD:EE:FF","RSSI":-70,"voltage":370}'
```

### Test External API:
```bash
# Query data from Lambda exposure endpoint  
curl -X GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/water-level/latest \
  -H 'X-API-Key: rid-ms-prod-1234567890abcdef'
```

### Check EC2 Services:
```bash
# SSH to EC2 and check
docker-compose -f docker-compose.ec2-consolidated.yml ps
docker-compose -f docker-compose.ec2-consolidated.yml logs -f
```

### Monitor Consumer Dashboard:
- http://43.209.12.182:3002 - Real-time sensor data dashboard

## Summary

1. **Data Flow**: ✅ Both ingestion and external API configured to use EC2 database
2. **Services**: ⚠️ Need to fix port conflict and update deployment workflow  
3. **Environment**: ⚠️ Need to fill in external API keys
4. **Deployment**: ⚠️ Need to set GitHub secrets or use manual deployment