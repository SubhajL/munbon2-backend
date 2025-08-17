#!/bin/bash

# Migrate all databases to postgres_aws_munbon on AWS RDS
set -e

EC2_IP="${EC2_HOST:-43.208.201.191}"
SSH_KEY="/Users/subhajlimanond/dev/munbon2-backend/th-lab01.pem"
EC2_USER="ubuntu"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=== Migrating databases to AWS RDS postgres_aws_munbon ===${NC}"

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
cd /home/ubuntu/munbon2-backend

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# AWS RDS credentials
RDS_HOST="ec2-${EC2_HOST:-43.208.201.191}.ap-southeast-7.compute.amazonaws.com"
RDS_PORT="5432"
RDS_USER="postgres"
RDS_PASSWORD="postgres123"

echo -e "${BLUE}1. Testing connection to AWS RDS...${NC}"
PGPASSWORD=$RDS_PASSWORD psql -h $RDS_HOST -p $RDS_PORT -U $RDS_USER -d postgres -c "SELECT version();" || { echo -e "${RED}Failed to connect to AWS RDS${NC}"; exit 1; }

echo -e "\n${BLUE}2. Creating all required databases on AWS RDS...${NC}"
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
    echo -e "${YELLOW}Creating database: $db${NC}"
    PGPASSWORD=$RDS_PASSWORD psql -h $RDS_HOST -p $RDS_PORT -U $RDS_USER -d postgres -c "CREATE DATABASE $db;" 2>/dev/null || echo "Database $db already exists"
done

echo -e "\n${BLUE}3. Enabling required extensions...${NC}"
# Try to enable TimescaleDB for sensor_data (may not be available on RDS)
echo "Checking available extensions..."
PGPASSWORD=$RDS_PASSWORD psql -h $RDS_HOST -p $RDS_PORT -U $RDS_USER -d postgres -c "SELECT * FROM pg_available_extensions WHERE name IN ('timescaledb', 'postgis');"

# Enable PostGIS for gis_db (usually available on RDS)
echo "Enabling PostGIS for gis_db..."
PGPASSWORD=$RDS_PASSWORD psql -h $RDS_HOST -p $RDS_PORT -U $RDS_USER -d gis_db -c "CREATE EXTENSION IF NOT EXISTS postgis;" 2>/dev/null || echo "PostGIS may not be available"

echo -e "\n${BLUE}4. Migrating data from local Docker containers to AWS RDS...${NC}"

# Dump and restore sensor_data from munbon-timescaledb (5433)
echo -e "${YELLOW}Migrating sensor_data from local port 5433 to AWS RDS...${NC}"
docker exec munbon-timescaledb pg_dump -U postgres -d sensor_data --no-owner --no-acl -f /tmp/sensor_data.sql 2>/dev/null || echo "No sensor_data to export"
docker cp munbon-timescaledb:/tmp/sensor_data.sql /tmp/sensor_data.sql 2>/dev/null || true
if [ -f /tmp/sensor_data.sql ] && [ -s /tmp/sensor_data.sql ]; then
    PGPASSWORD=$RDS_PASSWORD psql -h $RDS_HOST -p $RDS_PORT -U $RDS_USER -d sensor_data < /tmp/sensor_data.sql
    echo -e "${GREEN}✓ sensor_data migrated to AWS RDS${NC}"
else
    echo "No sensor_data to migrate"
fi

# Dump and restore databases from munbon-postgres (5434)
for db in auth_db gis_db ros_db rid_db weather_db awd_db; do
    echo -e "${YELLOW}Migrating $db from local port 5434 to AWS RDS...${NC}"
    docker exec munbon-postgres pg_dump -U postgres -d $db --no-owner --no-acl -f /tmp/$db.sql 2>/dev/null || echo "No $db to export"
    docker cp munbon-postgres:/tmp/$db.sql /tmp/$db.sql 2>/dev/null || true
    if [ -f /tmp/$db.sql ] && [ -s /tmp/$db.sql ]; then
        PGPASSWORD=$RDS_PASSWORD psql -h $RDS_HOST -p $RDS_PORT -U $RDS_USER -d $db < /tmp/$db.sql
        echo -e "${GREEN}✓ $db migrated to AWS RDS${NC}"
    else
        echo "No $db data to migrate"
    fi
done

echo -e "\n${BLUE}5. Updating all service .env files to use AWS RDS...${NC}"

# Update all services to use AWS RDS
services=(
    "sensor-data"
    "auth"
    "weather-monitoring"
    "gis"
    "ros"
    "rid-ms"
    "awd-control"
    "moisture-monitoring"
    "water-level-monitoring"
)

for service in "${services[@]}"; do
    if [ -f "services/$service/.env" ]; then
        echo -e "${YELLOW}Updating $service to use AWS RDS...${NC}"
        # Backup original
        cp "services/$service/.env" "services/$service/.env.local-backup"
        
        # Create new .env pointing to AWS RDS
        cat > "services/$service/.env.new" << ENVEOF
NODE_ENV=production
PORT=$(grep "^PORT=" "services/$service/.env" | cut -d= -f2)
HOST=0.0.0.0

# AWS RDS PostgreSQL
POSTGRES_HOST=$RDS_HOST
POSTGRES_PORT=$RDS_PORT
POSTGRES_USER=$RDS_USER
POSTGRES_PASSWORD=$RDS_PASSWORD

# TimescaleDB settings (pointing to same RDS)
TIMESCALE_HOST=$RDS_HOST
TIMESCALE_PORT=$RDS_PORT
TIMESCALE_USER=$RDS_USER
TIMESCALE_PASSWORD=$RDS_PASSWORD

# Database name based on service
ENVEOF

        # Set correct database name for each service
        case $service in
            "sensor-data"|"moisture-monitoring"|"water-level-monitoring"|"weather-monitoring")
                echo "POSTGRES_DB=sensor_data" >> "services/$service/.env.new"
                echo "TIMESCALE_DB=sensor_data" >> "services/$service/.env.new"
                echo "TIMESCALE_DATABASE=sensor_data" >> "services/$service/.env.new"
                echo "DATABASE_URL=postgresql://$RDS_USER:$RDS_PASSWORD@$RDS_HOST:$RDS_PORT/sensor_data" >> "services/$service/.env.new"
                ;;
            "auth")
                echo "POSTGRES_DB=auth_db" >> "services/$service/.env.new"
                echo "DATABASE_URL=postgresql://$RDS_USER:$RDS_PASSWORD@$RDS_HOST:$RDS_PORT/auth_db" >> "services/$service/.env.new"
                echo "JWT_SECRET=your-jwt-secret-key" >> "services/$service/.env.new"
                ;;
            "gis")
                echo "POSTGRES_DB=gis_db" >> "services/$service/.env.new"
                echo "DATABASE_URL=postgresql://$RDS_USER:$RDS_PASSWORD@$RDS_HOST:$RDS_PORT/gis_db" >> "services/$service/.env.new"
                ;;
            "ros")
                echo "POSTGRES_DB=ros_db" >> "services/$service/.env.new"
                echo "DB_NAME=ros_db" >> "services/$service/.env.new"
                echo "DB_HOST=$RDS_HOST" >> "services/$service/.env.new"
                echo "DB_PORT=$RDS_PORT" >> "services/$service/.env.new"
                echo "DB_USER=$RDS_USER" >> "services/$service/.env.new"
                echo "DB_PASSWORD=$RDS_PASSWORD" >> "services/$service/.env.new"
                echo "DATABASE_URL=postgresql://$RDS_USER:$RDS_PASSWORD@$RDS_HOST:$RDS_PORT/ros_db" >> "services/$service/.env.new"
                ;;
            "rid-ms")
                echo "POSTGRES_DB=rid_db" >> "services/$service/.env.new"
                echo "DATABASE_URL=postgresql://$RDS_USER:$RDS_PASSWORD@$RDS_HOST:$RDS_PORT/rid_db" >> "services/$service/.env.new"
                ;;
            "awd-control")
                echo "POSTGRES_DB=awd_db" >> "services/$service/.env.new"
                echo "TIMESCALE_DB=sensor_data" >> "services/$service/.env.new"
                echo "DATABASE_URL=postgresql://$RDS_USER:$RDS_PASSWORD@$RDS_HOST:$RDS_PORT/awd_db" >> "services/$service/.env.new"
                ;;
        esac
        
        # Add Redis and other services (still local)
        echo "" >> "services/$service/.env.new"
        echo "# Redis (local)" >> "services/$service/.env.new"
        echo "REDIS_HOST=localhost" >> "services/$service/.env.new"
        echo "REDIS_PORT=6379" >> "services/$service/.env.new"
        echo "REDIS_URL=redis://localhost:6379" >> "services/$service/.env.new"
        
        # Add any service-specific vars
        grep -E "MQTT_|AWS_|CORS_" "services/$service/.env" >> "services/$service/.env.new" || true
        
        # Replace old .env with new one
        mv "services/$service/.env.new" "services/$service/.env"
    fi
done

echo -e "\n${BLUE}6. Verifying migration...${NC}"
echo -e "${YELLOW}Databases in AWS RDS:${NC}"
PGPASSWORD=$RDS_PASSWORD psql -h $RDS_HOST -p $RDS_PORT -U $RDS_USER -d postgres -c "\l" | grep -E "sensor_data|auth_db|gis_db|ros_db|rid_db|weather_db|awd_db"

echo -e "\n${BLUE}7. Testing connections to AWS RDS...${NC}"
for db in "${databases[@]}"; do
    printf "Testing $db: "
    if PGPASSWORD=$RDS_PASSWORD psql -h $RDS_HOST -p $RDS_PORT -U $RDS_USER -d $db -c "SELECT 1;" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Connected${NC}"
    else
        echo -e "${RED}✗ Failed${NC}"
    fi
done

echo -e "\n${GREEN}Migration to AWS RDS complete!${NC}"
echo -e "${YELLOW}Services now configured to use AWS RDS at $RDS_HOST:$RDS_PORT${NC}"

# Clean up
rm -f /tmp/*.sql
docker exec munbon-timescaledb rm -f /tmp/*.sql 2>/dev/null || true
docker exec munbon-postgres rm -f /tmp/*.sql 2>/dev/null || true

EOF

echo -e "\n${GREEN}Database migration to AWS RDS completed!${NC}"