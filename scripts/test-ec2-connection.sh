#!/bin/bash

# Test EC2 database connections with new IP
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# EC2 connection details
EC2_HOST="${EC2_HOST:-43.208.201.191}"
EC2_PORT="5432"
EC2_USER="postgres"
EC2_PASSWORD="P@ssw0rd123!"

echo -e "${BLUE}=== Testing EC2 Database Connections ===${NC}"
echo -e "${YELLOW}Target: $EC2_HOST:$EC2_PORT${NC}"
echo ""

# Test 1: Basic connectivity
echo -e "${BLUE}1. Testing basic connectivity...${NC}"
if nc -zv $EC2_HOST $EC2_PORT 2>&1 | grep -q "succeeded"; then
    echo -e "${GREEN}✓ Port $EC2_PORT is reachable${NC}"
else
    echo -e "${RED}✗ Cannot reach port $EC2_PORT${NC}"
    exit 1
fi

# Test 2: PostgreSQL connection
echo -e "\n${BLUE}2. Testing PostgreSQL connection...${NC}"
if PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -c "SELECT version();" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PostgreSQL connection successful${NC}"
    PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -c "SELECT version();" | grep "PostgreSQL"
else
    echo -e "${RED}✗ PostgreSQL connection failed${NC}"
    exit 1
fi

# Test 3: List databases
echo -e "\n${BLUE}3. Listing available databases...${NC}"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -c "\l" | grep -E "munbon_dev|sensor_data" || true

# Test 4: Check munbon_dev schemas
echo -e "\n${BLUE}4. Checking munbon_dev schemas...${NC}"
if PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d munbon_dev -c "\dn" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Connected to munbon_dev${NC}"
    PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d munbon_dev -c "\dn" | grep -E "auth|gis|ros|awd" || true
else
    echo -e "${YELLOW}⚠ munbon_dev database not found${NC}"
fi

# Test 5: Check sensor_data database
echo -e "\n${BLUE}5. Checking sensor_data database...${NC}"
if PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Connected to sensor_data${NC}"
    
    # Check for TimescaleDB
    echo -e "\n${BLUE}   Checking TimescaleDB extension...${NC}"
    PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';" | grep timescaledb || echo -e "${YELLOW}   ⚠ TimescaleDB not installed${NC}"
else
    echo -e "${YELLOW}⚠ sensor_data database not found${NC}"
fi

# Test 6: Check table counts
echo -e "\n${BLUE}6. Checking table counts...${NC}"
if [ -n "$(PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -l | grep munbon_dev)" ]; then
    echo -e "${BLUE}   munbon_dev tables:${NC}"
    PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d munbon_dev -c "
    SELECT n.nspname as schema, COUNT(*) as table_count 
    FROM pg_class c 
    JOIN pg_namespace n ON n.oid = c.relnamespace 
    WHERE c.relkind = 'r' 
    AND n.nspname NOT IN ('pg_catalog', 'information_schema')
    GROUP BY n.nspname 
    ORDER BY n.nspname;" 2>/dev/null || true
fi

if [ -n "$(PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -l | grep sensor_data)" ]; then
    echo -e "\n${BLUE}   sensor_data tables:${NC}"
    PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "
    SELECT COUNT(*) as table_count 
    FROM pg_tables 
    WHERE schemaname = 'public';" 2>/dev/null || true
fi

echo -e "\n${GREEN}=== Connection Test Complete ===${NC}"
echo -e "${YELLOW}Summary:${NC}"
echo "- Host: $EC2_HOST"
echo "- Port: $EC2_PORT"
echo "- User: $EC2_USER"
echo "- Databases: Check output above for available databases"