#!/bin/bash

# Comprehensive Test Runner for All Backend Services with EC2 Database
# Tests 17 implemented services using consolidated PostgreSQL on EC2

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# EC2 Database Configuration
export POSTGRES_HOST="${EC2_HOST:-43.208.201.191}"
export POSTGRES_PORT="5432"
export POSTGRES_USER="postgres"
export POSTGRES_PASSWORD="P@ssw0rd123!"
export TIMESCALE_HOST="${EC2_HOST:-43.208.201.191}"
export TIMESCALE_PORT="5432"  # Same as PostgreSQL
export REDIS_HOST="localhost"
export REDIS_PORT="6379"

# Service ports - using simple arrays for compatibility
SERVICE_NAMES="auth sensor-data sensor-consumer moisture-monitoring weather-monitoring gis water-level-monitoring scada-integration rid-ms awd-control flow-monitoring ros ros-gis-integration scheduler gravity-optimizer water-accounting sensor-location-mapping sensor-network-management unified-api"
SERVICE_PORTS="3001 3003 3004 3005 3006 3007 3008 3015 3011 3013 3014 3047 3022 3021 3016 3019 3018 3023 3000"

# Convert to arrays
SERVICE_NAME_ARRAY=($SERVICE_NAMES)
SERVICE_PORT_ARRAY=($SERVICE_PORTS)

# Test results
PASSED_TESTS=0
FAILED_TESTS=0
TOTAL_TESTS=0

# Log file
LOG_FILE="test-results-$(date +%Y%m%d-%H%M%S).log"

# Function to log messages
log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

# Function to test database connectivity
test_database_connection() {
    log "${BLUE}=== Phase 1: Testing EC2 Database Connectivity ===${NC}"
    
    # Test PostgreSQL connection
    log "Testing PostgreSQL connection..."
    if PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d postgres -c "SELECT version();" > /dev/null 2>&1; then
        log "${GREEN}✓ PostgreSQL connection successful${NC}"
        ((PASSED_TESTS++))
    else
        log "${RED}✗ PostgreSQL connection failed${NC}"
        ((FAILED_TESTS++))
    fi
    ((TOTAL_TESTS++))
    
    # Test databases and schemas
    log "Testing database schemas..."
    for db in munbon_dev sensor_data; do
        if PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$db" -c "\dn" > /dev/null 2>&1; then
            log "${GREEN}✓ Database $db accessible${NC}"
            ((PASSED_TESTS++))
        else
            log "${RED}✗ Database $db not accessible${NC}"
            ((FAILED_TESTS++))
        fi
        ((TOTAL_TESTS++))
    done
    
    # Test TimescaleDB extension
    log "Testing TimescaleDB extension..."
    if PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d sensor_data -c "SELECT extname FROM pg_extension WHERE extname = 'timescaledb';" | grep -q timescaledb; then
        log "${GREEN}✓ TimescaleDB extension active${NC}"
        ((PASSED_TESTS++))
    else
        log "${RED}✗ TimescaleDB extension not found${NC}"
        ((FAILED_TESTS++))
    fi
    ((TOTAL_TESTS++))
    
    # Test Redis connection
    log "Testing Redis connection..."
    if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; then
        log "${GREEN}✓ Redis connection successful${NC}"
        ((PASSED_TESTS++))
    else
        log "${RED}✗ Redis connection failed${NC}"
        ((FAILED_TESTS++))
    fi
    ((TOTAL_TESTS++))
}

# Function to check service health
check_service_health() {
    local service=$1
    local port=$2
    
    if curl -s -f "http://localhost:$port/health" > /dev/null 2>&1; then
        log "${GREEN}✓ $service (port $port) is healthy${NC}"
        ((PASSED_TESTS++))
        return 0
    else
        log "${RED}✗ $service (port $port) is not responding${NC}"
        ((FAILED_TESTS++))
        return 1
    fi
    ((TOTAL_TESTS++))
}

# Function to test individual service
test_service() {
    local service=$1
    local port=$2
    
    log "\nTesting $service service..."
    
    # Check if service is running
    if ! check_service_health "$service" "$port"; then
        return 1
    fi
    
    # Service-specific tests
    case $service in
        "sensor-data")
            # Test sensor data ingestion
            if curl -s "http://localhost:$port/api/v1/telemetry/latest" > /dev/null 2>&1; then
                log "${GREEN}✓ Sensor data API responding${NC}"
                ((PASSED_TESTS++))
            else
                log "${RED}✗ Sensor data API failed${NC}"
                ((FAILED_TESTS++))
            fi
            ((TOTAL_TESTS++))
            ;;
        
        "auth")
            # Test auth endpoints
            if curl -s "http://localhost:$port/api/v1/auth/health" > /dev/null 2>&1; then
                log "${GREEN}✓ Auth API responding${NC}"
                ((PASSED_TESTS++))
            else
                log "${RED}✗ Auth API failed${NC}"
                ((FAILED_TESTS++))
            fi
            ((TOTAL_TESTS++))
            ;;
        
        "gis")
            # Test GIS endpoints
            if curl -s "http://localhost:$port/api/v1/parcels/count" > /dev/null 2>&1; then
                log "${GREEN}✓ GIS API responding${NC}"
                ((PASSED_TESTS++))
            else
                log "${RED}✗ GIS API failed${NC}"
                ((FAILED_TESTS++))
            fi
            ((TOTAL_TESTS++))
            ;;
        
        "ros")
            # Test ROS endpoints
            if curl -s "http://localhost:$port/api/v1/crops" > /dev/null 2>&1; then
                log "${GREEN}✓ ROS API responding${NC}"
                ((PASSED_TESTS++))
            else
                log "${RED}✗ ROS API failed${NC}"
                ((FAILED_TESTS++))
            fi
            ((TOTAL_TESTS++))
            ;;
        
        "flow-monitoring")
            # Test flow monitoring endpoints
            if curl -s "http://localhost:$port/api/v1/gates/state" > /dev/null 2>&1; then
                log "${GREEN}✓ Flow monitoring API responding${NC}"
                ((PASSED_TESTS++))
            else
                log "${RED}✗ Flow monitoring API failed${NC}"
                ((FAILED_TESTS++))
            fi
            ((TOTAL_TESTS++))
            ;;
    esac
}

# Function to test service integration
test_integration() {
    log "${BLUE}=== Phase 4: Integration Tests ===${NC}"
    
    # Test 1: Sensor to TimescaleDB flow
    log "\n1. Testing Sensor Data Flow..."
    if curl -s "http://localhost:3003/api/v1/telemetry/latest" | grep -q "data"; then
        log "${GREEN}✓ Sensor data flow working${NC}"
        ((PASSED_TESTS++))
    else
        log "${RED}✗ Sensor data flow failed${NC}"
        ((FAILED_TESTS++))
    fi
    ((TOTAL_TESTS++))
    
    # Test 2: Cross-service communication (ROS to GIS)
    log "\n2. Testing ROS-GIS Integration..."
    if [ -f "../services/ros-gis-integration/test-integration.sh" ]; then
        log "${YELLOW}! ROS-GIS integration test available${NC}"
    else
        log "${YELLOW}! ROS-GIS integration test not implemented${NC}"
    fi
    
    # Test 3: Redis pub/sub
    log "\n3. Testing Redis Pub/Sub..."
    redis-cli -h "$REDIS_HOST" PUBLISH test_channel "test_message" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        log "${GREEN}✓ Redis pub/sub working${NC}"
        ((PASSED_TESTS++))
    else
        log "${RED}✗ Redis pub/sub failed${NC}"
        ((FAILED_TESTS++))
    fi
    ((TOTAL_TESTS++))
}

# Function to run end-to-end tests
test_e2e() {
    log "${BLUE}=== Phase 5: End-to-End Tests ===${NC}"
    
    # E2E Test 1: Complete sensor data pipeline
    log "\n1. Testing complete sensor data pipeline..."
    
    # Simulate sensor data ingestion
    SENSOR_DATA='{
        "sensor_id": "TEST_SENSOR_001",
        "type": "moisture",
        "value": 65.5,
        "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
    }'
    
    if curl -s -X POST "http://localhost:3003/api/v1/telemetry" \
        -H "Content-Type: application/json" \
        -d "$SENSOR_DATA" > /dev/null 2>&1; then
        log "${GREEN}✓ Sensor data ingestion successful${NC}"
        ((PASSED_TESTS++))
    else
        log "${RED}✗ Sensor data ingestion failed${NC}"
        ((FAILED_TESTS++))
    fi
    ((TOTAL_TESTS++))
    
    # E2E Test 2: Irrigation decision flow
    log "\n2. Testing irrigation decision flow..."
    log "${YELLOW}! Irrigation flow test requires all services running${NC}"
}

# Function to run load tests
test_load() {
    log "${BLUE}=== Phase 6: Load Testing ===${NC}"
    
    # Check if k6 is installed
    if command -v k6 &> /dev/null; then
        log "Running load tests with k6..."
        # Create simple k6 test script
        cat > /tmp/k6-test.js << 'EOF'
import http from 'k6/http';
import { check } from 'k6';

export let options = {
    stages: [
        { duration: '30s', target: 10 },
        { duration: '1m', target: 50 },
        { duration: '30s', target: 0 },
    ],
    thresholds: {
        http_req_duration: ['p(95)<500'],
        http_req_failed: ['rate<0.1'],
    },
};

export default function() {
    let res = http.get('http://localhost:3003/health');
    check(res, {
        'status is 200': (r) => r.status === 200,
    });
}
EOF
        
        k6 run /tmp/k6-test.js --quiet > /tmp/k6-results.txt 2>&1
        if [ $? -eq 0 ]; then
            log "${GREEN}✓ Load test completed${NC}"
            ((PASSED_TESTS++))
        else
            log "${RED}✗ Load test failed${NC}"
            ((FAILED_TESTS++))
        fi
        ((TOTAL_TESTS++))
    else
        log "${YELLOW}! k6 not installed, skipping load tests${NC}"
    fi
}

# Function to generate test report
generate_report() {
    log "${BLUE}=== Phase 7: Test Report ===${NC}"
    
    local success_rate=$(awk "BEGIN {printf \"%.1f\", ($PASSED_TESTS/$TOTAL_TESTS)*100}")
    
    log "\n${BLUE}Test Summary:${NC}"
    log "Total Tests: $TOTAL_TESTS"
    log "${GREEN}Passed: $PASSED_TESTS${NC}"
    log "${RED}Failed: $FAILED_TESTS${NC}"
    log "Success Rate: ${success_rate}%"
    
    # Save detailed report
    cat > "test-report-$(date +%Y%m%d-%H%M%S).json" << EOF
{
    "test_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "environment": "EC2 Consolidated Database",
    "database_host": "$POSTGRES_HOST",
    "total_tests": $TOTAL_TESTS,
    "passed_tests": $PASSED_TESTS,
    "failed_tests": $FAILED_TESTS,
    "success_rate": "$success_rate%",
    "services_tested": ${#SERVICE_NAME_ARRAY[@]}
}
EOF
    
    log "\nDetailed log saved to: $LOG_FILE"
}

# Main execution
main() {
    log "${BLUE}Starting Comprehensive Backend Services Test${NC}"
    log "Test Date: $(date)"
    log "EC2 Database: $POSTGRES_HOST:$POSTGRES_PORT"
    log "========================================\n"
    
    # Phase 1: Database connectivity
    test_database_connection
    
    # Phase 2: Service health checks
    log "\n${BLUE}=== Phase 2: Service Health Checks ===${NC}"
    for i in ${!SERVICE_NAME_ARRAY[@]}; do
        test_service "${SERVICE_NAME_ARRAY[$i]}" "${SERVICE_PORT_ARRAY[$i]}"
    done
    
    # Phase 3: Integration tests
    test_integration
    
    # Phase 4: End-to-end tests
    test_e2e
    
    # Phase 5: Load tests
    test_load
    
    # Phase 6: Generate report
    generate_report
    
    # Exit with appropriate code
    if [ $FAILED_TESTS -eq 0 ]; then
        log "\n${GREEN}All tests passed!${NC}"
        exit 0
    else
        log "\n${RED}Some tests failed!${NC}"
        exit 1
    fi
}

# Run main function
main "$@"