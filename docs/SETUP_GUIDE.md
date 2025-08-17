# Munbon Backend Setup Guide

This guide will help you set up the Kong API Gateway, Authentication Service, and GIS Data Service for the Munbon Irrigation Control System.

## Prerequisites

Before starting, ensure you have the following installed:

- **Docker Desktop** (includes Docker and Docker Compose)
- **Node.js** 18+ and npm
- **Git**
- **PostgreSQL client tools** (optional, for database access)
- **curl** and **jq** (for testing)

### macOS Installation
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install required tools
brew install node@18 postgresql curl jq
brew install --cask docker
```

### Ubuntu/Debian Installation
```bash
# Update package list
sudo apt update

# Install Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install other tools
sudo apt install -y postgresql-client curl jq
```

## Quick Setup (Automated)

We provide an automated setup script that configures all services:

```bash
# Make the setup script executable
chmod +x setup-all-services.sh

# Run the setup script
./setup-all-services.sh

# Start all services
./start-services.sh

# Create admin user
./create-admin-user.sh

# Verify everything is working
./check-health.sh
```

## Manual Setup (Step by Step)

If you prefer to set up services manually or need to troubleshoot:

### 1. Clone the Repository
```bash
git clone <repository-url>
cd munbon2-backend
```

### 2. Generate JWT Secret
Create a shared JWT secret for all services:
```bash
# Generate secure random secret
JWT_SECRET=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
echo "JWT_SECRET=$JWT_SECRET" > .env.jwt.secret
```

### 3. Start Infrastructure Services

#### Kong API Gateway
```bash
# Start Kong and its PostgreSQL database
docker-compose -f docker-compose.kong.yml up -d

# Wait for Kong to be ready
sleep 30

# Configure Kong
cd infrastructure/kong
./setup-kong.sh
cd ../..
```

#### GIS Database and Cache
```bash
# Start PostGIS and Redis for GIS service
docker-compose -f services/gis/docker-compose.dev.yml up -d
```

### 4. Configure Authentication Service

```bash
cd services/auth

# Copy and configure environment
cp .env.example .env

# Edit .env and update:
# - JWT_SECRET (use the one generated above)
# - Database credentials
# - SMTP settings for email
# - OAuth credentials for Thai Digital ID

# Install dependencies
npm install

# Create database
docker exec -i munbon-kong-db psql -U postgres -c "CREATE DATABASE munbon_auth"

# Run migrations
npm run typeorm migration:run

# Start the service
npm run dev
```

### 5. Configure GIS Service

```bash
cd services/gis

# Copy and configure environment
cp .env.example .env

# Edit .env and update:
# - JWT_SECRET (use the same one)
# - Database credentials (should match docker-compose)

# Install dependencies
npm install

# Start the service
npm run dev
```

## Service URLs and Ports

After setup, services will be available at:

| Service | Direct URL | Via Kong Gateway | Port |
|---------|-----------|------------------|------|
| Kong Proxy | - | http://localhost:8000 | 8000 |
| Kong Admin | http://localhost:8001 | - | 8001 |
| Kong Manager | http://localhost:8002 | - | 8002 |
| Auth Service | http://localhost:3001 | http://localhost:8000/auth | 3001 |
| GIS Service | http://localhost:3006 | http://localhost:8000/gis | 3006 |
| PostgreSQL (Kong) | localhost:5433 | - | 5433 |
| PostgreSQL (GIS) | localhost:5432 | - | 5432 |
| Redis | localhost:6379 | - | 6379 |

## Environment Configuration

### Key Environment Variables

Each service has its own `.env` file. Here are the critical variables:

#### All Services
```env
JWT_SECRET=<same-secret-across-all-services>
NODE_ENV=development
```

#### Authentication Service
```env
# Database
DB_HOST=localhost
DB_PORT=5433
DB_NAME=munbon_auth
DB_USER=postgres
DB_PASSWORD=postgres

# Email (required for password reset, 2FA)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password

# OAuth - Thai Digital ID
THAI_DIGITAL_ID_CLIENT_ID=your-client-id
THAI_DIGITAL_ID_CLIENT_SECRET=your-client-secret
```

#### GIS Service
```env
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=munbon_gis
DB_USER=postgres
DB_PASSWORD=postgres123

# Redis
REDIS_URL=redis://localhost:6379
```

## Testing the Setup

### 1. Health Checks
```bash
# Check all services
./check-health.sh

# Or manually:
curl http://localhost:8000/health
curl http://localhost:3001/health
curl http://localhost:3006/health
```

### 2. Create Admin User
```bash
./create-admin-user.sh
# Follow the prompts to create an admin account
```

### 3. Test Authentication
```bash
# Login
curl -X POST http://localhost:8000/auth/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@munbon.com", "password": "Admin123!"}'

# Save the returned token for authenticated requests
TOKEN="<your-jwt-token>"
```

### 4. Test GIS Service
```bash
# Get zones (requires authentication)
curl http://localhost:8000/gis/api/v1/zones \
  -H "Authorization: Bearer $TOKEN"

# Get vector tiles (public)
curl http://localhost:8000/gis/api/v1/tiles/zones/10/817/507.pbf \
  --output tile.pbf
```

## Common Issues and Solutions

### Port Already in Use
```bash
# Find and kill process using a port
lsof -ti:8000 | xargs kill -9  # Kill process on port 8000
```

### Database Connection Failed
- Ensure Docker containers are running: `docker ps`
- Check database credentials in `.env` files
- For Docker networking, use `host.docker.internal` instead of `localhost`

### JWT Token Invalid
- Ensure all services use the same JWT_SECRET
- Check token expiration (default 15 minutes)
- Verify the token format: `Bearer <token>`

### PostGIS Extension Missing
```bash
# Connect to GIS database and create extension
docker exec -it munbon-gis-postgres psql -U postgres -d munbon_gis
CREATE EXTENSION IF NOT EXISTS postgis;
```

### Service Won't Start
- Check logs: `npm run dev` shows detailed errors
- Verify all dependencies installed: `npm install`
- Ensure `.env` file exists and is configured

## Development Workflow

### Starting Services
```bash
# Start all infrastructure
./start-services.sh

# Or start individually:
cd services/auth && npm run dev
cd services/gis && npm run dev
```

### Stopping Services
```bash
# Stop all services
./stop-services.sh

# Or stop Docker containers only:
docker-compose -f docker-compose.kong.yml down
docker-compose -f services/gis/docker-compose.dev.yml down
```

### Viewing Logs
```bash
# Docker logs
docker logs munbon-kong -f
docker logs munbon-gis-postgres -f

# Service logs (shown in terminal when running npm run dev)
```

### Database Access
```bash
# Connect to Auth database
docker exec -it munbon-kong-db psql -U postgres -d munbon_auth

# Connect to GIS database
docker exec -it munbon-gis-postgres psql -U postgres -d munbon_gis

# Run migrations
cd services/auth && npm run migration:run
cd services/gis && npm run migration:run
```

## Production Deployment

For production deployment:

1. Use proper secrets management (AWS Secrets Manager, Vault, etc.)
2. Enable SSL/TLS for all services
3. Use managed databases (AWS RDS with PostGIS)
4. Configure proper backup strategies
5. Set up monitoring and alerting
6. Use Kubernetes for orchestration
7. Implement proper logging aggregation

## Additional Resources

- [Kong Documentation](https://docs.konghq.com/)
- [PostGIS Documentation](https://postgis.net/documentation/)
- [TypeORM Documentation](https://typeorm.io/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)

## Support

For issues or questions:
1. Check the logs first
2. Ensure all prerequisites are installed
3. Verify environment variables are set correctly
4. Check if services are running: `docker ps` and `ps aux | grep node`