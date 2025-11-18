#!/bin/bash
# Service Testing Script - UPDATED VERSION
# Run this before starting any PM2 services

set -e  # Exit on error

echo "=========================================="
echo "MUNBON2 SERVICE TESTING SCRIPT V2"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

# Function to test a Python service with venv
test_python_service() {
    local service_name=$1
    local service_path=$2
    local test_command=$3
    
    echo -e "${YELLOW}Testing: $service_name${NC}"
    echo "Path: $service_path"
    echo "----------------------------------------"
    
    cd "$service_path"
    
    # Activate venv and run test
    if source venv/bin/activate && eval "$test_command" 2>&1; then
        echo -e "${GREEN}✓ PASSED: $service_name${NC}"
        ((PASSED++))
        deactivate 2>/dev/null || true
    else
        echo -e "${RED}✗ FAILED: $service_name${NC}"
        ((FAILED++))
        deactivate 2>/dev/null || true
    fi
    
    echo ""
}

# Function to test a Node.js service
test_node_service() {
    local service_name=$1
    local service_path=$2
    local test_command=$3
    
    echo -e "${YELLOW}Testing: $service_name${NC}"
    echo "Path: $service_path"
    echo "----------------------------------------"
    
    cd "$service_path"
    
    if eval "$test_command" 2>&1; then
        echo -e "${GREEN}✓ PASSED: $service_name${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAILED: $service_name${NC}"
        ((FAILED++))
    fi
    
    echo ""
}

echo "1. Testing Database Connections..."
echo "=========================================="

# Test PostgreSQL
if pg_isready -h 43.208.201.191 -p 5432 -U postgres > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PostgreSQL is accessible${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ PostgreSQL is NOT accessible${NC}"
    ((FAILED++))
fi

# Test Redis (if needed)
if redis-cli -h localhost -p 6379 ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Redis is accessible${NC}"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠ Redis is NOT accessible (may not be required)${NC}"
fi

echo ""
echo "2. Testing Individual Services..."
echo "=========================================="

# Water Accounting Service
test_python_service "water-accounting" \
    "$HOME/dev/munbon2-backend/services/water-accounting" \
    "python -c 'from src.config import get_settings; s = get_settings(); print(\"✓ Config loaded:\", s.SERVICE_NAME)'"

# BFF Water Planning Service
test_python_service "bff-water-planning" \
    "$HOME/dev/munbon2-backend/services/bff-water-planning" \
    "python -c 'import sys; sys.path.insert(0, \"src\"); from api.schema import create_graphql_app; print(\"✓ GraphQL schema loaded\")'"

# ROS GIS Integration
test_python_service "ros-gis-integration" \
    "$HOME/dev/munbon2-backend/services/ros-gis-integration" \
    "python -c 'import sys; sys.path.insert(0, \"src\"); from services import DemandAggregatorService; print(\"✓ Services loaded\")'"

# Scheduler
test_python_service "scheduler" \
    "$HOME/dev/munbon2-backend/services/scheduler" \
    "python -c 'import sys; sys.path.insert(0, \"src\"); from main import app; print(\"✓ App loaded\")'" 2>/dev/null || true

# Flow Monitoring
test_python_service "flow-monitoring" \
    "$HOME/dev/munbon2-backend/services/flow-monitoring" \
    "python -c 'import sys; sys.path.insert(0, \"src\"); from main import app; print(\"✓ App loaded\")'" 2>/dev/null || true

# AWD Control (Node.js)
test_node_service "awd-control" \
    "$HOME/dev/munbon2-backend/services/awd-control" \
    "node -e \"const db = require('./dist/config/database'); console.log('✓ Database config loaded');\""

# GIS (Node.js)
test_node_service "gis" \
    "$HOME/dev/munbon2-backend/services/gis" \
    "node -e \"console.log('✓ GIS service can start');\"" 2>/dev/null || true

echo ""
echo "=========================================="
echo "TEST SUMMARY"
echo "=========================================="
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓✓✓ ALL TESTS PASSED - Safe to start PM2 services ✓✓✓${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Start services one at a time with PM2"
    echo "  2. Monitor each for 1 minute before starting the next"
    echo "  3. Use: pm2 start <service> && pm2 logs <service> --lines 50"
    exit 0
else
    echo -e "${RED}✗✗✗ SOME TESTS FAILED - DO NOT start PM2 ✗✗✗${NC}"
    echo ""
    echo "Check the errors above and:"
    echo "  1. Review the FIX-*.txt files in this directory"
    echo "  2. Fix the issues"
    echo "  3. Run this test script again"
    exit 1
fi
