#!/bin/bash

# Migrate all services to use AWS RDS on port 5432
set -e

EC2_IP="${EC2_HOST:-43.208.201.191}"
SSH_KEY="/Users/subhajlimanond/dev/munbon2-backend/th-lab01.pem"
EC2_USER="ubuntu"

echo "=== Migrating all services to AWS RDS (port 5432) ==="

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
cd /home/ubuntu/munbon2-backend

echo "1. Installing PostgreSQL client..."
sudo apt-get update -qq
sudo apt-get install -y postgresql-client

echo -e "\n2. Testing AWS RDS connection..."
PGPASSWORD=postgres123 psql -h localhost -p 5432 -U postgres -c "SELECT current_database();" || { echo "Failed to connect to AWS RDS"; exit 1; }

echo -e "\n3. Creating all required databases on AWS RDS..."
databases=(
    "sensor_data"
    "auth_db"
    "gis_db"
    "ros_db"
    "rid_db"
    "weather_db"
    "awd_db"
)

for db in "${databases[@]}"; do
    echo "Creating database: $db"
    PGPASSWORD=postgres123 psql -h localhost -p 5432 -U postgres -c "CREATE DATABASE $db;" 2>/dev/null || echo "Database $db may already exist"
done

echo -e "\n4. Enabling TimescaleDB extension for sensor_data..."
PGPASSWORD=postgres123 psql -h localhost -p 5432 -U postgres -d sensor_data -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;" 2>/dev/null || echo "TimescaleDB extension may not be available on RDS"

echo -e "\n5. Enabling PostGIS for gis_db..."
PGPASSWORD=postgres123 psql -h localhost -p 5432 -U postgres -d gis_db -c "CREATE EXTENSION IF NOT EXISTS postgis;" 2>/dev/null || echo "PostGIS may not be available"

echo -e "\n6. Updating all service .env files to use AWS RDS (5432)..."

# Update sensor-data
echo "Updating sensor-data..."
sed -i 's/TIMESCALE_PORT=5433/TIMESCALE_PORT=5432/g' services/sensor-data/.env
sed -i 's/localhost:5433/localhost:5432/g' services/sensor-data/.env
sed -i 's/POSTGRES_PORT=5433/POSTGRES_PORT=5432/g' services/sensor-data/.env

# Update weather-monitoring
echo "Updating weather-monitoring..."
sed -i 's/TIMESCALE_PORT=5433/TIMESCALE_PORT=5432/g' services/weather-monitoring/.env
sed -i 's/POSTGRES_PORT=5434/POSTGRES_PORT=5432/g' services/weather-monitoring/.env

# Update moisture-monitoring
echo "Updating moisture-monitoring..."
sed -i 's/TIMESCALE_PORT=5433/TIMESCALE_PORT=5432/g' services/moisture-monitoring/.env

# Update water-level-monitoring
echo "Updating water-level-monitoring..."
sed -i 's/TIMESCALE_PORT=5433/TIMESCALE_PORT=5432/g' services/water-level-monitoring/.env

# Update awd-control
echo "Updating awd-control..."
sed -i 's/TIMESCALE_PORT=5433/TIMESCALE_PORT=5432/g' services/awd-control/.env
sed -i 's/POSTGRES_PORT=5434/POSTGRES_PORT=5432/g' services/awd-control/.env
sed -i 's/localhost:5434/localhost:5432/g' services/awd-control/.env

# Update auth
echo "Updating auth..."
sed -i 's/localhost:5434/localhost:5432/g' services/auth/.env
sed -i 's/POSTGRES_PORT=5434/POSTGRES_PORT=5432/g' services/auth/.env

# Update gis
echo "Updating gis..."
# GIS is already using 5432, just verify
grep "POSTGRES_PORT" services/gis/.env || echo "POSTGRES_PORT=5432" >> services/gis/.env

# Update ros
echo "Updating ros..."
# ROS is already using 5432, just verify
grep -q "DB_PORT=5432" services/ros/.env || sed -i 's/DB_PORT=.*/DB_PORT=5432/g' services/ros/.env

# Update rid-ms
echo "Updating rid-ms..."
sed -i 's/localhost:5434/localhost:5432/g' services/rid-ms/.env
sed -i 's/POSTGRES_PORT=5434/POSTGRES_PORT=5432/g' services/rid-ms/.env

echo -e "\n7. Restarting all services..."
pm2 restart all

echo -e "\n8. Waiting for services to stabilize..."
sleep 20

echo -e "\n9. Checking service status..."
echo "Service ports that should be working:"
for port in 3003 3005 3006 3007 3008 3010 3014 3047 3048; do
    printf "Port %s: " "$port"
    if timeout 1 bash -c "</dev/tcp/localhost/$port" 2>/dev/null; then
        echo "✓ OPEN"
    else
        echo "✗ CLOSED"
    fi
done

echo -e "\n10. Database verification:"
PGPASSWORD=postgres123 psql -h localhost -p 5432 -U postgres -c "\l" | grep -E "sensor_data|auth_db|gis_db|ros_db|rid_db|weather_db|awd_db"

EOF

echo -e "\nMigration to AWS RDS complete!"