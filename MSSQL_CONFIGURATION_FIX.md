# MSSQL Configuration Fix for AOS Endpoints

## Current Issue
The AOS endpoints are failing with "Login failed for user 'sa'" error when trying to connect to the SCADA database.

## MSSQL Connection Details (from screenshot)
- **Host**: moonup.hopto.org
- **Port**: 1433 
- **Database**: db_scada
- **Username**: sa
- **Password**: [Hidden in screenshot - needs to be provided]
- **Authentication**: SQL Server Authentication
- **Trust Server Certificate**: Enabled (unchecked in screenshot)

## What Has Been Fixed
1. ✅ Added port configuration (1433) to the source code
2. ✅ Updated environment variables to include MSSQL_PORT
3. ✅ Set trustServerCertificate to true in connection options

## What Needs to Be Done

### Update the MSSQL Password on EC2:
```bash
# SSH to EC2
ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191

# Update the password in .env file
cd /home/ubuntu/external-api-v2
nano .env

# Find and update this line with the correct password:
MSSQL_PASSWORD=P@ssw0rd  # <- Replace with actual password

# Save and restart the service
pm2 restart external-api-v2
```

### Test the Connection:
```bash
# Test health endpoint
curl -s http://localhost:8081/health | jq .

# Test AOS latest endpoint
curl -s -H "x-api-key: rid-ms-prod-key1" \
  http://localhost:8081/api/v1/public/aos/latest | jq .
```

## Expected Results After Fix

Once the correct password is set, the AOS endpoints should return data like:
```json
{
  "data_type": "aos_weather",
  "request_time": "2025-09-10T09:30:00.000Z",
  "request_time_buddhist": "10/09/2568",  
  "station_count": 1,
  "stations": [
    {
      "station_id": "AOS001",
      "rainfall_mm": 0,
      "temperature_celsius": 28.5,
      "humidity_percentage": 75,
      // ... other weather data
    }
  ]
}
```

## All Working Endpoints

### Through AWS Lambda (Production):
- ✅ Water Level: https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/latest
- ✅ Moisture: https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/moisture/latest
- ❌ AOS: Waiting for correct MSSQL password

### Direct EC2 (Backup):
- ✅ Water Level: http://43.208.201.191:8081/api/v1/public/water-levels/latest
- ✅ Moisture: http://43.208.201.191:8081/api/v1/public/moisture/latest
- ❌ AOS: Waiting for correct MSSQL password