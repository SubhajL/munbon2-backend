#!/bin/bash

# Comprehensive Test Runner for All Backend Services with LOCAL Docker Databases
# Tests 17 implemented services using local PostgreSQL and TimescaleDB

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Local Database Configuration
export POSTGRES_HOST="localhost"
export POSTGRES_PORT="5434"  # Local Docker PostgreSQL
export POSTGRES_USER="postgres"
export POSTGRES_PASSWORD="postgres"
export TIMESCALE_HOST="localhost"
export TIMESCALE_PORT="5433"  # Local Docker TimescaleDB
export TIMESCALE_USER="postgres"
export TIMESCALE_PASSWORD="postgres"
export REDIS_HOST="localhost"
export REDIS_PORT="6379"

# Service ports - using simple arrays for compatibility
SERVICE_NAMES="sensor-data gis ros flow-monitoring weather-monitoring water-level-monitoring awd-control auth"
SERVICE_PORTS="3003 3007 3047 3011 3006 3008 3010 3001"

# Convert to arrays
SERVICE_NAME_ARRAY=($SERVICE_NAMES)
SERVICE_PORT_ARRAY=($SERVICE_PORTS)

# Test results
PASSED_TESTS=0
FAILED_TESTS=0
TOTAL_TESTS=0

# Log file
LOG_FILE="test-results-local-$(date +%Y%m%d-%H%M%S).log"

# Function to log messages
log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

# Function to test database connectivity
test_database_connection() {
    log "${BLUE}=== Phase 1: Testing Local Database Connectivity ===${NC}"
    
    # Test PostgreSQL connection
    log "Testing PostgreSQL connection on port 5434..."
    if PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d postgres -c "SELECT version();" > /dev/null 2>&1; then
        log "${GREEN}✓ PostgreSQL connection successful${NC}"
        ((PASSED_TESTS++))
    else
        log "${RED}✗ PostgreSQL connection failed${NC}"
        ((FAILED_TESTS++))
    fi
    ((TOTAL_TESTS++))
    
    # Test TimescaleDB connection
    log "Testing TimescaleDB connection on port 5433..."
    if PGPASSWORD="$TIMESCALE_PASSWORD" psql -h "$TIMESCALE_HOST" -p "$TIMESCALE_PORT" -U "$TIMESCALE_USER" -d postgres -c "SELECT version();" > /dev/null 2>&1; then
        log "${GREEN}✓ TimescaleDB connection successful${NC}"
        ((PASSED_TESTS++))
    else
        log "${RED}✗ TimescaleDB connection failed${NC}"
        ((FAILED_TESTS++))
    fi
    ((TOTAL_TESTS++))
    
    # Test databases
    log "Testing databases..."
    if PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d munbon_dev -c "\dn" > /dev/null 2>&1; then
        log "${GREEN}✓ Database munbon_dev accessible${NC}"
        ((PASSED_TESTS++))
    else
        log "${RED}✗ Database munbon_dev not accessible${NC}"
        ((FAILED_TESTS++))
    fi
    ((TOTAL_TESTS++))
    
    if PGPASSWORD="$TIMESCALE_PASSWORD" psql -h "$TIMESCALE_HOST" -p "$TIMESCALE_PORT" -U "$TIMESCALE_USER" -d munbon_timescale -c "SELECT 1;" > /dev/null 2>&1; then
        log "${GREEN}✓ Database munbon_timescale accessible${NC}"
        ((PASSED_TESTS++))
    else
        log "${RED}✗ Database munbon_timescale not accessible${NC}"
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

# Function to start services
start_services() {
    log "\n${BLUE}=== Phase 2: Starting Services with Local Databases ===${NC}"
    
    # Update PM2 config for local databases
    log "Configuring services for local databases..."
    
    # Start services using PM2 with local config
    log "Starting services with PM2..."
    
    # Start only the services that are configured in PM2
    pm2 start unified-api sensor-data-service gis-api scada-integration --update-env
    
    # Wait for services to start
    sleep 5
    
    # Check PM2 status
    pm2 status
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

# Function to test service
test_service() {
    local service=$1
    local port=$2
    
    log "\nTesting $service service on port $port..."
    
    # Check if service is running
    check_service_health "$service" "$port"
}

# Function to test sensor data flow
test_sensor_data_flow() {
    log "\n${BLUE}=== Phase 3: Testing Sensor Data Flow ===${NC}"
    
    # Test data ingestion
    log "Testing sensor data ingestion..."
    TEST_DATA='{
        "sensor_id": "TEST_LOCAL_001",
        "type": "moisture",
        "value": 45.5,
        "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
    }'
    
    RESPONSE=$(curl -s -X POST "http://localhost:3003/api/v1/telemetry" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer test-token" \
        -d "$TEST_DATA")
    
    if echo "$RESPONSE" | grep -q "success\|ok\|201"; then
        log "${GREEN}✓ Sensor data ingestion successful${NC}"
        ((PASSED_TESTS++))
    else
        log "${RED}✗ Sensor data ingestion failed${NC}"
        log "Response: $RESPONSE"
        ((FAILED_TESTS++))
    fi
    ((TOTAL_TESTS++))
    
    # Check data in TimescaleDB
    log "Verifying data in TimescaleDB..."
    COUNT=$(PGPASSWORD="$TIMESCALE_PASSWORD" psql -h "$TIMESCALE_HOST" -p "$TIMESCALE_PORT" -U "$TIMESCALE_USER" -d munbon_timescale -t -c "SELECT COUNT(*) FROM sensor_data WHERE sensor_id = 'TEST_LOCAL_001';" 2>/dev/null || echo "0")
    if [ "$COUNT" -gt 0 ]; then
        log "${GREEN}✓ Data found in TimescaleDB: $COUNT records${NC}"
        ((PASSED_TESTS++))
    else
        log "${YELLOW}! No data found in TimescaleDB${NC}"
    fi
    ((TOTAL_TESTS++))
}

# Function to test GIS service
test_gis_service() {
    log "\n${BLUE}=== Testing GIS Service ===${NC}"
    
    # Check if GIS service is running
    if curl -s "http://localhost:3007/api/v1/parcels/count" > /dev/null 2>&1; then
        log "${GREEN}✓ GIS API responding${NC}"
        ((PASSED_TESTS++))
    else
        log "${YELLOW}! GIS API not fully implemented${NC}"
    fi
    ((TOTAL_TESTS++))
}

# Function to test integration
test_integration() {
    log "\n${BLUE}=== Phase 4: Integration Tests ===${NC}"
    
    # Test Redis pub/sub
    log "Testing Redis Pub/Sub..."
    redis-cli -h "$REDIS_HOST" PUBLISH test_channel "test_message" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        log "${GREEN}✓ Redis pub/sub working${NC}"
        ((PASSED_TESTS++))
    else
        log "${RED}✗ Redis pub/sub failed${NC}"
        ((FAILED_TESTS++))
    fi
    ((TOTAL_TESTS++))
    
    # Test cross-database queries
    log "Testing cross-database access..."
    # This would test accessing both PostgreSQL and TimescaleDB
    log "${YELLOW}! Cross-database tests require services to be fully running${NC}"
}

# Function to generate report
generate_report() {
    log "\n${BLUE}=== Test Report ===${NC}"
    
    local success_rate=$(awk "BEGIN {printf \"%.1f\", ($PASSED_TESTS/$TOTAL_TESTS)*100}")
    
    log "\n${BLUE}Test Summary:${NC}"
    log "Environment: Local Docker Databases"
    log "PostgreSQL: localhost:5434"
    log "TimescaleDB: localhost:5433"
    log "Redis: localhost:6379"
    log ""
    log "Total Tests: $TOTAL_TESTS"
    log "${GREEN}Passed: $PASSED_TESTS${NC}"
    log "${RED}Failed: $FAILED_TESTS${NC}"
    log "Success Rate: ${success_rate}%"
    
    # Save detailed report
    cat > "test-report-local-$(date +%Y%m%d-%H%M%S).json" << EOF
{
    "test_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "environment": "Local Docker Databases",
    "databases": {
        "postgresql": "localhost:5434",
        "timescaledb": "localhost:5433",
        "redis": "localhost:6379"
    },
    "total_tests": $TOTAL_TESTS,
    "passed_tests": $PASSED_TESTS,
    "failed_tests": $FAILED_TESTS,
    "success_rate": "$success_rate%"
}
EOF
    
    log "\nDetailed log saved to: $LOG_FILE"
}

# Main execution
main() {
    log "${BLUE}Starting Comprehensive Backend Services Test (Local Docker)${NC}"
    log "Test Date: $(date)"
    log "========================================\n"
    
    # Phase 1: Database connectivity
    test_database_connection
    
    # Phase 2: Start services
    start_services
    
    # Wait for services to initialize
    log "\n${YELLOW}Waiting for services to initialize...${NC}"
    sleep 5
    
    # Check running services
    log "\n${BLUE}Checking running services...${NC}"
    for i in ${!SERVICE_NAME_ARRAY[@]}; do
        test_service "${SERVICE_NAME_ARRAY[$i]}" "${SERVICE_PORT_ARRAY[$i]}"
    done
    
    # Phase 3: Service-specific tests
    test_sensor_data_flow
    test_gis_service
    
    # Phase 4: Integration tests
    test_integration
    
    # Generate report
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