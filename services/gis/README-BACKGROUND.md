# Running GIS Services in Background

## Quick Start

### Option 1: Simple Background (nohup)
```bash
# Start both services
./start-gis-background.sh

# Check status
./status-gis.sh

# Stop services
./stop-gis-background.sh

# View logs
tail -f logs/gis-api.log
tail -f logs/gis-queue-processor.log
```

### Option 2: PM2 (Recommended for Production)
```bash
# Install PM2 globally
npm install -g pm2

# Start services
pm2 start ecosystem.config.js

# Check status
pm2 status

# View logs
pm2 logs gis-api
pm2 logs gis-queue-processor

# Stop services
pm2 stop all

# Restart services
pm2 restart all

# Save PM2 process list (survives reboot)
pm2 save
pm2 startup  # Follow instructions to enable startup on boot
```

## Service Details

### GIS API Service
- **Port**: 3007
- **Health Check**: http://localhost:3007/health
- **Endpoints**:
  - POST /api/v1/gis/shapefiles/upload (external)
  - POST /api/v1/gis/shapefiles/internal/upload (internal)

### GIS Queue Processor
- **Type**: Background worker
- **Queue**: munbon-gis-shapefile-queue
- **Process**: Extracts parcels from uploaded shape files

## Monitoring

### Check if services are running:
```bash
# Check processes
ps aux | grep -E "gis.*index.ts|shapefile-queue-processor"

# Check ports
lsof -i :3007

# Check health endpoint
curl http://localhost:3007/health
```

### Check queue status:
```bash
aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-gis-shapefile-queue \
  --attribute-names All \
  --region ap-southeast-1
```

## Troubleshooting

### Service won't start
1. Check if port 3007 is already in use: `lsof -i :3007`
2. Kill existing process: `kill -9 <PID>`
3. Check logs: `tail -100 logs/gis-api.log`

### Queue processor not processing
1. Check SQS queue for messages
2. Check DLQ for failed messages
3. Verify database connection
4. Check processor logs: `tail -f logs/gis-queue-processor.log`

### High memory usage
- PM2 will automatically restart if memory exceeds limits
- API: 1GB limit
- Queue Processor: 500MB limit