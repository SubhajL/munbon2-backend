# Docker Migration Guide - From PM2 to Docker on EC2

## Overview
This guide explains how to migrate from PM2-based deployment to Docker-based deployment on EC2.

## What Changed

### Previous Setup (PM2)
- Services ran directly on EC2 using PM2 process manager
- Each service installed dependencies individually
- Services restarted on failure via PM2
- Logs managed by PM2

### New Setup (Docker)
- All services run in isolated Docker containers
- Dependencies bundled in Docker images
- Services restart automatically via Docker restart policies
- Logs managed by Docker

## Migration Steps

### 1. Manual Deployment (One-time migration)
```bash
# From your local machine
cd munbon2-backend
./scripts/deploy-docker-ec2.sh
```

### 2. Automatic Deployment (GitHub Actions)
- Push to `main` branch triggers automatic Docker deployment
- Uses `.github/workflows/deploy-ec2.yml` (updated for Docker)

### 3. Environment Configuration
1. Copy `.env.ec2.example` to `.env.ec2` on EC2
2. Update with production values:
   - Database credentials (AWS RDS)
   - JWT secrets
   - API keys
   - Service-specific configs

## Key Files

1. **docker-compose.ec2.yml** - Production Docker Compose configuration
2. **.env.ec2.example** - Environment template
3. **scripts/deploy-docker-ec2.sh** - Manual deployment script
4. **.github/workflows/deploy-ec2.yml** - GitHub Actions workflow

## Service Ports
- 3001: Sensor Data API
- 3002: Authentication Service
- 3003: Moisture Monitoring
- 3004: Weather Monitoring
- 3005: Water Level Monitoring
- 3006: GIS Service
- 3011: RID-MS Service
- 3012: ROS Service
- 3013: AWD Control
- 3014: Flow Monitoring

## Docker Commands on EC2

### View all containers
```bash
sudo docker compose -f docker-compose.ec2.yml ps
```

### View logs
```bash
# All services
sudo docker compose -f docker-compose.ec2.yml logs -f

# Specific service
sudo docker compose -f docker-compose.ec2.yml logs -f sensor-data
```

### Restart services
```bash
# All services
sudo docker compose -f docker-compose.ec2.yml restart

# Specific service
sudo docker compose -f docker-compose.ec2.yml restart gis
```

### Stop all services
```bash
sudo docker compose -f docker-compose.ec2.yml down
```

### Start all services
```bash
sudo docker compose -f docker-compose.ec2.yml up -d
```

### Rebuild and restart
```bash
sudo docker compose -f docker-compose.ec2.yml build
sudo docker compose -f docker-compose.ec2.yml up -d
```

## Monitoring

### Check service health
```bash
# From EC2
curl http://localhost:3001/health  # Sensor Data
curl http://localhost:3002/health  # Auth
curl http://localhost:3006/health  # GIS
# etc...
```

### View resource usage
```bash
sudo docker stats
```

### Check disk usage
```bash
sudo docker system df
```

### Clean up unused resources
```bash
sudo docker system prune -a --volumes
```

## Troubleshooting

### Service not responding
1. Check container status: `sudo docker compose -f docker-compose.ec2.yml ps`
2. View logs: `sudo docker compose -f docker-compose.ec2.yml logs [service-name]`
3. Restart service: `sudo docker compose -f docker-compose.ec2.yml restart [service-name]`

### Database connection issues
1. Verify AWS RDS is accessible
2. Check security groups allow connection from EC2
3. Verify credentials in `.env.ec2`

### Out of disk space
```bash
# Clean Docker resources
sudo docker system prune -a --volumes

# Check disk usage
df -h
```

## Rollback to PM2 (if needed)
```bash
# Stop Docker containers
sudo docker compose -f docker-compose.ec2.yml down

# Start PM2 services
pm2 start ecosystem.config.js
```

## Benefits of Docker Deployment

1. **Consistency**: Same environment in development and production
2. **Isolation**: Services don't interfere with each other
3. **Easy scaling**: Add more containers as needed
4. **Simple updates**: Just rebuild and restart containers
5. **Better resource management**: Set limits per service
6. **Easier debugging**: Isolated logs and environments

## Security Notes

1. Docker runs with root privileges - be careful with commands
2. Keep Docker and Docker Compose updated
3. Use secrets management for sensitive data
4. Regularly update base images for security patches
5. Monitor container resource usage to prevent DoS

## Next Steps

1. Set up container monitoring (Prometheus/Grafana)
2. Implement container orchestration (Docker Swarm/Kubernetes)
3. Set up automated backups
4. Configure log aggregation (ELK stack)
5. Implement health check endpoints for all services