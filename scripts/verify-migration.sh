#!/bin/bash

# Verify migration from local to EC2
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=== MIGRATION VERIFICATION ===${NC}"

# Local database info
echo -e "\n${YELLOW}LOCAL DATABASES:${NC}"

# Check munbon_dev on local
echo -e "\n${BLUE}munbon_dev (local port 5434):${NC}"
docker exec munbon-postgres psql -U postgres -d munbon_dev -c "
SELECT n.nspname as schema_name, COUNT(c.*) as table_count
FROM pg_namespace n
LEFT JOIN pg_class c ON n.oid = c.relnamespace AND c.relkind = 'r'
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
GROUP BY n.nspname
ORDER BY n.nspname;"

# Check specific tables in gis schema
echo -e "\n${BLUE}GIS schema tables (local):${NC}"
docker exec munbon-postgres psql -U postgres -d munbon_dev -c "
SELECT tablename, 
       (SELECT COUNT(*) FROM gis.agricultural_plots) as agricultural_plots_count,
       (SELECT COUNT(*) FROM gis.canal_network) as canal_network_count,
       (SELECT COUNT(*) FROM gis.control_structures) as control_structures_count
FROM pg_tables 
WHERE schemaname = 'gis' 
LIMIT 1;"

# Check sensor_data on local
echo -e "\n${BLUE}sensor_data (local port 5433):${NC}"
docker exec munbon-timescaledb psql -U postgres -d sensor_data -c "
SELECT n.nspname as schema_name, COUNT(c.*) as table_count
FROM pg_namespace n
LEFT JOIN pg_class c ON n.oid = c.relnamespace AND c.relkind = 'r'
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast', '_timescaledb_catalog', '_timescaledb_internal', '_timescaledb_config', '_timescaledb_cache')
GROUP BY n.nspname
ORDER BY n.nspname;"

echo -e "\n${GREEN}=== Local database verification complete ===${NC}"
echo -e "\n${YELLOW}To check EC2 databases, use DBeaver with:${NC}"
echo "Host: ${EC2_HOST:-43.208.201.191}"
echo "Port: 5432" 
echo "Username: postgres"
echo "Password: P@ssw0rd123!"
echo "Databases: munbon_dev, sensor_data"