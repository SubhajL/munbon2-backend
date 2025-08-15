#!/bin/bash

# Update service configurations for EC2 database consolidation
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# EC2 Database Configuration
EC2_HOST="43.209.22.250"
EC2_PORT="5432"
EC2_USER="postgres"
EC2_PASSWORD="P@ssw0rd123!"

echo -e "${BLUE}=== Updating Service Configurations for EC2 Database ===${NC}"

# Function to create .env file
create_env_file() {
    local service=$1
    local env_file="services/$service/.env"
    local env_example="services/$service/.env.example"
    
    echo -e "${YELLOW}Updating $service...${NC}"
    
    # Backup existing .env if it exists
    if [ -f "$env_file" ]; then
        cp "$env_file" "$env_file.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Copy from example if .env doesn't exist
    if [ ! -f "$env_file" ] && [ -f "$env_example" ]; then
        cp "$env_example" "$env_file"
    fi
}

# 1. Auth Service
create_env_file "auth"
cat > services/auth/.env << EOF
NODE_ENV=production
PORT=3002
DATABASE_URL=postgresql://${EC2_USER}:${EC2_PASSWORD}@${EC2_HOST}:${EC2_PORT}/munbon_dev?schema=auth
REDIS_URL=redis://redis:6379
JWT_SECRET=your-jwt-secret-here
SESSION_SECRET=your-session-secret-here
OAUTH_CALLBACK_URL=http://your-domain/auth/callback
THAI_DIGITAL_ID_CLIENT_ID=your-client-id
THAI_DIGITAL_ID_CLIENT_SECRET=your-client-secret
THAI_DIGITAL_ID_AUTH_URL=https://api.thaidi.gov.th/auth
THAI_DIGITAL_ID_TOKEN_URL=https://api.thaidi.gov.th/token
THAI_DIGITAL_ID_USERINFO_URL=https://api.thaidi.gov.th/userinfo
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
SMTP_FROM=noreply@munbon.th
CORS_ORIGIN=http://localhost:3000
EOF

# 2. GIS Service
create_env_file "gis"
cat > services/gis/.env << EOF
NODE_ENV=production
PORT=3006
DATABASE_URL=postgresql://${EC2_USER}:${EC2_PASSWORD}@${EC2_HOST}:${EC2_PORT}/munbon_dev?schema=gis
GIS_SCHEMA=gis
REDIS_URL=redis://redis:6379
UPLOAD_DIR=/tmp/gis-uploads
TILE_CACHE_DIR=/tmp/gis-tiles
CORS_ORIGIN=http://localhost:3000
EOF

# 3. Sensor Data Service
create_env_file "sensor-data"
cat > services/sensor-data/.env << EOF
NODE_ENV=production
PORT=3001
CONSUMER_PORT=3004
TIMESCALE_HOST=${EC2_HOST}
TIMESCALE_PORT=${EC2_PORT}
TIMESCALE_DB=sensor_data
TIMESCALE_USER=${EC2_USER}
TIMESCALE_PASSWORD=${EC2_PASSWORD}
REDIS_HOST=redis
REDIS_PORT=6379
MQTT_PORT=1883
MQTT_WS_PORT=8083
CORS_ORIGIN=http://localhost:3000
EOF

# 4. ROS Service
create_env_file "ros"
cat > services/ros/.env << EOF
NODE_ENV=production
PORT=3012
DB_HOST=${EC2_HOST}
DB_PORT=${EC2_PORT}
DB_NAME=munbon_dev
DB_SCHEMA=ros
DB_USER=${EC2_USER}
DB_PASSWORD=${EC2_PASSWORD}
REDIS_URL=redis://redis:6379
EOF

# 5. RID-MS Service
create_env_file "rid-ms"
cat > services/rid-ms/.env << EOF
NODE_ENV=production
PORT=3011
POSTGRES_HOST=${EC2_HOST}
POSTGRES_PORT=${EC2_PORT}
POSTGRES_DB=munbon_dev
POSTGRES_SCHEMA=gis
POSTGRES_USER=${EC2_USER}
POSTGRES_PASSWORD=${EC2_PASSWORD}
REDIS_URL=redis://redis:6379
KAFKA_BROKERS=kafka:9092
EOF

# 6. Moisture Monitoring Service
create_env_file "moisture-monitoring"
cat > services/moisture-monitoring/.env << EOF
NODE_ENV=production
PORT=3003
TIMESCALE_HOST=${EC2_HOST}
TIMESCALE_PORT=${EC2_PORT}
TIMESCALE_DATABASE=sensor_data
TIMESCALE_USER=${EC2_USER}
TIMESCALE_PASSWORD=${EC2_PASSWORD}
REDIS_HOST=redis
REDIS_PORT=6379
EOF

# 7. Weather Monitoring Service
create_env_file "weather-monitoring"
cat > services/weather-monitoring/.env << EOF
NODE_ENV=production
PORT=3004
DATABASE_URL=postgresql://${EC2_USER}:${EC2_PASSWORD}@${EC2_HOST}:${EC2_PORT}/sensor_data
TIMESCALE_URL=postgresql://${EC2_USER}:${EC2_PASSWORD}@${EC2_HOST}:${EC2_PORT}/sensor_data
REDIS_URL=redis://redis:6379
TMD_API_KEY=your-tmd-api-key
TMD_API_URL=https://api.tmd.go.th/v1
EOF

# 8. Water Level Monitoring Service
create_env_file "water-level-monitoring"
cat > services/water-level-monitoring/.env << EOF
NODE_ENV=production
PORT=3005
TIMESCALE_URL=postgresql://${EC2_USER}:${EC2_PASSWORD}@${EC2_HOST}:${EC2_PORT}/sensor_data
REDIS_URL=redis://redis:6379
ALERT_THRESHOLD_HIGH=4.5
ALERT_THRESHOLD_LOW=0.5
EOF

# 9. AWD Control Service
create_env_file "awd-control"
cat > services/awd-control/.env << EOF
NODE_ENV=production
PORT=3013
POSTGRES_HOST=${EC2_HOST}
POSTGRES_PORT=${EC2_PORT}
POSTGRES_DB=munbon_dev
POSTGRES_SCHEMA=awd
POSTGRES_USER=${EC2_USER}
POSTGRES_PASSWORD=${EC2_PASSWORD}
TIMESCALE_HOST=${EC2_HOST}
TIMESCALE_PORT=${EC2_PORT}
TIMESCALE_DB=sensor_data
TIMESCALE_USER=${EC2_USER}
TIMESCALE_PASSWORD=${EC2_PASSWORD}
REDIS_URL=redis://redis:6379
EOF

# 10. Flow Monitoring Service
create_env_file "flow-monitoring"
cat > services/flow-monitoring/.env << EOF
NODE_ENV=production
PORT=3014
DATABASE_URL=postgresql://${EC2_USER}:${EC2_PASSWORD}@${EC2_HOST}:${EC2_PORT}/munbon_dev
TIMESCALE_URL=postgresql://${EC2_USER}:${EC2_PASSWORD}@${EC2_HOST}:${EC2_PORT}/sensor_data
INFLUXDB_URL=http://influxdb:8086
INFLUXDB_TOKEN=your-influxdb-token
INFLUXDB_ORG=munbon
INFLUXDB_BUCKET=flow_data
REDIS_URL=redis://redis:6379
EOF

# Create schema creation script
echo -e "\n${BLUE}Creating schema setup script...${NC}"
cat > scripts/create-ec2-schemas.sql << EOF
-- Connect to munbon_dev and create missing schemas
\c munbon_dev

-- Create AWD schema for AWD Control Service
CREATE SCHEMA IF NOT EXISTS awd;
GRANT ALL ON SCHEMA awd TO postgres;

-- Ensure all schemas exist
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS gis;
CREATE SCHEMA IF NOT EXISTS ros;
CREATE SCHEMA IF NOT EXISTS config;

-- Grant permissions
GRANT ALL ON SCHEMA auth TO postgres;
GRANT ALL ON SCHEMA gis TO postgres;
GRANT ALL ON SCHEMA ros TO postgres;
GRANT ALL ON SCHEMA config TO postgres;

-- List all schemas
\dn

-- Connect to sensor_data and ensure TimescaleDB
\c sensor_data

-- Ensure TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- List extensions
\dx
EOF

echo -e "\n${GREEN}=== Configuration Update Complete ===${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Run schema creation on EC2:"
echo "   PGPASSWORD='${EC2_PASSWORD}' psql -h ${EC2_HOST} -U ${EC2_USER} -f scripts/create-ec2-schemas.sql"
echo ""
echo "2. Update docker-compose.ec2.yml with new environment variables"
echo ""
echo "3. Deploy services using:"
echo "   docker-compose -f docker-compose.ec2.yml up -d"
echo ""
echo -e "${GREEN}All service .env files have been updated for EC2 database consolidation!${NC}"