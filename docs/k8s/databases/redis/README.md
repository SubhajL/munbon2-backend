# Redis Deployment

This directory contains Kubernetes manifests for deploying Redis with Sentinel for the Munbon Irrigation Project.

## Components

1. **Redis Master-Replica**: 3-node setup (1 master, 2 replicas)
2. **Redis Sentinel**: High availability monitoring
3. **Redis Commander**: Web-based management UI
4. **Persistent Storage**: Data persistence with PVC

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Redis-0       │     │   Redis-1       │     │   Redis-2       │
│   (Master)      │────▶│   (Replica)     │────▶│   (Replica)     │
│   Sentinel      │     │   Sentinel      │     │   Sentinel      │
└────────┬────────┘     └─────────────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│ Redis Commander │
│   (Web UI)      │
└─────────────────┘
```

## Deployment

```bash
# Deploy all resources
kubectl apply -f .

# Check deployment
kubectl get pods -n munbon-databases | grep redis
```

## Configuration

### Update Secrets
**IMPORTANT**: Change the password in `02-secret.yaml`:
```bash
# Generate secure password
openssl rand -base64 32
```

### Storage Class
Update `storageClassName` in `03-statefulset.yaml` based on your cluster.

## Access

### Internal Access
```bash
# Master endpoint
redis-0.redis.munbon-databases.svc.cluster.local:6379

# Any available Redis (for reads)
redis.munbon-databases.svc.cluster.local:6379

# Connection with auth
redis-cli -h redis-0.redis.munbon-databases.svc.cluster.local -a <password>
```

### External Access
```bash
# Get LoadBalancer IP
kubectl get service redis-lb -n munbon-databases

# Connect
redis-cli -h <EXTERNAL_IP> -a <password>
```

### Redis Commander
Access the web UI at `http://redis.munbon.local` (requires ingress setup).

## Usage Examples

### Session Storage
```javascript
// Node.js example
const redis = require('redis');
const client = redis.createClient({
  host: 'redis.munbon-databases.svc.cluster.local',
  port: 6379,
  password: process.env.REDIS_PASSWORD
});

// Store session
client.setex(`session:${sessionId}`, 86400, JSON.stringify(sessionData));
```

### Caching
```javascript
// Cache sensor data
const key = `cache:sensor:${sensorId}`;
const ttl = 300; // 5 minutes
client.setex(key, ttl, JSON.stringify(sensorData));
```

### Rate Limiting
```javascript
// Check rate limit
const key = `ratelimit:${userId}:${endpoint}`;
const limit = 100;
const window = 3600;

client.incr(key, (err, count) => {
  if (count === 1) {
    client.expire(key, window);
  }
  if (count > limit) {
    // Rate limit exceeded
  }
});
```

### Pub/Sub
```javascript
// Publisher
client.publish('alerts:critical', JSON.stringify({
  type: 'water_level_critical',
  sensorId: 'sensor123',
  value: 35,
  timestamp: new Date()
}));

// Subscriber
const subscriber = redis.createClient({...});
subscriber.subscribe('alerts:critical');
subscriber.on('message', (channel, message) => {
  const alert = JSON.parse(message);
  // Handle alert
});
```

## Data Structures

### Key Namespaces
- `session:*` - User sessions
- `cache:*` - Cached data
- `ratelimit:*` - Rate limiting counters
- `queue:*` - Task queues
- `lock:*` - Distributed locks
- `metrics:*` - Real-time metrics

### Cache TTLs
- Sessions: 24 hours
- Sensor data: 5 minutes
- GIS data: 1 hour
- Reports: 30 minutes
- Feature flags: 5 minutes

## Monitoring

### Health Check
```bash
kubectl exec -it redis-0 -n munbon-databases -- redis-cli -a <password> ping
```

### Memory Usage
```bash
kubectl exec -it redis-0 -n munbon-databases -- redis-cli -a <password> info memory
```

### Monitor Commands
```bash
kubectl exec -it redis-0 -n munbon-databases -- redis-cli -a <password> monitor
```

### Slow Queries
```bash
kubectl exec -it redis-0 -n munbon-databases -- redis-cli -a <password> slowlog get 10
```

## Backup and Restore

### Manual Backup
```bash
# Create backup
kubectl exec -it redis-0 -n munbon-databases -- redis-cli -a <password> BGSAVE

# Copy backup file
kubectl cp munbon-databases/redis-0:/data/dump.rdb ./redis-backup.rdb
```

### Restore
```bash
# Copy backup to pod
kubectl cp ./redis-backup.rdb munbon-databases/redis-0:/data/dump.rdb

# Restart Redis
kubectl delete pod redis-0 -n munbon-databases
```

## Maintenance

### Flush Database
```bash
# Flush specific database
kubectl exec -it redis-0 -n munbon-databases -- redis-cli -a <password> -n 0 FLUSHDB

# Flush all databases (CAUTION!)
kubectl exec -it redis-0 -n munbon-databases -- redis-cli -a <password> FLUSHALL
```

### Configuration Changes
```bash
# Runtime config change
kubectl exec -it redis-0 -n munbon-databases -- redis-cli -a <password> CONFIG SET maxmemory 8gb

# Permanent changes - edit ConfigMap and restart pods
kubectl edit configmap redis-config -n munbon-databases
kubectl rollout restart statefulset redis -n munbon-databases
```

## Troubleshooting

### Connection Issues
```bash
# Check pod status
kubectl describe pod redis-0 -n munbon-databases

# Check logs
kubectl logs redis-0 -n munbon-databases -c redis
```

### Replication Issues
```bash
# Check replication status
kubectl exec -it redis-0 -n munbon-databases -- redis-cli -a <password> info replication
```

### Memory Issues
```bash
# Check memory stats
kubectl exec -it redis-0 -n munbon-databases -- redis-cli -a <password> info memory

# Find large keys
kubectl exec -it redis-0 -n munbon-databases -- redis-cli -a <password> --bigkeys
```