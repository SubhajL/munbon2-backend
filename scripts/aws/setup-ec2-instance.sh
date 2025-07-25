#!/bin/bash

# EC2 Instance Setup Script for Munbon Backend
# This script creates an EC2 instance and configures it for deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
AWS_REGION="${AWS_REGION:-ap-southeast-1}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.medium}"  # 2 vCPU, 4GB RAM
KEY_NAME="${KEY_NAME:-munbon-ec2-key}"
SECURITY_GROUP_NAME="munbon-backend-sg"
INSTANCE_NAME="munbon-backend-server"

echo -e "${BLUE}[INFO]${NC} Setting up EC2 instance for Munbon Backend"
echo -e "${BLUE}[INFO]${NC} Region: $AWS_REGION"
echo -e "${BLUE}[INFO]${NC} Instance Type: $INSTANCE_TYPE"

# Get latest Ubuntu 22.04 AMI
echo -e "${BLUE}[INFO]${NC} Finding latest Ubuntu 22.04 AMI..."
AMI_ID=$(aws ec2 describe-images \
    --owners 099720109477 \
    --filters \
        "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
        "Name=state,Values=available" \
    --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
    --output text \
    --region $AWS_REGION)

echo -e "${GREEN}[SUCCESS]${NC} Found AMI: $AMI_ID"

# Create key pair if not exists
echo -e "${BLUE}[INFO]${NC} Checking for SSH key pair..."
if aws ec2 describe-key-pairs --key-names "$KEY_NAME" --region $AWS_REGION &> /dev/null; then
    echo -e "${YELLOW}[WARNING]${NC} Key pair $KEY_NAME already exists"
else
    echo -e "${BLUE}[INFO]${NC} Creating new key pair..."
    aws ec2 create-key-pair \
        --key-name "$KEY_NAME" \
        --query 'KeyMaterial' \
        --output text \
        --region $AWS_REGION > "$KEY_NAME.pem"
    chmod 400 "$KEY_NAME.pem"
    echo -e "${GREEN}[SUCCESS]${NC} Key pair created and saved to $KEY_NAME.pem"
    echo -e "${YELLOW}[WARNING]${NC} Keep this key file safe! You'll need it for SSH access."
fi

# Get default VPC
VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=is-default,Values=true" \
    --query "Vpcs[0].VpcId" \
    --output text \
    --region $AWS_REGION)

# Create security group
echo -e "${BLUE}[INFO]${NC} Creating security group..."
SG_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=$SECURITY_GROUP_NAME" \
    --query "SecurityGroups[0].GroupId" \
    --output text \
    --region $AWS_REGION 2>/dev/null)

if [ "$SG_ID" == "None" ] || [ -z "$SG_ID" ]; then
    SG_ID=$(aws ec2 create-security-group \
        --group-name "$SECURITY_GROUP_NAME" \
        --description "Security group for Munbon Backend" \
        --vpc-id "$VPC_ID" \
        --query "GroupId" \
        --output text \
        --region $AWS_REGION)
    
    echo -e "${BLUE}[INFO]${NC} Adding security group rules..."
    
    # SSH access
    aws ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp \
        --port 22 \
        --cidr 0.0.0.0/0 \
        --region $AWS_REGION
    
    # Application ports
    for port in 3000 3001 3002 3003 3006 3011 3012 4001 4002 4003 8000 8001; do
        aws ec2 authorize-security-group-ingress \
            --group-id "$SG_ID" \
            --protocol tcp \
            --port $port \
            --cidr 0.0.0.0/0 \
            --region $AWS_REGION
    done
    
    # Database ports (restricted to VPC)
    VPC_CIDR=$(aws ec2 describe-vpcs \
        --vpc-ids "$VPC_ID" \
        --query "Vpcs[0].CidrBlock" \
        --output text \
        --region $AWS_REGION)
    
    for port in 5432 5433 6379 8086 27017; do
        aws ec2 authorize-security-group-ingress \
            --group-id "$SG_ID" \
            --protocol tcp \
            --port $port \
            --cidr "$VPC_CIDR" \
            --region $AWS_REGION
    done
    
    echo -e "${GREEN}[SUCCESS]${NC} Security group created: $SG_ID"
else
    echo -e "${YELLOW}[WARNING]${NC} Security group already exists: $SG_ID"
fi

# Create EC2 instance
echo -e "${BLUE}[INFO]${NC} Launching EC2 instance..."

# User data script to pre-install Docker
USER_DATA=$(cat <<'EOF'
#!/bin/bash
apt-get update
apt-get install -y curl git

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
usermod -aG docker ubuntu

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.20.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install Node.js and PM2
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
export NVM_DIR="/home/ubuntu/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm install 18
npm install -g pm2

# Configure PM2 to start on boot
pm2 startup systemd -u ubuntu --hp /home/ubuntu
EOF
)

INSTANCE_ID=$(aws ec2 run-instances \
    --image-id "$AMI_ID" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_NAME" \
    --security-group-ids "$SG_ID" \
    --user-data "$USER_DATA" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
    --query "Instances[0].InstanceId" \
    --output text \
    --region $AWS_REGION)

echo -e "${GREEN}[SUCCESS]${NC} Instance launched: $INSTANCE_ID"

# Wait for instance to be running
echo -e "${BLUE}[INFO]${NC} Waiting for instance to be running..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region $AWS_REGION

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE_ID" \
    --query "Reservations[0].Instances[0].PublicIpAddress" \
    --output text \
    --region $AWS_REGION)

echo -e "${GREEN}[SUCCESS]${NC} Instance is running!"
echo -e "${GREEN}[SUCCESS]${NC} Public IP: $PUBLIC_IP"

# Create GitHub secrets file
cat > github-secrets.txt << EOL
EC2_HOST=$PUBLIC_IP
EC2_USER=ubuntu
EC2_SSH_KEY=<contents of $KEY_NAME.pem>
EOL

# Output summary
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}EC2 Instance Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "\nInstance Details:"
echo -e "- Instance ID: $INSTANCE_ID"
echo -e "- Public IP: $PUBLIC_IP"
echo -e "- Instance Type: $INSTANCE_TYPE"
echo -e "- Security Group: $SG_ID"
echo -e "- SSH Key: $KEY_NAME.pem"
echo -e "\nNext Steps:"
echo -e "1. Add these secrets to your GitHub repository:"
echo -e "   - EC2_HOST: $PUBLIC_IP"
echo -e "   - EC2_USER: ubuntu"
echo -e "   - EC2_SSH_KEY: (contents of $KEY_NAME.pem)"
echo -e "\n2. Test SSH connection:"
echo -e "   ssh -i $KEY_NAME.pem ubuntu@$PUBLIC_IP"
echo -e "\n3. Push code to trigger deployment!"
echo -e "\nIMPORTANT: Save the $KEY_NAME.pem file securely!"