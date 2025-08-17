# Troubleshooting Guide

This guide helps resolve common issues when setting up and running the Munbon Backend services.

## Table of Contents
1. [Setup Issues](#setup-issues)
2. [Service Startup Issues](#service-startup-issues)
3. [Database Issues](#database-issues)
4. [Authentication Issues](#authentication-issues)
5. [GIS Service Issues](#gis-service-issues)
6. [Kong Gateway Issues](#kong-gateway-issues)
7. [Performance Issues](#performance-issues)

## Setup Issues

### Script Permission Denied
**Error:** `bash: ./setup-all-services.sh: Permission denied`

**Solution:**
```bash
chmod +x setup-all-services.sh
chmod +x start-services.sh
chmod +x stop-services.sh
chmod +x check-health.sh
chmod +x create-admin-user.sh
```

### Docker Not Running
**Error:** `Cannot connect to the Docker daemon`

**Solution:**
- macOS: Start Docker Desktop from Applications
- Linux: `sudo systemctl start docker`
- Verify: `docker ps`

### Port Already in Use
**Error:** `Error starting userland proxy: listen tcp4 0.0.0.0:8000: bind: address already in use`

**Solution:**
```bash
# Find process using the port
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use different ports in docker-compose files
```

## Service Startup Issues

### npm install Fails
**Error:** `npm ERR! code ERESOLVE`

**Solution:**
```bash
# Clear npm cache
npm cache clean --force

# Delete node_modules and package-lock.json
rm -rf node_modules package-lock.json

# Reinstall
npm install
```

### TypeScript Compilation Errors
**Error:** `Cannot find module '@types/node'`

**Solution:**
```bash
# Install TypeScript dependencies
npm install --save-dev @types/node typescript

# Check TypeScript version
npx tsc --version
```

### Service Crashes on Startup
**Error:** `Error: Cannot find module`

**Solution:**
1. Check all dependencies are installed: `npm install`
2. Verify `.env` file exists and is configured
3. Check Node.js version: `node --version` (should be 18+)

## Database Issues

### Cannot Connect to PostgreSQL
**Error:** `Error: connect ECONNREFUSED 127.0.0.1:5432`

**Solution:**
```bash
# Check if PostgreSQL container is running
docker ps | grep postgres

# If not running, start it
docker-compose -f services/gis/docker-compose.dev.yml up -d

# Check logs
docker logs munbon-gis-postgres
```

### PostGIS Extension Not Found
**Error:** `ERROR: type "geometry" does not exist`

**Solution:**
```bash
# Connect to database
docker exec -it munbon-gis-postgres psql -U postgres -d munbon_gis

# Create extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
\q
```

### Migration Errors
**Error:** `QueryFailedError: relation "users" already exists`

**Solution:**
```bash
# Check migration status
npm run typeorm migration:show

# Revert last migration if needed
npm run typeorm migration:revert

# Run migrations again
npm run typeorm migration:run
```

## Authentication Issues

### JWT Token Invalid
**Error:** `JsonWebTokenError: invalid signature`

**Solution:**
1. Ensure all services use the same JWT_SECRET
2. Check `.env.jwt.secret` file exists
3. Restart all services after updating JWT_SECRET

### Cannot Create Admin User
**Error:** `Auth service is not running`

**Solution:**
```bash
# Start auth service
cd services/auth
npm run dev

# Wait for service to be ready
curl http://localhost:3001/health

# Then create admin user
./create-admin-user.sh
```

### Login Fails
**Error:** `Invalid credentials`

**Solution:**
1. Verify user exists in database
2. Check password is correct (case-sensitive)
3. Ensure user is active and verified
4. Check database connection

### 2FA Not Working
**Error:** `Invalid TOTP code`

**Solution:**
1. Verify system time is synchronized
2. Check TOTP secret is correctly stored
3. Ensure 6-digit code is entered correctly
4. Try regenerating 2FA setup

## GIS Service Issues

### Vector Tiles Not Loading
**Error:** `404 Not Found` for tile requests

**Solution:**
1. Check tile URL format: `/api/v1/tiles/{layer}/{z}/{x}/{y}.pbf`
2. Verify layer exists (zones, parcels, canals, gates, pumps)
3. Check zoom level is within bounds (8-20)
4. Clear tile cache: `redis-cli FLUSHDB`

### Spatial Queries Fail
**Error:** `Invalid geometry`

**Solution:**
```bash
# Validate GeoJSON
curl -X POST http://localhost:3006/api/v1/spatial/validate \
  -H "Content-Type: application/json" \
  -d '{"geometry": <your-geojson>}'

# Check SRID is correct (4326 for WGS84)
```

### Large File Import Timeout
**Error:** `Request timeout`

**Solution:**
1. Increase timeout in nginx/Kong configuration
2. Use bulk import endpoints
3. Split large files into smaller chunks
4. Process imports asynchronously

## Kong Gateway Issues

### Kong Not Routing Requests
**Error:** `no Route matched with those values`

**Solution:**
```bash
# Check Kong configuration
curl http://localhost:8001/routes

# Reapply configuration
cd infrastructure/kong
./setup-kong.sh
```

### Rate Limiting Too Restrictive
**Error:** `API rate limit exceeded`

**Solution:**
1. Check rate limit configuration in `kong.yml`
2. Adjust limits based on user tier
3. Clear rate limit counters: `redis-cli DEL *rate-limiting*`

### Thai Digital ID Plugin Error
**Error:** `Thai Digital ID validation failed`

**Solution:**
1. Verify OAuth credentials in Kong configuration
2. Check Thai Digital ID service is accessible
3. Verify callback URL is correctly configured
4. Check plugin logs: `docker logs munbon-kong`

## Performance Issues

### Slow Database Queries
**Solution:**
```sql
-- Check query performance
EXPLAIN ANALYZE <your-query>;

-- Create missing indexes
CREATE INDEX idx_parcels_zone_id ON parcels(zone_id);
CREATE INDEX idx_canals_geometry ON canals USING GIST(geometry);

-- Update statistics
ANALYZE;
```

### High Memory Usage
**Solution:**
```bash
# Check memory usage
docker stats

# Limit container memory
docker update --memory="1g" munbon-gis-postgres

# Adjust Node.js memory
NODE_OPTIONS="--max-old-space-size=2048" npm run dev
```

### Redis Cache Issues
**Solution:**
```bash
# Check Redis memory
redis-cli INFO memory

# Clear cache if needed
redis-cli FLUSHDB

# Set memory limit
redis-cli CONFIG SET maxmemory 512mb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

## Debug Mode

Enable detailed logging for troubleshooting:

### Auth Service
```env
# In services/auth/.env
LOG_LEVEL=debug
DB_LOGGING=true
```

### GIS Service
```env
# In services/gis/.env
LOG_LEVEL=debug
DB_LOGGING=true
TILE_DEBUG=true
```

### Kong Gateway
```bash
# Set Kong log level
docker exec munbon-kong kong config set log_level debug
```

## Getting Help

If issues persist:

1. **Check Logs:**
   ```bash
   # Service logs
   docker logs <container-name> --tail 100
   
   # Application logs (in terminal)
   npm run dev
   ```

2. **Verify Configuration:**
   - All `.env` files are properly configured
   - JWT_SECRET is the same across services
   - Database credentials are correct
   - Services can reach each other

3. **Test Connectivity:**
   ```bash
   # Test database
   docker exec -it <container> pg_isready -U postgres
   
   # Test Redis
   docker exec -it munbon-gis-redis redis-cli ping
   
   # Test services
   curl http://localhost:3001/health
   curl http://localhost:3006/health
   ```

4. **Clean Restart:**
   ```bash
   # Stop everything
   ./stop-services.sh
   
   # Remove volumes (WARNING: deletes data)
   docker-compose -f docker-compose.kong.yml down -v
   docker-compose -f services/gis/docker-compose.dev.yml down -v
   
   # Start fresh
   ./setup-all-services.sh
   ```

## Logging and Monitoring

For production debugging:

1. **Structured Logging:**
   - All services use Winston for structured JSON logging
   - Logs include correlation IDs for request tracking

2. **Health Endpoints:**
   - `/health` - Basic health check
   - `/metrics` - Prometheus metrics (planned)
   - `/ready` - Readiness probe

3. **Database Monitoring:**
   ```sql
   -- Check active connections
   SELECT count(*) FROM pg_stat_activity;
   
   -- Check slow queries
   SELECT query, mean_exec_time 
   FROM pg_stat_statements 
   ORDER BY mean_exec_time DESC 
   LIMIT 10;
   ```