#!/bin/bash

# Consolidate all databases to existing timescaledb container on port 5432
set -e

EC2_IP="43.209.12.182"
SSH_KEY="/Users/subhajlimanond/dev/munbon2-backend/th-lab01.pem"
EC2_USER="ubuntu"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=== Consolidating all databases to port 5432 ===${NC}"

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
cd /home/ubuntu/munbon2-backend

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}1. Testing connection to timescaledb container (port 5432)...${NC}"
docker exec timescaledb psql -U postgres -c "SELECT version();"

echo -e "\n${BLUE}2. Creating all required databases in port 5432...${NC}"
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
    docker exec timescaledb psql -U postgres -c "CREATE DATABASE $db;" 2>/dev/null || echo "Database $db already exists"
done

echo -e "\n${BLUE}3. Enabling required extensions...${NC}"
# Enable TimescaleDB for sensor_data
echo "Enabling TimescaleDB for sensor_data..."
docker exec timescaledb psql -U postgres -d sensor_data -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;" 2>/dev/null || echo "TimescaleDB extension already exists"

# Enable PostGIS for gis_db
echo "Enabling PostGIS for gis_db..."
docker exec timescaledb psql -U postgres -d gis_db -c "CREATE EXTENSION IF NOT EXISTS postgis;" 2>/dev/null || echo "PostGIS extension already exists"

echo -e "\n${BLUE}4. Migrating data from other containers...${NC}"

# Migrate sensor_data from munbon-timescaledb (5433) if it has data
echo -e "${YELLOW}Checking sensor_data in port 5433...${NC}"
if docker exec munbon-timescaledb psql -U postgres -lqt | cut -d \| -f 1 | grep -qw sensor_data; then
    echo "Migrating sensor_data from port 5433..."
    docker exec munbon-timescaledb pg_dump -U postgres -d sensor_data --no-owner --no-acl > /tmp/sensor_data_5433.sql
    docker exec -i timescaledb psql -U postgres -d sensor_data < /tmp/sensor_data_5433.sql
    echo -e "${GREEN}✓ sensor_data migrated${NC}"
    rm -f /tmp/sensor_data_5433.sql
fi

# Migrate databases from munbon-postgres (5434)
for db in auth_db gis_db ros_db rid_db weather_db awd_db; do
    echo -e "${YELLOW}Checking $db in port 5434...${NC}"
    if docker exec munbon-postgres psql -U postgres -lqt | cut -d \| -f 1 | grep -qw $db; then
        echo "Migrating $db from port 5434..."
        docker exec munbon-postgres pg_dump -U postgres -d $db --no-owner --no-acl > /tmp/${db}_5434.sql
        docker exec -i timescaledb psql -U postgres -d $db < /tmp/${db}_5434.sql
        echo -e "${GREEN}✓ $db migrated${NC}"
        rm -f /tmp/${db}_5434.sql
    fi
done

echo -e "\n${BLUE}5. Updating all service .env files to use port 5432...${NC}"

# Update all services to use port 5432
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
    "flow-monitoring"
)

for service in "${services[@]}"; do
    if [ -f "services/$service/.env" ]; then
        echo -e "${YELLOW}Updating $service to use port 5432...${NC}"
        # Backup original
        cp "services/$service/.env" "services/$service/.env.pre-consolidation"
        
        # Update ports to 5432
        sed -i 's/POSTGRES_PORT=5433/POSTGRES_PORT=5432/g' "services/$service/.env"
        sed -i 's/POSTGRES_PORT=5434/POSTGRES_PORT=5432/g' "services/$service/.env"
        sed -i 's/TIMESCALE_PORT=5433/TIMESCALE_PORT=5432/g' "services/$service/.env"
        sed -i 's/DB_PORT=5433/DB_PORT=5432/g' "services/$service/.env"
        sed -i 's/DB_PORT=5434/DB_PORT=5432/g' "services/$service/.env"
        
        # Update connection strings
        sed -i 's/localhost:5433/localhost:5432/g' "services/$service/.env"
        sed -i 's/localhost:5434/localhost:5432/g' "services/$service/.env"
        
        # Update password to postgres123 (as per DBeaver screenshot)
        sed -i 's/POSTGRES_PASSWORD=postgres$/POSTGRES_PASSWORD=postgres123/g' "services/$service/.env"
        sed -i 's/TIMESCALE_PASSWORD=postgres$/TIMESCALE_PASSWORD=postgres123/g' "services/$service/.env"
        sed -i 's/DB_PASSWORD=postgres$/DB_PASSWORD=postgres123/g' "services/$service/.env"
        
        # Update DATABASE_URL passwords
        sed -i 's/postgres:postgres@/postgres:postgres123@/g' "services/$service/.env"
        
        echo -e "${GREEN}✓ Updated $service${NC}"
    fi
done

echo -e "\n${BLUE}6. Verifying consolidation...${NC}"
echo -e "${YELLOW}Databases in port 5432:${NC}"
docker exec timescaledb psql -U postgres -c "\l" | grep -E "sensor_data|auth_db|gis_db|ros_db|rid_db|weather_db|awd_db"

echo -e "\n${BLUE}7. Testing connections...${NC}"
for db in "${databases[@]}"; do
    printf "Testing $db: "
    if docker exec timescaledb psql -U postgres -d $db -c "SELECT 1;" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Connected${NC}"
    else
        echo -e "${RED}✗ Failed${NC}"
    fi
done

echo -e "\n${BLUE}8. Restarting all services to use consolidated database...${NC}"
pm2 restart all

echo -e "\n${BLUE}9. Waiting for services to stabilize...${NC}"
sleep 20

echo -e "\n${BLUE}10. Final service status check...${NC}"
pm2 list

echo -e "\n${GREEN}Consolidation complete!${NC}"
echo -e "${YELLOW}All databases now running on port 5432${NC}"
echo -e "${YELLOW}You can now stop the other containers if desired:${NC}"
echo "  docker stop munbon-timescaledb munbon-postgres"

EOF

echo -e "\n${GREEN}Database consolidation completed!${NC}"