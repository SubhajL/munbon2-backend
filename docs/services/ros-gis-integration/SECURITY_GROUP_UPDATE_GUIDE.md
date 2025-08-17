# Security Group Update Guide for ROS/GIS Integration Service

## Current Status
- ✅ Service is running correctly in Docker on port 3022
- ✅ Internally accessible at http://localhost:3022
- ❌ Externally blocked by firewall/security group

## Quick Fix Options

### Option 1: AWS Console (Recommended)
1. **Login to AWS Console**: https://console.aws.amazon.com/
2. **Navigate to EC2**:
   - Services → EC2
   - Or direct: https://console.aws.amazon.com/ec2/
3. **Find the Instance**:
   - Look for instance with Public IP: `43.209.22.250`
   - Or search by Instance ID: `i-04ff727ac3337a608`
4. **Update Security Group**:
   - Click on the instance
   - Go to "Security" tab
   - Click on the security group link
   - Click "Edit inbound rules"
   - Click "Add rule"
   - Configure:
     - Type: `Custom TCP`
     - Port range: `3022`
     - Source: `0.0.0.0/0` (or your specific IP for security)
     - Description: `ROS/GIS Integration Service`
   - Click "Save rules"

### Option 2: AWS CLI (If Configured)
```bash
# Find the security group
aws ec2 describe-instances \
  --filters "Name=ip-address,Values=43.209.22.250" \
  --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' \
  --output text

# Add the rule (replace sg-xxxxx with actual security group ID)
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxx \
  --protocol tcp \
  --port 3022 \
  --cidr 0.0.0.0/0 \
  --group-rule-description "ROS/GIS Integration Service"
```

### Option 3: Alternative Cloud Providers

#### DigitalOcean
- Go to Networking → Firewalls
- Edit firewall rules
- Add inbound rule for TCP port 3022

#### Google Cloud
- Go to VPC network → Firewall rules
- Create firewall rule
- Allow TCP port 3022

#### Azure
- Go to Network security groups
- Add inbound security rule
- Allow TCP port 3022

#### Alibaba Cloud
- Go to Security Groups
- Add rule for TCP port 3022

### Option 4: Local Firewall (Temporary)
If cloud security group cannot be updated immediately:
```bash
# On the server (temporary fix)
ssh -i ~/dev/th-lab01.pem ubuntu@43.209.22.250
sudo ufw allow 3022/tcp
sudo ufw --force enable
sudo ufw reload
```

## Verification
After updating the security group, test access:

```bash
# Test connectivity
curl http://43.209.22.250:3022/health

# Expected response:
{
  "status": "healthy",
  "service": "ros-gis-integration",
  "version": "1.0.0",
  "databases": {
    "postgres": true,
    "redis": true
  },
  "external_services": {
    "flow_monitoring": true,
    "scheduler": true,
    "ros": true,
    "gis": true
  }
}
```

## Service Endpoints
Once the security group is updated, these endpoints will be accessible:

- **Health Check**: http://43.209.22.250:3022/health
- **GraphQL Playground**: http://43.209.22.250:3022/graphql
- **API Status**: http://43.209.22.250:3022/api/v1/status
- **Admin Health**: http://43.209.22.250:3022/api/v1/admin/health/detailed

## Security Recommendations
1. **Restrict Source IPs**: Instead of `0.0.0.0/0`, use specific IP ranges
2. **Use HTTPS**: Configure SSL/TLS for production
3. **API Authentication**: Implement API keys or OAuth for production
4. **Rate Limiting**: Add rate limiting to prevent abuse
5. **Monitoring**: Set up monitoring and alerts

## Troubleshooting
If the service is still not accessible after updating security group:

1. **Check Instance Status**:
   ```bash
   ssh -i ~/dev/th-lab01.pem ubuntu@43.209.22.250
   docker ps | grep ros-gis-integration
   ```

2. **Check Logs**:
   ```bash
   docker logs ros-gis-integration
   ```

3. **Test Internal Access**:
   ```bash
   curl http://localhost:3022/health
   ```

4. **Check Network**:
   ```bash
   sudo ss -tlnp | grep 3022
   ```

## Contact for Help
If you need assistance with AWS access or security group updates, contact your AWS administrator or DevOps team.