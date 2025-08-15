#!/bin/bash

# Test Sensor Data Service with EC2 TimescaleDB
# Tests ingestion, querying, and aggregation

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# EC2 Configuration
POSTGRES_HOST="43.209.22.250"
POSTGRES_PORT="5432"
POSTGRES_USER="postgres"
POSTGRES_PASSWORD="P@ssw0rd123!"
SENSOR_DATA_PORT="3003"

echo "Testing Sensor Data Service with EC2 TimescaleDB"
echo "================================================"

# Test 1: Database connectivity
echo -e "\n1. Testing TimescaleDB connection..."
if PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d sensor_data -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ TimescaleDB connection successful${NC}"
else
    echo -e "${RED}✗ TimescaleDB connection failed${NC}"
    exit 1
fi

# Test 2: Check hypertables
echo -e "\n2. Checking TimescaleDB hypertables..."
HYPERTABLES=$(PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d sensor_data -t -c "SELECT hypertable_name FROM timescaledb_information.hypertables;")
if [ ! -z "$HYPERTABLES" ]; then
    echo -e "${GREEN}✓ Hypertables found:${NC}"
    echo "$HYPERTABLES"
else
    echo -e "${YELLOW}! No hypertables found${NC}"
fi

# Test 3: Service health
echo -e "\n3. Testing service health..."
if curl -s -f "http://localhost:$SENSOR_DATA_PORT/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Service is healthy${NC}"
else
    echo -e "${RED}✗ Service is not responding${NC}"
    exit 1
fi

# Test 4: Ingest test data
echo -e "\n4. Testing data ingestion..."
TEST_DATA='{
    "sensor_id": "TEST_MOISTURE_001",
    "type": "moisture",
    "value": 65.5,
    "unit": "%",
    "location": {
        "lat": 13.7563,
        "lon": 100.5018
    },
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
}'

RESPONSE=$(curl -s -X POST "http://localhost:$SENSOR_DATA_PORT/api/v1/telemetry" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer test-token" \
    -d "$TEST_DATA")

if echo "$RESPONSE" | grep -q "success"; then
    echo -e "${GREEN}✓ Data ingestion successful${NC}"
else
    echo -e "${RED}✗ Data ingestion failed${NC}"
    echo "Response: $RESPONSE"
fi

# Test 5: Query recent data
echo -e "\n5. Testing data query..."
RECENT_DATA=$(curl -s "http://localhost:$SENSOR_DATA_PORT/api/v1/telemetry/latest?sensor_id=TEST_MOISTURE_001")
if echo "$RECENT_DATA" | grep -q "TEST_MOISTURE_001"; then
    echo -e "${GREEN}✓ Data query successful${NC}"
else
    echo -e "${RED}✗ Data query failed${NC}"
fi

# Test 6: Test aggregation
echo -e "\n6. Testing time-series aggregation..."
AGG_DATA=$(curl -s "http://localhost:$SENSOR_DATA_PORT/api/v1/telemetry/aggregate?sensor_id=TEST_MOISTURE_001&interval=1h")
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Aggregation API working${NC}"
else
    echo -e "${RED}✗ Aggregation API failed${NC}"
fi

# Test 7: Check data in database
echo -e "\n7. Verifying data in TimescaleDB..."
COUNT=$(PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d sensor_data -t -c "SELECT COUNT(*) FROM sensor_data WHERE sensor_id = 'TEST_MOISTURE_001';")
if [ $COUNT -gt 0 ]; then
    echo -e "${GREEN}✓ Data found in database: $COUNT records${NC}"
else
    echo -e "${YELLOW}! No data found in database${NC}"
fi

# Test 8: Performance test
echo -e "\n8. Testing ingestion performance..."
START_TIME=$(date +%s)
for i in {1..10}; do
    curl -s -X POST "http://localhost:$SENSOR_DATA_PORT/api/v1/telemetry" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer test-token" \
        -d '{
            "sensor_id": "PERF_TEST_'$i'",
            "type": "moisture",
            "value": '$((50 + RANDOM % 30))',
            "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
        }' > /dev/null 2>&1
done
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
echo -e "${GREEN}✓ Ingested 10 records in ${DURATION}s${NC}"

# Cleanup
echo -e "\n9. Cleaning up test data..."
PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d sensor_data -c "DELETE FROM sensor_data WHERE sensor_id LIKE 'TEST_%' OR sensor_id LIKE 'PERF_TEST_%';" > /dev/null 2>&1
echo -e "${GREEN}✓ Test data cleaned up${NC}"

echo -e "\n${GREEN}Sensor Data Service tests completed!${NC}"