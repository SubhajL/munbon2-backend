# Lambda CloudWatch Investigation Results

## Key Findings

### 1. Root Cause: Database Connection Timeout
- All Lambda functions are timing out after 6 seconds (now updated to 30 seconds)
- Functions only log: "Loaded 4 API keys from Parameter Store" then hang
- Original DB_HOST was pointing to wrong IP: 43.209.12.182

### 2. Configuration Updates Made
- Updated all functions to use correct database hosts:
  - PostgreSQL: 43.208.201.191 (EC2 instance)
  - MSSQL: moonup.hopto.org (SCADA database)
- Increased timeout from 6 to 30 seconds
- Maintained all existing environment variables

### 3. Current Status: Still Failing
- Functions continue to timeout even with correct configuration
- Possible reasons:
  1. Lambda functions cannot reach the EC2 database (network/security group issue)
  2. Lambda function code may need updates to handle connection properly
  3. Database credentials might be incorrect
  4. Lambda functions may not have proper IAM permissions

## CloudWatch Logs Pattern
```
START RequestId: xxx
INFO Loaded 4 API keys from Parameter Store
[No further logs - function hangs here]
END RequestId: xxx
REPORT Duration: 30000.00 ms Status: timeout
```

## Next Steps to Investigate

### 1. Network Connectivity
- Lambda functions are not in VPC (VpcConfig is empty)
- EC2 database (43.208.201.191) needs to accept connections from Lambda
- Security group on EC2 must allow inbound PostgreSQL (5432)

### 2. Test Database Connection Directly
From EC2 or local machine:
```bash
psql -h 43.208.201.191 -p 5432 -U postgres -d sensor_data
```

### 3. Lambda Code Issues
- Functions might be using wrong database driver
- Connection string format might be incorrect
- Missing error handling for connection failures

### 4. Alternative Solutions
1. **Use EC2 API** (Already deployed)
   - http://43.208.201.191:8081/api/v1
   - Working for water level and moisture
   - Needs MSSQL fix for AOS

2. **Redeploy Lambda Functions**
   - With updated code that includes better error logging
   - With proper connection handling
   - With VPC configuration if needed

3. **Create New Lambda Functions**
   - Fresh deployment with correct configuration
   - Better error handling and logging
   - Test with simple health check first

## Recommendation
Since Lambda functions require significant debugging and the EC2 implementation is already working, recommend using the EC2 API endpoint (http://43.208.201.191:8081/api/v1) after:
1. Fixing MSSQL authentication for AOS data
2. Opening port 8081 in security group for external access