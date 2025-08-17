# InfluxDB Deployment

This directory contains Kubernetes manifests for deploying InfluxDB 2.x time-series database for the Munbon Irrigation Project.

## Components

1. **InfluxDB**: Time-series database for metrics storage
2. **Telegraf**: Metrics collection agent (DaemonSet)
3. **Chronograf**: Visualization and monitoring UI
4. **Pre-configured buckets**: For different metric types with retention policies

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Telegraf      │────▶│    InfluxDB     │◀────│   Chronograf    │
│  (DaemonSet)    │     │   (StatefulSet) │     │  (Deployment)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                                                │
         │                                                │
         ▼                                                ▼
┌─────────────────┐                              ┌─────────────────┐
│ System Metrics  │                              │   Dashboards    │
│ Container Stats │                              │   Visualizations│
│ App Metrics     │                              │   Alerts        │
└─────────────────┘                              └─────────────────┘
```

## Deployment

```bash
# Deploy all resources
kubectl apply -f .

# Check deployment status
kubectl get pods -n munbon-databases | grep -E "influx|telegraf|chronograf"

# Initialize buckets and tasks (after InfluxDB is ready)
kubectl exec -it influxdb-0 -n munbon-databases -- bash
/scripts/influxdb/init-influxdb.sh
```

## Configuration

### Update Secrets
**IMPORTANT**: Change all passwords and tokens in `02-secret.yaml`:
```bash
# Generate secure token
openssl rand -hex 32
```

### Storage Class
Update `storageClassName` in `03-statefulset.yaml` based on your cluster.

## Access

### InfluxDB API
```bash
# Internal access
http://influxdb.munbon-databases.svc.cluster.local:8086

# External access (if LoadBalancer configured)
kubectl get service influxdb-lb -n munbon-databases
```

### InfluxDB UI
Access the built-in UI at `http://<EXTERNAL_IP>:8086`

### Chronograf UI
Access at `http://metrics.munbon.local` (requires ingress setup)

## Buckets and Retention

| Bucket | Retention | Purpose |
|--------|-----------|---------|
| system-metrics | 30 days | System performance metrics |
| sensor-data | 90 days | Raw sensor readings |
| sensor-data-hourly | 1 year | Aggregated sensor data |
| water-usage | 5 years | Water consumption metrics |
| control-metrics | 90 days | Control system operations |
| api-metrics | 7 days | API performance data |
| alert-metrics | 30 days | System alerts |

## Usage Examples

### Writing Metrics (Line Protocol)
```bash
# Using curl
curl -X POST "http://influxdb:8086/api/v2/write?org=munbon&bucket=sensor-data" \
  -H "Authorization: Token YOUR_TOKEN" \
  -d "water_level,sensor_id=WL001,zone_id=zone1 level_cm=15.5 $(date +%s)000000000"
```

### Writing Metrics (Node.js)
```javascript
const {InfluxDB, Point} = require('@influxdata/influxdb-client');

const influxDB = new InfluxDB({
  url: 'http://influxdb:8086',
  token: process.env.INFLUX_TOKEN,
});

const writeApi = influxDB.getWriteApi('munbon', 'sensor-data');

const point = new Point('water_level')
  .tag('sensor_id', 'WL001')
  .tag('zone_id', 'zone1')
  .floatField('level_cm', 15.5);

writeApi.writePoint(point);
await writeApi.close();
```

### Querying Data (Flux)
```javascript
const queryApi = influxDB.getQueryApi('munbon');

const query = `
  from(bucket: "sensor-data")
    |> range(start: -1h)
    |> filter(fn: (r) => r._measurement == "water_level")
    |> filter(fn: (r) => r.sensor_id == "WL001")
    |> aggregateWindow(every: 5m, fn: mean)
`;

const results = await queryApi.collectRows(query);
```

## Continuous Queries

### Downsampling Task
Automatically aggregates high-resolution data:
```flux
from(bucket: "sensor-data")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "sensor_reading")
  |> aggregateWindow(every: 1h, fn: mean)
  |> to(bucket: "sensor-data-hourly")
```

### Water Usage Calculation
Integrates flow rate to calculate volume:
```flux
from(bucket: "sensor-data")
  |> range(start: -5m)
  |> filter(fn: (r) => r._measurement == "flow_rate")
  |> integral(unit: 1m)
  |> map(fn: (r) => ({r with _measurement: "water_volume"}))
  |> to(bucket: "water-usage")
```

## Alerts

### High Water Level Alert
```flux
data
  |> filter(fn: (r) => r._field == "level_cm")
  |> monitor.check(
    crit: (r) => r.level_cm > 25.0,
    warn: (r) => r.level_cm > 20.0,
    messageFn: (r) => "Water level critical: ${r.level_cm}cm"
  )
```

### Low Moisture Alert
```flux
data
  |> filter(fn: (r) => r._field == "moisture_percent")
  |> monitor.check(
    crit: (r) => r.moisture_percent < 20.0,
    warn: (r) => r.moisture_percent < 30.0,
    messageFn: (r) => "Soil moisture low: ${r.moisture_percent}%"
  )
```

## Telegraf Metrics Collection

Telegraf automatically collects:
- System metrics (CPU, memory, disk, network)
- Kubernetes metrics (pods, nodes, deployments)
- Docker container metrics
- PostgreSQL statistics
- Redis metrics
- MongoDB metrics
- HTTP endpoint health checks

## Maintenance

### Backup
```bash
# Backup to file
kubectl exec -it influxdb-0 -n munbon-databases -- \
  influx backup /backup/$(date +%Y%m%d) \
  --token $INFLUX_TOKEN

# Copy backup locally
kubectl cp munbon-databases/influxdb-0:/backup ./influxdb-backup
```

### Restore
```bash
# Copy backup to pod
kubectl cp ./influxdb-backup munbon-databases/influxdb-0:/backup

# Restore
kubectl exec -it influxdb-0 -n munbon-databases -- \
  influx restore /backup/20240620 \
  --token $INFLUX_TOKEN
```

### Delete Old Data
```bash
# Delete data older than timestamp
influx delete \
  --bucket sensor-data \
  --start 2020-01-01T00:00:00Z \
  --stop 2023-01-01T00:00:00Z \
  --org munbon
```

## Monitoring

### Check InfluxDB Health
```bash
curl http://influxdb:8086/health
```

### View Tasks
```bash
kubectl exec -it influxdb-0 -n munbon-databases -- \
  influx task list --org munbon
```

### View Bucket Statistics
```bash
kubectl exec -it influxdb-0 -n munbon-databases -- \
  influx bucket list --org munbon
```

## Troubleshooting

### Connection Issues
```bash
# Check pod logs
kubectl logs influxdb-0 -n munbon-databases

# Test connection
kubectl exec -it influxdb-0 -n munbon-databases -- \
  influx ping --host http://localhost:8086
```

### Query Performance
```bash
# Enable query logging
kubectl exec -it influxdb-0 -n munbon-databases -- \
  influx config set --log-level debug
```

### Storage Issues
```bash
# Check disk usage
kubectl exec -it influxdb-0 -n munbon-databases -- df -h

# Check database size
kubectl exec -it influxdb-0 -n munbon-databases -- \
  du -sh /var/lib/influxdb2
```

## Best Practices

1. **Tag Design**: Use consistent tag names and limit cardinality
2. **Batch Writes**: Group multiple points for better performance
3. **Retention Policies**: Set appropriate retention for each data type
4. **Downsampling**: Use continuous queries for long-term storage
5. **Monitoring**: Set up alerts for disk usage and query performance