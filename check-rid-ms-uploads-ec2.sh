#!/bin/bash

echo "=== Searching EC2 Database for RID-MS Zipped File Uploads ==="
echo "Date: $(date)"
echo ""

# Configuration
EC2_IP="43.208.201.191"
SSH_KEY="~/dev/th-lab01.pem"

echo "1. Checking for GIS/shapefile related tables..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -c "\l" | grep -E "(gis|shape)" || echo "No GIS databases found"

echo ""
echo "Checking all databases for shapefile/upload tables..."
for db in sensor_data gis munbon postgres; do
  echo "Database: $db"
  docker exec postgres_timescale_postgis psql -U postgres -d $db -c "
    SELECT table_schema, table_name 
    FROM information_schema.tables 
    WHERE table_name LIKE '%upload%' 
       OR table_name LIKE '%shape%' 
       OR table_name LIKE '%parcel%' 
       OR table_name LIKE '%zone%'
       OR table_name LIKE '%gis%'
    AND table_schema NOT IN ('pg_catalog', 'information_schema')
    ORDER BY table_schema, table_name;" 2>/dev/null || echo "  Database $db not accessible"
  echo ""
done
EOF

echo ""
echo "2. Searching for shape_file_uploads table and checking RID-MS uploads..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
# Try different databases
for db in gis sensor_data munbon postgres; do
  echo "Checking database: $db"
  docker exec postgres_timescale_postgis psql -U postgres -d $db -c "
    SELECT * FROM shape_file_uploads 
    WHERE metadata->>'waterDemandMethod' = 'RID-MS' 
       OR metadata->>'source' = 'rid-ms'
       OR file_name LIKE '%.zip'
       OR file_name LIKE '%.gpkg'
    ORDER BY created_at DESC
    LIMIT 20;" 2>/dev/null || echo "  No shape_file_uploads table in $db"
  echo ""
done
EOF

echo ""
echo "3. Checking for parcel data with RID-MS metadata..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
for db in gis sensor_data munbon postgres; do
  echo "Checking parcels in database: $db"
  
  # Check parcels table
  docker exec postgres_timescale_postgis psql -U postgres -d $db -c "
    SELECT COUNT(*) as total_parcels,
           COUNT(CASE WHEN properties->>'waterDemandMethod' = 'RID-MS' THEN 1 END) as rid_ms_parcels,
           MIN(created_at) as first_upload,
           MAX(created_at) as last_upload
    FROM parcels
    WHERE properties IS NOT NULL;" 2>/dev/null || echo "  No parcels table in $db"
  
  # Check parcel_simple table
  docker exec postgres_timescale_postgis psql -U postgres -d $db -c "
    SELECT upload_id, COUNT(*) as parcel_count,
           MIN(created_at) as upload_date
    FROM parcel_simple
    GROUP BY upload_id
    ORDER BY MIN(created_at) DESC
    LIMIT 10;" 2>/dev/null || echo "  No parcel_simple table in $db"
  
  echo ""
done
EOF

echo ""
echo "4. Checking S3 bucket for RID-MS uploads via EC2..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
# Check if AWS CLI is available
if command -v aws &> /dev/null; then
  echo "Checking S3 bucket munbon-gis-shape-files for recent uploads..."
  aws s3 ls s3://munbon-gis-shape-files/shape-files/ --recursive | grep -E "(\.zip|\.gpkg)" | sort -r | head -20
else
  echo "AWS CLI not available on EC2"
fi
EOF

echo ""
echo "5. Checking SQS queue for processed messages..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
# Check PM2 logs for processing evidence
echo "Recent shapefile processing logs from PM2:"
if [ -f ~/.pm2/logs/shapefile-queue-processor-out.log ]; then
  tail -50 ~/.pm2/logs/shapefile-queue-processor-out.log | grep -E "(RID-MS|rid-ms|processing|completed|failed|\.zip|\.gpkg)" | tail -20
else
  echo "No shapefile queue processor logs found"
fi

# Check general logs
echo ""
echo "Checking application logs for shapefile processing:"
find /home/ubuntu -name "*.log" -type f 2>/dev/null | while read log; do
  if grep -l -E "(shapefile|geopackage|RID-MS)" "$log" 2>/dev/null; then
    echo "Found in: $log"
    grep -E "(RID-MS|shapefile.*upload|processing.*complete|\.zip|\.gpkg)" "$log" | tail -10
  fi
done
EOF

echo ""
echo "6. Looking for specific upload ID: 62c52d9b-be71-4434-b9dd-189dfdab5941..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
UPLOAD_ID="62c52d9b-be71-4434-b9dd-189dfdab5941"
echo "Searching for upload ID: $UPLOAD_ID"

for db in gis sensor_data munbon postgres; do
  echo "In database: $db"
  
  # Check various tables
  docker exec postgres_timescale_postgis psql -U postgres -d $db -c "
    -- Check parcels
    SELECT 'parcels' as table_name, COUNT(*) as records 
    FROM parcels 
    WHERE properties->>'uploadId' = '$UPLOAD_ID'
    UNION ALL
    -- Check zones
    SELECT 'zones' as table_name, COUNT(*) as records 
    FROM zones 
    WHERE properties->>'uploadId' = '$UPLOAD_ID'
    UNION ALL
    -- Check uploads
    SELECT 'shape_file_uploads' as table_name, COUNT(*) as records 
    FROM shape_file_uploads 
    WHERE upload_id = '$UPLOAD_ID';" 2>/dev/null || true
done
EOF

echo ""
echo "=== Summary ==="
echo "Searched for RID-MS zipped file uploads in EC2 database"
echo "Checked for upload records, processing status, and unpacked data"