#!/bin/bash

echo "=== GIS Database Migration Status Check ==="
echo "Comparing Local (localhost:5434) vs EC2 (43.209.22.250:5432)"
echo ""

# Local database connection
LOCAL_DB="postgresql://postgres:postgres@localhost:5434/munbon_dev"

# EC2 database connection (you'll need to update the password)
EC2_DB="postgresql://postgres:P@ssw0rd123!@43.209.22.250:5432/munbon_dev"

echo "1. Checking local GIS tables and row counts:"
echo "----------------------------------------"
PGPASSWORD=postgres psql -h localhost -p 5434 -U postgres -d munbon_dev -c "
SELECT 
    schemaname,
    tablename,
    n_live_tup as row_count
FROM pg_stat_user_tables 
WHERE schemaname = 'gis'
ORDER BY n_live_tup DESC;"

echo ""
echo "2. Checking if GIS schema exists on EC2:"
echo "----------------------------------------"
# This will fail if password is wrong, but shows what needs to be checked
PGPASSWORD='P@ssw0rd123!' psql -h 43.209.22.250 -p 5432 -U postgres -d munbon_dev -c "\dn" 2>&1 | grep -E "gis|error"

echo ""
echo "3. Shape file uploads status:"
echo "----------------------------------------"
echo "Local:"
PGPASSWORD=postgres psql -h localhost -p 5434 -U postgres -d munbon_dev -t -c "
SELECT COUNT(*) || ' records in gis.shape_file_uploads' FROM gis.shape_file_uploads;"

echo ""
echo "To migrate the entire GIS schema to EC2, you would need to:"
echo "1. Ensure PostGIS extension is installed on EC2"
echo "2. Create the gis schema on EC2"
echo "3. Use pg_dump/pg_restore to migrate the schema and data"
echo ""
echo "Example migration command:"
echo "pg_dump -h localhost -p 5434 -U postgres -d munbon_dev -n gis -Fc > gis_schema_backup.dump"
echo "pg_restore -h 43.209.22.250 -p 5432 -U postgres -d munbon_dev gis_schema_backup.dump"