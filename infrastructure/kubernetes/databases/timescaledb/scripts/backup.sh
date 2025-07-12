#!/bin/bash

# TimescaleDB Backup Script
# Usage: ./backup.sh [namespace] [output-dir]

set -e

NAMESPACE=${1:-munbon-databases}
OUTPUT_DIR=${2:-./backups}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
POD_NAME=$(kubectl get pods -n $NAMESPACE -l app=timescaledb -o jsonpath='{.items[0].metadata.name}')

if [ -z "$POD_NAME" ]; then
    echo "Error: No TimescaleDB pod found in namespace $NAMESPACE"
    exit 1
fi

echo "Starting backup of TimescaleDB..."
echo "Pod: $POD_NAME"
echo "Namespace: $NAMESPACE"

# Create output directory
mkdir -p $OUTPUT_DIR

# Backup sensor_data database
echo "Backing up sensor_data database..."
kubectl exec -n $NAMESPACE $POD_NAME -- pg_dump -U postgres -d sensor_data \
    --verbose \
    --format=custom \
    --compress=9 \
    --file=/tmp/sensor_data_${TIMESTAMP}.dump

# Copy backup file from pod
echo "Copying backup file..."
kubectl cp $NAMESPACE/$POD_NAME:/tmp/sensor_data_${TIMESTAMP}.dump \
    $OUTPUT_DIR/sensor_data_${TIMESTAMP}.dump

# Clean up temp file in pod
kubectl exec -n $NAMESPACE $POD_NAME -- rm /tmp/sensor_data_${TIMESTAMP}.dump

# Create backup metadata
cat > $OUTPUT_DIR/sensor_data_${TIMESTAMP}.metadata <<EOF
Backup Timestamp: $TIMESTAMP
Database: sensor_data
Pod: $POD_NAME
Namespace: $NAMESPACE
TimescaleDB Version: $(kubectl exec -n $NAMESPACE $POD_NAME -- psql -U postgres -d sensor_data -t -c "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';")
Database Size: $(kubectl exec -n $NAMESPACE $POD_NAME -- psql -U postgres -d sensor_data -t -c "SELECT pg_size_pretty(pg_database_size('sensor_data'));")
EOF

echo "Backup completed: $OUTPUT_DIR/sensor_data_${TIMESTAMP}.dump"
echo "Metadata saved: $OUTPUT_DIR/sensor_data_${TIMESTAMP}.metadata"

# Optional: Keep only last 7 backups
echo "Cleaning old backups..."
ls -t $OUTPUT_DIR/sensor_data_*.dump | tail -n +8 | xargs -r rm
ls -t $OUTPUT_DIR/sensor_data_*.metadata | tail -n +8 | xargs -r rm

echo "Backup process completed successfully!"