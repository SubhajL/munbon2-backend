#!/bin/bash

# Water Accounting Service Test Runner

echo "=========================================="
echo "Water Accounting Service - Test Suite"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo -e "${YELLOW}Warning: Virtual environment not activated${NC}"
    echo "Consider running: source venv/bin/activate"
    echo ""
fi

# Install test dependencies if needed
echo "Checking test dependencies..."
pip install -q pytest pytest-asyncio pytest-cov

# Run different test suites
run_test_suite() {
    local suite_name=$1
    local test_command=$2
    
    echo ""
    echo -e "${GREEN}Running $suite_name...${NC}"
    echo "----------------------------------------"
    
    if eval $test_command; then
        echo -e "${GREEN}✓ $suite_name passed${NC}"
        return 0
    else
        echo -e "${RED}✗ $suite_name failed${NC}"
        return 1
    fi
}

# Track overall status
overall_status=0

# 1. Unit tests
if run_test_suite "Unit Tests" "pytest tests/test_volume_integration.py tests/test_loss_calculation.py tests/test_efficiency_calculator.py tests/test_deficit_tracker.py -v"; then
    :
else
    overall_status=1
fi

# 2. API tests
if run_test_suite "API Tests" "pytest tests/test_api_endpoints.py -v"; then
    :
else
    overall_status=1
fi

# 3. Integration tests
if run_test_suite "Integration Tests" "pytest tests/test_integration.py -v"; then
    :
else
    overall_status=1
fi

# 4. All tests with coverage
echo ""
echo -e "${GREEN}Running all tests with coverage...${NC}"
echo "=========================================="
pytest --cov=src --cov-report=term-missing --cov-report=html

# Generate coverage badge (optional)
if command -v coverage-badge &> /dev/null; then
    coverage-badge -o coverage.svg -f
    echo ""
    echo "Coverage badge generated: coverage.svg"
fi

# Summary
echo ""
echo "=========================================="
if [ $overall_status -eq 0 ]; then
    echo -e "${GREEN}All test suites passed!${NC}"
    echo ""
    echo "Coverage report available at: htmlcov/index.html"
else
    echo -e "${RED}Some test suites failed${NC}"
    echo "Please check the output above for details"
fi
echo "=========================================="

exit $overall_status