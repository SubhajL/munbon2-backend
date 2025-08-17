# Security Group Update Instructions

To allow external access to the ROS/GIS Integration Service on port 3022, follow these steps:

## AWS Console Method

1. **Login to AWS Console**
   - Go to https://console.aws.amazon.com/
   - Select region: **ap-southeast-1** (Singapore)

2. **Navigate to EC2**
   - Services → EC2
   - Or direct link: https://ap-southeast-1.console.aws.amazon.com/ec2/

3. **Find the Instance**
   - Go to Instances
   - Find instance with IP: **43.209.22.250**
   - Note the Instance ID: **i-04ff727ac3337a608**

4. **Update Security Group**
   - Click on the instance
   - Go to "Security" tab
   - Click on the security group link (likely "launch-wizard-2")
   - Click "Edit inbound rules"
   - Add new rule:
     - Type: Custom TCP
     - Port: 3022
     - Source: 0.0.0.0/0 (or restrict to your IP)
     - Description: ROS/GIS Integration Service
   - Click "Save rules"

## AWS CLI Method

If you have AWS CLI configured with proper credentials:

```bash
# Set region
export AWS_DEFAULT_REGION=ap-southeast-1

# Get security group ID
INSTANCE_ID="i-04ff727ac3337a608"
SG_ID=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' --output text)

# Add inbound rule
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 3022 \
    --cidr 0.0.0.0/0 \
    --group-rule-description "ROS/GIS Integration Service"
```

## Verification

After updating the security group, test external access:

```bash
# From your local machine
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

- Health Check: http://43.209.22.250:3022/health
- GraphQL Playground: http://43.209.22.250:3022/graphql
- API Status: http://43.209.22.250:3022/api/v1/status
- Admin Health: http://43.209.22.250:3022/api/v1/admin/health/detailed

## Security Considerations

- For production, consider restricting the source IP to specific ranges
- Use HTTPS with a proper SSL certificate
- Consider using an Application Load Balancer (ALB) instead of direct EC2 access
- Implement API authentication for production use