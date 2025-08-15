#!/bin/bash

# Run tests for the scheduler service

echo "Running Scheduler Service Tests..."
echo "================================="

# Set test environment
export ENVIRONMENT=test
export DATABASE_URL=sqlite+aiosqlite:///:memory:
export REDIS_URL=redis://localhost:6379/15
export JWT_SECRET_KEY=test-secret-key-123

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to run tests with nice output
run_test_suite() {
    local suite_name=$1
    local test_path=$2
    
    echo -e "\n${YELLOW}Running $suite_name...${NC}"
    
    if pytest $test_path -v --tb=short; then
        echo -e "${GREEN}✓ $suite_name passed${NC}"
    else
        echo -e "${RED}✗ $suite_name failed${NC}"
        exit 1
    fi
}

# Install test dependencies if needed
if [ "$1" = "--install" ]; then
    echo "Installing test dependencies..."
    pip install pytest pytest-asyncio pytest-cov pytest-mock aiosqlite
fi

# Run different test suites
if [ -z "$1" ] || [ "$1" = "--all" ]; then
    # Run all tests
    run_test_suite "Unit Tests" "tests/unit/"
    run_test_suite "Integration Tests" "tests/integration/"
    
    # Run with coverage if requested
    if [ "$2" = "--coverage" ]; then
        echo -e "\n${YELLOW}Running tests with coverage...${NC}"
        pytest tests/ --cov=src --cov-report=html --cov-report=term
        echo -e "${GREEN}Coverage report generated in htmlcov/${NC}"
    fi
    
elif [ "$1" = "--unit" ]; then
    run_test_suite "Unit Tests" "tests/unit/"
    
elif [ "$1" = "--integration" ]; then
    run_test_suite "Integration Tests" "tests/integration/"
    
elif [ "$1" = "--watch" ]; then
    echo "Running tests in watch mode..."
    pytest-watch tests/ -v
    
else
    # Run specific test file
    run_test_suite "Specific Test" "$1"
fi

echo -e "\n${GREEN}All tests completed!${NC}"