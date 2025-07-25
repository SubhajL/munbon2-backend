#!/bin/bash

# Complete fix for sensor-data service
set -e

EC2_IP="43.209.12.182"
SSH_KEY="/Users/subhajlimanond/dev/munbon2-backend/th-lab01.pem"
EC2_USER="ubuntu"

echo "=== Fixing sensor-data service completely ==="

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
cd /home/ubuntu/munbon2-backend

echo "1. Stopping sensor-data to prevent continuous restarts..."
pm2 stop sensor-data

echo "2. Creating sensor_data database in timescaledb container (port 5432)..."
docker exec timescaledb psql -U postgres -c "CREATE DATABASE sensor_data;" 2>/dev/null || echo "Database may exist"
docker exec timescaledb psql -U postgres -d sensor_data -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;" 2>/dev/null || true

echo "3. Creating .env file for sensor-data..."
cat > services/sensor-data/.env << 'ENVEOF'
NODE_ENV=production
PORT=3003
HOST=0.0.0.0

# TimescaleDB connection (port 5432)
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5432
TIMESCALE_DB=sensor_data
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=postgres
TIMESCALE_DATABASE=sensor_data

# Also set POSTGRES vars for compatibility
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=sensor_data
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sensor_data

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_URL=redis://localhost:6379

# AWS (dummy for now)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=dummy
AWS_SECRET_ACCESS_KEY=dummy
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/dummy/queue

# Monitoring
HEALTH_MONITOR_PORT=3003
ENVEOF

echo "4. Installing dependencies..."
cd services/sensor-data
npm install --production

echo "5. Testing database connection..."
docker exec timescaledb psql -U postgres -d sensor_data -c "SELECT version();" && echo "✓ Database connection successful"

echo "6. Starting sensor-data service..."
cd /home/ubuntu/munbon2-backend
pm2 start services/sensor-data/src/cmd/server/main.ts --name sensor-data \
  --interpreter "node" \
  --interpreter-args "-r ts-node/register" \
  --env production \
  --update-env \
  --merge-logs

echo "7. Waiting for service to stabilize..."
sleep 10

echo "8. Checking service status..."
pm2 describe sensor-data | grep -E "status|restarts|uptime"

echo "9. Testing port 3003..."
if timeout 2 bash -c "</dev/tcp/localhost/3003" 2>/dev/null; then
    echo "✓ Port 3003 is open"
    curl -s http://localhost:3003/health | head -20 || echo "No health endpoint"
else
    echo "✗ Port 3003 is not open"
    echo "Recent logs:"
    pm2 logs sensor-data --lines 20 --nostream
fi

EOF

echo "Fix complete!"