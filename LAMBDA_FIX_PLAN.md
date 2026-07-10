# Lambda Functions Database Configuration Fix

## Current Issue
All Lambda functions are timing out because:
- They're trying to connect to DB_HOST: 43.209.12.182 (wrong/inaccessible host)
- Timeout is set to only 6 seconds
- No VPC configuration (so they can't reach private IPs)

## Required Configuration

### 1. Water Level & Moisture Lambda Functions
Should connect to EC2 PostgreSQL/TimescaleDB:
- Host: 43.208.201.191
- Port: 5432
- Database: sensor_data
- User: postgres
- Password: __ROTATED_DB_PASSWORD__

### 2. AOS Lambda Functions
Should connect to MSSQL SCADA:
- Host: moonup.hopto.org
- Database: db_scada
- User: sa
- Password: P@ssw0rd
- Table: dbo.tb_aos

## Functions to Update

### Water Level Functions:
- munbon-data-api-prod-waterLevelLatest
- munbon-data-api-prod-waterLevelTimeseries
- munbon-data-api-prod-waterLevelStatistics

### Moisture Functions:
- munbon-data-api-prod-moistureLatest
- munbon-data-api-prod-moistureTimeseries
- munbon-data-api-prod-moistureStatistics

### AOS Functions (need different config):
- munbon-data-api-prod-aosLatest
- munbon-data-api-prod-aosTimeseries
- munbon-data-api-prod-aosStatistics

## Update Commands

### For Water Level & Moisture Functions:
```bash
# Update each function's environment variables
aws lambda update-function-configuration \
  --function-name FUNCTION_NAME \
  --region ap-southeast-1 \
  --timeout 30 \
  --environment Variables="{
    DB_HOST='43.208.201.191',
    DB_PORT='5432',
    DB_NAME='sensor_data',
    DB_USER='postgres',
    DB_PASSWORD='__ROTATED_DB_PASSWORD__',
    STAGE='prod'
  }"
```

### For AOS Functions:
```bash
# Update with MSSQL configuration
aws lambda update-function-configuration \
  --function-name FUNCTION_NAME \
  --region ap-southeast-1 \
  --timeout 30 \
  --environment Variables="{
    MSSQL_HOST='moonup.hopto.org',
    MSSQL_DATABASE='db_scada',
    MSSQL_USER='sa',
    MSSQL_PASSWORD='P@ssw0rd',
    DB_HOST='43.208.201.191',
    DB_PORT='5432',
    DB_NAME='sensor_data',
    DB_USER='postgres',
    DB_PASSWORD='__ROTATED_DB_PASSWORD__',
    STAGE='prod'
  }"
```

## Important Notes
1. Increased timeout from 6 to 30 seconds
2. Both databases are publicly accessible (no VPC needed)
3. AOS functions need both database configs (some may need PostgreSQL for metadata)