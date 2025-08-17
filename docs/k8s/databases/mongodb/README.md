# MongoDB Deployment

This directory contains Kubernetes manifests for deploying MongoDB replica set for the Munbon Irrigation Project.

## Components

1. **ConfigMaps**: MongoDB configuration and initialization scripts
2. **Secrets**: Database passwords and replica set key
3. **StatefulSet**: MongoDB 3-node replica set
4. **Services**: Internal and external access
5. **Job**: Replica set initialization
6. **CronJob**: Automated daily backups
7. **Monitoring**: MongoDB exporter for Prometheus

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   MongoDB-0     │     │   MongoDB-1     │     │   MongoDB-2     │
│   (Primary)     │◄────┤   (Secondary)   │◄────┤   (Secondary)   │
│   Priority: 2   │     │   Priority: 1   │     │   Priority: 1   │
└────────┬────────┘     └─────────────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│ MongoDB Exporter│
│ (Metrics)       │
└─────────────────┘
```

## Deployment

```bash
# Deploy all resources
kubectl apply -f .

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=mongodb -n munbon-databases --timeout=300s

# Initialize replica set (run once after first deployment)
kubectl apply -f 04-init-replica-set.yaml
```

## Configuration

### Storage
Update `storageClassName` in `03-statefulset.yaml`:
- `fast-ssd`: For primary data storage (recommended)
- `standard`: For backup storage

### Secrets
**IMPORTANT**: Update all passwords in `02-secret.yaml` before production:
```bash
# Generate secure passwords
openssl rand -base64 32
```

### Resource Limits
Adjust CPU and memory in `03-statefulset.yaml` based on workload.

## Access

### Internal Access
```
# Connection string for replica set
mongodb://user:password@mongodb-0.mongodb:27017,mongodb-1.mongodb:27017,mongodb-2.mongodb:27017/database?replicaSet=munbon-rs

# Service endpoints
mongodb.munbon-databases.svc.cluster.local:27017
```

### External Access
If LoadBalancer is configured:
```bash
kubectl get service mongodb-lb -n munbon-databases
```

## Collections

### munbon_dev Database
- `system_config`: System configuration
- `alert_rules`: Alert rule definitions
- `notification_templates`: Message templates
- `maintenance_schedules`: Equipment maintenance
- `report_definitions`: Report configurations
- `file_metadata`: File storage metadata

### munbon_config Database
- `feature_flags`: Feature toggles

### munbon_logs Database
- `audit_logs`: Capped collection for audit trail

## Operations

### Connect to MongoDB Shell
```bash
kubectl exec -it mongodb-0 -n munbon-databases -- mongosh \
  -u admin -p <password> --authenticationDatabase admin
```

### Check Replica Set Status
```bash
kubectl exec -it mongodb-0 -n munbon-databases -- mongosh \
  -u admin -p <password> --authenticationDatabase admin \
  --eval "rs.status()"
```

### Manual Backup
```bash
kubectl exec -it mongodb-0 -n munbon-databases -- mongodump \
  --username=admin --password=<password> \
  --authenticationDatabase=admin \
  --oplog --gzip --archive=/tmp/backup.gz
```

### Restore from Backup
```bash
kubectl exec -i mongodb-0 -n munbon-databases -- mongorestore \
  --username=admin --password=<password> \
  --authenticationDatabase=admin \
  --oplogReplay --gzip --archive < backup.gz
```

## Monitoring

### Prometheus Metrics
MongoDB exporter provides metrics at:
```
http://mongodb-exporter.munbon-databases.svc.cluster.local:9216/metrics
```

Key metrics to monitor:
- `mongodb_up`: MongoDB instance availability
- `mongodb_replset_member_state`: Replica set member states
- `mongodb_connections`: Connection count
- `mongodb_memory`: Memory usage
- `mongodb_opcounters`: Operation counters

### Check Logs
```bash
# MongoDB logs
kubectl logs mongodb-0 -n munbon-databases

# Exporter logs
kubectl logs deployment/mongodb-exporter -n munbon-databases
```

## Scaling

### Add Replica Set Members
1. Scale StatefulSet:
   ```bash
   kubectl scale statefulset mongodb -n munbon-databases --replicas=5
   ```

2. Add new members to replica set:
   ```javascript
   rs.add("mongodb-3.mongodb:27017")
   rs.add("mongodb-4.mongodb:27017")
   ```

## Security

### Authentication
- Root user: Full admin access
- munbon_app: Application read/write access
- backup_user: Backup operations only

### Network Security
1. Use NetworkPolicies to restrict access
2. Enable TLS/SSL for production
3. Rotate passwords regularly
4. Use keyFile authentication for replica set

## Troubleshooting

### Common Issues

1. **Replica set not initialized**
   ```bash
   kubectl logs job/mongodb-init-replica-set -n munbon-databases
   ```

2. **Authentication failures**
   - Check secret values
   - Verify keyFile permissions

3. **Storage issues**
   ```bash
   kubectl describe pvc -n munbon-databases
   ```

4. **Performance issues**
   - Check resource utilization
   - Review slow query logs
   - Analyze index usage