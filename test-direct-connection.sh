#!/bin/bash

echo "Testing direct connection to EC2 PostgreSQL..."
echo "Host: ${EC2_HOST:-43.208.201.191}"
echo "Port: 5432"
echo ""

# Test using psql if available
if command -v psql &> /dev/null; then
    echo "Using psql to test connection..."
    
    # Test munbon_dev
    echo "=== Testing munbon_dev database ==="
    PGPASSWORD='P@ssw0rd123!' psql -h ${EC2_HOST:-43.208.201.191} -p 5432 -U postgres -d munbon_dev -c "SELECT 'gis.canal_network' as table_name, COUNT(*) FROM gis.canal_network;"
    
    # Test sensor_data
    echo ""
    echo "=== Testing sensor_data database ==="
    PGPASSWORD='P@ssw0rd123!' psql -h ${EC2_HOST:-43.208.201.191} -p 5432 -U postgres -d sensor_data -c "SELECT 'public.sensor_readings' as table_name, COUNT(*) FROM public.sensor_readings;"
else
    echo "psql not found, using Python..."
    python3 check-ec2-status.py
fi

echo ""
echo "If you see data above, the migration was successful!"
echo ""
echo "In DBeaver, make sure to:"
echo "1. Disconnect and reconnect"
echo "2. Right-click on the database → Refresh"
echo "3. Navigate to the correct schema (gis, ros, or public)"
echo "4. Ensure you're connected to the right database (munbon_dev or sensor_data)"