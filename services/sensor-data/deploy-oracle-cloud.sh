#!/bin/bash

echo "Deploy to Oracle Cloud Free Tier"
echo "================================"
echo ""
echo "1. Sign up at: https://signup.cloud.oracle.com/"
echo "   - Use real info (they verify)"
echo "   - Credit card required but NOT charged"
echo ""
echo "2. Create Always Free ARM VM:"
echo "   - Shape: VM.Standard.A1.Flex"
echo "   - OCPU: 1"
echo "   - RAM: 6 GB"
echo "   - Ubuntu 22.04"
echo ""
echo "3. SSH to instance and setup:"

cat > setup-on-oracle.sh << 'EOF'
# Update system
sudo apt update && sudo apt upgrade -y

# Install Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install PM2
sudo npm install -g pm2

# Clone your repo
git clone https://github.com/yourusername/munbon2-backend.git
cd munbon2-backend/services/sensor-data

# Install dependencies
npm install

# Setup environment
cat > .env << 'ENVFILE'
TIMESCALE_HOST=your-timescale-host
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

# Start with PM2
pm2 start src/unified-api.js --name unified-api
pm2 save
pm2 startup

# Open firewall
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 3000 -j ACCEPT
sudo netfilter-persistent save
EOF

echo ""
echo "4. Update Lambda to use: http://your-oracle-ip:3000"
echo "   No more tunnel needed!"