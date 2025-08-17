# Docker Hub Deployment Guide

## Step 1: Create Docker Hub Account

1. Go to https://hub.docker.com
2. Click "Sign Up" (it's free)
3. Create account with:
   - Username: `subhajl` (or your preferred username)
   - Email: `limanond.subhaj@gmail.com`
   - Password: (choose a strong password)

## Step 2: Login to Docker Hub Locally

```bash
# On your local machine
docker login

# Enter your Docker Hub username and password
```

## Step 3: Build and Tag Images

```bash
# In your project directory
cd /Users/subhajlimanond/dev/munbon2-backend

# Build all images
docker-compose -f docker-compose.ec2-consolidated.yml build

# Tag images for Docker Hub (replace 'subhajl' with your Docker Hub username)
docker tag munbon-sensor-data:latest subhajl/munbon-sensor-data:latest
docker tag munbon-sensor-data:latest subhajl/munbon-sensor-data:v1.0

docker tag munbon-auth:latest subhajl/munbon-auth:latest
docker tag munbon-auth:latest subhajl/munbon-auth:v1.0

# Tag other services as needed...
```

## Step 4: Push Images to Docker Hub

```bash
# Push sensor-data service
docker push subhajl/munbon-sensor-data:latest
docker push subhajl/munbon-sensor-data:v1.0

# Push auth service
docker push subhajl/munbon-auth:latest
docker push subhajl/munbon-auth:v1.0

# Continue for other services...
```

## Step 5: Create EC2 Docker Compose (Images Only)

Create `docker-compose.production.yml`:

```yaml
version: '3.8'

services:
  # Database (using official image)
  postgres:
    image: postgres:15-alpine
    container_name: munbon-postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: P@ssw0rd123!
      POSTGRES_DB: munbon_dev
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    restart: unless-stopped

  # Redis (using official image)
  redis:
    image: redis:7-alpine
    container_name: munbon-redis
    ports:
      - "6379:6379"
    restart: unless-stopped

  # Your services (from Docker Hub)
  sensor-data:
    image: subhajl/munbon-sensor-data:latest
    container_name: munbon-sensor-data
    environment:
      NODE_ENV: production
      PORT: 3003
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: P@ssw0rd123!
      TIMESCALE_DB: sensor_data
      REDIS_URL: redis://redis:6379
      JWT_SECRET: ${JWT_SECRET}
    ports:
      - "3003:3003"
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  sensor-data-consumer:
    image: subhajl/munbon-sensor-data:latest
    container_name: munbon-sensor-data-consumer
    command: ["npm", "run", "consumer:prod"]
    environment:
      NODE_ENV: production
      CONSUMER_PORT: 3004
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: P@ssw0rd123!
      TIMESCALE_DB: sensor_data
      REDIS_URL: redis://redis:6379
      AWS_REGION: ap-southeast-1
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
      SQS_QUEUE_URL: ${SQS_QUEUE_URL}
    ports:
      - "3004:3004"
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  auth:
    image: subhajl/munbon-auth:latest
    container_name: munbon-auth
    environment:
      NODE_ENV: production
      PORT: 3001
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: P@ssw0rd123!
      DATABASE_URL: postgresql://postgres:P@ssw0rd123!@postgres:5432/munbon_dev?schema=auth
      REDIS_URL: redis://redis:6379
      JWT_SECRET: ${JWT_SECRET}
    ports:
      - "3001:3001"
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

volumes:
  postgres-data:

networks:
  default:
    name: munbon-network
```

## Step 6: Deploy to EC2 (No Source Code)

On EC2, you only need:
1. Docker and Docker Compose installed
2. The production docker-compose file
3. Environment variables

```bash
# SSH to EC2
ssh -i th-lab01.pem ubuntu@43.209.22.250

# Create deployment directory
mkdir -p ~/munbon-deployment
cd ~/munbon-deployment

# Create .env file
cat > .env << 'EOF'
JWT_SECRET=fZtyKjPf2vdCfqZrHYAioaVKSYzmwlMt
AWS_ACCESS_KEY_ID=AKIARSUGAPRU5GWX5G6I
AWS_SECRET_ACCESS_KEY=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
SQS_QUEUE_URL=https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue
EOF

# Create database init script
cat > init-db.sql << 'EOF'
CREATE DATABASE IF NOT EXISTS sensor_data;
\c sensor_data
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb;
EOF

# Copy docker-compose.production.yml from above
nano docker-compose.production.yml
# Paste the content

# Pull and run
docker-compose -f docker-compose.production.yml pull
docker-compose -f docker-compose.production.yml up -d

# Check status
docker ps
```

## Step 7: Automated CI/CD with GitHub Actions

Create `.github/workflows/docker-hub-deploy.yml`:

```yaml
name: Build and Deploy via Docker Hub

on:
  push:
    branches: [main]

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_HUB_USERNAME }}
          password: ${{ secrets.DOCKER_HUB_TOKEN }}
      
      - name: Build and push sensor-data
        uses: docker/build-push-action@v5
        with:
          context: ./services/sensor-data
          push: true
          tags: |
            ${{ secrets.DOCKER_HUB_USERNAME }}/munbon-sensor-data:latest
            ${{ secrets.DOCKER_HUB_USERNAME }}/munbon-sensor-data:${{ github.sha }}
      
      - name: Build and push auth
        uses: docker/build-push-action@v5
        with:
          context: ./services/auth
          push: true
          tags: |
            ${{ secrets.DOCKER_HUB_USERNAME }}/munbon-auth:latest
            ${{ secrets.DOCKER_HUB_USERNAME }}/munbon-auth:${{ github.sha }}

  deploy:
    needs: build-and-push
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to EC2
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ${{ secrets.EC2_USER }}
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            cd ~/munbon-deployment
            docker-compose -f docker-compose.production.yml pull
            docker-compose -f docker-compose.production.yml up -d
            docker ps
```

## GitHub Secrets Needed:
- `DOCKER_HUB_USERNAME`: Your Docker Hub username
- `DOCKER_HUB_TOKEN`: Docker Hub access token (not password)
- `EC2_HOST`: 43.209.22.250
- `EC2_USER`: ubuntu
- `EC2_SSH_KEY`: Your PEM file content

## Benefits of This Approach:

1. **No source code on EC2** - Only Docker images
2. **Version control** - Each push creates versioned images
3. **Fast deployments** - EC2 only pulls updated images
4. **Rollback capability** - Can revert to previous image versions
5. **Security** - Source code never touches production server

## Docker Hub Access Token:

1. Go to https://hub.docker.com/settings/security
2. Click "New Access Token"
3. Description: "GitHub Actions"
4. Click "Generate"
5. Copy the token (you'll see it only once)
6. Add as GitHub secret: `DOCKER_HUB_TOKEN`