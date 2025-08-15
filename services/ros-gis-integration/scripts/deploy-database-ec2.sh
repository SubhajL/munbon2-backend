#!/bin/bash

# ROS/GIS Integration Service - EC2 Database Deployment Script
# This script sets up the database schema on the EC2 PostgreSQL instance

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# EC2 Database Configuration
DB_HOST="43.209.22.250"
DB_PORT="5432"
DB_NAME="munbon_dev"
DB_USER="postgres"
DB_PASSWORD="P@ssw0rd123!"
DB_SCHEMA="ros_gis"

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MIGRATIONS_DIR="$PROJECT_ROOT/migrations"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}ROS/GIS Integration Database Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Target Database:${NC}"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo "  Database: $DB_NAME"
echo "  Schema: $DB_SCHEMA"
echo ""

# Function to execute SQL
execute_sql() {
    local sql_file=$1
    local description=$2
    
    echo -e "${YELLOW}Executing: ${description}${NC}"
    PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -f "$sql_file" \
        -v ON_ERROR_STOP=1
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ ${description} completed successfully${NC}"
    else
        echo -e "${RED}✗ ${description} failed${NC}"
        exit 1
    fi
    echo ""
}

# Function to execute single SQL command
execute_sql_command() {
    local sql_command=$1
    local description=$2
    
    echo -e "${YELLOW}Executing: ${description}${NC}"
    PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -c "$sql_command" \
        -v ON_ERROR_STOP=1 > /dev/null
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ ${description} completed successfully${NC}"
    else
        echo -e "${RED}✗ ${description} failed${NC}"
        exit 1
    fi
}

# Check if psql is installed
if ! command -v psql &> /dev/null; then
    echo -e "${RED}Error: psql command not found. Please install PostgreSQL client.${NC}"
    echo "On macOS: brew install postgresql"
    echo "On Ubuntu: sudo apt-get install postgresql-client"
    exit 1
fi

# Test database connection
echo -e "${YELLOW}Testing database connection...${NC}"
PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -c "SELECT version();" > /dev/null 2>&1

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Failed to connect to database${NC}"
    echo "Please check your connection settings and ensure the EC2 instance is accessible."
    exit 1
fi
echo -e "${GREEN}✓ Database connection successful${NC}"
echo ""

# Check if PostGIS is installed
echo -e "${YELLOW}Checking PostGIS extension...${NC}"
POSTGIS_CHECK=$(PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -t -c "SELECT COUNT(*) FROM pg_extension WHERE extname = 'postgis';" | tr -d ' ')

if [ "$POSTGIS_CHECK" -eq "0" ]; then
    echo -e "${YELLOW}PostGIS not found. Installing...${NC}"
    execute_sql_command "CREATE EXTENSION IF NOT EXISTS postgis;" "Install PostGIS extension"
else
    echo -e "${GREEN}✓ PostGIS extension already installed${NC}"
fi
echo ""

# Create schema if not exists
echo -e "${YELLOW}Creating schema if not exists...${NC}"
execute_sql_command "CREATE SCHEMA IF NOT EXISTS ${DB_SCHEMA};" "Create ros_gis schema"
echo ""

# Check for existing tables
echo -e "${YELLOW}Checking for existing tables...${NC}"
EXISTING_TABLES=$(PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '${DB_SCHEMA}';" | tr -d ' ')

if [ "$EXISTING_TABLES" -gt "0" ]; then
    echo -e "${YELLOW}Found ${EXISTING_TABLES} existing tables in ${DB_SCHEMA} schema${NC}"
    echo -e "${YELLOW}Do you want to continue? This will update existing tables.${NC}"
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Deployment cancelled${NC}"
        exit 0
    fi
fi
echo ""

# Execute migrations
echo -e "${GREEN}Executing database migrations...${NC}"
echo ""

# Migration 1: Core tables
if [ -f "$MIGRATIONS_DIR/001_create_tables.sql" ]; then
    execute_sql "$MIGRATIONS_DIR/001_create_tables.sql" "Migration 001: Core tables and schema"
else
    echo -e "${RED}✗ Migration file 001_create_tables.sql not found${NC}"
    exit 1
fi

# Migration 2: Daily demands tables
if [ -f "$MIGRATIONS_DIR/002_add_daily_demands_tables.sql" ]; then
    execute_sql "$MIGRATIONS_DIR/002_add_daily_demands_tables.sql" "Migration 002: Daily demands and plot tables"
else
    echo -e "${RED}✗ Migration file 002_add_daily_demands_tables.sql not found${NC}"
    exit 1
fi

# Verify deployment
echo -e "${GREEN}Verifying deployment...${NC}"
echo ""

# Count tables
TABLE_COUNT=$(PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '${DB_SCHEMA}' AND table_type = 'BASE TABLE';" | tr -d ' ')

VIEW_COUNT=$(PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '${DB_SCHEMA}' AND table_type = 'VIEW';" | tr -d ' ')

echo -e "${GREEN}Deployment Summary:${NC}"
echo "  Tables created: $TABLE_COUNT"
echo "  Views created: $VIEW_COUNT"
echo ""

# List all tables
echo -e "${GREEN}Tables in ${DB_SCHEMA} schema:${NC}"
PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -c "SELECT table_name, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
         FROM pg_tables 
         WHERE schemaname = '${DB_SCHEMA}' 
         ORDER BY table_name;"

echo ""

# Create connection test script
echo -e "${GREEN}Creating connection test script...${NC}"
cat > "$PROJECT_ROOT/scripts/test-ec2-connection.py" << 'EOF'
#!/usr/bin/env python3
"""Test EC2 database connection"""

import asyncio
import asyncpg
import os

async def test_connection():
    try:
        # Connection parameters
        conn = await asyncpg.connect(
            host='43.209.22.250',
            port=5432,
            user='postgres',
            password='P@ssw0rd123!',
            database='munbon_dev'
        )
        
        # Test query
        version = await conn.fetchval('SELECT version()')
        print(f"✓ Connected to PostgreSQL: {version}")
        
        # Check PostGIS
        postgis = await conn.fetchval("SELECT PostGIS_Version()")
        print(f"✓ PostGIS version: {postgis}")
        
        # Check schema
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'ros_gis' 
            ORDER BY table_name
        """)
        
        print(f"\n✓ Found {len(tables)} tables in ros_gis schema:")
        for table in tables:
            print(f"  - {table['table_name']}")
        
        await conn.close()
        print("\n✓ Connection test successful!")
        
    except Exception as e:
        print(f"✗ Connection test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(test_connection())
EOF

chmod +x "$PROJECT_ROOT/scripts/test-ec2-connection.py"
echo -e "${GREEN}✓ Created test-ec2-connection.py${NC}"
echo ""

# Create environment file for EC2 deployment
echo -e "${GREEN}Creating EC2 environment file...${NC}"
cat > "$PROJECT_ROOT/.env.ec2-deploy" << EOF
# ROS/GIS Integration Service - EC2 Deployment Configuration
# Generated on $(date)

# Database Configuration
POSTGRES_URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}

# Redis Configuration (assumes Redis on same EC2 or separate)
REDIS_URL=redis://${DB_HOST}:6379/2

# Service Configuration
ENVIRONMENT=production
LOG_LEVEL=INFO
USE_MOCK_SERVER=false

# External Services (update these with actual EC2 service URLs)
FLOW_MONITORING_URL=http://${DB_HOST}:3011
SCHEDULER_URL=http://${DB_HOST}:3021
ROS_SERVICE_URL=http://${DB_HOST}:3047
GIS_SERVICE_URL=http://${DB_HOST}:3007

# Flow Monitoring Network File (update path as needed)
FLOW_MONITORING_NETWORK_FILE=/data/munbon_network_final.json

# Demand Calculation
DEMAND_COMBINATION_STRATEGY=aquacrop_priority
EOF

echo -e "${GREEN}✓ Created .env.ec2-deploy${NC}"
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Database deployment completed!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Test the connection: python3 scripts/test-ec2-connection.py"
echo "2. Update .env.ec2-deploy with correct service URLs"
echo "3. Deploy the service to EC2"
echo ""
echo "To run the service with EC2 database:"
echo "  export $(cat .env.ec2-deploy | xargs)"
echo "  python src/main.py"
echo ""