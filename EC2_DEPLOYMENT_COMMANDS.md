# EC2 Docker Deployment Commands

Run these commands on your EC2 instance (43.209.12.182) to deploy the services:

## 1. Clone/Update Repository
```bash
# If first time
git clone https://github.com/SubhajL/munbon2-backend.git
cd munbon2-backend

# If already cloned
cd munbon2-backend
git pull origin main
```

## 2. Copy Environment File
```bash
# Use the committed .env.ec2 file
cp .env.ec2 .env
```

## 3. Deploy with Docker Compose
```bash
# Use the consolidated Docker Compose file
docker-compose -f docker-compose.ec2-consolidated.yml up -d --build

# Check status
docker-compose -f docker-compose.ec2-consolidated.yml ps

# View logs
docker-compose -f docker-compose.ec2-consolidated.yml logs -f
```

## 4. Initialize Database (if needed)
```bash
# Create sensor_data database
docker exec -it munbon-postgres psql -U postgres -c "CREATE DATABASE sensor_data;"

# Enable extensions
docker exec -it munbon-postgres psql -U postgres -d sensor_data -c "CREATE EXTENSION IF NOT EXISTS postgis;"
docker exec -it munbon-postgres psql -U postgres -d sensor_data -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

## 5. Verify Services
```bash
# Check health endpoints
curl http://localhost:3001/health  # Sensor Data Service
curl http://localhost:3002         # Consumer Dashboard
curl http://localhost:3003/health  # Auth Service
curl http://localhost:3004/health  # GIS Service
```

## 6. Update Security Group
Make sure these ports are open in your EC2 security group:
- 5432 (PostgreSQL) - for Lambda connections
- 3001 (Sensor Data) - for Cloudflare tunnel
- 3002 (Consumer Dashboard) - for monitoring
- 3003-3014 (Other microservices)