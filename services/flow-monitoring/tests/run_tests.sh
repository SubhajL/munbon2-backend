#!/bin/bash

# Run tests for Flow Monitoring Service
# Usage: ./run_tests.sh [test-type]
# test-type: all (default), unit, integration, performance, coverage

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get test type from argument
TEST_TYPE=${1:-all}

echo -e "${GREEN}Running Flow Monitoring Service Tests${NC}"
echo -e "Test type: ${YELLOW}${TEST_TYPE}${NC}"

# Change to project root
cd "$(dirname "$0")/.."

# Ensure virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    else
        echo -e "${RED}Virtual environment not found. Creating...${NC}"
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt
    fi
fi

# Run tests based on type
case $TEST_TYPE in
    unit)
        echo -e "${GREEN}Running unit tests...${NC}"
        pytest tests/unit -v -m unit
        ;;
    
    integration)
        echo -e "${GREEN}Running integration tests...${NC}"
        pytest tests/integration -v -m integration
        ;;
    
    performance)
        echo -e "${GREEN}Running performance benchmarks...${NC}"
        pytest tests/performance -v -m performance --benchmark-only
        ;;
    
    coverage)
        echo -e "${GREEN}Running all tests with coverage...${NC}"
        pytest tests/ -v --cov=src --cov-report=html --cov-report=term
        echo -e "${GREEN}Coverage report generated in htmlcov/index.html${NC}"
        ;;
    
    all)
        echo -e "${GREEN}Running all tests...${NC}"
        pytest tests/ -v
        ;;
    
    *)
        echo -e "${RED}Invalid test type: ${TEST_TYPE}${NC}"
        echo "Usage: $0 [all|unit|integration|performance|coverage]"
        exit 1
        ;;
esac

# Check exit code
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Tests completed successfully!${NC}"
else
    echo -e "${RED}Tests failed!${NC}"
    exit 1
fi