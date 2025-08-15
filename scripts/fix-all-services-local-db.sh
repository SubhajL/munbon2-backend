#!/bin/bash

# Fix all services to use correct local Docker databases
set -e

EC2_IP="43.209.22.250"
SSH_KEY="/Users/subhajlimanond/dev/munbon2-backend/th-lab01.pem"
EC2_USER="ubuntu"

echo "=== Fixing all services to use local Docker databases ==="

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
cd /home/ubuntu/munbon2-backend

echo "1. Creating databases in the correct containers..."

# Port 5432 - timescaledb container (main TimescaleDB)
echo "Creating sensor_data in timescaledb container (5432)..."
docker exec timescaledb psql -U postgres -c "CREATE DATABASE sensor_data;" 2>/dev/null || true
docker exec timescaledb psql -U postgres -d sensor_data -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" 2>/dev/null || true

# Port 5434 - munbon-postgres container (for non-timeseries data)
echo "Creating databases in munbon-postgres (5434)..."
databases=("auth_db" "gis_db" "ros_db" "rid_db" "weather_db" "awd_db")
for db in "${databases[@]}"; do
    docker exec munbon-postgres psql -U postgres -c "CREATE DATABASE $db;" 2>/dev/null || echo "$db may exist"
done

# Enable PostGIS for gis_db
docker exec munbon-postgres psql -U postgres -d gis_db -c "CREATE EXTENSION IF NOT EXISTS postgis;" 2>/dev/null || true

echo -e "\n2. Fixing service configurations..."

# Fix sensor-data to use 5432
echo "Fixing sensor-data..."
cat > services/sensor-data/.env << 'ENVEOF'
NODE_ENV=production
PORT=3003
HOST=0.0.0.0
HEALTH_MONITOR_PORT=3003

# TimescaleDB on 5432
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5432
TIMESCALE_DB=sensor_data
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=postgres
TIMESCALE_DATABASE=sensor_data

DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sensor_data
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=sensor_data
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_URL=redis://localhost:6379

# AWS (dummy)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=dummy
AWS_SECRET_ACCESS_KEY=dummy
SQS_QUEUE_URL=dummy
ENVEOF

# Fix weather-monitoring
echo "Fixing weather-monitoring..."
sed -i 's/TIMESCALE_PORT=.*/TIMESCALE_PORT=5432/g' services/weather-monitoring/.env
sed -i 's/POSTGRES_PORT=.*/POSTGRES_PORT=5434/g' services/weather-monitoring/.env
sed -i 's/TIMESCALE_PASSWORD=.*/TIMESCALE_PASSWORD=postgres/g' services/weather-monitoring/.env
sed -i 's/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=postgres/g' services/weather-monitoring/.env

# Fix GIS (already correct at 5432)
echo "Fixing GIS..."
sed -i 's/POSTGRES_PORT=.*/POSTGRES_PORT=5434/g' services/gis/.env
sed -i 's/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=postgres/g' services/gis/.env
sed -i 's|DATABASE_URL=.*|DATABASE_URL=postgresql://postgres:postgres@localhost:5434/gis_db|g' services/gis/.env

# Fix ROS
echo "Fixing ROS..."
sed -i 's/DB_PORT=.*/DB_PORT=5434/g' services/ros/.env
sed -i 's/POSTGRES_PORT=.*/POSTGRES_PORT=5434/g' services/ros/.env
sed -i 's/DB_PASSWORD=.*/DB_PASSWORD=postgres/g' services/ros/.env
sed -i 's/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=postgres/g' services/ros/.env
sed -i 's|DATABASE_URL=.*|DATABASE_URL=postgresql://postgres:postgres@localhost:5434/ros_db|g' services/ros/.env

# Fix AWD-control
echo "Fixing AWD-control..."
sed -i 's/POSTGRES_PORT=.*/POSTGRES_PORT=5434/g' services/awd-control/.env
sed -i 's/TIMESCALE_PORT=.*/TIMESCALE_PORT=5432/g' services/awd-control/.env
sed -i 's/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=postgres/g' services/awd-control/.env
sed -i 's/TIMESCALE_PASSWORD=.*/TIMESCALE_PASSWORD=postgres/g' services/awd-control/.env

# Fix RID-MS
echo "Fixing RID-MS..."
sed -i 's/POSTGRES_PORT=.*/POSTGRES_PORT=5434/g' services/rid-ms/.env
sed -i 's/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=postgres/g' services/rid-ms/.env
sed -i 's|DATABASE_URL=.*|DATABASE_URL=postgresql://postgres:postgres@localhost:5434/rid_db|g' services/rid-ms/.env

echo -e "\n3. Restarting all services..."
pm2 restart all

echo -e "\n4. Waiting for services..."
sleep 15

echo -e "\n5. Testing services..."
echo "Service Status:"
for service in "sensor-data:3003" "weather-monitoring:3006" "gis:3007" "awd-control:3010" "ros:3047" "rid-ms:3048"; do
    IFS=':' read -r name port <<< "$service"
    printf "%-20s (port %s): " "$name" "$port"
    if timeout 1 bash -c "</dev/tcp/localhost/$port" 2>/dev/null; then
        echo "✓ OPEN"
    else
        echo "✗ CLOSED"
        echo "  Last error:"
        pm2 logs "$name" --lines 3 --nostream --err 2>/dev/null | grep -i error | tail -1 | sed 's/^/  /'
    fi
done

echo -e "\n6. Database check:"
echo "TimescaleDB (5432):"
docker exec timescaledb psql -U postgres -c "\l" | grep sensor_data || echo "No sensor_data"
echo -e "\nPostgreSQL (5434):"
docker exec munbon-postgres psql -U postgres -c "\l" | grep -E "auth_db|gis_db|ros_db|rid_db|awd_db" || echo "No databases"

EOF