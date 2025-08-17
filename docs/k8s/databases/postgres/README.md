# PostgreSQL with PostGIS Deployment

This directory contains Kubernetes manifests for deploying PostgreSQL with PostGIS extension for the Munbon Irrigation Project.

## Components

1. **Namespace**: Dedicated namespace for all database resources
2. **ConfigMaps**: PostgreSQL configuration and initialization scripts
3. **Secrets**: Database passwords (update before production deployment)
4. **PersistentVolumeClaims**: Storage for data and backups
5. **StatefulSet**: PostgreSQL primary instance
6. **Services**: Internal and external access
7. **CronJob**: Automated daily backups

## Deployment

```bash
# Deploy all resources
kubectl apply -f .

# Or deploy in order
kubectl apply -f 00-namespace.yaml
kubectl apply -f 01-configmap.yaml
kubectl apply -f 02-secret.yaml
kubectl apply -f 03-pvc.yaml
kubectl apply -f 04-statefulset.yaml
kubectl apply -f 05-backup-cronjob.yaml
```

## Configuration

### Storage Classes
Update the `storageClassName` in `03-pvc.yaml` based on your cluster:
- `fast-ssd`: For primary data storage
- `standard`: For backup storage

### Secrets
**IMPORTANT**: Update all passwords in `02-secret.yaml` before production deployment:
```bash
# Generate secure passwords
openssl rand -base64 32
```

### Resource Limits
Adjust CPU and memory limits in `04-statefulset.yaml` based on your workload.

## Access

### Internal Access
- Service: `postgres-primary.munbon-databases.svc.cluster.local`
- Port: 5432

### External Access
If LoadBalancer is configured:
```bash
kubectl get service postgres-lb -n munbon-databases
```

### Connection String
```
postgresql://postgres:<password>@postgres-primary.munbon-databases.svc.cluster.local:5432/munbon_prod
```

## Backup and Restore

### Manual Backup
```bash
kubectl exec -it postgres-primary-0 -n munbon-databases -- \
  pg_dump -U postgres -d munbon_prod | gzip > backup.sql.gz
```

### Restore
```bash
kubectl exec -i postgres-primary-0 -n munbon-databases -- \
  gunzip -c | psql -U postgres -d munbon_prod < backup.sql.gz
```

## Monitoring

Check pod status:
```bash
kubectl get pods -n munbon-databases
kubectl logs postgres-primary-0 -n munbon-databases
```

## PostGIS Extensions

The following extensions are automatically enabled:
- postgis
- postgis_topology
- postgis_raster
- uuid-ossp
- pgcrypto

## Schemas

Three schemas are created:
- `gis`: Spatial data tables
- `auth`: Authentication and user management
- `config`: Configuration data