#!/bin/bash

# Final fix for all services - use correct database containers
set -e

EC2_IP="43.209.22.250"
SSH_KEY="/Users/subhajlimanond/dev/munbon2-backend/th-lab01.pem"
EC2_USER="ubuntu"

echo "=== Final fix for all services ==="

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
cd /home/ubuntu/munbon2-backend

echo "1. Creating databases in correct containers..."

# Create sensor_data in munbon-timescaledb (5433)
echo "Creating sensor_data in munbon-timescaledb..."
docker exec munbon-timescaledb psql -U postgres -c "CREATE DATABASE sensor_data;" 2>/dev/null || echo "Database exists"
docker exec munbon-timescaledb psql -U postgres -d sensor_data -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;" 2>/dev/null || true

# Create other databases in munbon-postgres (5434)
echo "Creating databases in munbon-postgres..."
for db in auth_db gis_db ros_db rid_db weather_db awd_db; do
    docker exec munbon-postgres psql -U postgres -c "CREATE DATABASE $db;" 2>/dev/null || echo "$db exists"
done

# Enable PostGIS for gis_db
docker exec munbon-postgres psql -U postgres -d gis_db -c "CREATE EXTENSION IF NOT EXISTS postgis;" 2>/dev/null || true

echo -e "\n2. Updating service configurations..."

# Fix sensor-data to use munbon-timescaledb (5433)
cat > services/sensor-data/.env << 'ENVEOF'
NODE_ENV=production
PORT=3003
HOST=0.0.0.0

# TimescaleDB
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_DB=sensor_data
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=postgres123
TIMESCALE_DATABASE=sensor_data

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

# AWS
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/test/test
ENVEOF

# Fix auth to use munbon-postgres (5434)
cat > services/auth/.env << 'ENVEOF'
NODE_ENV=production
PORT=3002
HOST=0.0.0.0

DATABASE_URL=postgresql://postgres:postgres123@localhost:5434/auth_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5434
POSTGRES_DB=auth_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123

JWT_SECRET=your-jwt-secret-key
REDIS_URL=redis://localhost:6379
ENVEOF

# Fix gis to use munbon-postgres (5434)
cat > services/gis/.env << 'ENVEOF'
NODE_ENV=production
PORT=3007
HOST=0.0.0.0

DATABASE_URL=postgresql://postgres:postgres123@localhost:5434/gis_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5434
POSTGRES_DB=gis_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123

REDIS_URL=redis://localhost:6379
ENVEOF

# Fix weather-monitoring
cat > services/weather-monitoring/.env << 'ENVEOF'
NODE_ENV=production
PORT=3006
HOST=0.0.0.0
CORS_ORIGIN=*

# TimescaleDB for sensor data
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_DATABASE=sensor_data
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=postgres123

# PostgreSQL for weather data
POSTGRES_HOST=localhost
POSTGRES_PORT=5434
POSTGRES_DATABASE=weather_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123

MQTT_BROKER_URL=mqtt://localhost:1883
REDIS_HOST=localhost
REDIS_PORT=6379
ENVEOF

# Fix ros
cat > services/ros/.env << 'ENVEOF'
NODE_ENV=production
PORT=3047
HOST=0.0.0.0

DATABASE_URL=postgresql://postgres:postgres123@localhost:5434/ros_db
DB_HOST=localhost
DB_PORT=5434
DB_NAME=ros_db
DB_USER=postgres
DB_PASSWORD=postgres123
POSTGRES_HOST=localhost
POSTGRES_PORT=5434
POSTGRES_DB=ros_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123

REDIS_HOST=localhost
REDIS_PORT=6379
ENVEOF

# Fix rid-ms
cat > services/rid-ms/.env << 'ENVEOF'
NODE_ENV=production
PORT=3048
HOST=0.0.0.0

DATABASE_URL=postgresql://postgres:postgres123@localhost:5434/rid_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5434
POSTGRES_DB=rid_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123

REDIS_HOST=localhost
REDIS_PORT=6379
ENVEOF

# Fix awd-control
cat > services/awd-control/.env << 'ENVEOF'
NODE_ENV=production
PORT=3010
HOST=0.0.0.0

# PostgreSQL for control data
POSTGRES_HOST=localhost
POSTGRES_PORT=5434
POSTGRES_DB=awd_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123

# TimescaleDB for sensor data
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_DB=sensor_data
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=postgres123

REDIS_HOST=localhost
REDIS_PORT=6379
ENVEOF

echo -e "\n3. Installing missing dependencies..."
cd services/gis && npm install express-async-handler && cd ../..
cd services/rid-ms && npm install node-cron @nestjs/swagger && cd ../..

echo -e "\n4. Restarting all services..."
pm2 delete all || true

# Start services with correct interpreters
pm2 start services/sensor-data/src/cmd/server/main.ts --name sensor-data --interpreter "node" --interpreter-args "-r ts-node/register"
pm2 start services/auth/src/index.ts --name auth --interpreter "npx" --interpreter-args "ts-node --transpile-only"
pm2 start services/weather-monitoring/src/index.ts --name weather-monitoring --interpreter "npx" --interpreter-args "ts-node"
pm2 start services/gis/src/index.ts --name gis --interpreter "npx" --interpreter-args "ts-node"
pm2 start services/moisture-monitoring/src/index.ts --name moisture-monitoring --interpreter "npx" --interpreter-args "ts-node"
pm2 start services/water-level-monitoring/src/index.ts --name water-level-monitoring --interpreter "npx" --interpreter-args "ts-node"
pm2 start services/awd-control/src/index.ts --name awd-control --interpreter "npx" --interpreter-args "ts-node"
pm2 start services/ros/src/index.ts --name ros --interpreter "npx" --interpreter-args "ts-node"
pm2 start services/rid-ms/src/main.ts --name rid-ms --interpreter "npx" --interpreter-args "ts-node"
pm2 start services/flow-monitoring/src/main.py --name flow-monitoring --interpreter "python3"

pm2 save

echo -e "\n5. Waiting for services to stabilize..."
sleep 30

echo -e "\n6. Final status check..."
echo "=== PM2 Status ==="
pm2 list

echo -e "\n=== Port Status ==="
services=(
    "auth:3002"
    "sensor-data:3003"
    "moisture-monitoring:3005"
    "weather-monitoring:3006"
    "gis:3007"
    "water-level-monitoring:3008"
    "awd-control:3010"
    "flow-monitoring:3014"
    "ros:3047"
    "rid-ms:3048"
)

working=0
for service_info in "${services[@]}"; do
    IFS=':' read -r name port <<< "$service_info"
    printf "%-25s (port %s): " "$name" "$port"
    if timeout 1 bash -c "</dev/tcp/localhost/$port" 2>/dev/null; then
        echo "✓ WORKING"
        ((working++))
    else
        echo "✗ NOT WORKING"
    fi
done

echo -e "\nTotal working: $working/10"

echo -e "\n=== Database Status ==="
docker ps --format "table {{.Names}}\t{{.Ports}}\t{{.Status}}" | grep -E "NAME|postgres|timescale|redis|mongo|influx"

EOF

echo "Fix complete!"