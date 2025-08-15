#!/bin/bash

# Fix environment variables in existing .env files
# Usage: ./fix-env-variables-ec2.sh

set -e

# Configuration
EC2_IP="43.209.22.250"
SSH_KEY="/Users/subhajlimanond/dev/munbon2-backend/th-lab01.pem"
EC2_USER="ubuntu"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}Fixing environment variables in .env files on EC2...${NC}"

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd /home/ubuntu/munbon2-backend

# Fix moisture-monitoring .env (needs TIMESCALE_DATABASE not TIMESCALE_DB)
echo -e "${BLUE}Fixing moisture-monitoring .env...${NC}"
if [ -f "services/moisture-monitoring/.env" ]; then
    # Add missing TIMESCALE_DATABASE
    if ! grep -q "TIMESCALE_DATABASE" services/moisture-monitoring/.env; then
        sed -i 's/TIMESCALE_DB=/TIMESCALE_DATABASE=/' services/moisture-monitoring/.env
    fi
    # Add missing MQTT_BROKER_URL
    if ! grep -q "MQTT_BROKER_URL" services/moisture-monitoring/.env; then
        echo "MQTT_BROKER_URL=mqtt://localhost:1883" >> services/moisture-monitoring/.env
    fi
fi

# Fix weather-monitoring .env
echo -e "${BLUE}Fixing weather-monitoring .env...${NC}"
if [ -f "services/weather-monitoring/.env" ]; then
    # Fix TIMESCALE_DATABASE
    sed -i 's/TIMESCALE_DB=/TIMESCALE_DATABASE=/' services/weather-monitoring/.env
    # Add missing MQTT_BROKER_URL
    if ! grep -q "MQTT_BROKER_URL" services/weather-monitoring/.env; then
        echo "MQTT_BROKER_URL=mqtt://localhost:1883" >> services/weather-monitoring/.env
    fi
    # Add PostgreSQL config
    if ! grep -q "POSTGRES_HOST" services/weather-monitoring/.env; then
        cat >> services/weather-monitoring/.env << 'ENVEOF'

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5434
POSTGRES_DATABASE=weather_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123
ENVEOF
    fi
fi

# Fix water-level-monitoring .env
echo -e "${BLUE}Fixing water-level-monitoring .env...${NC}"
if [ -f "services/water-level-monitoring/.env" ]; then
    sed -i 's/TIMESCALE_DB=/TIMESCALE_DATABASE=/' services/water-level-monitoring/.env
    if ! grep -q "MQTT_BROKER_URL" services/water-level-monitoring/.env; then
        echo "MQTT_BROKER_URL=mqtt://localhost:1883" >> services/water-level-monitoring/.env
    fi
fi

# Fix auth service .env - needs more environment variables
echo -e "${BLUE}Fixing auth service .env...${NC}"
if [ -f "services/auth/.env" ]; then
    # Add missing required variables
    if ! grep -q "REDIS_URL" services/auth/.env; then
        cat >> services/auth/.env << 'ENVEOF'

# Redis
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=

# Session
SESSION_SECRET=your-session-secret-change-in-production

# OAuth (dummy values for now)
OAUTH_CALLBACK_URL=http://localhost:3002/auth/callback
THAI_DIGITAL_ID_CLIENT_ID=dummy-client-id
THAI_DIGITAL_ID_CLIENT_SECRET=dummy-client-secret
THAI_DIGITAL_ID_AUTH_URL=https://example.com/auth
THAI_DIGITAL_ID_TOKEN_URL=https://example.com/token
THAI_DIGITAL_ID_USERINFO_URL=https://example.com/userinfo

# SMTP (dummy values for now)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=dummy@example.com
SMTP_PASS=dummy-password
EMAIL_FROM=noreply@munbon.com
ENVEOF
    fi
fi

# Fix GIS service .env - needs REDIS_URL
echo -e "${BLUE}Fixing GIS service .env...${NC}"
if [ -f "services/gis/.env" ]; then
    if ! grep -q "REDIS_URL" services/gis/.env; then
        echo "REDIS_URL=redis://localhost:6379" >> services/gis/.env
        echo "REDIS_PASSWORD=" >> services/gis/.env
    fi
fi

# Fix rid-ms service .env - it uses different variable names
echo -e "${BLUE}Fixing rid-ms service .env...${NC}"
if [ -f "services/rid-ms/.env" ]; then
    # RID-MS uses POSTGRES_DB not DATABASE_URL
    if ! grep -q "POSTGRES_PASSWORD" services/rid-ms/.env; then
        echo "POSTGRES_PASSWORD=postgres123" >> services/rid-ms/.env
    fi
    # Add Kafka config
    if ! grep -q "KAFKA_BROKERS" services/rid-ms/.env; then
        echo "KAFKA_BROKERS=localhost:9092" >> services/rid-ms/.env
    fi
fi

# Check sensor-data service
echo -e "${BLUE}Checking sensor-data service...${NC}"
if [ -f "services/sensor-data/.env" ]; then
    echo "sensor-data .env exists, checking contents..."
    # This service might need DATABASE config
    if ! grep -q "DATABASE_URL" services/sensor-data/.env; then
        echo "DATABASE_URL=postgresql://postgres:postgres123@localhost:5433/sensor_data" >> services/sensor-data/.env
    fi
fi

# Show current .env files
echo -e "\n${GREEN}Current .env file contents:${NC}"
for service in sensor-data auth moisture-monitoring weather-monitoring water-level-monitoring gis rid-ms awd-control; do
    if [ -f "services/$service/.env" ]; then
        echo -e "\n${YELLOW}=== $service .env ===${NC}"
        cat "services/$service/.env" | head -20
    fi
done

# Restart all services
echo -e "\n${BLUE}Restarting all services with fixed environment variables...${NC}"
pm2 restart all

# Wait for services to start
sleep 10

# Check status
echo -e "\n${GREEN}Service status after fix:${NC}"
pm2 status

# Test endpoints
echo -e "\n${BLUE}Testing service endpoints:${NC}"
for port in 3001 3002 3003 3004 3005 3006 3011 3012 3013 3014; do
    service_name=""
    case $port in
        3001) service_name="sensor-data" ;;
        3002) service_name="auth" ;;
        3003) service_name="moisture-monitoring" ;;
        3004) service_name="weather-monitoring" ;;
        3005) service_name="water-level-monitoring" ;;
        3006) service_name="gis" ;;
        3011) service_name="rid-ms" ;;
        3012) service_name="ros" ;;
        3013) service_name="awd-control" ;;
        3014) service_name="flow-monitoring" ;;
    esac
    
    printf "%-25s: " "$service_name (port $port)"
    if curl -s -m 2 "http://localhost:$port/health" >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Working${NC}"
    else
        echo -e "${RED}✗ Not responding${NC}"
    fi
done

# Check listening ports
echo -e "\n${BLUE}Listening ports:${NC}"
sudo ss -tlnp | grep -E ":(300[1-6]|301[1-4])" || echo "Checking..."
EOF

echo -e "\n${GREEN}Environment variables fixed!${NC}"