#!/bin/bash

# Quick Deploy Script for Oracle Cloud Instance
# Assumes you already have an Oracle Cloud instance running

set -e

# Configuration - Update these values
ORACLE_INSTANCE_IP="${ORACLE_INSTANCE_IP:-}"  # Set your Oracle instance IP
SSH_KEY_PATH="${SSH_KEY_PATH:-~/.ssh/munbon-oracle}"
INTERNAL_API_KEY="${INTERNAL_API_KEY:-munbon-internal-f3b89263126548}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if IP is provided
if [ -z "$ORACLE_INSTANCE_IP" ]; then
    echo -e "${RED}Error: Please set ORACLE_INSTANCE_IP environment variable${NC}"
    echo "Usage: ORACLE_INSTANCE_IP=xxx.xxx.xxx.xxx ./quick-deploy-oracle.sh"
    exit 1
fi

echo -e "${GREEN}======================================"
echo "Quick Deploy to Oracle Cloud"
echo "Target: $ORACLE_INSTANCE_IP"
echo "======================================${NC}"

# Create deployment package
echo -e "${YELLOW}Creating deployment package...${NC}"
mkdir -p /tmp/munbon-deploy/src

# Copy necessary files
cp src/unified-api-v2.js /tmp/munbon-deploy/src/
cp package.json /tmp/munbon-deploy/
cp package-lock.json /tmp/munbon-deploy/ 2>/dev/null || true

# Create simplified Dockerfile
cat > /tmp/munbon-deploy/Dockerfile << 'EOF'
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production || npm install --production

# Copy application
COPY src/unified-api-v2.js ./src/

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000/health', (r) => { process.exit(r.statusCode === 200 ? 0 : 1); })"

# Start application
CMD ["node", "src/unified-api-v2.js"]
EOF

# Create docker-compose.yml
cat > /tmp/munbon-deploy/docker-compose.yml << EOF
version: '3.8'

services:
  unified-api:
    build: .
    container_name: munbon-unified-api
    restart: always
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - PORT=3000
      - INTERNAL_API_KEY=$INTERNAL_API_KEY
      # TimescaleDB settings (update if needed)
      - TIMESCALE_HOST=host.docker.internal
      - TIMESCALE_PORT=5433
      - TIMESCALE_DB=sensor_data
      - TIMESCALE_USER=postgres
      - TIMESCALE_PASSWORD=postgres
      # MSSQL settings
      - MSSQL_HOST=moonup.hopto.org
      - MSSQL_PORT=1433
      - MSSQL_DB=db_scada
      - MSSQL_USER=sa
      - MSSQL_PASSWORD=bangkok1234
    extra_hosts:
      - "host.docker.internal:host-gateway"
EOF

# Create deployment script
cat > /tmp/munbon-deploy/deploy.sh << 'EOF'
#!/bin/bash
cd /opt/munbon-api
sudo docker-compose down || true
sudo docker-compose build
sudo docker-compose up -d
echo "Deployment complete! Checking status..."
sleep 5
sudo docker-compose ps
sudo docker-compose logs --tail=50
EOF

chmod +x /tmp/munbon-deploy/deploy.sh

# Copy files to server
echo -e "${YELLOW}Copying files to Oracle instance...${NC}"
ssh -i $SSH_KEY_PATH -o StrictHostKeyChecking=no opc@$ORACLE_INSTANCE_IP "sudo mkdir -p /opt/munbon-api && sudo chown opc:opc /opt/munbon-api"
scp -i $SSH_KEY_PATH -r /tmp/munbon-deploy/* opc@$ORACLE_INSTANCE_IP:/opt/munbon-api/

# Deploy application
echo -e "${YELLOW}Deploying application...${NC}"
ssh -i $SSH_KEY_PATH opc@$ORACLE_INSTANCE_IP 'bash /opt/munbon-api/deploy.sh'

# Update AWS Lambda configuration
echo -e "${YELLOW}Updating AWS Lambda configuration...${NC}"
aws lambda update-function-configuration \
    --function-name munbon-sensor-handler \
    --environment "Variables={UNIFIED_API_URL=http://$ORACLE_INSTANCE_IP:3000,INTERNAL_API_KEY=$INTERNAL_API_KEY}" \
    --region ap-southeast-1 2>/dev/null || echo "Note: AWS Lambda update skipped (AWS CLI not configured or Lambda not found)"

# Test deployment
echo -e "${YELLOW}Testing deployment...${NC}"
sleep 10

# Test health endpoint
echo "Testing health endpoint..."
curl -s http://$ORACLE_INSTANCE_IP:3000/health | jq . || echo "Health check failed"

# Test API endpoint
echo -e "\nTesting API endpoint..."
curl -s -X GET http://$ORACLE_INSTANCE_IP:3000/api/v1/sensors/water-level/latest \
    -H "x-internal-key: $INTERNAL_API_KEY" | jq . || echo "API test failed"

echo -e "\n${GREEN}======================================"
echo "Deployment Complete!"
echo "======================================"
echo "Unified API URL: http://$ORACLE_INSTANCE_IP:3000"
echo ""
echo "To view logs:"
echo "ssh -i $SSH_KEY_PATH opc@$ORACLE_INSTANCE_IP 'sudo docker-compose -f /opt/munbon-api/docker-compose.yml logs -f'"
echo ""
echo "To restart service:"
echo "ssh -i $SSH_KEY_PATH opc@$ORACLE_INSTANCE_IP 'cd /opt/munbon-api && sudo docker-compose restart'"
echo "======================================${NC}"

# Cleanup
rm -rf /tmp/munbon-deploy