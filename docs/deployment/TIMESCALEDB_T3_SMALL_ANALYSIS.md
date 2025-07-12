# TimescaleDB on AWS t3.small - Feasibility Analysis

## t3.small Specifications
- **vCPUs**: 2 (burstable)
- **RAM**: 2 GB
- **Network**: Up to 5 Gbps
- **EBS Bandwidth**: Up to 2,085 Mbps
- **CPU Credits**: 24 credits/hour (burst performance)

## Cost Analysis

### Monthly Costs
```
t3.small Instance:
- On-Demand: $0.0208/hour × 730 hours = $15.18/month
- 1-Year Reserved: ~$9.50/month (37% savings)
- 3-Year Reserved: ~$6.00/month (60% savings)

Storage (100 GB gp3):
- $0.08/GB × 100 GB = $8.00/month

Backup Storage (S3):
- 100 GB snapshots: $2.30/month

Data Transfer:
- Estimated 50 GB/month = $4.50/month

Total Monthly Cost:
- On-Demand: $15.18 + $8 + $2.30 + $4.50 = $29.98/month
- 1-Year Reserved: $9.50 + $8 + $2.30 + $4.50 = $24.30/month
```

## Performance Considerations

### Memory Constraints (2 GB RAM)
```yaml
# PostgreSQL memory allocation for 2 GB system
shared_buffers: 512MB          # 25% of RAM
effective_cache_size: 1.5GB    # 75% of RAM
work_mem: 4MB                  # Conservative setting
maintenance_work_mem: 128MB    # For vacuum, index creation
max_connections: 50            # Reduced from default 100
```

### Current Data Load
Based on your sensor data:
- **20 sensors** (10 water level + 10 moisture)
- **1 reading/minute/sensor** = 28,800 readings/day
- **~42 MB/day** of raw data
- **1.3 GB/month** of new data

### Will t3.small Handle This?

#### ✅ **Pros - It Should Work For:**
1. **Data Ingestion**: 20 readings/minute is low volume
2. **Storage**: 100 GB is sufficient for 2+ years
3. **Query Load**: If queries are well-optimized with indexes
4. **API Serving**: For < 100 concurrent users

#### ❌ **Cons - Limitations:**
1. **Memory Pressure**: Only 2 GB RAM limits caching
2. **Complex Queries**: Aggregations may be slow
3. **Concurrent Users**: Limited to ~50 connections
4. **Background Jobs**: Compression/maintenance compete for resources
5. **Growth**: No headroom for expansion

## Optimization Requirements for t3.small

### 1. Connection Pooling (Critical)
```yaml
# PgBouncer configuration - REQUIRED for t3.small
[databases]
munbon = host=localhost port=5432 dbname=munbon_timescale

[pgbouncer]
pool_mode = transaction
max_client_conn = 200
default_pool_size = 10        # Reduced for 2GB RAM
max_db_connections = 30       # Leave some for maintenance
```

### 2. Aggressive Data Compression
```sql
-- Compress data older than 1 day (instead of 7)
SELECT add_compression_policy('water_level_readings', INTERVAL '1 day');
SELECT add_compression_policy('moisture_readings', INTERVAL '1 day');

-- Compression can achieve 90%+ reduction
-- 1.3 GB/month → ~130 MB/month compressed
```

### 3. Continuous Aggregates (Pre-computed)
```sql
-- Create hourly aggregates to reduce query load
CREATE MATERIALIZED VIEW water_level_hourly
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', time) AS hour,
    sensor_id,
    AVG(level_cm) as avg_level,
    MIN(level_cm) as min_level,
    MAX(level_cm) as max_level
FROM water_level_readings
GROUP BY hour, sensor_id;

-- Auto-refresh policy
SELECT add_continuous_aggregate_policy('water_level_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');
```

### 4. Query Optimization
```sql
-- Essential indexes for t3.small
CREATE INDEX idx_water_level_sensor_time ON water_level_readings (sensor_id, time DESC);
CREATE INDEX idx_moisture_sensor_time ON moisture_readings (sensor_id, time DESC);

-- Use BRIN indexes for time columns (smaller size)
CREATE INDEX idx_water_level_time_brin ON water_level_readings USING BRIN (time);
```

### 5. API Caching Strategy
```javascript
// Redis caching for frequently accessed data
const cacheMiddleware = {
  latestReadings: 60,        // Cache for 1 minute
  hourlyAggregates: 3600,    // Cache for 1 hour
  dailyAggregates: 86400,    // Cache for 1 day
  sensorList: 3600           // Cache for 1 hour
};
```

## Performance Test Results (Estimated)

### Expected Performance on t3.small
| Operation | t3.small | t3.medium | t3.large |
|-----------|----------|-----------|----------|
| Data Ingestion | ✅ Good | ✅ Good | ✅ Good |
| Latest Readings API | ✅ < 100ms | ✅ < 50ms | ✅ < 30ms |
| 24h Aggregations | ⚠️ 500-1000ms | ✅ 200-400ms | ✅ 100-200ms |
| 7-day Reports | ❌ 2-5s | ⚠️ 1-2s | ✅ < 1s |
| Concurrent Users | ⚠️ 50 | ✅ 200 | ✅ 500+ |

## Monitoring Requirements

### Critical Metrics for t3.small
```yaml
CloudWatch Alarms:
  - CPU Credits Balance < 50     # Risk of throttling
  - Memory Usage > 85%            # Swap risk
  - Database Connections > 40     # Connection limit
  - Disk Queue Length > 10        # I/O bottleneck
  - Query Duration > 2s           # Performance degradation
```

## Recommendation Summary

### ✅ **t3.small IS VIABLE IF:**
1. You implement aggressive caching (Redis)
2. Use connection pooling (PgBouncer)
3. Enable TimescaleDB compression
4. Create continuous aggregates
5. Limit concurrent users to ~50
6. Monitor performance closely

### ❌ **Choose t3.medium/large IF:**
1. You expect > 50 concurrent users
2. Need complex real-time analytics
3. Want room for growth
4. Require faster query response times
5. Plan to add more sensors soon

## Cost-Benefit Analysis

| Instance | Monthly Cost | Suitable For |
|----------|--------------|--------------|
| **t3.small** | $24-30 | MVP, Dev/Test, <50 users, <50 sensors |
| **t3.medium** | $38-45 | Production, <200 users, <100 sensors |
| **t3.large** | $54-75 | Scale Production, 500+ users, 200+ sensors |

## Migration Path Using t3.small

### Phase 1: Start Small (Month 1-3)
- Deploy on t3.small ($24/month)
- Implement all optimizations
- Monitor performance metrics

### Phase 2: Evaluate (Month 3)
- If CPU credits stable: Continue
- If memory pressure: Add Redis cache
- If query slow: Scale to t3.medium

### Phase 3: Scale Decision
```javascript
// Scaling triggers
if (avgCPUCredits < 100 || 
    avgMemoryUsage > 85% || 
    p95QueryTime > 1000ms ||
    dailyActiveUsers > 50) {
  scaleToT3Medium();
}
```

## Conclusion

**t3.small CAN work for Munbon's current requirements** (20 sensors, limited users) but requires:
1. Careful optimization and configuration
2. Aggressive caching strategy
3. Close performance monitoring
4. Readiness to scale when needed

**Total cost with optimizations**: ~$30-35/month (including Redis cache)

For just $10-15 more per month, t3.medium provides much better headroom and peace of mind. But if budget is critical, t3.small is a viable starting point.