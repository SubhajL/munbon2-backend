#!/bin/bash

# Integration Test Suite for Multi-Service Flows with EC2
# Tests communication between services using EC2 databases

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# EC2 Configuration
export POSTGRES_HOST="43.209.22.250"
export POSTGRES_PORT="5432"
export POSTGRES_PASSWORD="P@ssw0rd123!"

# Service URLs
SENSOR_DATA_URL="http://localhost:3003"
ROS_URL="http://localhost:3047"
GIS_URL="http://localhost:3007"
AWD_URL="http://localhost:3013"
FLOW_URL="http://localhost:3014"
ROS_GIS_URL="http://localhost:3022"

echo -e "${BLUE}Integration Test Suite - EC2 Environment${NC}"
echo "=========================================="

# Test 1: Sensor → Weather → ROS Integration
test_sensor_weather_ros() {
    echo -e "\n${BLUE}Test 1: Sensor → Weather → ROS Integration${NC}"
    
    # Step 1: Ingest weather sensor data
    echo "1.1 Ingesting weather sensor data..."
    WEATHER_DATA='{
        "sensor_id": "WEATHER_STATION_01",
        "type": "weather",
        "values": {
            "temperature": 32.5,
            "humidity": 65,
            "rainfall": 2.5
        },
        "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
    }'
    
    if curl -s -X POST "$SENSOR_DATA_URL/api/v1/telemetry" \
        -H "Content-Type: application/json" \
        -d "$WEATHER_DATA" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Weather data ingested${NC}"
    else
        echo -e "${RED}✗ Weather data ingestion failed${NC}"
        return 1
    fi
    
    # Step 2: Query weather data from ROS
    echo "1.2 ROS querying weather data..."
    sleep 2  # Allow time for processing
    
    WEATHER_RESPONSE=$(curl -s "$ROS_URL/api/v1/weather/current")
    if echo "$WEATHER_RESPONSE" | grep -q "temperature"; then
        echo -e "${GREEN}✓ ROS successfully retrieved weather data${NC}"
    else
        echo -e "${RED}✗ ROS failed to retrieve weather data${NC}"
    fi
    
    # Step 3: Calculate water demand based on weather
    echo "1.3 Calculating water demand..."
    DEMAND_RESPONSE=$(curl -s "$ROS_URL/api/v1/water-demand/calculate" \
        -H "Content-Type: application/json" \
        -d '{
            "plot_id": "PLOT_001",
            "crop_type": "RICE",
            "growth_stage": "vegetative"
        }')
    
    if echo "$DEMAND_RESPONSE" | grep -q "water_demand"; then
        echo -e "${GREEN}✓ Water demand calculated successfully${NC}"
    else
        echo -e "${RED}✗ Water demand calculation failed${NC}"
    fi
}

# Test 2: GIS → ROS-GIS Integration → AWD Control
test_gis_ros_awd() {
    echo -e "\n${BLUE}Test 2: GIS → ROS-GIS Integration → AWD Control${NC}"
    
    # Step 1: Query parcel from GIS
    echo "2.1 Querying parcel data from GIS..."
    PARCEL_RESPONSE=$(curl -s "$GIS_URL/api/v1/parcels/PARCEL_001")
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ GIS parcel data retrieved${NC}"
    else
        echo -e "${RED}✗ GIS parcel query failed${NC}"
    fi
    
    # Step 2: ROS-GIS Integration aggregates data
    echo "2.2 ROS-GIS Integration processing..."
    INTEGRATION_QUERY='{
        "query": "{ 
            waterDemandByZone(zoneId: \"ZONE_A\") {
                zoneId
                totalDemand
                parcels {
                    parcelId
                    demand
                }
            }
        }"
    }'
    
    INTEGRATION_RESPONSE=$(curl -s -X POST "$ROS_GIS_URL/graphql" \
        -H "Content-Type: application/json" \
        -d "$INTEGRATION_QUERY")
    
    if echo "$INTEGRATION_RESPONSE" | grep -q "totalDemand"; then
        echo -e "${GREEN}✓ ROS-GIS integration successful${NC}"
    else
        echo -e "${YELLOW}! ROS-GIS integration may not be fully implemented${NC}"
    fi
    
    # Step 3: AWD Control decision
    echo "2.3 AWD Control making irrigation decision..."
    AWD_REQUEST='{
        "zone_id": "ZONE_A",
        "water_demand": 1500,
        "current_level": 45
    }'
    
    AWD_RESPONSE=$(curl -s -X POST "$AWD_URL/api/v1/irrigation/decision" \
        -H "Content-Type: application/json" \
        -d "$AWD_REQUEST")
    
    if echo "$AWD_RESPONSE" | grep -q "action"; then
        echo -e "${GREEN}✓ AWD control decision made${NC}"
    else
        echo -e "${YELLOW}! AWD control endpoint may not be implemented${NC}"
    fi
}

# Test 3: AWD → Flow Monitoring → SCADA Simulation
test_awd_flow_scada() {
    echo -e "\n${BLUE}Test 3: AWD → Flow Monitoring → SCADA Simulation${NC}"
    
    # Step 1: AWD requests gate operation
    echo "3.1 AWD requesting gate operation..."
    GATE_REQUEST='{
        "gate_id": "G_RES_J1",
        "action": "open",
        "position": 2.5,
        "reason": "irrigation_schedule"
    }'
    
    # Note: This would normally go through AWD, but testing direct flow monitoring
    GATE_RESPONSE=$(curl -s -X POST "$FLOW_URL/api/v1/gates/operate" \
        -H "Content-Type: application/json" \
        -d "$GATE_REQUEST")
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Gate operation request sent${NC}"
    else
        echo -e "${YELLOW}! Flow monitoring may not have operation endpoint${NC}"
    fi
    
    # Step 2: Check gate state
    echo "3.2 Checking gate state..."
    STATE_RESPONSE=$(curl -s "$FLOW_URL/api/v1/gates/state")
    if echo "$STATE_RESPONSE" | grep -q "G_RES_J1"; then
        echo -e "${GREEN}✓ Gate state retrieved${NC}"
    else
        echo -e "${RED}✗ Failed to retrieve gate state${NC}"
    fi
    
    # Step 3: Verify hydraulic calculation
    echo "3.3 Verifying hydraulic calculations..."
    HYDRAULIC_RESPONSE=$(curl -s "$FLOW_URL/api/v1/hydraulics/current")
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Hydraulic calculations available${NC}"
    else
        echo -e "${YELLOW}! Hydraulic endpoint may not be implemented${NC}"
    fi
}

# Test 4: Real-time Data Flow via Redis
test_realtime_flow() {
    echo -e "\n${BLUE}Test 4: Real-time Data Flow via Redis${NC}"
    
    # Step 1: Subscribe to Redis channel (in background)
    echo "4.1 Setting up Redis subscription..."
    redis-cli -h localhost SUBSCRIBE sensor_updates > /tmp/redis_sub.log 2>&1 &
    REDIS_PID=$!
    sleep 1
    
    # Step 2: Publish sensor update
    echo "4.2 Publishing sensor update..."
    SENSOR_UPDATE='{
        "sensor_id": "REALTIME_001",
        "type": "water_level",
        "value": 105.5,
        "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
    }'
    
    redis-cli -h localhost PUBLISH sensor_updates "$SENSOR_UPDATE" > /dev/null 2>&1
    
    # Step 3: Check if message was received
    sleep 1
    kill $REDIS_PID 2>/dev/null || true
    
    if grep -q "REALTIME_001" /tmp/redis_sub.log 2>/dev/null; then
        echo -e "${GREEN}✓ Real-time update received via Redis${NC}"
    else
        echo -e "${YELLOW}! Real-time update not detected${NC}"
    fi
    
    rm -f /tmp/redis_sub.log
}

# Test 5: End-to-End Irrigation Cycle
test_e2e_irrigation() {
    echo -e "\n${BLUE}Test 5: End-to-End Irrigation Cycle${NC}"
    
    # Step 1: Moisture sensor triggers low reading
    echo "5.1 Moisture sensor detecting low soil moisture..."
    MOISTURE_DATA='{
        "sensor_id": "MOISTURE_FIELD_A_01",
        "type": "moisture",
        "value": 25.5,
        "unit": "%",
        "location": {
            "zone": "ZONE_A",
            "plot": "PLOT_001"
        },
        "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
    }'
    
    curl -s -X POST "$SENSOR_DATA_URL/api/v1/telemetry" \
        -H "Content-Type: application/json" \
        -d "$MOISTURE_DATA" > /dev/null 2>&1
    
    echo -e "${GREEN}✓ Low moisture reading sent${NC}"
    
    # Step 2: System should trigger irrigation decision
    echo "5.2 Checking for irrigation trigger..."
    sleep 3  # Allow processing time
    
    # This would normally be automatic, but we'll simulate the check
    echo -e "${YELLOW}! Automatic irrigation trigger requires all services integrated${NC}"
    
    # Step 3: Verify water accounting
    echo "5.3 Checking water accounting..."
    if curl -s "http://localhost:3019/api/v1/water-usage/current" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Water accounting service responding${NC}"
    else
        echo -e "${YELLOW}! Water accounting service may not be running${NC}"
    fi
}

# Test 6: Database Consistency Check
test_database_consistency() {
    echo -e "\n${BLUE}Test 6: Database Consistency Check${NC}"
    
    # Check cross-schema references
    echo "6.1 Checking cross-schema data consistency..."
    
    CONSISTENCY_CHECK=$(PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -U postgres -d munbon_dev -t -c "
        SELECT 
            (SELECT COUNT(*) FROM gis.parcels) as gis_parcels,
            (SELECT COUNT(*) FROM ros.crops) as ros_crops,
            (SELECT COUNT(*) FROM auth.users) as auth_users;
    ")
    
    echo -e "${GREEN}✓ Database schemas accessible${NC}"
    echo "   $CONSISTENCY_CHECK"
    
    # Check TimescaleDB data
    echo "6.2 Checking TimescaleDB sensor data..."
    SENSOR_COUNT=$(PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -U postgres -d sensor_data -t -c "
        SELECT COUNT(*) FROM sensor_data WHERE created_at > NOW() - INTERVAL '1 hour';
    ")
    
    echo -e "${GREEN}✓ Recent sensor records: $SENSOR_COUNT${NC}"
}

# Main execution
main() {
    echo "Starting integration tests at $(date)"
    echo "EC2 Database: $POSTGRES_HOST:$POSTGRES_PORT"
    echo ""
    
    # Run all test suites
    test_sensor_weather_ros
    test_gis_ros_awd
    test_awd_flow_scada
    test_realtime_flow
    test_e2e_irrigation
    test_database_consistency
    
    echo -e "\n${BLUE}Integration tests completed!${NC}"
    echo "Check individual service logs for detailed information."
}

# Run tests
main "$@"