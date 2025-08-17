#!/bin/bash

# Fix sensor-data service (port 3003)
set -e

EC2_IP="${EC2_HOST:-43.208.201.191}"
SSH_KEY="/Users/subhajlimanond/dev/munbon2-backend/th-lab01.pem"
EC2_USER="ubuntu"

echo "=== Fixing sensor-data service (3003) ==="

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
cd /home/ubuntu/munbon2-backend

echo "1. Creating sensor_data database in TimescaleDB..."
docker exec munbon-timescaledb psql -U postgres -c "CREATE DATABASE sensor_data;" 2>/dev/null || echo "Database may already exist"

echo "2. Enabling TimescaleDB extension..."
docker exec munbon-timescaledb psql -U postgres -d sensor_data -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" 2>/dev/null || true

echo "3. Updating sensor-data .env with correct settings..."
cat > services/sensor-data/.env << 'ENVEOF'
NODE_ENV=production
PORT=3003
HOST=0.0.0.0
HEALTH_MONITOR_PORT=3003

# TimescaleDB
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_DB=sensor_data
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=postgres123
TIMESCALE_DATABASE=sensor_data

# Alternative connection strings
DATABASE_URL=postgresql://postgres:postgres123@localhost:5433/sensor_data
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=sensor_data
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_URL=redis://localhost:6379

# AWS (dummy values for now)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=dummy
AWS_SECRET_ACCESS_KEY=dummy
SQS_QUEUE_URL=dummy
ENVEOF

echo "4. Restarting sensor-data with PM2..."
pm2 delete sensor-data 2>/dev/null || true
pm2 start services/sensor-data/src/cmd/server/main.ts --name sensor-data --interpreter "npx" --interpreter-args "ts-node" -- --port 3003

echo "5. Waiting for service to start..."
sleep 15

echo "6. Testing sensor-data on port 3003..."
if timeout 2 bash -c "</dev/tcp/localhost/3003" 2>/dev/null; then
    echo "✓ Port 3003 is open"
    curl -s http://localhost:3003/health | head -100 || echo "No health response"
else
    echo "✗ Port 3003 is not open"
    echo "Checking logs..."
    pm2 logs sensor-data --lines 20 --nostream | grep -i error | tail -10
fi

echo "7. Service status:"
pm2 describe sensor-data | grep -E "status|restarts|uptime"
EOF