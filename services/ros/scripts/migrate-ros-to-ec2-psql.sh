#!/bin/bash

# Migrate ROS schema and tables using psql COPY commands
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Local source
export PGPASSWORD_LOCAL="postgres"
LOCAL_HOST="localhost"
LOCAL_PORT="5434"
LOCAL_DB="munbon_dev"
LOCAL_USER="postgres"

# EC2 target
export PGPASSWORD_EC2="P@ssw0rd123!"
EC2_HOST="43.209.22.250"
EC2_PORT="5432"
EC2_DB="munbon_dev"
EC2_USER="postgres"

echo -e "${BLUE}=== MIGRATE ROS SCHEMA TO EC2 (PSQL Method) ===${NC}"
echo -e "${YELLOW}Source: $LOCAL_HOST:$LOCAL_PORT/$LOCAL_DB${NC}"
echo -e "${YELLOW}Target: $EC2_HOST:$EC2_PORT/$EC2_DB${NC}"
echo ""

# Step 1: Create ROS schema and tables on EC2
echo -e "${BLUE}Step 1: Creating ROS schema and tables on EC2...${NC}"
PGPASSWORD=$PGPASSWORD_EC2 psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB << 'EOF'
-- Create schema
CREATE SCHEMA IF NOT EXISTS ros;

-- Set search path
SET search_path TO ros, public;

-- Create trigger function
CREATE OR REPLACE FUNCTION ros.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Drop existing tables if any (to ensure clean migration)
DROP TABLE IF EXISTS ros.plot_water_demand_weekly CASCADE;
DROP TABLE IF EXISTS ros.plot_water_demand_seasonal CASCADE;
DROP TABLE IF EXISTS ros.plot_crop_schedule CASCADE;
DROP TABLE IF EXISTS ros.plots CASCADE;
DROP TABLE IF EXISTS ros.water_demand_calculations CASCADE;
EOF

# Step 2: Copy table structures
echo -e "\n${BLUE}Step 2: Copying table structures...${NC}"
PGPASSWORD=$PGPASSWORD_LOCAL psql -h $LOCAL_HOST -p $LOCAL_PORT -U $LOCAL_USER -d $LOCAL_DB -c "\
SELECT string_agg(
    'CREATE TABLE ros.' || table_name || ' (LIKE ros.' || table_name || ' INCLUDING ALL);',
    E'\n'
)
FROM information_schema.tables 
WHERE table_schema = 'ros' 
  AND table_type = 'BASE TABLE';" -t -A | \
PGPASSWORD=$PGPASSWORD_EC2 psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB

# Step 3: Export and import each table's data
echo -e "\n${BLUE}Step 3: Migrating table data...${NC}"

# Create output directory
mkdir -p /tmp/ros_migration

# Function to migrate a table
migrate_table() {
    local table_name=$1
    echo -e "${YELLOW}Migrating $table_name...${NC}"
    
    # Export to CSV
    PGPASSWORD=$PGPASSWORD_LOCAL psql -h $LOCAL_HOST -p $LOCAL_PORT -U $LOCAL_USER -d $LOCAL_DB -c "\
    COPY ros.$table_name TO '/tmp/ros_migration/${table_name}.csv' WITH CSV HEADER;"
    
    # Import from CSV
    PGPASSWORD=$PGPASSWORD_EC2 psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -c "\
    COPY ros.$table_name FROM '/tmp/ros_migration/${table_name}.csv' WITH CSV HEADER;"
    
    # Get count
    local count=$(PGPASSWORD=$PGPASSWORD_EC2 psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -t -c "SELECT COUNT(*) FROM ros.$table_name;")
    echo -e "${GREEN}✓ Migrated $count records${NC}"
}

# Get list of tables
TABLES=$(PGPASSWORD=$PGPASSWORD_LOCAL psql -h $LOCAL_HOST -p $LOCAL_PORT -U $LOCAL_USER -d $LOCAL_DB -t -c "
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'ros' 
  AND table_type = 'BASE TABLE'
ORDER BY table_name;")

# Migrate each table
for table in $TABLES; do
    if [ ! -z "$table" ]; then
        migrate_table "$table"
    fi
done

# Step 4: Recreate constraints and indexes
echo -e "\n${BLUE}Step 4: Recreating constraints and indexes...${NC}"
PGPASSWORD=$PGPASSWORD_LOCAL psql -h $LOCAL_HOST -p $LOCAL_PORT -U $LOCAL_USER -d $LOCAL_DB << 'EOF' | \
PGPASSWORD=$PGPASSWORD_EC2 psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB
-- Get all foreign key constraints
SELECT 
    'ALTER TABLE ros.' || tc.table_name || 
    ' ADD CONSTRAINT ' || tc.constraint_name || 
    ' FOREIGN KEY (' || kcu.column_name || ')' ||
    ' REFERENCES ros.' || ccu.table_name || '(' || ccu.column_name || ');'
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu 
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY' 
    AND tc.table_schema = 'ros';
EOF

# Step 5: Migrate GIS water demand table
echo -e "\n${BLUE}Step 5: Migrating GIS water demand table...${NC}"
PGPASSWORD=$PGPASSWORD_EC2 psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -c "CREATE SCHEMA IF NOT EXISTS gis;"

# Check if table exists in GIS schema
if PGPASSWORD=$PGPASSWORD_LOCAL psql -h $LOCAL_HOST -p $LOCAL_PORT -U $LOCAL_USER -d $LOCAL_DB -t -c "SELECT 1 FROM information_schema.tables WHERE table_schema='gis' AND table_name='ros_water_demands';" | grep -q 1; then
    echo "Migrating gis.ros_water_demands..."
    
    # Create table structure
    PGPASSWORD=$PGPASSWORD_LOCAL psql -h $LOCAL_HOST -p $LOCAL_PORT -U $LOCAL_USER -d $LOCAL_DB -c "\
    SELECT 'CREATE TABLE gis.ros_water_demands (LIKE gis.ros_water_demands INCLUDING ALL);'" -t -A | \
    PGPASSWORD=$PGPASSWORD_EC2 psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB
    
    # Copy data
    PGPASSWORD=$PGPASSWORD_LOCAL psql -h $LOCAL_HOST -p $LOCAL_PORT -U $LOCAL_USER -d $LOCAL_DB -c "\
    COPY gis.ros_water_demands TO '/tmp/ros_migration/gis_ros_water_demands.csv' WITH CSV HEADER;"
    
    PGPASSWORD=$PGPASSWORD_EC2 psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -c "\
    COPY gis.ros_water_demands FROM '/tmp/ros_migration/gis_ros_water_demands.csv' WITH CSV HEADER;"
fi

# Step 6: Verify migration
echo -e "\n${BLUE}Step 6: Verifying migration...${NC}"
echo -e "${YELLOW}Record counts on EC2:${NC}"
PGPASSWORD=$PGPASSWORD_EC2 psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB << EOF
SELECT 
    n.nspname as schema,
    c.relname as table_name,
    pg_size_pretty(pg_total_relation_size(c.oid)) as size,
    (xpath('/row/cnt/text()', xml_count))[1]::text::int as row_count
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
CROSS JOIN LATERAL (
    SELECT query_to_xml(format('SELECT COUNT(*) as cnt FROM %I.%I', n.nspname, c.relname), false, true, '') as xml_count
) AS x
WHERE n.nspname IN ('ros', 'gis')
  AND c.relkind = 'r'
  AND c.relname IN ('plot_water_demand_weekly', 'plot_water_demand_seasonal', 
                    'water_demand_calculations', 'plots', 'plot_crop_schedule', 
                    'ros_water_demands')
ORDER BY n.nspname, c.relname;
EOF

# Clean up
rm -rf /tmp/ros_migration

echo -e "\n${GREEN}✅ Migration complete!${NC}"
echo -e "${BLUE}EC2 Database Connection:${NC}"
echo -e "psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB"
echo -e "Password: $PGPASSWORD_EC2"