#!/bin/bash

# Test connectivity to new EC2 instance IP
# New IP: ${EC2_HOST:-43.208.201.191} (changed from ${EC2_HOST:-43.208.201.191})

echo "=== Testing EC2 Database Connectivity ==="
echo "New EC2 IP: ${EC2_HOST:-43.208.201.191}"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test PostgreSQL connection
echo "1. Testing PostgreSQL connection (munbon_dev)..."
PGPASSWORD=P@ssw0rd123! psql -h ${EC2_HOST:-43.208.201.191} -U postgres -d munbon_dev -c "SELECT version();" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ PostgreSQL munbon_dev connection successful${NC}"
else
    echo -e "${RED}✗ Failed to connect to PostgreSQL munbon_dev${NC}"
fi

# Test SCADA database connection
echo ""
echo "2. Testing SCADA database connection (db_scada)..."
PGPASSWORD=P@ssw0rd123! psql -h ${EC2_HOST:-43.208.201.191} -U postgres -d db_scada -c "SELECT COUNT(*) FROM tb_site;" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ SCADA database connection successful${NC}"
    # Show site count
    SITE_COUNT=$(PGPASSWORD=P@ssw0rd123! psql -h ${EC2_HOST:-43.208.201.191} -U postgres -d db_scada -t -c "SELECT COUNT(*) FROM tb_site WHERE stationcode IS NOT NULL;")
    echo -e "${YELLOW}  Control sites available: $SITE_COUNT${NC}"
else
    echo -e "${RED}✗ Failed to connect to SCADA database${NC}"
fi

# Test TimescaleDB connection
echo ""
echo "3. Testing TimescaleDB connection (sensor_data)..."
PGPASSWORD=P@ssw0rd123! psql -h ${EC2_HOST:-43.208.201.191} -U postgres -d sensor_data -c "SELECT version();" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ TimescaleDB sensor_data connection successful${NC}"
else
    echo -e "${RED}✗ Failed to connect to TimescaleDB sensor_data${NC}"
fi

# Test tb_gatelevel_command table
echo ""
echo "4. Testing gate command table..."
PGPASSWORD=P@ssw0rd123! psql -h ${EC2_HOST:-43.208.201.191} -U postgres -d db_scada -c "\d tb_gatelevel_command" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ tb_gatelevel_command table accessible${NC}"
    # Show recent commands
    echo -e "${YELLOW}Recent gate commands:${NC}"
    PGPASSWORD=P@ssw0rd123! psql -h ${EC2_HOST:-43.208.201.191} -U postgres -d db_scada -c "
    SELECT id, gate_name, gate_level, 
           startdatetime AT TIME ZONE 'Asia/Bangkok' as start_time,
           CASE completestatus 
             WHEN 0 THEN 'Pending'
             WHEN 1 THEN 'Complete'
           END as status
    FROM tb_gatelevel_command 
    ORDER BY id DESC 
    LIMIT 5;"
else
    echo -e "${RED}✗ tb_gatelevel_command table not accessible${NC}"
fi

# Test AWD schema
echo ""
echo "5. Testing AWD schema in munbon_dev..."
PGPASSWORD=P@ssw0rd123! psql -h ${EC2_HOST:-43.208.201.191} -U postgres -d munbon_dev -c "SELECT COUNT(*) FROM awd.awd_fields;" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ AWD schema accessible${NC}"
    FIELD_COUNT=$(PGPASSWORD=P@ssw0rd123! psql -h ${EC2_HOST:-43.208.201.191} -U postgres -d munbon_dev -t -c "SELECT COUNT(*) FROM awd.awd_fields;")
    echo -e "${YELLOW}  AWD fields configured: $FIELD_COUNT${NC}"
else
    echo -e "${RED}✗ AWD schema not accessible${NC}"
fi

echo ""
echo "=== Connection Test Summary ==="
echo "All critical databases should be accessible on the new IP."
echo "If any connections failed, please check:"
echo "1. Network connectivity to ${EC2_HOST:-43.208.201.191}"
echo "2. PostgreSQL service is running on the new EC2 instance"
echo "3. Firewall rules allow connections on port 5432"
echo "4. Database credentials are correct"