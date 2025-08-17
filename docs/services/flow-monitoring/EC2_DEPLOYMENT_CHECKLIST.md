# Flow Monitoring Service - EC2 Deployment Checklist

## Pre-Deployment Checklist

### Local Testing
- [ ] Run local Docker test: `./test-local-docker.sh`
- [ ] Verify health endpoint responds
- [ ] Check database connectivity (if local DBs are running)
- [ ] Review logs for any errors

### Docker Hub
- [ ] Login to Docker Hub: `docker login`
- [ ] Ensure `subhaj888/munbon-flow-monitoring` repository exists
- [ ] Verify push permissions

### Configuration Files
- [ ] `.env.ec2` file is properly configured with EC2 database credentials
- [ ] `src/munbon_network_final.json` exists and is valid
- [ ] `canal_geometry_template.json` exists and is valid
- [ ] Port 3011 is correctly configured (not 3014)

### EC2 Prerequisites
- [ ] SSH key `~/dev/th-lab01.pem` has correct permissions (600)
- [ ] Can SSH to EC2: `ssh -i ~/dev/th-lab01.pem ubuntu@43.209.22.250`
- [ ] Docker and docker-compose are installed on EC2
- [ ] PostgreSQL databases exist on EC2:
  - [ ] `munbon_dev` database
  - [ ] `sensor_data` database with TimescaleDB extension

## Deployment Steps

### 1. Update docker-compose.ec2.yml on EC2
```bash
# SSH to EC2
ssh -i ~/dev/th-lab01.pem ubuntu@43.209.22.250

# Edit docker-compose.ec2.yml
cd /home/ubuntu/munbon2-backend
nano docker-compose.ec2.yml
```

Replace the flow-monitoring service section with the content from `docker-compose.ec2.snippet.yml`:
- Change port from 3014 to 3011
- Add all environment variables
- Add volume mounts for JSON files
- Add health check

### 2. Create Required Directories on EC2
```bash
# On EC2
mkdir -p /home/ubuntu/munbon2-backend/services/flow-monitoring/src
```

### 3. Run Deployment Script
```bash
# From local machine
cd services/flow-monitoring
./deploy-to-ec2.sh
```

### 4. Verify Deployment
```bash
# Check container status
docker ps | grep flow-monitoring

# Check health
curl http://43.209.22.250:3011/health

# Check logs
docker logs munbon-flow-monitoring

# Test an API endpoint
curl http://43.209.22.250:3011/api/v1/gates
```

## Post-Deployment Verification

### Service Health
- [ ] Container is running: `docker ps | grep flow-monitoring`
- [ ] Health endpoint returns healthy: `curl http://43.209.22.250:3011/health`
- [ ] No errors in logs: `docker logs --tail 50 munbon-flow-monitoring`

### Database Connectivity
- [ ] PostgreSQL connection successful (check logs)
- [ ] TimescaleDB connection successful
- [ ] Redis connection successful
- [ ] Tables created in databases

### API Functionality
- [ ] Root endpoint: `curl http://43.209.22.250:3011/`
- [ ] API docs accessible: `http://43.209.22.250:3011/docs`
- [ ] Gate states endpoint: `curl http://43.209.22.250:3011/api/v1/gates`

### Integration
- [ ] Service is accessible from other containers
- [ ] Port 3011 is open and accessible
- [ ] No port conflicts with other services

## Troubleshooting

### Container Won't Start
```bash
# Check detailed logs
docker logs munbon-flow-monitoring

# Check if port is already in use
sudo lsof -i :3011

# Inspect container
docker inspect munbon-flow-monitoring
```

### Database Connection Errors
```bash
# Test connection from container
docker exec munbon-flow-monitoring python -c "
import asyncpg
import asyncio
async def test():
    conn = await asyncpg.connect('postgresql://postgres:P@ssw0rd123!@43.209.22.250:5432/munbon_dev')
    print('Connected!')
    await conn.close()
asyncio.run(test())
"
```

### Missing Files
```bash
# Check if files exist in container
docker exec munbon-flow-monitoring ls -la /app/src/munbon_network_final.json
docker exec munbon-flow-monitoring ls -la /app/canal_geometry_template.json
```

## Rollback Procedure
1. Stop current container: `docker-compose -f docker-compose.ec2.yml stop flow-monitoring`
2. Remove container: `docker-compose -f docker-compose.ec2.yml rm -f flow-monitoring`
3. Pull previous version: `docker pull subhaj888/munbon-flow-monitoring:previous-tag`
4. Update docker-compose.ec2.yml with previous tag
5. Start service: `docker-compose -f docker-compose.ec2.yml up -d flow-monitoring`

## Success Criteria
- [ ] Service responds to health checks
- [ ] API endpoints return expected data
- [ ] No errors in logs after 5 minutes of running
- [ ] Service integrates with other microservices
- [ ] Hydraulic calculations are working correctly