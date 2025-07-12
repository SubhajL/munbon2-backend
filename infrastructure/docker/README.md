# Docker Infrastructure

This directory contains Docker configurations and tools for the Munbon Backend microservices.

## Overview

Our Docker setup is optimized for local development on Apple Silicon (M4 Pro) with:
- Multi-stage Dockerfiles for optimal image sizes
- Development stages with hot-reload capabilities
- Security best practices (non-root users, minimal base images)
- ARM64 native builds for better performance
- Local registry for fast builds and deployments

## Quick Start

### 1. Start Infrastructure

```bash
# Start all databases and tools
make up

# Or start minimal setup (just PostgreSQL and Redis)
make up-min
```

### 2. Check Status

```bash
make status
```

This shows:
- Running containers
- Database connection strings
- Management UI URLs

### 3. Build Services

```bash
# Build all services
make build

# Build specific service
make build-service SERVICE=api-gateway
```

## Docker Compose Services

### Databases

| Service | Port | Connection String |
|---------|------|-------------------|
| PostgreSQL + PostGIS | 5432 | `postgresql://postgres:postgres@localhost:5432/munbon_dev` |
| TimescaleDB | 5433 | `postgresql://postgres:postgres@localhost:5433/munbon_timeseries` |
| MongoDB | 27017 | `mongodb://admin:admin@localhost:27017/munbon_dev` |
| Redis | 6379 | `redis://localhost:6379` |
| InfluxDB | 8086 | `http://localhost:8086` (admin/admin123456) |

### Message Queue

| Service | Port | Purpose |
|---------|------|---------|
| Kafka | 9092 | Event streaming |
| Zookeeper | 2181 | Kafka coordination |

### Management UIs

| Tool | URL | Credentials |
|------|-----|-------------|
| Kafka UI | http://localhost:8090 | - |
| Mongo Express | http://localhost:8091 | - |
| Redis Commander | http://localhost:8092 | - |
| pgAdmin | http://localhost:8093 | admin@munbon.local / admin |

## Dockerfile Structure

Each service has a multi-stage Dockerfile:

```dockerfile
# Build stage - compile/build
FROM base AS builder
...

# Production stage - minimal runtime
FROM base AS production
...

# Development stage - hot-reload
FROM base AS development
...
```

### Security Features

1. **Non-root users**: All containers run as non-root
2. **Minimal images**: Alpine/distroless base images
3. **Health checks**: Built-in health check endpoints
4. **Signal handling**: Proper PID 1 signal handling with dumb-init
5. **Read-only filesystems**: Where applicable

### Optimization for M4 Pro

- Native ARM64 builds: `--platform linux/arm64`
- BuildKit enabled for faster builds
- Layer caching optimized
- Multi-stage builds reduce final image size

## Local Registry

A local Docker registry runs at `localhost:5000` for:
- Fast push/pull operations
- No internet dependency
- Easy integration with Kubernetes

```bash
# Start registry
make registry-start

# List images in registry
make registry-list
```

## Development Workflow

### 1. Hot Reload Development

```bash
# Start service with hot-reload
docker-compose up api-gateway

# The service will auto-reload on code changes
```

### 2. Building Images

```bash
# Build for production
docker build --target production -t myservice:prod .

# Build for development
docker build --target development -t myservice:dev .
```

### 3. Security Scanning

```bash
# Scan all images
./scripts/docker/scan-images.sh

# Scan specific image
./scripts/docker/scan-images.sh image localhost:5000/munbon/api-gateway

# Generate security report
./scripts/docker/scan-images.sh report
```

## Resource Management

Docker Desktop recommended settings for M4 Pro:
- CPUs: 6 cores
- Memory: 12 GB
- Disk: 80 GB

Each service is limited to:
- CPU: 0.5 cores (max)
- Memory: 512MB (max)
- CPU reservation: 0.1 cores
- Memory reservation: 128MB

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs service-name

# Check health
docker-compose ps
```

### Out of disk space

```bash
# Clean up unused resources
docker system prune -a

# Remove volumes (WARNING: deletes data)
docker volume prune
```

### Slow builds

```bash
# Enable BuildKit
export DOCKER_BUILDKIT=1

# Check builder cache
docker buildx du
```

### Can't connect to service

```bash
# Check if service is running
docker-compose ps

# Check port mapping
docker-compose port service-name 8080

# Check network
docker network ls
```

## Best Practices

1. **Always use multi-stage builds** to minimize image size
2. **Run as non-root user** for security
3. **Use health checks** for better orchestration
4. **Tag images properly** with version and timestamp
5. **Scan images regularly** for vulnerabilities
6. **Use .dockerignore** to exclude unnecessary files
7. **Layer cache optimization** - put rarely changing items first
8. **Use specific versions** for base images, not `latest`

## CI/CD Integration

GitHub Actions workflow automatically:
1. Builds images on push to main/develop
2. Runs security scans with Trivy
3. Pushes to GitHub Container Registry
4. Supports multi-platform builds (AMD64/ARM64)

See `.github/workflows/docker-build.yml` for details.