#!/bin/bash

# TimescaleDB Restore Script
# Usage: ./restore.sh [backup-file] [namespace]

set -e

BACKUP_FILE=$1
NAMESPACE=${2:-munbon-databases}

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: ./restore.sh <backup-file> [namespace]"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

POD_NAME=$(kubectl get pods -n $NAMESPACE -l app=timescaledb -o jsonpath='{.items[0].metadata.name}')

if [ -z "$POD_NAME" ]; then
    echo "Error: No TimescaleDB pod found in namespace $NAMESPACE"
    exit 1
fi

echo "Starting restore of TimescaleDB..."
echo "Backup file: $BACKUP_FILE"
echo "Pod: $POD_NAME"
echo "Namespace: $NAMESPACE"

# Copy backup file to pod
echo "Copying backup file to pod..."
kubectl cp $BACKUP_FILE $NAMESPACE/$POD_NAME:/tmp/restore.dump

# Drop and recreate database (optional - uncomment if needed)
# echo "Dropping existing database..."
# kubectl exec -n $NAMESPACE $POD_NAME -- psql -U postgres -c "DROP DATABASE IF EXISTS sensor_data;"
# kubectl exec -n $NAMESPACE $POD_NAME -- psql -U postgres -c "CREATE DATABASE sensor_data;"

# Restore database
echo "Restoring database..."
kubectl exec -n $NAMESPACE $POD_NAME -- pg_restore -U postgres -d sensor_data \
    --verbose \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    /tmp/restore.dump

# Clean up temp file in pod
kubectl exec -n $NAMESPACE $POD_NAME -- rm /tmp/restore.dump

# Verify restore
echo "Verifying restore..."
kubectl exec -n $NAMESPACE $POD_NAME -- psql -U postgres -d sensor_data -c "\dt sensor.*"

echo "Restore completed successfully!"