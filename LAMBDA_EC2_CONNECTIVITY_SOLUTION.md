# Lambda to EC2 Database Connectivity Issue & Solution

## Why Lambda Can Reach Your Local DB but Not EC2

### 1. **The Key Difference: Security Groups**

**Your Local Machine:**
- Your home router likely uses NAT/port forwarding
- No AWS Security Groups blocking connections
- Your ISP provides a public IP that accepts connections

**EC2 Instance (43.208.201.191):**
- Protected by AWS Security Groups (virtual firewall)
- Security Group likely only allows YOUR IP address
- Lambda functions come from AWS IP ranges, not your IP

### 2. **How AWS Lambda Works:**
- Lambda runs in AWS-managed infrastructure
- Each execution gets a random IP from AWS IP ranges
- These IPs change with every execution
- Lambda is NOT coming from your home IP

### 3. **Current Security Group Problem:**
```
Your Security Group Rule (likely):
- Type: PostgreSQL
- Port: 5432
- Source: YOUR_HOME_IP/32 ✅ (That's why YOU can connect)
- Source: AWS Lambda IPs ❌ (Not included)
```

## Solution Options

### Option 1: Open PostgreSQL to All IPs (Quick but Less Secure)
```bash
# Add rule to allow PostgreSQL from anywhere
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxxx \
  --protocol tcp \
  --port 5432 \
  --cidr 0.0.0.0/0 \
  --region ap-southeast-1
```
⚠️ **Security Risk**: Anyone can attempt to connect to your database

### Option 2: Add AWS Lambda IP Ranges (More Secure)
```bash
# Get AWS Lambda IP ranges for ap-southeast-1
curl -s https://ip-ranges.amazonaws.com/ip-ranges.json | \
  jq -r '.prefixes[] | select(.region=="ap-southeast-1") | select(.service=="LAMBDA") | .ip_prefix'

# Add each range to security group
```
⚠️ **Maintenance**: AWS IP ranges can change

### Option 3: Use VPC for Lambda (Most Secure) - COMPLEX
1. Create VPC with private subnets
2. Put EC2 in the VPC
3. Configure Lambda to use same VPC
4. Use security groups for internal communication

### Option 4: Use RDS Instead of EC2 PostgreSQL (AWS Best Practice)
1. Migrate database to Amazon RDS
2. Use IAM database authentication
3. Lambda can connect securely without managing IPs

## Recommended Immediate Solution

Since you need it working quickly, do Option 1 temporarily:

1. **Open PostgreSQL port to all IPs** (temporary):
```bash
# First, find your security group ID
aws ec2 describe-instances \
  --instance-ids $(aws ec2 describe-instances --filters "Name=ip-address,Values=43.208.201.191" --query 'Reservations[0].Instances[0].InstanceId' --output text --region ap-southeast-1) \
  --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' \
  --output text \
  --region ap-southeast-1
```

2. **Add the rule**:
```bash
aws ec2 authorize-security-group-ingress \
  --group-id [YOUR_SG_ID] \
  --protocol tcp \
  --port 5432 \
  --cidr 0.0.0.0/0 \
  --region ap-southeast-1
```

3. **Test Lambda again**

4. **Later: Implement proper security** (VPC or RDS)

## Alternative: Just Use the EC2 API

Since the EC2 API is already working on port 8081:
1. Open port 8081 in security group (same issue, but only for API)
2. This is actually MORE SECURE than opening database port
3. You already have it working locally

## Summary

**The Problem**: EC2 Security Group only allows YOUR IP, not AWS Lambda IPs
**Quick Fix**: Open port 5432 to 0.0.0.0/0 (temporarily)
**Better Fix**: Use EC2 API on port 8081 instead
**Best Fix**: Redesign with VPC or RDS