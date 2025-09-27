#!/bin/bash

EC2_HOST="43.208.201.191"

echo "=== Querying Moisture Data Directly ==="
echo ""

# Use PGPASSWORD to connect directly to PostgreSQL from local machine if port is exposed
export PGPASSWORD="postgres"

echo "1. Trying to connect to PostgreSQL directly on port 5432:"
psql -h ${EC2_HOST} -p 5432 -U postgres -d sensor_data -c "SELECT COUNT(*) FROM moisture_readings;" 2>&1 || echo "Direct connection failed"

echo ""
echo "2. Checking available API documentation:"
curl -s http://${EC2_HOST}:8080/ | jq '.'

echo ""
echo "3. Looking for moisture query endpoint:"
# The service description shows it's only an ingestion endpoint, not a query endpoint
echo "Based on the service info, this appears to be an ingestion-only service."
echo "The moisture data is being saved to the database at ${EC2_HOST}:5432"
echo ""
echo "To check if moisture data is coming in, we would need to:"
echo "- Access the PostgreSQL database directly (requires SSH or exposed port)"
echo "- Check PM2 logs on the EC2 instance"
echo "- Or set up a separate query API endpoint"

echo ""
echo "4. Let's check if there's a query service on another port:"
for port in 3000 3001 3002 8081 8082; do
    echo -n "Checking port $port: "
    nc -zv ${EC2_HOST} $port 2>&1 | grep -E "(succeeded|Connected)" || echo "Not available"
done