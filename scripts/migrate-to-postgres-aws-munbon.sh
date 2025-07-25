#!/bin/bash

# Migrate all databases to postgres_aws_munbon on port 5432
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

echo -e "${BLUE}=== Migrating databases to postgres_aws_munbon (port 5432) ===${NC}"

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
cd /home/ubuntu/munbon2-backend

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}1. Testing connection to postgres_aws_munbon...${NC}"
PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -c "SELECT version();" || { echo -e "${RED}Failed to connect to AWS RDS${NC}"; exit 1; }

echo -e "\n${BLUE}2. Creating all required databases...${NC}"
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
    PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -c "CREATE DATABASE $db;" 2>/dev/null || echo "Database $db already exists"
done

echo -e "\n${BLUE}3. Enabling required extensions...${NC}"
# Enable TimescaleDB for sensor_data (if available)
echo "Enabling extensions for sensor_data..."
PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -d sensor_data << SQL
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS postgis;
SQL

# Enable PostGIS for gis_db
echo "Enabling PostGIS for gis_db..."
PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -d gis_db -c "CREATE EXTENSION IF NOT EXISTS postgis;"

echo -e "\n${BLUE}4. Migrating data from local containers...${NC}"

# Dump and restore sensor_data from munbon-timescaledb (5433)
echo -e "${YELLOW}Migrating sensor_data from port 5433...${NC}"
docker exec munbon-timescaledb pg_dump -U postgres -d sensor_data --no-owner --no-acl > /tmp/sensor_data.sql 2>/dev/null || echo "No data to migrate"
if [ -f /tmp/sensor_data.sql ] && [ -s /tmp/sensor_data.sql ]; then
    PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -d sensor_data < /tmp/sensor_data.sql
    echo -e "${GREEN}✓ sensor_data migrated${NC}"
else
    echo "No sensor_data to migrate"
fi

# Dump and restore databases from munbon-postgres (5434)
for db in auth_db gis_db ros_db rid_db weather_db awd_db; do
    echo -e "${YELLOW}Migrating $db from port 5434...${NC}"
    docker exec munbon-postgres pg_dump -U postgres -d $db --no-owner --no-acl > /tmp/$db.sql 2>/dev/null || echo "No data to migrate"
    if [ -f /tmp/$db.sql ] && [ -s /tmp/$db.sql ]; then
        PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -d $db < /tmp/$db.sql
        echo -e "${GREEN}✓ $db migrated${NC}"
    else
        echo "No $db data to migrate"
    fi
done

echo -e "\n${BLUE}5. Updating all service .env files to use postgres_aws_munbon...${NC}"

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
)

for service in "${services[@]}"; do
    if [ -f "services/$service/.env" ]; then
        echo -e "${YELLOW}Updating $service...${NC}"
        # Backup original
        cp "services/$service/.env" "services/$service/.env.backup"
        
        # Update ports to 5432
        sed -i 's/POSTGRES_PORT=5433/POSTGRES_PORT=5432/g' "services/$service/.env"
        sed -i 's/POSTGRES_PORT=5434/POSTGRES_PORT=5432/g' "services/$service/.env"
        sed -i 's/TIMESCALE_PORT=5433/TIMESCALE_PORT=5432/g' "services/$service/.env"
        sed -i 's/DB_PORT=5433/DB_PORT=5432/g' "services/$service/.env"
        sed -i 's/DB_PORT=5434/DB_PORT=5432/g' "services/$service/.env"
        
        # Update connection strings
        sed -i 's/localhost:5433/localhost:5432/g' "services/$service/.env"
        sed -i 's/localhost:5434/localhost:5432/g' "services/$service/.env"
        
        # Ensure password is correct for AWS RDS
        sed -i 's/POSTGRES_PASSWORD=postgres123/POSTGRES_PASSWORD=postgres/g' "services/$service/.env"
        sed -i 's/TIMESCALE_PASSWORD=postgres123/TIMESCALE_PASSWORD=postgres/g' "services/$service/.env"
        sed -i 's/DB_PASSWORD=postgres123/DB_PASSWORD=postgres/g' "services/$service/.env"
    fi
done

echo -e "\n${BLUE}6. Verifying migration...${NC}"
echo -e "${YELLOW}Databases in postgres_aws_munbon:${NC}"
PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -c "\l" | grep -E "sensor_data|auth_db|gis_db|ros_db|rid_db|weather_db|awd_db"

echo -e "\n${BLUE}7. Testing connections...${NC}"
for db in "${databases[@]}"; do
    printf "Testing $db: "
    if PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -d $db -c "SELECT 1;" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Connected${NC}"
    else
        echo -e "${RED}✗ Failed${NC}"
    fi
done

echo -e "\n${GREEN}Migration complete!${NC}"
echo -e "${YELLOW}Note: Services need to be restarted to use the new database connections.${NC}"

# Clean up
rm -f /tmp/*.sql

EOF

echo -e "\n${GREEN}Database migration to postgres_aws_munbon completed!${NC}"