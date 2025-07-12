#!/bin/bash

echo "Deploy to AWS EC2 Free Tier"
echo "==========================="
echo ""
echo "1. Launch EC2 Instance:"
echo "   - AMI: Amazon Linux 2023 or Ubuntu 22.04"
echo "   - Type: t2.micro (free tier)"
echo "   - Storage: 8-30 GB (free tier)"
echo "   - Security Group: Open port 3000"
echo ""
echo "2. Connect via SSH and run:"

cat > setup-ec2.sh << 'EOF'
# For Amazon Linux 2023
sudo yum update -y
sudo yum install -y nodejs npm git

# OR for Ubuntu
# sudo apt update && sudo apt install -y nodejs npm git

# Install PM2
sudo npm install -g pm2

# Clone repository
git clone https://github.com/yourusername/munbon2-backend.git
cd munbon2-backend/services/sensor-data

# Install dependencies
npm install

# Create environment file
cat > .env << 'ENVFILE'
TIMESCALE_HOST=your-rds-endpoint.amazonaws.com
TIMESCALE_PORT=5433
TIMESCALE_DB=sensor_data
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=your-password

MSSQL_HOST=moonup.hopto.org
MSSQL_PORT=1433
MSSQL_DB=db_scada
MSSQL_USER=sa
MSSQL_PASSWORD=bangkok1234

INTERNAL_API_KEY=munbon-internal-f3b89263126548
PORT=3000
ENVFILE

# Start application
pm2 start src/unified-api.js --name unified-api
pm2 save
pm2 startup

# Update Parameter Store with EC2 IP
aws ssm put-parameter \
    --name "/munbon/api-endpoint" \
    --value "http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):3000" \
    --type "String" \
    --overwrite \
    --region ap-southeast-1
EOF

echo ""
echo "3. Lambda can now connect directly via:"
echo "   - Public IP: http://your-ec2-ip:3000"
echo "   - Or via VPC if in same network"