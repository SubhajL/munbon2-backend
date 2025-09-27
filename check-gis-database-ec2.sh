#!/bin/bash

echo "=== Checking GIS Databases for RID-MS Upload Data ==="
echo "Date: $(date)"
echo ""

# Configuration
EC2_IP="43.208.201.191"
SSH_KEY="~/dev/th-lab01.pem"

echo "1. Checking gis_db database for tables..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
echo "Database: gis_db"
docker exec postgres_timescale_postgis psql -U postgres -d gis_db -c "
SELECT table_schema, table_name 
FROM information_schema.tables 
WHERE table_schema NOT IN ('pg_catalog', 'information_schema', '_timescaledb_internal')
ORDER BY table_schema, table_name;" 2>/dev/null || echo "Cannot access gis_db"
EOF

echo ""
echo "2. Checking gisdb database for tables..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
echo "Database: gisdb"
docker exec postgres_timescale_postgis psql -U postgres -d gisdb -c "
SELECT table_schema, table_name 
FROM information_schema.tables 
WHERE table_schema NOT IN ('pg_catalog', 'information_schema', '_timescaledb_internal')
ORDER BY table_schema, table_name;" 2>/dev/null || echo "Cannot access gisdb"
EOF

echo ""
echo "3. Checking for shape_file_uploads in gis_db..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d gis_db -c "
SELECT * FROM shape_file_uploads ORDER BY created_at DESC LIMIT 10;" 2>/dev/null || echo "No shape_file_uploads table in gis_db"

docker exec postgres_timescale_postgis psql -U postgres -d gis_db -c "
SELECT * FROM public.shape_file_uploads ORDER BY created_at DESC LIMIT 10;" 2>/dev/null || echo "No public.shape_file_uploads table"

docker exec postgres_timescale_postgis psql -U postgres -d gis_db -c "
SELECT * FROM gis.shape_file_uploads ORDER BY created_at DESC LIMIT 10;" 2>/dev/null || echo "No gis.shape_file_uploads table"
EOF

echo ""
echo "4. Checking for parcels in gis_db..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d gis_db -c "
SELECT COUNT(*) as total_parcels FROM parcels;" 2>/dev/null || echo "No parcels table in gis_db"

docker exec postgres_timescale_postgis psql -U postgres -d gis_db -c "
SELECT COUNT(*) as total_parcels FROM public.parcels;" 2>/dev/null || echo "No public.parcels table"

docker exec postgres_timescale_postgis psql -U postgres -d gis_db -c "
SELECT COUNT(*) as total_parcels FROM gis.parcels;" 2>/dev/null || echo "No gis.parcels table"
EOF

echo ""
echo "5. Checking gisdb database similarly..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
# Check for uploads
docker exec postgres_timescale_postgis psql -U postgres -d gisdb -c "
SELECT * FROM shape_file_uploads 
WHERE file_name LIKE '%.zip' OR file_name LIKE '%.gpkg'
ORDER BY created_at DESC LIMIT 10;" 2>/dev/null || echo "No shape_file_uploads in gisdb"

# Check for parcels
docker exec postgres_timescale_postgis psql -U postgres -d gisdb -c "
SELECT COUNT(*) as count, 
       MIN(created_at) as first_created, 
       MAX(created_at) as last_created 
FROM parcels;" 2>/dev/null || echo "No parcels table in gisdb"
EOF

echo ""
echo "6. Checking postgres database gis schema..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d postgres -c "
\dt gis.*" 2>/dev/null || echo "No gis schema tables"

docker exec postgres_timescale_postgis psql -U postgres -d postgres -c "
SELECT * FROM gis.zone LIMIT 10;" 2>/dev/null || echo "Cannot read gis.zone table"
EOF

echo ""
echo "7. Looking for any evidence of shapefile processing..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
# Check all PM2 logs
echo "Checking all PM2 logs for shapefile/geopackage processing..."
cd ~/.pm2/logs 2>/dev/null && grep -l -E "(shapefile|geopackage|gpkg|RID-MS)" *.log 2>/dev/null | while read logfile; do
  echo "Found in $logfile:"
  grep -E "(shapefile|geopackage|gpkg|RID-MS|\.zip.*process|upload.*complete)" "$logfile" | tail -5
done || echo "No PM2 logs with shapefile references"

# Check for GIS service
pm2 list | grep -i gis || echo "No GIS service in PM2"
EOF

echo ""
echo "=== Summary ==="
echo "Checked all GIS-related databases for RID-MS uploads and processing evidence"