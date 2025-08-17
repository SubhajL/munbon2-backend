# EC2 Deployment Quick Start Guide

## Current Status
- ✅ PostgreSQL is running on EC2 (port 5432)
- ✅ Lambda functions updated to connect to EC2 database
- ✅ Cloudflare tunnel configured to point to EC2
- ❌ Services not yet deployed to EC2

## Quick Deployment Commands

Run these commands on your EC2 instance (43.209.22.250):

### 1. Install Docker and Docker Compose (if not installed)
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Logout and login again for docker group to take effect
```

### 2. Setup Project Directory
```bash
# Create project directory
mkdir -p ~/munbon2-backend/services
cd ~/munbon2-backend
```

### 3. Create docker-compose.yml
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:13-alpine
    container_name: munbon-postgres
    environment:
      POSTGRES_PASSWORD: P@ssw0rd123!
      POSTGRES_DB: munbon_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:6-alpine
    container_name: munbon-redis
    ports:
      - "6379:6379"
    restart: unless-stopped

  sensor-data:
    image: node:18-alpine
    container_name: munbon-sensor-data
    working_dir: /app
    volumes:
      - ./services/sensor-data:/app
    environment:
      NODE_ENV: production
      PORT: 3001
      TIMESCALE_HOST: postgres
      TIMESCALE_PORT: 5432
      TIMESCALE_DB: sensor_data
      TIMESCALE_USER: postgres
      TIMESCALE_PASSWORD: P@ssw0rd123!
      REDIS_HOST: redis
      REDIS_PORT: 6379
    ports:
      - "3001:3001"
    depends_on:
      - postgres
      - redis
    command: sh -c "npm install && npm start"
    restart: unless-stopped

  sensor-data-consumer:
    image: node:18-alpine
    container_name: munbon-sensor-data-consumer
    working_dir: /app
    volumes:
      - ./services/sensor-data:/app
    environment:
      NODE_ENV: production
      CONSUMER_PORT: 3002
      TIMESCALE_HOST: postgres
      TIMESCALE_PORT: 5432
      TIMESCALE_DB: sensor_data
      TIMESCALE_USER: postgres
      TIMESCALE_PASSWORD: P@ssw0rd123!
      AWS_REGION: ap-southeast-1
      AWS_ACCESS_KEY_ID: AKIARSUGAPRU5GWX5G6I
      AWS_SECRET_ACCESS_KEY: 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
      SQS_QUEUE_URL: https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue
    ports:
      - "3002:3002"
    depends_on:
      - postgres
      - redis
    command: sh -c "npm install && npm run consumer:prod"
    restart: unless-stopped

volumes:
  postgres_data:
```

### 4. Upload Service Code
Upload the sensor-data service directory from your local machine to EC2:
```bash
# From local machine
scp -r /Users/subhajlimanond/dev/munbon2-backend/services/sensor-data user@43.209.22.250:~/munbon2-backend/services/

# Or use any file transfer method available
```

### 5. Create Database
```bash
# Connect to PostgreSQL
docker exec -it munbon-postgres psql -U postgres

# Create sensor_data database with TimescaleDB
CREATE DATABASE sensor_data;
\c sensor_data
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb;
\q
```

### 6. Start Services
```bash
# Start all services
docker-compose up -d

# Check status
docker ps

# View logs
docker-compose logs -f
```

### 7. Update Security Group
Ensure these ports are open in your firewall/security group:
- 5432 - PostgreSQL (for Lambda functions)
- 3001 - Sensor Data Service (for Cloudflare tunnel)
- 3002 - Consumer Dashboard (for monitoring)

## Verification
Once deployed, test with:
```bash
# Test locally on EC2
curl http://localhost:3001/health
curl http://localhost:3002

# Test from external
curl http://43.209.22.250:3001/health
curl http://43.209.22.250:3002
```

## Current Data Flow
1. **Ingestion**: IoT Sensors → AWS Lambda → SQS → Consumer (EC2) → PostgreSQL (EC2)
2. **Exposure**: External API Request → AWS Lambda → PostgreSQL (EC2) → Response
3. **Moisture**: Sensor → Cloudflare Tunnel → Sensor Service (EC2) → PostgreSQL (EC2)