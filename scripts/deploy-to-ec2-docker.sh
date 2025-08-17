#!/bin/bash

# Deploy services to EC2 using Docker Compose

echo "=== Deploying Services to EC2 with Docker ==="
echo ""

# Configuration
EC2_HOST="${EC2_HOST:-43.208.201.191}"
EC2_USER="ubuntu"  # Adjust if different
PROJECT_DIR="/home/ubuntu/munbon2-backend"
LOCAL_DIR="/Users/subhajlimanond/dev/munbon2-backend"

# Check if we can connect to EC2
echo "Testing connection to EC2..."
nc -zv $EC2_HOST 22 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Cannot connect to EC2 on port 22"
    echo "Please ensure:"
    echo "1. EC2 instance is running"
    echo "2. SSH port 22 is open in security group"
    echo "3. You have the correct SSH key"
    exit 1
fi

echo "✅ EC2 is reachable"
echo ""

# Since we can't SSH directly, let's create a local deployment package
echo "Creating deployment package..."

# Create deployment directory
DEPLOY_DIR="/tmp/munbon-deploy-$(date +%s)"
mkdir -p $DEPLOY_DIR

# Copy necessary files
cp $LOCAL_DIR/docker-compose.ec2-consolidated.yml $DEPLOY_DIR/docker-compose.yml
cp $LOCAL_DIR/.env.ec2 $DEPLOY_DIR/.env

# Copy service directories (only the ones we need for now)
echo "Copying service files..."
mkdir -p $DEPLOY_DIR/services
cp -r $LOCAL_DIR/services/sensor-data $DEPLOY_DIR/services/
cp -r $LOCAL_DIR/services/auth $DEPLOY_DIR/services/
cp -r $LOCAL_DIR/services/gis $DEPLOY_DIR/services/

# Create deployment instructions
cat > $DEPLOY_DIR/deploy-instructions.md << 'EOF'
# EC2 Deployment Instructions

Since SSH access is not configured, please follow these manual steps:

## 1. Transfer Files to EC2

Use your preferred method to transfer this deployment package to EC2:
- SCP if you have SSH access
- Upload via a web interface if available
- Use cloud storage as intermediary

## 2. On the EC2 Instance

```bash
# Navigate to the deployment directory
cd /home/ubuntu/munbon2-backend

# Create necessary directories
mkdir -p services

# Copy the services from deployment package
cp -r /path/to/deployment/services/* ./services/

# Copy docker-compose.yml and .env
cp /path/to/deployment/docker-compose.yml .
cp /path/to/deployment/.env .

# Build and start services
docker-compose build
docker-compose up -d

# Check running containers
docker ps

# View logs
docker-compose logs -f
```

## 3. Verify Services

Check that services are running:
- Sensor Data API: http://${EC2_HOST:-43.208.201.191}:3001/health
- Consumer Dashboard: http://${EC2_HOST:-43.208.201.191}:3002
- Auth Service: http://${EC2_HOST:-43.208.201.191}:3003/health
- GIS Service: http://${EC2_HOST:-43.208.201.191}:3004/health

## 4. Database Setup

If not already done, initialize the database:
```bash
docker-compose exec sensor-data npm run migrate
```
EOF

echo ""
echo "Deployment package created at: $DEPLOY_DIR"
echo ""

# Create a simpler automated deployment script
cat > $LOCAL_DIR/scripts/deploy-via-docker-commands.sh << 'EOF'
#!/bin/bash

# Direct Docker deployment commands for EC2
# Run these commands on the EC2 instance

echo "=== EC2 Docker Deployment ==="
echo ""

# Pull latest images (if using Docker Hub)
# docker pull munbon/sensor-data:latest
# docker pull munbon/auth:latest

# Stop existing containers
docker stop munbon-sensor-data munbon-sensor-data-consumer munbon-auth munbon-gis || true
docker rm munbon-sensor-data munbon-sensor-data-consumer munbon-auth munbon-gis || true

# Start PostgreSQL if not running
docker ps | grep postgres || docker run -d \
  --name postgres \
  -e POSTGRES_PASSWORD=P@ssw0rd123! \
  -p 5432:5432 \
  -v postgres_data:/var/lib/postgresql/data \
  postgres:13-alpine

# Start Redis if not running  
docker ps | grep redis || docker run -d \
  --name redis \
  -p 6379:6379 \
  redis:6-alpine

# Wait for PostgreSQL to be ready
sleep 5

# Run sensor-data service
docker run -d \
  --name munbon-sensor-data \
  --network host \
  -e NODE_ENV=production \
  -e PORT=3001 \
  -e TIMESCALE_HOST=localhost \
  -e TIMESCALE_PORT=5432 \
  -e TIMESCALE_DB=sensor_data \
  -e TIMESCALE_USER=postgres \
  -e TIMESCALE_PASSWORD=P@ssw0rd123! \
  -e REDIS_HOST=localhost \
  -e REDIS_PORT=6379 \
  -v /home/ubuntu/munbon2-backend/services/sensor-data:/app \
  -w /app \
  node:18-alpine \
  sh -c "npm install && npm start"

# Run consumer service
docker run -d \
  --name munbon-sensor-data-consumer \
  --network host \
  -e NODE_ENV=production \
  -e CONSUMER_PORT=3002 \
  -e TIMESCALE_HOST=localhost \
  -e TIMESCALE_PORT=5432 \
  -e TIMESCALE_DB=sensor_data \
  -e TIMESCALE_USER=postgres \
  -e TIMESCALE_PASSWORD=P@ssw0rd123! \
  -e AWS_REGION=ap-southeast-1 \
  -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  -e SQS_QUEUE_URL=https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue \
  -v /home/ubuntu/munbon2-backend/services/sensor-data:/app \
  -w /app \
  node:18-alpine \
  sh -c "npm install && npm run consumer:prod"

echo ""
echo "Services deployed!"
echo "Check status: docker ps"
echo "View logs: docker logs -f munbon-sensor-data"
EOF

chmod +x $LOCAL_DIR/scripts/deploy-via-docker-commands.sh

echo "=== Deployment Package Ready ==="
echo ""
echo "Since direct SSH access is not available, you have two options:"
echo ""
echo "1. Manual deployment:"
echo "   - Package location: $DEPLOY_DIR"
echo "   - Follow instructions in: $DEPLOY_DIR/deploy-instructions.md"
echo ""
echo "2. Run commands directly on EC2:"
echo "   - Use the script: $LOCAL_DIR/scripts/deploy-via-docker-commands.sh"
echo "   - Copy and run the commands on your EC2 instance"
echo ""
echo "The services will be available at:"
echo "- Sensor Data API: http://${EC2_HOST:-43.208.201.191}:3001"
echo "- Consumer Dashboard: http://${EC2_HOST:-43.208.201.191}:3002"