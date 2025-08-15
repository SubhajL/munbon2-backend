#!/bin/bash

# Deploy enhanced moisture HTTP server to EC2
# This script updates the moisture service to handle the new JSON format

set -e

echo "🚀 Deploying enhanced moisture service to EC2..."

# Server details
EC2_HOST="43.209.22.250"
EC2_USER="ubuntu"
SSH_KEY="$HOME/dev/th-lab01.pem"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}📦 Preparing files for deployment...${NC}"

# Create deployment directory
DEPLOY_DIR="/tmp/moisture-deploy-$(date +%s)"
mkdir -p $DEPLOY_DIR

# Copy enhanced server file
cp src/simple-http-server-enhanced.ts $DEPLOY_DIR/simple-http-server.ts
cp src/services/sqs-processor-enhanced.ts $DEPLOY_DIR/sqs-processor-enhanced.ts

# Copy package files
cp package.json $DEPLOY_DIR/
cp package-lock.json $DEPLOY_DIR/
cp tsconfig.json $DEPLOY_DIR/

# Create backup script
cat > $DEPLOY_DIR/backup-and-deploy.sh << 'EOF'
#!/bin/bash
set -e

echo "📋 Creating backup of current moisture service..."
cd /home/ubuntu/app/moisture-http-server
mkdir -p backups
cp -r src backups/src-$(date +%Y%m%d-%H%M%S)

echo "📥 Updating moisture HTTP server..."
cp /tmp/moisture-deploy/simple-http-server.ts src/simple-http-server.ts

echo "📥 Adding enhanced SQS processor..."
mkdir -p src/services
cp /tmp/moisture-deploy/sqs-processor-enhanced.ts src/services/

echo "📦 Installing dependencies..."
npm install

echo "🔄 Restarting moisture service..."
pm2 restart moisture-http

echo "✅ Deployment complete!"
echo "📊 Check logs with: pm2 logs moisture-http"
EOF

chmod +x $DEPLOY_DIR/backup-and-deploy.sh

echo -e "${YELLOW}📤 Uploading files to EC2...${NC}"

# Copy files to EC2
scp -i $SSH_KEY -r $DEPLOY_DIR $EC2_USER@$EC2_HOST:/tmp/moisture-deploy

echo -e "${YELLOW}🔧 Running deployment on EC2...${NC}"

# Execute deployment
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "sudo bash /tmp/moisture-deploy/backup-and-deploy.sh"

echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "📊 To check the service status:"
echo "   ssh -i $SSH_KEY $EC2_USER@$EC2_HOST 'pm2 status moisture-http'"
echo ""
echo "📋 To view logs:"
echo "   ssh -i $SSH_KEY $EC2_USER@$EC2_HOST 'pm2 logs moisture-http --lines 50'"
echo ""
echo "📈 To check statistics:"
echo "   curl http://$EC2_HOST:8080/api/stats"
echo ""
echo "🧪 To test with sample data:"
echo "   ./test-moisture-with-sensors.sh"

# Cleanup
rm -rf $DEPLOY_DIR