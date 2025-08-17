#!/bin/bash

# Direct connection from local to EC2 PostgreSQL
export PGPASSWORD='P@ssw0rd123!'

echo "=== Direct query from local machine to EC2 PostgreSQL ==="
echo "Host: ${EC2_HOST:-43.208.201.191}"
echo "Port: 5432"
echo "Database: sensor_data"
echo ""

# Check if psql is available locally
if ! command -v psql &> /dev/null; then
    echo "psql not found locally. Using Python instead..."
    python3 << 'EOF'
import psycopg2

try:
    conn = psycopg2.connect(
        host='${EC2_HOST:-43.208.201.191}',
        port=5432,
        user='postgres',
        password='P@ssw0rd123!',
        database='sensor_data'
    )
    cur = conn.cursor()
    
    print("\nChecking ALL tables in public schema:")
    tables = ['moisture_readings', 'sensor_calibrations', 'sensor_location_history', 
              'sensor_readings', 'sensor_registry', 'water_level_readings']
    
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM public.{table}")
        count = cur.fetchone()[0]
        print(f"public.{table}: {count} rows")
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
EOF
else
    psql -h ${EC2_HOST:-43.208.201.191} -p 5432 -U postgres -d sensor_data << 'SQL'
SELECT 'public.' || tablename as table_name, 
       (xpath('/row/count/text()', 
              query_to_xml(format('SELECT COUNT(*) FROM %I.%I', 'public', tablename), 
                          true, true, '')))[1]::text::int as row_count
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY tablename;
SQL
fi