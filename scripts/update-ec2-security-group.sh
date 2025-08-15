#!/bin/bash

# Update EC2 security group to allow service ports
# Usage: ./update-ec2-security-group.sh

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}Updating EC2 Security Group for service ports...${NC}"

# Get the security group ID for the EC2 instance
INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=private-ip-address,Values=172.31.44.252" \
  --query "Reservations[0].Instances[0].InstanceId" \
  --output text 2>/dev/null)

if [ "$INSTANCE_ID" = "None" ] || [ -z "$INSTANCE_ID" ]; then
  echo -e "${YELLOW}Could not find instance by private IP, trying by public IP...${NC}"
  INSTANCE_ID=$(aws ec2 describe-instances \
    --filters "Name=ip-address,Values=43.209.22.250" \
    --query "Reservations[0].Instances[0].InstanceId" \
    --output text 2>/dev/null)
fi

if [ "$INSTANCE_ID" = "None" ] || [ -z "$INSTANCE_ID" ]; then
  echo -e "${RED}Could not find EC2 instance. Please update security group manually.${NC}"
  echo -e "${YELLOW}Manual commands for your security group:${NC}"
  echo "aws ec2 authorize-security-group-ingress --group-id <YOUR-SG-ID> --protocol tcp --port 3002-3003 --cidr 0.0.0.0/0"
  echo "aws ec2 authorize-security-group-ingress --group-id <YOUR-SG-ID> --protocol tcp --port 3005-3008 --cidr 0.0.0.0/0" 
  echo "aws ec2 authorize-security-group-ingress --group-id <YOUR-SG-ID> --protocol tcp --port 3010 --cidr 0.0.0.0/0"
  echo "aws ec2 authorize-security-group-ingress --group-id <YOUR-SG-ID> --protocol tcp --port 3014 --cidr 0.0.0.0/0"
  echo "aws ec2 authorize-security-group-ingress --group-id <YOUR-SG-ID> --protocol tcp --port 3047-3048 --cidr 0.0.0.0/0"
  exit 0
fi

echo -e "${GREEN}Found instance: $INSTANCE_ID${NC}"

# Get security group ID
SG_ID=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --query "Reservations[0].Instances[0].SecurityGroups[0].GroupId" \
  --output text)

echo -e "${GREEN}Security Group ID: $SG_ID${NC}"

# Define ports to open
PORTS=(
  "3002-3003:Auth and Sensor Data services"
  "3005-3008:Monitoring services (moisture, weather, water-level) and GIS"
  "3010:AWD Control service"
  "3014:Flow Monitoring service"
  "3047-3048:ROS and RID-MS services"
  "1883:MQTT Broker"
)

echo -e "${BLUE}Adding inbound rules for service ports...${NC}"

for port_info in "${PORTS[@]}"; do
  IFS=':' read -r port_range description <<< "$port_info"
  echo -e "${YELLOW}Opening port $port_range - $description${NC}"
  
  # Check if rule already exists
  existing=$(aws ec2 describe-security-groups \
    --group-ids "$SG_ID" \
    --query "SecurityGroups[0].IpPermissions[?FromPort==\`${port_range%-*}\`]" \
    --output text 2>/dev/null || echo "")
  
  if [ -n "$existing" ] && [ "$existing" != "None" ]; then
    echo "  Rule already exists, skipping..."
  else
    # Add the rule
    if aws ec2 authorize-security-group-ingress \
      --group-id "$SG_ID" \
      --protocol tcp \
      --port "$port_range" \
      --cidr 0.0.0.0/0 2>/dev/null; then
      echo -e "  ${GREEN}✓ Added successfully${NC}"
    else
      echo -e "  ${YELLOW}Rule may already exist or failed to add${NC}"
    fi
  fi
done

echo -e "\n${GREEN}Security group update complete!${NC}"
echo -e "${BLUE}Current inbound rules:${NC}"
aws ec2 describe-security-groups \
  --group-ids "$SG_ID" \
  --query 'SecurityGroups[0].IpPermissions[?IpProtocol==`tcp`].[FromPort,ToPort,IpRanges[0].CidrIp]' \
  --output table

echo -e "\n${GREEN}You can now access services from:${NC}"
echo "http://43.209.22.250:3005/health - Moisture Monitoring"
echo "http://43.209.22.250:3008/health - Water Level Monitoring"
echo "http://43.209.22.250:3014/health - Flow Monitoring"