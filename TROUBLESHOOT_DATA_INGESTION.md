# Troubleshooting Data Ingestion - Stuck at July 15

## Current Situation
- Last data: July 15, 2024
- Expected: Real-time data should be flowing
- Issue: Consumer service not processing new SQS messages

## Step 1: Check if Consumer Service is Running on EC2

```bash
# SSH to EC2
ssh -i th-lab01.pem ubuntu@43.209.12.182

# Check if consumer is running
docker ps | grep consumer

# If not running, check all containers
docker-compose -f docker-compose.ec2-consolidated.yml ps

# Check consumer logs
docker-compose -f docker-compose.ec2-consolidated.yml logs sensor-data-consumer --tail 50
```

## Step 2: Verify AWS Credentials in Container

```bash
# Check if AWS credentials are set in container
docker exec munbon-sensor-data-consumer env | grep AWS

# Should see:
# AWS_REGION=ap-southeast-1
# AWS_ACCESS_KEY_ID=AKIARSUGAPRU5GWX5G6I
# AWS_SECRET_ACCESS_KEY=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
```

## Step 3: Check SQS Queue Status

Go to AWS Console: https://console.aws.amazon.com/sqs/v2/home?region=ap-southeast-1#/queues

Check queue: `munbon-sensor-ingestion-dev-queue`
- Messages Available: Should be 0 if consumer is working
- Messages in Flight: Should be 0 if consumer is working
- If many messages available: Consumer not pulling messages

## Step 4: Test Lambda → SQS Flow

```bash
# Send test data to Lambda
curl -X POST https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridr-water-level/telemetry \
  -H 'Content-Type: application/json' \
  -d '{
    "deviceID": "DEBUG-TEST-001",
    "macAddress": "AA:BB:CC:DD:EE:FF",
    "latitude": 13.756331,
    "longitude": 100.501765,
    "RSSI": -70,
    "voltage": 370,
    "level": 99,
    "timestamp": '$(date +%s)000'
  }'

# Check if message appears in SQS queue (refresh AWS console)
```

## Step 5: Start/Restart Consumer Service

```bash
# On EC2:
# Stop consumer
docker-compose -f docker-compose.ec2-consolidated.yml stop sensor-data-consumer

# Start with fresh logs
docker-compose -f docker-compose.ec2-consolidated.yml up -d sensor-data-consumer

# Watch logs
docker-compose -f docker-compose.ec2-consolidated.yml logs -f sensor-data-consumer
```

## Step 6: Check Database Connection

```bash
# Test database connection from consumer container
docker exec -it munbon-sensor-data-consumer sh -c 'PGPASSWORD=$TIMESCALE_PASSWORD psql -h $TIMESCALE_HOST -U $TIMESCALE_USER -d $TIMESCALE_DB -c "SELECT NOW()"'
```

## Step 7: Manual Consumer Test

If consumer isn't starting, try running it manually:

```bash
# Enter the container
docker exec -it munbon-sensor-data-consumer bash

# Check environment
env | grep -E 'AWS|TIMESCALE|SQS'

# Try running consumer
npm run consumer:prod
```

## Common Issues & Fixes

### 1. Consumer Not Running
```bash
# Ensure .env file exists
cp .env.ec2 .env

# Rebuild and restart
docker-compose -f docker-compose.ec2-consolidated.yml up -d --build sensor-data-consumer
```

### 2. AWS Credentials Missing
```bash
# Edit .env file on EC2
nano .env

# Add AWS credentials:
AWS_REGION=ap-southeast-1
AWS_ACCESS_KEY_ID=AKIARSUGAPRU5GWX5G6I
AWS_SECRET_ACCESS_KEY=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
SQS_QUEUE_URL=https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue
```

### 3. Wrong Docker Compose File
Make sure using the consolidated version:
```bash
# Wrong:
docker-compose -f docker-compose.ec2.yml ...

# Correct:
docker-compose -f docker-compose.ec2-consolidated.yml ...
```

### 4. Consumer Dashboard Check
Open: http://43.209.12.182:3004
- Should show statistics
- "Messages Received" should increase when testing

## Quick Fix Script

```bash
#!/bin/bash
# Run on EC2

# Ensure we're in the right directory
cd ~/munbon2-backend

# Pull latest code
git pull origin main

# Copy environment file
cp .env.ec2 .env

# Restart consumer service
docker-compose -f docker-compose.ec2-consolidated.yml down
docker-compose -f docker-compose.ec2-consolidated.yml up -d

# Check logs
docker-compose -f docker-compose.ec2-consolidated.yml logs -f sensor-data-consumer
```

## Expected Log Output

When working correctly, you should see:
```
🚀 Starting SQS consumer...
✅ Connected to TimescaleDB
📊 Dashboard running at http://localhost:3004
🔄 Starting SQS polling...
Received X messages from SQS
📡 New Telemetry Data
💧 Water Level Data
```